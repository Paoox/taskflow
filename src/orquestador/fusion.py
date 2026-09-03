"""TF-0027 — Fusión de hallazgos propuestos por un agente de descubrimiento.

Contrato esperado en `SalidaAgente.resultado` de cualquier agente de
descubrimiento inyectado en `ejecutar_orquestador()`:

    {"hallazgos": [
        {"campo": "tipo_proyecto", "valor": "CLI", "estado": "confirmed",
         "origen": "file", "confianza": "ALTA", "notas": "..."},
        ...
    ]}

`parsear_hallazgos()` es tolerante (JSON inválido o forma inesperada -> lista
vacía + problema; una entrada individual inválida se descarta sin abortar el
resto). `fusionar_hallazgos()` pre-valida cada hallazgo (checklist raíz
vigente, `origen` nunca `user` viniendo de un agente, `transicion_valida()`
de TF-0026) **antes** de aplicarlo a una copia en memoria del expediente, de
modo que un hallazgo inválido nunca invalida el resto del lote ni dispara
`TransicionEstadoInvalida` en `RepositorioExpedientes.guardar()`.

Solo fusiona en `expediente.descubrimiento` (la raíz): un agente de
descubrimiento en TF-0027 no propone datos de disciplinas (fuera de alcance,
le pertenecen a agentes especializados que no existen todavía).

No persiste nada: devuelve el expediente actualizado en memoria, persistirlo
es responsabilidad del llamador (`orquestador.py`).

Sin dependencias nuevas. No importa Flask, `src.database`, `src.app`, `src.ai`
ni `src.agentes`.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.proyectos.checklist import campos_esperados
from src.proyectos.estado import (
    Dato,
    EstadoDato,
    ExpedienteProyecto,
    NivelConfianza,
    OrigenDato,
    transicion_valida,
)

__all__ = ["HallazgoPropuesto", "parsear_hallazgos", "fusionar_hallazgos"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


@dataclass
class HallazgoPropuesto:
    """Un hallazgo ya parseado, todavía sin pre-validar contra el expediente.

    Tipo puramente interno a la fusión: nunca se persiste tal cual (se
    convierte en `Dato` solo si sobrevive `fusionar_hallazgos()`); por eso no
    tiene `to_dict`/`from_dict` — no hay nada que lo (de)serialice fuera de
    este módulo.
    """

    campo: str
    valor: Any
    estado: EstadoDato
    origen: OrigenDato
    confianza: NivelConfianza
    notas: str = ""


def parsear_hallazgos(texto: str) -> tuple[list[HallazgoPropuesto], list[str]]:
    """Parsea `texto` (se espera `SalidaAgente.resultado`) según el contrato
    de hallazgos. Nunca lanza: JSON inválido, forma inesperada o una entrada
    con un valor de enum no reconocido se reportan en `problemas` y no
    detienen el resto del parseo.
    """
    try:
        datos = json.loads(texto)
    except (ValueError, TypeError):
        return [], ["resultado del agente de descubrimiento no es JSON válido"]

    if not isinstance(datos, dict) or not isinstance(datos.get("hallazgos"), list):
        return [], [
            "resultado del agente de descubrimiento no tiene la forma esperada "
            "({'hallazgos': [...]})"
        ]

    hallazgos: list[HallazgoPropuesto] = []
    problemas: list[str] = []
    for i, item in enumerate(datos["hallazgos"]):
        if not isinstance(item, dict):
            problemas.append(f"hallazgo #{i} no es un objeto: descartado")
            continue
        try:
            hallazgos.append(HallazgoPropuesto(
                campo=item["campo"],
                valor=item["valor"],
                estado=EstadoDato(item["estado"]),
                origen=OrigenDato(item["origen"]),
                confianza=NivelConfianza(item["confianza"]),
                notas=item.get("notas", ""),
            ))
        except (KeyError, ValueError) as exc:
            problemas.append(f"hallazgo #{i} inválido ({exc}): descartado")
    return hallazgos, problemas


def fusionar_hallazgos(
    expediente: ExpedienteProyecto, hallazgos: list[HallazgoPropuesto],
) -> tuple[ExpedienteProyecto, int, list[str]]:
    """Pre-valida cada hallazgo y los fusiona en una COPIA de `expediente`.

    Devuelve `(expediente_actualizado, cantidad_aplicada, problemas)`.
    `expediente` (el original) nunca se muta.
    """
    problemas: list[str] = []
    esperados = set(campos_esperados(expediente.checklist_version)["_raiz"])
    actualizado = copy.deepcopy(expediente)
    aplicados = 0

    for h in hallazgos:
        if h.campo not in esperados:
            problemas.append(f"campo '{h.campo}' no pertenece al checklist raíz: descartado")
            continue

        origen = h.origen
        if origen == OrigenDato.USER:
            problemas.append(
                f"hallazgo de agente para '{h.campo}' reclamaba origen=user: forzado a agent"
            )
            origen = OrigenDato.AGENT

        anterior = actualizado.descubrimiento.get(h.campo)
        if anterior is not None and not transicion_valida(anterior.estado, h.estado, origen):
            problemas.append(
                f"transición no permitida en '{h.campo}': "
                f"{anterior.estado.value} -> {h.estado.value} (origen={origen.value}): descartado"
            )
            continue

        actualizado.descubrimiento[h.campo] = Dato(
            valor=h.valor, estado=h.estado, origen=origen,
            confianza=h.confianza, actualizado_en=_ahora(), notas=h.notas,
        )
        aplicados += 1

    return actualizado, aplicados, problemas
