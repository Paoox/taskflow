"""TF-0026 — PROJECT_STATE: expediente maestro de un proyecto de software.

`ExpedienteProyecto` es la fuente de verdad de COORDINACIÓN de un proyecto
orquestado por Taskflow: identidad + lo mínimo que el Orquestador necesita
para saber qué falta, qué tan resuelto está y a quién le toca. **No** es el
contenido detallado de ninguna disciplina — eso vivirá en su futuro
`*_STATE` (ARCHITECTURE_STATE, UX_STATE, ANALYSIS_STATE,
IMPLEMENTATION_STATE, TEST_STATE, SECURITY_STATE, DOCUMENTATION_STATE),
referenciado por `ResumenDisciplina.referencia_estado`, fuera de alcance de
TF-0026.

`ResumenDisciplina.datos` solo admite las claves de
`src.proyectos.checklist.campos_esperados()` para la `checklist_version` del
propio expediente — no es una bolsa abierta sin límite.

No confundir con `src.modelos.Proyecto` (el agrupador de tareas del CRUD
original de Taskflow): son dominios distintos, sin relación ni FK entre sí.

Dataclasses puras con `to_dict()`/`from_dict()` simétrico, igual criterio que
`src.agentes.contrato`. Sin lógica de persistencia (`src.repositorios.
expedientes`) ni de cálculo de salud (`src.proyectos.salud`).

Sin dependencias nuevas. No importa Flask, `src.database`, `src.app`,
`src.agentes` ni `src.ai`.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum
from typing import Any, Optional

from src.proyectos.checklist import CHECKLIST_VERSION_ACTUAL, DISCIPLINAS

__all__ = [
    "EstadoDato", "OrigenDato", "NivelConfianza", "AplicabilidadDisciplina",
    "Readiness", "EstadoAprobacionMockup",
    "Dato", "ResumenDisciplina", "Mockup", "ExpedienteProyecto",
    "TRANSICIONES_RESTRINGIDAS", "transicion_valida",
]


# --- Enums (vocabulario aprobado en el checkpoint TF-0026; valores literales
# en inglés para EstadoDato/OrigenDato/AplicabilidadDisciplina/Readiness/
# EstadoAprobacionMockup — NO traducir. NivelConfianza es la excepción
# explícita: se mantiene en español, consistente con el resto del repo). ----

class EstadoDato(str, Enum):
    CONFIRMED = "confirmed"
    DISCOVERED = "discovered"
    INFERRED = "inferred"
    UNKNOWN = "unknown"
    NOT_FOUND = "not_found"
    NOT_APPLICABLE = "not_applicable"
    PENDING_DECISION = "pending_decision"
    INCOMPLETE = "incomplete"


class OrigenDato(str, Enum):
    USER = "user"
    CONVERSATION = "conversation"
    FILE = "file"
    CODE = "code"
    DOCUMENTATION = "documentation"
    REPOSITORY = "repository"
    TOOL = "tool"
    EXTERNAL = "external"
    INFERENCE = "inference"
    AGENT = "agent"
    CONFIGURATION = "configuration"


class NivelConfianza(str, Enum):
    ALTA = "ALTA"
    MEDIA = "MEDIA"
    BAJA = "BAJA"


class AplicabilidadDisciplina(str, Enum):
    REQUIRED = "required"
    CONDITIONAL = "conditional"
    NOT_APPLICABLE = "not_applicable"
    UNKNOWN = "unknown"


class Readiness(str, Enum):
    READY = "READY"
    READY_WITH_WARNINGS = "READY_WITH_WARNINGS"
    INCOMPLETE = "INCOMPLETE"
    BLOCKED = "BLOCKED"


class EstadoAprobacionMockup(str, Enum):
    DRAFT = "draft"
    IN_REVIEW = "in_review"
    APPROVED = "approved"
    REJECTED = "rejected"


# --- Transiciones restringidas -----------------------------------------
# Nunca deben ocurrir de forma automática (agente/modelo); solo una persona
# (origen=USER) puede decidirlas explícitamente. "no encontré el logo"
# (not_found) nunca se auto-convierte en "el proyecto no tiene logo"
# (not_applicable); "unknown" tampoco se auto-resuelve a "not_applicable"; una
# inferencia del modelo nunca se auto-promueve a "confirmed".
TRANSICIONES_RESTRINGIDAS = frozenset({
    (EstadoDato.INFERRED, EstadoDato.CONFIRMED),
    (EstadoDato.NOT_FOUND, EstadoDato.NOT_APPLICABLE),
    (EstadoDato.UNKNOWN, EstadoDato.NOT_APPLICABLE),
})


def transicion_valida(desde: EstadoDato, hacia: EstadoDato, origen: OrigenDato) -> bool:
    """True si el cambio de estado `desde -> hacia` es aceptable dado `origen`.

    Las transiciones de `TRANSICIONES_RESTRINGIDAS` solo son válidas cuando
    `origen == OrigenDato.USER` (una persona lo decidió explícitamente); un
    agente/modelo no puede producirlas por sí mismo. Cualquier otra
    transición (incluida quedarse en el mismo estado) es válida.
    """
    if (desde, hacia) in TRANSICIONES_RESTRINGIDAS:
        return origen == OrigenDato.USER
    return True


# --- Estructuras de datos --------------------------------------------------

@dataclass
class Dato:
    """Un valor descubierto/declarado, con su estado, origen y confianza.

    `confianza` es categórica (`NivelConfianza`), nunca un score numérico
    inventado: el modelo clasifica, no calcula.
    """

    valor: Any
    estado: EstadoDato
    origen: OrigenDato
    confianza: NivelConfianza
    actualizado_en: str
    notas: str = ""

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Dato":
        return cls(
            valor=d["valor"],
            estado=EstadoDato(d["estado"]),
            origen=OrigenDato(d["origen"]),
            confianza=NivelConfianza(d["confianza"]),
            actualizado_en=d["actualizado_en"],
            notas=d.get("notas", ""),
        )


@dataclass
class Mockup:
    """Un artefacto de UX versionable (wireframe, mockup, prototipo…).

    Contrato **independiente**: en TF-0026 no cuelga de `ResumenDisciplina`
    ni de `ExpedienteProyecto` — PROJECT_STATE se mantiene acotado al
    checklist de coordinación (`campos_esperados()`), sin campos añadidos sin
    decisión explícita. Dónde vive un `Mockup` en la práctica (¿su propia
    tabla?, ¿colgado de un futuro `UX_STATE`?) y cómo se versiona el archivo
    físico (`docs/proyectos/<codigo>/mockups/`, según el diseño original)
    queda para un ticket posterior de UX/estado especializado. Aquí solo se
    fija la forma de sus metadatos.

    `tipo` es texto libre corto (no un enum cerrado): admite categorías no
    previstas sin tocar el contrato.
    """

    id: str
    nombre: str
    tipo: str
    ruta: str
    version: int
    estado_aprobacion: EstadoAprobacionMockup
    creado_en: str
    actualizado_en: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "Mockup":
        return cls(
            id=d["id"],
            nombre=d["nombre"],
            tipo=d["tipo"],
            ruta=d["ruta"],
            version=d["version"],
            estado_aprobacion=EstadoAprobacionMockup(d["estado_aprobacion"]),
            creado_en=d["creado_en"],
            actualizado_en=d["actualizado_en"],
        )


@dataclass
class ResumenDisciplina:
    """Resumen de COORDINACIÓN de una disciplina — no su trabajo detallado.

    `datos` solo debe poblarse con claves de `campos_esperados()[<disciplina>]`
    para la `checklist_version` del expediente que la contiene.
    `referencia_estado` es el puntero (futuro) al `*_STATE` especializado
    donde vive el trabajo real de la disciplina; en TF-0026 queda siempre en
    `None` porque ningún `*_STATE` existe todavía.
    """

    aplicabilidad: AplicabilidadDisciplina
    datos: dict[str, Dato] = field(default_factory=dict)
    notas: str = ""
    referencia_estado: Optional[str] = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ResumenDisciplina":
        return cls(
            aplicabilidad=AplicabilidadDisciplina(d["aplicabilidad"]),
            datos={k: Dato.from_dict(v) for k, v in d.get("datos", {}).items()},
            notas=d.get("notas", ""),
            referencia_estado=d.get("referencia_estado"),
        )


def _disciplinas_por_defecto() -> dict[str, ResumenDisciplina]:
    return {
        nombre: ResumenDisciplina(aplicabilidad=AplicabilidadDisciplina.UNKNOWN)
        for nombre in DISCIPLINAS
    }


@dataclass
class ExpedienteProyecto:
    """PROJECT_STATE: expediente maestro de un proyecto de software.

    `codigo` ("PROY-001", …) lo asigna `RepositorioExpedientes.crear()`, no
    este dataclass ni el usuario. `checklist_version` se fija en creación y
    no debe cambiar salvo una migración explícita (fuera de alcance de
    TF-0026): `calcular_salud()` siempre resuelve el checklist contra este
    valor, nunca contra `CHECKLIST_VERSION_ACTUAL` directamente.
    """

    codigo: Optional[str] = None
    nombre: str = ""
    descripcion: str = ""
    checklist_version: str = CHECKLIST_VERSION_ACTUAL
    descubrimiento: dict[str, Dato] = field(default_factory=dict)
    disciplinas: dict[str, ResumenDisciplina] = field(default_factory=_disciplinas_por_defecto)
    creado_en: str = ""
    actualizado_en: str = ""
    last_analyzed_at: Optional[str] = None

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ExpedienteProyecto":
        return cls(
            codigo=d.get("codigo"),
            nombre=d.get("nombre", ""),
            descripcion=d.get("descripcion", ""),
            checklist_version=d.get("checklist_version", CHECKLIST_VERSION_ACTUAL),
            descubrimiento={
                k: Dato.from_dict(v) for k, v in d.get("descubrimiento", {}).items()
            },
            disciplinas={
                k: ResumenDisciplina.from_dict(v) for k, v in d.get("disciplinas", {}).items()
            },
            creado_en=d.get("creado_en", ""),
            actualizado_en=d.get("actualizado_en", ""),
            last_analyzed_at=d.get("last_analyzed_at"),
        )
