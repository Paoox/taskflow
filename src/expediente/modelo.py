"""Modelo conceptual consolidado del Expediente Maestro: dataclasses y enums.

Fuente de verdad exclusiva del nuevo flujo de Discovery (checkpoint de
consolidación). Deliberadamente NO importa ni depende de `src.proyectos.
estado.EstadoDato`, `src.proyectos.checklist` ni `campos_esperados()` — ese
es el checklist raíz antiguo (PROJECT_STATE), que queda fuera de este modelo
por decisión explícita (no debe alimentarlo ni duplicarlo).

Sí reutiliza `OrigenDato` y `NivelConfianza` de `src.proyectos.estado`:
son vocabulario puro (de dónde salió un dato / qué tan seguro se está de
él), sin acoplarse a `EstadoDato` ni al checklist — reutilizarlos evita
duplicar un enum idéntico (CLAUDE.md §17) sin reintroducir la dependencia
que sí se quiere evitar.

`NaturalezaInformacion` es el eje nuevo (declarado/observado/deducido) que
reemplaza, para estas entidades, la doble función que `EstadoDato` cumplía
en el modelo antiguo (mezclaba cobertura de investigación con clasificación
epistémica). Deliberadamente tiene solo 3 valores: "propuesto" nunca es un
valor de `naturaleza` de ninguna entidad — es una entidad distinta,
`FeaturePropuesta` (ver `RepositorioFeaturesPropuestas`), y "pendiente" no es
un valor de nada — es la ausencia de una entidad, representada por un `Gap`
cuando esa ausencia importa. Es una garantía estructural: no existe ningún
campo en `Requisito`/`Capacidad`/`Dato` donde "propuesto" o "pendiente"
puedan escribirse por accidente.

Ninguna dataclass de este módulo implementa `to_dict()`/`from_dict()`
simétrico (a diferencia de `ExpedienteProyecto`/`EntradaBrief`): esas
entidades se serializan enteras como un único blob JSON en una columna: aquí
cada campo es su propia columna de una tabla relacional, así que no hay
ningún blob que serializar — `from_row()` (fila de SQLite -> dataclass) es
lo único que hace falta, y vive en cada repositorio de
`src.repositorios`, no aquí.

Sin dependencias nuevas. No importa Flask, `src.database`, `src.app`,
`src.agentes` ni `src.ai`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass
from enum import Enum
from typing import Optional

from src.proyectos.estado import NivelConfianza, OrigenDato

__all__ = [
    "NaturalezaInformacion", "TipoRelacion", "TipoPregunta",
    "EstadoRequisito", "EstadoFeaturePropuesta", "EstadoGap", "EstadoContradiccion",
    "FuenteDirecta",
    "Perfil", "Requisito", "Capacidad", "Funcionalidad", "Dato", "Restriccion",
    "FeaturePropuesta", "Gap", "Contradiccion", "Relacion",
    "RespuestaFormulario", "EstadoObservado",
]


# --- Enums -------------------------------------------------------------

class NaturalezaInformacion(str, Enum):
    """Eje epistémico de Requisito/Capacidad/Dato/Perfil. Nunca "propuesto"
    ni "pendiente" — ver docstring del módulo."""

    DECLARADO = "declarado"
    OBSERVADO = "observado"
    DEDUCIDO = "deducido"


class TipoRelacion(str, Enum):
    """Los 4 tipos de arista del grafo (checkpoint de persistencia mínima,
    tabla única `relaciones`)."""

    REQUIERE = "requiere"          # Requisito -> Capacidad
    DEPENDE_DE = "depende_de"      # Capacidad -> Capacidad
    OPERA_SOBRE = "opera_sobre"    # Capacidad -> Dato
    AGRUPA = "agrupa"              # Funcionalidad -> Requisito


class TipoPregunta(str, Enum):
    OPCION_CERRADA = "opcion_cerrada"
    TEXTO_LIBRE = "texto_libre"


class EstadoRequisito(str, Enum):
    ACTIVO = "activo"
    DESCARTADO = "descartado"


class EstadoFeaturePropuesta(str, Enum):
    PROPUESTA = "propuesta"
    ACEPTADA = "aceptada"
    RECHAZADA = "rechazada"


class EstadoGap(str, Enum):
    ABIERTO = "abierto"
    RESUELTO = "resuelto"
    DOCUMENTADO_NO_BLOQUEANTE = "documentado_no_bloqueante"


class EstadoContradiccion(str, Enum):
    ABIERTA = "abierta"
    RESUELTA = "resuelta"


# --- Fuente directa (trazabilidad) --------------------------------------

@dataclass(frozen=True)
class FuenteDirecta:
    """Puntero al mensaje humano concreto que originó una entidad —
    complementa `accion_id_origen` (que solo dice qué ejecución del
    Orquestador la produjo, no qué dijo la persona).

    `tipo` es texto libre corto por diseño (no un enum cerrado): los valores
    esperados hoy son "brief", "formulario" y "evidencia", pero no vale la
    pena congelarlos en un enum para un campo que solo se usa para
    referenciar, nunca para decidir lógica.
    """

    tipo: str
    referencia: str

    def to_json(self) -> str:
        return json.dumps({"tipo": self.tipo, "referencia": self.referencia}, ensure_ascii=False)

    @classmethod
    def from_json(cls, texto: Optional[str]) -> Optional["FuenteDirecta"]:
        if not texto:
            return None
        datos = json.loads(texto)
        return cls(tipo=datos["tipo"], referencia=datos["referencia"])


# --- Entidades -----------------------------------------------------------

@dataclass
class Perfil:
    """Quién es la persona, funcionalmente (D1 — no confundir con rol/permisos,
    que queda fuera de este primer corte)."""

    id: Optional[int]
    codigo: str
    nombre: str
    descripcion: str
    naturaleza: NaturalezaInformacion
    origen: OrigenDato
    confianza: NivelConfianza
    accion_id_origen: Optional[int]
    fuente_directa: Optional[FuenteDirecta]
    creado_en: str


@dataclass
class Requisito:
    """QUÉ debe cumplir el sistema. Incluye lo que antes se hubiera llamado
    "regla de negocio" — no es una entidad aparte (checkpoint de
    consolidación)."""

    id: Optional[int]
    codigo: str
    descripcion: str
    naturaleza: NaturalezaInformacion
    origen: OrigenDato
    confianza: NivelConfianza
    estado: EstadoRequisito
    accion_id_origen: Optional[int]
    fuente_directa: Optional[FuenteDirecta]
    creado_en: str
    actualizado_en: Optional[str]


@dataclass
class Capacidad:
    """QUÉ HABILIDAD necesita el sistema para cumplir uno o más Requisitos.
    Agnóstica de tecnología por contrato: `tipo` es vocabulario abierto
    (D4) pero nunca nombra un producto/framework concreto."""

    id: Optional[int]
    codigo: str
    descripcion: str
    tipo: str
    naturaleza: NaturalezaInformacion
    origen: OrigenDato
    confianza: NivelConfianza
    accion_id_origen: Optional[int]
    fuente_directa: Optional[FuenteDirecta]
    creado_en: str


@dataclass
class Funcionalidad:
    """Agrupación organizativa de Requisitos relacionados. Sin naturaleza
    propia: nunca es una fuente de verdad paralela a sus Requisitos."""

    id: Optional[int]
    codigo: str
    nombre: str
    descripcion: str
    tier: Optional[str]
    creado_en: str


@dataclass
class Dato:
    """Concepto de información que el sistema maneja (no un esquema de BD).

    Nombre compartido con `src.proyectos.estado.Dato` (modelo antiguo) por
    coincidencia de vocabulario de dominio — son clases distintas, en
    módulos distintos, sin relación entre sí.
    """

    id: Optional[int]
    codigo: str
    descripcion: str
    temporalidad: Optional[str]
    sensibilidad: Optional[str]
    naturaleza: NaturalezaInformacion
    origen: OrigenDato
    confianza: NivelConfianza
    accion_id_origen: Optional[int]
    fuente_directa: Optional[FuenteDirecta]
    creado_en: str


@dataclass
class Restriccion:
    """Límite declarado explícitamente por el usuario/equipo. `naturaleza`
    solo puede ser `DECLARADO` — validado por `RepositorioRestricciones`, no
    solo por convención. Incluye lo que antes era `stack_declarado`."""

    id: Optional[int]
    codigo: str
    tipo: str
    descripcion: str
    naturaleza: NaturalezaInformacion
    origen: OrigenDato
    accion_id_origen: Optional[int]
    fuente_directa: Optional[FuenteDirecta]
    creado_en: str


@dataclass
class FeaturePropuesta:
    """Idea que aporta valor potencial pero no es necesaria para cumplir lo
    declarado. `origen` solo puede ser `AGENT` — validado por
    `RepositorioFeaturesPropuestas`. Nunca vive dentro de `Requisito`."""

    id: Optional[int]
    codigo: str
    descripcion: str
    motivo: str
    origen: OrigenDato
    confianza: NivelConfianza
    impacto: Optional[str]
    estado: EstadoFeaturePropuesta
    campo_relacionado_tipo: Optional[str]
    campo_relacionado_id: Optional[int]
    accion_id_origen: Optional[int]
    creado_en: str
    actualizado_en: Optional[str]


@dataclass
class Gap:
    """Ausencia relevante de información. `criticidad` es un campo cacheado
    de lectura: se calcula por código (D5) recorriendo `relaciones`, nunca la
    declara el modelo — este primer corte solo persiste el valor, el cálculo
    en sí queda para el Orquestador Discovery (fuera de alcance aquí)."""

    id: Optional[int]
    codigo: str
    entidad_afectada_tipo: str
    entidad_afectada_id: Optional[int]
    campo_o_concepto: str
    motivo: Optional[str]
    bloquea: list  # [{"tipo": ..., "id": ...}, ...] — JSON, D2
    criticidad: Optional[str]
    estado: EstadoGap
    creado_en: str
    resuelto_en: Optional[str]


@dataclass
class Contradiccion:
    """Relación entre 2+ afirmaciones en conflicto — nunca un estado de una
    entidad individual (D2). `afirmaciones` es JSON por ahora (aprobado)."""

    id: Optional[int]
    codigo: str
    entidad_tipo: str
    concepto: str
    afirmaciones: list  # [{"valor": ..., "origen": ..., "naturaleza": ...}, ...]
    estado: EstadoContradiccion
    resolucion_valor: Optional[str]
    resolucion_accion_id: Optional[int]
    creado_en: str
    resuelto_en: Optional[str]


@dataclass
class Relacion:
    """Una arista del grafo. Tabla única y genérica (aprobada como solución
    definitiva) en vez de una tabla por tipo de relación."""

    id: Optional[int]
    codigo: str
    tipo: TipoRelacion
    origen_tipo: str
    origen_id: int
    destino_tipo: str
    destino_id: int
    creado_en: str


@dataclass
class RespuestaFormulario:
    """Captura cruda de una pregunta+respuesta del árbol de decisión, antes
    de interpretarse en cualquier entidad del modelo. `pregunta_id` es texto
    libre mantenido por el código del árbol (sin catálogo todavía —
    decisión aprobada)."""

    id: Optional[int]
    codigo: str
    pregunta_id: str
    pregunta_texto: str
    tipo_pregunta: TipoPregunta
    respuesta: str
    respondido_en: str
    accion_id_origen: Optional[int]


@dataclass
class EstadoObservado:
    """Una versión de evidencia técnica de un repositorio existente (D3).
    Append-only — nunca se sobreescribe una versión anterior. Nunca se
    mezcla con `Requisito` (lo deseado) — dominio separado por diseño."""

    id: Optional[int]
    codigo: str
    version: int
    capturado_en: str
    tecnologias_detectadas: list
    funcionalidades_detectadas: list
    aparenta_funcionar: Optional[str]
    accion_id_origen: Optional[int]
