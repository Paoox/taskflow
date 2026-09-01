"""TF-0021 — Contrato común de agentes (`CLAUDE.md` §27).

Estructuras de datos puras (dataclasses) para la entrada y la salida de un
agente, con serialización simétrica a/desde `dict` / JSON.

Reglas de este módulo:

* sin lógica de negocio;
* no importa Flask, `src.database`, `src.app` ni red;
* `to_dict()` produce estructuras JSON-serializables (`json.dumps` sin
  `default=`); `from_dict()` reconstruye instancias equivalentes
  (`x == from_dict(to_dict(x))`).

`EntradaAgente` y `SalidaAgente` contienen exactamente los campos del §27.
`SalidaAgente` añade `artefactos` y `meta` (decisión de diseño Opción A del
checkpoint de TF-0021): **no** son campos especulativos, están justificados por
`CLAUDE.md` §26 (coste / latencia), §28 (`correlation_id` / trazabilidad) y §29.1
(artefactos de ticket), y los consume TF-0022 al persistir `acciones.resultado`.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass, field
from typing import List

__all__ = [
    "EntradaAgente",
    "SalidaAgente",
    "Artefacto",
    "ResumenPruebas",
    "Meta",
]


@dataclass
class EntradaAgente:
    """Lo que recibe un agente (`CLAUDE.md` §27)."""

    ticket: str
    objetivo: str
    contexto: str = ""
    restricciones: List[str] = field(default_factory=list)
    criterios_aceptacion: List[str] = field(default_factory=list)
    archivos_relevantes: List[str] = field(default_factory=list)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "EntradaAgente":
        return cls(
            ticket=d["ticket"],
            objetivo=d["objetivo"],
            contexto=d.get("contexto", ""),
            restricciones=list(d.get("restricciones", [])),
            criterios_aceptacion=list(d.get("criterios_aceptacion", [])),
            archivos_relevantes=list(d.get("archivos_relevantes", [])),
        )


@dataclass
class Artefacto:
    """Un fichero producido por un agente (contenido en memoria, aún sin escribir)."""

    ruta: str
    contenido: str
    tipo: str = "texto"

    @classmethod
    def from_dict(cls, d: dict) -> "Artefacto":
        return cls(
            ruta=d["ruta"],
            contenido=d["contenido"],
            tipo=d.get("tipo", "texto"),
        )


@dataclass
class ResumenPruebas:
    """Pruebas asociadas a la salida de un agente.

    `no_ejecutadas` es una lista de `{"prueba": str, "motivo": str}` (`CLAUDE.md`
    §20 / §32: distinguir ejecutado de no ejecutado, con motivo).
    """

    ejecutadas: List[str] = field(default_factory=list)
    fallidas: List[str] = field(default_factory=list)
    no_ejecutadas: List[dict] = field(default_factory=list)

    @classmethod
    def from_dict(cls, d: dict) -> "ResumenPruebas":
        return cls(
            ejecutadas=list(d.get("ejecutadas", [])),
            fallidas=list(d.get("fallidas", [])),
            no_ejecutadas=[dict(x) for x in d.get("no_ejecutadas", [])],
        )


@dataclass
class Meta:
    """Metadatos de una ejecución (`CLAUDE.md` §26 coste/latencia, §28 trazabilidad).

    `duracion_s` en segundos (número JSON, no `timedelta`). `tokens` es el total.
    `correlation_id` lo puebla el llamador (runner futuro); este módulo no importa
    `src.observabilidad`.
    """

    modelo: str = ""
    tokens: int = 0
    coste_estimado: float = 0.0
    duracion_s: float = 0.0
    correlation_id: str = ""

    @classmethod
    def from_dict(cls, d: dict) -> "Meta":
        return cls(
            modelo=d.get("modelo", ""),
            tokens=d.get("tokens", 0),
            coste_estimado=d.get("coste_estimado", 0.0),
            duracion_s=d.get("duracion_s", 0.0),
            correlation_id=d.get("correlation_id", ""),
        )


@dataclass
class SalidaAgente:
    """Lo que devuelve un agente.

    Campos del §27 (`resultado`, `cambios`, `pruebas`, `problemas`,
    `recomendaciones`) más `artefactos` y `meta` (Opción A del checkpoint).
    """

    resultado: str
    cambios: List[str] = field(default_factory=list)
    pruebas: ResumenPruebas = field(default_factory=ResumenPruebas)
    problemas: List[str] = field(default_factory=list)
    recomendaciones: List[str] = field(default_factory=list)
    artefactos: List[Artefacto] = field(default_factory=list)
    meta: Meta = field(default_factory=Meta)

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)

    @classmethod
    def from_dict(cls, d: dict) -> "SalidaAgente":
        return cls(
            resultado=d["resultado"],
            cambios=list(d.get("cambios", [])),
            pruebas=ResumenPruebas.from_dict(d.get("pruebas", {})),
            problemas=list(d.get("problemas", [])),
            recomendaciones=list(d.get("recomendaciones", [])),
            artefactos=[Artefacto.from_dict(a) for a in d.get("artefactos", [])],
            meta=Meta.from_dict(d.get("meta", {})),
        )
