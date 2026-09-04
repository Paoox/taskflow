"""Brief del cliente: comunicación humana original, separada de PROJECT_STATE.

Corrección arquitectónica aprobada tras los smoke tests reales de TF-0028/
TF-0029 con Ollama/Qwen: la metadata de coordinación de TaskFlow (`ticket`,
`objetivo` interno del agente, `codigo` de expediente) se estaba mezclando
con la evidencia del proyecto dentro del prompt del Descubridor. Este módulo
introduce el brief del cliente como **fuente de datos de primera clase**,
distinta tanto de la metadata de TaskFlow como del `ExpedienteProyecto`
(`src.proyectos.estado`, PROJECT_STATE) y de la evidencia recolectada por
Tools (`src.orquestador.evidencia`).

`EntradaBrief` es deliberadamente **inmutable** (`frozen=True`) y **no** se
convierte directamente en `Dato`: es material sin interpretar, a analizar por
un agente de descubrimiento — decidir qué campo de PROJECT_STATE informa cada
frase del brief es un problema de extracción determinista, fuera de alcance
de este módulo (y de este ticket).

`origen` reutiliza `OrigenDato` de `src.proyectos.estado` — no se duplica
vocabulario ya aprobado; para un brief real será casi siempre `USER`.

Dataclass pura con `to_dict()`/`from_dict()` simétrico, mismo criterio que
`src.agentes.contrato` y `src.proyectos.estado`. Sin lógica de persistencia
(eso vive en `src.repositorios.briefs`).

Sin dependencias nuevas. No importa Flask, `src.database`, `src.app`,
`src.agentes` ni `src.ai`.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from enum import Enum

from src.proyectos.estado import OrigenDato

__all__ = ["TipoEntradaBrief", "EntradaBrief"]


class TipoEntradaBrief(str, Enum):
    """`(str, Enum)` — mismo criterio que los enums de `src.proyectos.estado`:
    el valor es directamente el texto que se guarda en SQLite y se serializa
    en JSON, sin codificador a medida.
    """

    INICIAL = "inicial"
    RESPUESTA_CLIENTE = "respuesta_cliente"


@dataclass(frozen=True)
class EntradaBrief:
    """Una entrada de comunicación directa del cliente, ya registrada.

    `id`/`ronda`/`recibido_en` los asigna `RepositorioBriefs.registrar()`, no
    el llamador ni este dataclass. `texto` se conserva **verbatim**: ningún
    campo de esta clase reinterpreta, recorta ni normaliza el contenido.

    `frozen=True`: una vez registrada, una `EntradaBrief` no se modifica —
    corresponde a la regla de persistencia "append-only" de
    `RepositorioBriefs` (sin `actualizar()` ni `eliminar()`).
    """

    id: int | None
    codigo: str
    ronda: int
    tipo: TipoEntradaBrief
    texto: str
    origen: OrigenDato
    recibido_en: str

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EntradaBrief":
        return cls(
            id=d.get("id"),
            codigo=d["codigo"],
            ronda=d["ronda"],
            tipo=TipoEntradaBrief(d["tipo"]),
            texto=d["texto"],
            origen=OrigenDato(d["origen"]),
            recibido_en=d["recibido_en"],
        )
