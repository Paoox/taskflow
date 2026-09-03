"""TF-0027 — Contrato del Orquestador: acción decidida + resultado de un ciclo.

Dataclasses puras con `to_dict()`/`from_dict()` simétrico, mismo criterio que
`src.agentes.contrato` y `src.proyectos.estado`/`salud`. Sin lógica de
decisión aquí (eso vive en `orquestador.py`).

Sin dependencias nuevas. No importa Flask, `src.database`, `src.app`, `src.ai`
ni `src.agentes`.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from enum import Enum

from src.proyectos.salud import SaludProyecto

__all__ = ["AccionOrquestador", "PreguntaPendiente", "ResultadoOrquestador"]


class AccionOrquestador(str, Enum):
    """Las 4 acciones posibles de un ciclo de coordinación (checkpoint TF-0027)."""

    INVESTIGAR = "investigar"
    PREGUNTAR = "preguntar"
    HANDOFF = "handoff"
    BLOQUEADO = "bloqueado"


@dataclass
class PreguntaPendiente:
    """Una pregunta derivada de un campo raíz sin resolver.

    No se persiste como entidad propia: `src.orquestador.preguntas.
    preguntas_pendientes()` la deriva en cada llamada a partir del
    `ExpedienteProyecto` y el checklist — sin estado paralelo que pueda
    desincronizarse.
    """

    campo: str
    pregunta: str
    motivo: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "PreguntaPendiente":
        return cls(campo=d["campo"], pregunta=d["pregunta"], motivo=d["motivo"])


@dataclass
class ResultadoOrquestador:
    """Resultado de un ciclo de `ejecutar_orquestador()`."""

    codigo: str
    accion: AccionOrquestador
    salud: SaludProyecto
    preguntas: list[PreguntaPendiente] = field(default_factory=list)
    problemas: list[str] = field(default_factory=list)
    hallazgos_aplicados: int = 0

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "ResultadoOrquestador":
        return cls(
            codigo=d["codigo"],
            accion=AccionOrquestador(d["accion"]),
            salud=SaludProyecto.from_dict(d["salud"]),
            preguntas=[PreguntaPendiente.from_dict(p) for p in d.get("preguntas", [])],
            problemas=list(d.get("problemas", [])),
            hallazgos_aplicados=d.get("hallazgos_aplicados", 0),
        )
