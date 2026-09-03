"""TF-0026 — PROJECT_HEALTH: cálculo determinista de salud de un
`ExpedienteProyecto`.

Este módulo es código puro. El modelo/LLM solo clasifica `EstadoDato` /
`OrigenDato` / `NivelConfianza` por campo (`src.proyectos.estado`); nunca
produce un porcentaje, un blocker, un warning ni un `next_agent` — eso lo
calcula, valida y controla exclusivamente `calcular_salud()`.

`next_agent` se delega a `src.proyectos.workflow.determinar_siguiente_agente`
con una sola llamada: este módulo no reimplementa el orden de etapas.

Sin dependencias nuevas. No importa Flask, `src.database`, `src.agentes` ni
`src.ai`.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from datetime import datetime

from src.proyectos import workflow
from src.proyectos.checklist import DISCIPLINAS, campos_esperados
from src.proyectos.constantes import PESO_APLICABILIDAD_CONDITIONAL, UMBRAL_AVANCE_LISTO
from src.proyectos.estado import (
    AplicabilidadDisciplina,
    Dato,
    EstadoDato,
    ExpedienteProyecto,
    NivelConfianza,
    Readiness,
)

__all__ = [
    "UMBRAL_AVANCE_LISTO", "PESO_APLICABILIDAD_CONDITIONAL",
    "PESO_ESTADO_COMPLETITUD", "PESO_APLICABILIDAD",
    "MetricaDimension", "Hallazgo", "SaludProyecto", "calcular_salud",
]

# --- Pesos deterministas (checkpoint TF-0026, corrección del peso de
# `not_found`: pesa 0 igual que `unknown`/`pending_decision`, nunca "resuelto";
# `not_applicable` se filtra antes de llegar a este diccionario). ------------
PESO_ESTADO_COMPLETITUD = {
    EstadoDato.CONFIRMED: 1.0,
    EstadoDato.DISCOVERED: 1.0,
    EstadoDato.INFERRED: 0.5,
    EstadoDato.INCOMPLETE: 0.5,
    EstadoDato.UNKNOWN: 0.0,
    EstadoDato.PENDING_DECISION: 0.0,
    EstadoDato.NOT_FOUND: 0.0,
}

PESO_APLICABILIDAD = {
    AplicabilidadDisciplina.REQUIRED: 1.0,
    AplicabilidadDisciplina.CONDITIONAL: PESO_APLICABILIDAD_CONDITIONAL,
    AplicabilidadDisciplina.UNKNOWN: 1.0,
    # NOT_APPLICABLE: no tiene entrada -> se filtra explícitamente antes de
    # consultar este diccionario (excluida de numerador y denominador).
}

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


@dataclass
class MetricaDimension:
    """Cobertura, completitud y avance de una dimensión (raíz o disciplina).

    `cobertura`: % de `campos_esperados` ya investigados (cualquier estado).
    `completitud`: % de calidad, solo sobre lo investigado y aplicable.
    `avance = cobertura * completitud` — el número único "honesto": no puede
    dar 100% solo porque lo poco investigado resultó impecable.
    """

    cobertura: float
    completitud: float
    avance: float
    campos_investigados: int
    campos_esperados_total: int

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "MetricaDimension":
        return cls(
            cobertura=d["cobertura"],
            completitud=d["completitud"],
            avance=d["avance"],
            campos_investigados=d["campos_investigados"],
            campos_esperados_total=d["campos_esperados_total"],
        )


@dataclass
class Hallazgo:
    """Un blocker o warning con la disciplina de origen (`None` = raíz).

    Tipo puramente interno: nunca cruza el límite de `SaludProyecto` (que solo
    expone `blockers`/`warnings` como `list[str]`), por eso no tiene
    `to_dict`/`from_dict` — no hay nada que lo (de)serialice.
    """

    disciplina: str | None
    mensaje: str


@dataclass
class SaludProyecto:
    """PROJECT_HEALTH de un expediente en un momento dado."""

    descubrimiento: MetricaDimension
    por_disciplina: dict[str, MetricaDimension]
    estado_general: float
    blockers: list[str]
    warnings: list[str]
    readiness: Readiness
    next_agent: str
    checklist_version: str
    calculado_en: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SaludProyecto":
        return cls(
            descubrimiento=MetricaDimension.from_dict(d["descubrimiento"]),
            por_disciplina={
                k: MetricaDimension.from_dict(v) for k, v in d["por_disciplina"].items()
            },
            estado_general=d["estado_general"],
            blockers=list(d.get("blockers", [])),
            warnings=list(d.get("warnings", [])),
            readiness=Readiness(d["readiness"]),
            next_agent=d["next_agent"],
            checklist_version=d["checklist_version"],
            calculado_en=d["calculado_en"],
        )


def _metrica(campos: tuple[str, ...], datos: dict[str, Dato]) -> MetricaDimension:
    total = len(campos)
    investigados = [datos[c] for c in campos if c in datos]
    aplicables = [d for d in investigados if d.estado != EstadoDato.NOT_APPLICABLE]

    cobertura = (len(investigados) / total) if total else 0.0
    if aplicables:
        completitud = sum(PESO_ESTADO_COMPLETITUD[d.estado] for d in aplicables) / len(aplicables)
    elif investigados:
        # todo lo investigado resultó not_applicable: no queda nada por resolver.
        completitud = 1.0
    else:
        # nada investigado todavía: no hay base para afirmar que está resuelto.
        completitud = 0.0
    avance = cobertura * completitud
    return MetricaDimension(cobertura, completitud, avance, len(investigados), total)


def _blockers_y_warnings(
    expediente: ExpedienteProyecto,
    metrica_raiz: MetricaDimension,
    metricas: dict[str, MetricaDimension],
) -> tuple[list[Hallazgo], list[Hallazgo]]:
    blockers: list[Hallazgo] = []
    warnings: list[Hallazgo] = []

    if metrica_raiz.avance < UMBRAL_AVANCE_LISTO:
        blockers.append(Hallazgo(
            None, f"Descubrimiento del proyecto incompleto ({metrica_raiz.avance:.0%})"
        ))
    _revisar_datos(expediente.descubrimiento, None, blockers, warnings)

    for k in DISCIPLINAS:
        disciplina = expediente.disciplinas[k]
        ap = disciplina.aplicabilidad
        m = metricas[k]

        if ap == AplicabilidadDisciplina.REQUIRED and m.avance < UMBRAL_AVANCE_LISTO:
            blockers.append(Hallazgo(
                k, f"Disciplina '{k}' requerida con avance {m.avance:.0%} "
                   f"(< {UMBRAL_AVANCE_LISTO:.0%})"
            ))
        if ap == AplicabilidadDisciplina.UNKNOWN:
            blockers.append(Hallazgo(k, f"Aplicabilidad de '{k}' sin determinar"))
        if ap == AplicabilidadDisciplina.CONDITIONAL and m.campos_investigados == 0:
            warnings.append(Hallazgo(k, f"Aplicabilidad condicional de '{k}' aún no evaluada"))

        _revisar_datos(disciplina.datos, k, blockers, warnings)

    return blockers, warnings


def _revisar_datos(
    datos: dict[str, Dato],
    disciplina: str | None,
    blockers: list[Hallazgo],
    warnings: list[Hallazgo],
) -> None:
    etiqueta = disciplina if disciplina is not None else "descubrimiento"
    for campo, dato in datos.items():
        if dato.estado == EstadoDato.PENDING_DECISION:
            blockers.append(Hallazgo(disciplina, f"Decisión pendiente en '{etiqueta}.{campo}'"))
        if dato.estado == EstadoDato.NOT_FOUND:
            warnings.append(Hallazgo(
                disciplina,
                f"Campo '{etiqueta}.{campo}' no encontrado — confirmar si realmente no existe",
            ))
        if dato.estado in (EstadoDato.CONFIRMED, EstadoDato.DISCOVERED) \
                and dato.confianza == NivelConfianza.BAJA:
            warnings.append(Hallazgo(
                disciplina, f"Campo '{etiqueta}.{campo}' confirmado con confianza baja"
            ))


def _estado_general(
    metrica_raiz: MetricaDimension,
    expediente: ExpedienteProyecto,
    metricas: dict[str, MetricaDimension],
) -> float:
    # El descubrimiento (raíz) siempre pondera como si fuera "required": es
    # el gate de la etapa ORQUESTADOR, no una disciplina que pueda excluirse.
    terminos = [(metrica_raiz.avance, 1.0)]
    for k in DISCIPLINAS:
        ap = expediente.disciplinas[k].aplicabilidad
        if ap == AplicabilidadDisciplina.NOT_APPLICABLE:
            continue
        terminos.append((metricas[k].avance, PESO_APLICABILIDAD[ap]))
    peso_total = sum(p for _, p in terminos)
    return (sum(a * p for a, p in terminos) / peso_total) if peso_total else 0.0


def _determinar_readiness(estado_general: float, blockers: list[Hallazgo], warnings: list[Hallazgo]) -> Readiness:
    """Regla de `Readiness`, aislada para poder testear el borde exacto de
    `UMBRAL_AVANCE_LISTO` sin depender de la cantidad de campos del checklist.
    """
    if blockers:
        return Readiness.BLOCKED
    if estado_general < UMBRAL_AVANCE_LISTO:
        return Readiness.INCOMPLETE
    if warnings:
        return Readiness.READY_WITH_WARNINGS
    return Readiness.READY


def calcular_salud(expediente: ExpedienteProyecto) -> SaludProyecto:
    """Calcula `SaludProyecto` de forma 100% determinista a partir de
    `expediente`. No inventa números: solo agrega `EstadoDato` ya clasificados
    por el modelo, contra el checklist de `expediente.checklist_version`.
    """
    esperados = campos_esperados(expediente.checklist_version)

    metrica_raiz = _metrica(esperados["_raiz"], expediente.descubrimiento)
    metricas = {
        k: _metrica(esperados[k], expediente.disciplinas[k].datos) for k in DISCIPLINAS
    }

    blockers_h, warnings_h = _blockers_y_warnings(expediente, metrica_raiz, metricas)
    estado_general = _estado_general(metrica_raiz, expediente, metricas)

    readiness = _determinar_readiness(estado_general, blockers_h, warnings_h)

    next_agent = workflow.determinar_siguiente_agente(
        expediente.disciplinas, metrica_raiz, metricas, blockers_h,
    )

    return SaludProyecto(
        descubrimiento=metrica_raiz,
        por_disciplina=metricas,
        estado_general=estado_general,
        blockers=[h.mensaje for h in blockers_h],
        warnings=[h.mensaje for h in warnings_h],
        readiness=readiness,
        next_agent=next_agent,
        checklist_version=expediente.checklist_version,
        calculado_en=_ahora(),
    )
