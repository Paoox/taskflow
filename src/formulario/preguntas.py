"""Catálogo de preguntas del formulario — datos puros, sin lógica de árbol.

`DefinicionPregunta` describe una pregunta tal como debe mostrarse; la
secuencia/dependencias entre preguntas vive en `src.formulario.arbol`, no
aquí (separación deliberada: catálogo vs. navegación).

Reutiliza `TipoPregunta` de `src.expediente.modelo` sin agregar un tercer
valor: una pregunta de selección múltiple sigue siendo `OPCION_CERRADA`,
distinguida únicamente por `multiple=True` — la base de datos no necesita
saberlo, es un atributo del catálogo (checkpoint de diseño, decisión
cerrada: "reutilizar TipoPregunta existente").

Todas las preguntas están redactadas en lenguaje llano, sin nombrar ninguna
tecnología, framework o patrón de arquitectura (principio general del
checkpoint: preguntar decisiones de negocio/comportamiento esperado, nunca
conceptos técnicos).
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.expediente.modelo import TipoPregunta

__all__ = [
    "DefinicionPregunta", "PREGUNTAS",
    "OPCION_NUEVO", "OPCION_EXISTENTE",
    "OPCION_SI", "OPCION_NO", "OPCION_NO_SE",
    "OPCION_PLATAFORMA_NAVEGADOR", "OPCION_PLATAFORMA_CELULAR",
    "OPCION_PLATAFORMA_COMPUTADORA", "OPCION_PLATAFORMA_VARIAS",
    "OPCION_PLATAFORMA_NO_SEGURO", "OPCION_DETALLE_CELULAR",
    "OPCION_UNA_PERSONA", "OPCION_VARIAS_PERSONAS", "OPCION_ADMIN_NO_SE",
    "OPCION_OTRA_COSA",
    "OPCION_MONETIZACION_NO", "OPCION_MONETIZACION_SI", "OPCION_MONETIZACION_NO_DECIDIDO",
]


@dataclass(frozen=True)
class DefinicionPregunta:
    """Una pregunta del árbol, tal como se muestra a la persona.

    `opciones` solo aplica a `tipo_pregunta=OPCION_CERRADA` (`None` para
    texto libre). `multiple` solo puede ser `True` si `tipo_pregunta` es
    `OPCION_CERRADA` — una pregunta de texto libre nunca es "múltiple".
    `obligatoria` es informativa para una futura UI (qué no se puede saltar
    sin responder algo, aunque sea "no sé"); la navegación del árbol
    (`arbol.py`) no la necesita para decidir la siguiente pregunta.
    """

    pregunta_id: str
    texto: str
    tipo_pregunta: TipoPregunta
    opciones: Optional[tuple[str, ...]] = None
    multiple: bool = False
    obligatoria: bool = False

    def __post_init__(self):
        if self.multiple and self.tipo_pregunta != TipoPregunta.OPCION_CERRADA:
            raise ValueError(
                f"{self.pregunta_id!r}: multiple=True requiere tipo_pregunta=OPCION_CERRADA"
            )
        if self.tipo_pregunta == TipoPregunta.OPCION_CERRADA and not self.opciones:
            raise ValueError(f"{self.pregunta_id!r}: OPCION_CERRADA requiere 'opciones' no vacío")
        if self.tipo_pregunta == TipoPregunta.TEXTO_LIBRE and self.opciones:
            raise ValueError(f"{self.pregunta_id!r}: TEXTO_LIBRE no admite 'opciones'")


# --- Constantes de opciones reutilizadas por arbol.py para ramificar -------
# (evita strings mágicos duplicados entre el catálogo y la lógica de árbol)

OPCION_NUEVO = "Es un proyecto nuevo"
OPCION_EXISTENTE = "Ya tengo algo construido"

OPCION_SI = "Sí"
OPCION_NO = "No"
OPCION_NO_SE = "No sé"

OPCION_PLATAFORMA_NAVEGADOR = "Desde un navegador web"
OPCION_PLATAFORMA_CELULAR = "Desde el celular"
OPCION_PLATAFORMA_COMPUTADORA = "Desde una computadora (programa instalado)"
OPCION_PLATAFORMA_VARIAS = "En varios de estos lugares"
OPCION_PLATAFORMA_NO_SEGURO = "No estoy seguro todavía"
OPCION_DETALLE_CELULAR = "Celular"

OPCION_UNA_PERSONA = "Una sola persona"
OPCION_VARIAS_PERSONAS = "Varias personas"
OPCION_ADMIN_NO_SE = "Todavía no lo sé"

OPCION_OTRA_COSA = "Otra cosa"

OPCION_MONETIZACION_NO = "No, es gratis"
OPCION_MONETIZACION_SI = "Sí, de alguna forma"
OPCION_MONETIZACION_NO_DECIDIDO = "Todavía no lo he decidido"


def _cerrada(pregunta_id, texto, opciones, *, multiple=False, obligatoria=False):
    return DefinicionPregunta(
        pregunta_id=pregunta_id, texto=texto, tipo_pregunta=TipoPregunta.OPCION_CERRADA,
        opciones=tuple(opciones), multiple=multiple, obligatoria=obligatoria,
    )


def _libre(pregunta_id, texto, *, obligatoria=False):
    return DefinicionPregunta(
        pregunta_id=pregunta_id, texto=texto, tipo_pregunta=TipoPregunta.TEXTO_LIBRE,
        obligatoria=obligatoria,
    )


# --- Catálogo completo ------------------------------------------------------
# Bloque 0 — Punto de partida

_LISTA: tuple[DefinicionPregunta, ...] = (
    _cerrada(
        "nuevo_o_existente", "¿Es un proyecto nuevo o ya tienes algo construido?",
        [OPCION_NUEVO, OPCION_EXISTENTE], obligatoria=True,
    ),
    _libre(
        "referencia_proyecto_existente", "¿Dónde está ese proyecto?", obligatoria=True,
    ),

    # Bloque 1 — Identidad y objetivo
    _libre("nombre_proyecto", "¿Cómo se llama tu proyecto?"),
    _libre(
        "problema_objetivo",
        "En pocas palabras, ¿qué problema quieres resolver o qué quieres lograr con este proyecto?",
        obligatoria=True,
    ),
    _libre(
        "objetivo_proyecto_existente",
        "¿Qué quieres conseguir ahora con el proyecto que ya tienes? "
        "¿Vas a continuar lo mismo, cambiar el rumbo, o algo más?",
        obligatoria=True,
    ),

    # Bloque 2 — Plataformas
    _cerrada(
        "plataforma", "¿Dónde quieres que la gente use tu proyecto?",
        [
            OPCION_PLATAFORMA_NAVEGADOR, OPCION_PLATAFORMA_CELULAR,
            OPCION_PLATAFORMA_COMPUTADORA, OPCION_PLATAFORMA_VARIAS,
            OPCION_PLATAFORMA_NO_SEGURO,
        ],
        obligatoria=True,
    ),
    _cerrada(
        "plataforma_detalle", "¿Cuáles, específicamente?",
        [OPCION_PLATAFORMA_NAVEGADOR, OPCION_DETALLE_CELULAR, OPCION_PLATAFORMA_COMPUTADORA],
        multiple=True,
    ),
    _cerrada(
        "plataforma_offline", "¿Debe funcionar sin conexión a internet?",
        [OPCION_SI, OPCION_NO, OPCION_NO_SE],
    ),

    # Bloque 3a — Perfiles de usuario
    _libre(
        "perfil_usuario", "¿Quién va a usar tu proyecto? Descríbelo con tus palabras.",
        obligatoria=True,
    ),
    _cerrada(
        "perfil_usuario_continuar", "¿Hay otro tipo de persona que también lo use?",
        [OPCION_SI, OPCION_NO],
    ),

    # Bloque 3b — Administración / roles y permisos, en lenguaje llano
    _cerrada(
        "administracion_cantidad",
        "¿Cuántas personas administrarán el proyecto cuando esté terminado?",
        [OPCION_UNA_PERSONA, OPCION_VARIAS_PERSONAS, OPCION_ADMIN_NO_SE],
    ),
    _cerrada(
        "administracion_diferencias",
        "¿Habrá diferencias entre lo que puede hacer cada una?",
        [OPCION_SI, OPCION_NO, "No estoy seguro"],
    ),
    _libre(
        "administrador_tipo_nombre",
        "¿Cómo llamarías a este tipo de persona? (por ejemplo: \"el dueño\", \"los vendedores\")",
    ),
    _cerrada(
        "administrador_tipo_acciones", "¿Qué podrá hacer esta persona?",
        [
            "Ver información", "Agregar cosas nuevas", "Cambiar lo que ya existe",
            "Eliminar cosas", "Controlar/administrar todo el proyecto", OPCION_OTRA_COSA,
        ],
        multiple=True,
    ),
    _libre("administrador_tipo_otra", "Cuéntame qué más podrá hacer."),
    _cerrada(
        "administrador_tipo_continuar", "¿Hay otro tipo de persona administradora?",
        [OPCION_SI, OPCION_NO],
    ),

    # Bloque 4 — Qué debe poder hacer
    _libre(
        "funcionalidad_declarada",
        "¿Qué cosas debe poder hacer una persona en tu proyecto? Cuéntame una por una.",
        obligatoria=True,
    ),
    _cerrada(
        "funcionalidad_declarada_continuar", "¿Algo más que deba poder hacer?",
        [OPCION_SI, OPCION_NO],
    ),

    # Bloque 5 — Dinero
    _cerrada(
        "monetizacion", "¿Tu proyecto va a cobrar algo, de cualquier forma?",
        [OPCION_MONETIZACION_NO, OPCION_MONETIZACION_SI, OPCION_MONETIZACION_NO_DECIDIDO],
        obligatoria=True,
    ),
    _cerrada(
        "monetizacion_forma", "¿Cómo prefieres cobrar?",
        ["Una sola vez", "Suscripción (pago recurrente)", "Depende del uso", OPCION_NO_SE],
    ),

    # Bloque 6 — Información que maneja
    _cerrada(
        "dato_recordar",
        "¿Hay algo que tu proyecto deba recordar entre una visita y otra? "
        "Por ejemplo, información de la persona, cosas que guardó, historial, etc.",
        [OPCION_SI, OPCION_NO, "No estoy seguro"],
        obligatoria=True,
    ),
    _libre("dato_recordar_detalle", "¿Qué debe recordar?"),
    _cerrada(
        "dato_recordar_detalle_continuar", "¿Algo más que deba recordar?",
        [OPCION_SI, OPCION_NO],
    ),

    # Bloque 7 — Restricciones y preferencias
    _libre(
        "restriccion_tecnica",
        "¿Tu equipo ya sabe trabajar con alguna tecnología en particular, "
        "o ya tienen algo funcionando que prefieran reusar?",
    ),
    _libre("restriccion_tiempo_presupuesto", "¿Hay algún límite de tiempo o presupuesto que debamos tener en cuenta?"),
    _libre(
        "restriccion_negocio",
        "¿Hay algo que el proyecto NO deba hacer, o alguna regla legal o de negocio que debamos respetar?",
    ),

    # Cierre
    _libre("cierre_libre", "¿Hay algo más que quieras contarme sobre tu proyecto?"),
)

PREGUNTAS: dict[str, DefinicionPregunta] = {p.pregunta_id: p for p in _LISTA}
