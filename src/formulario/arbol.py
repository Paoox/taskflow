"""Árbol de decisión determinista: `siguiente_pregunta()`.

Dada la lista de respuestas ya registradas para un expediente (en el orden
en que se dieron — mismo contrato que `RepositorioRespuestasFormulario.
listar()`), decide cuál es la siguiente pregunta a mostrar, o `None` si el
árbol ya se completó. Función pura: no abre conexión a la base de datos, no
llama a ningún proveedor de IA, no interpreta el contenido de ninguna
respuesta — solo mira qué `pregunta_id` ya tienen fila y, para las
preguntas cerradas que ramifican, qué opción se eligió.

El llamador (fuera de este paquete: una futura ruta Flask, o un script)
es quien:
  1. obtiene `RepositorioRespuestasFormulario().listar(codigo)`;
  2. le pasa esa lista a `siguiente_pregunta()`;
  3. muestra la pregunta devuelta;
  4. valida+serializa la respuesta (`src.formulario.respuestas`) y la
     persiste con `RepositorioRespuestasFormulario().registrar(...)`.

Este módulo nunca importa `src.repositorios` ni escribe nada — coherente
con la frontera ya cerrada: Formulario -> respuestas_formulario -> Discovery
-> Expediente. Tampoco crea `Requisito`/`Capacidad`/etc.: esa interpretación
es responsabilidad exclusiva de Discovery.
"""
from __future__ import annotations

from typing import Optional

from src.expediente.modelo import RespuestaFormulario
from src.formulario.preguntas import (
    OPCION_DETALLE_CELULAR, OPCION_EXISTENTE, OPCION_MONETIZACION_SI,
    OPCION_OTRA_COSA, OPCION_PLATAFORMA_CELULAR, OPCION_PLATAFORMA_VARIAS,
    OPCION_SI, OPCION_VARIAS_PERSONAS, PREGUNTAS, DefinicionPregunta,
)
from src.formulario.respuestas import deserializar_respuesta

__all__ = ["siguiente_pregunta"]


def _respuestas_de(respuestas: list[RespuestaFormulario], pregunta_id: str) -> list[RespuestaFormulario]:
    return [r for r in respuestas if r.pregunta_id == pregunta_id]


def _ultima(respuestas: list[RespuestaFormulario], pregunta_id: str) -> Optional[str]:
    de_esta = _respuestas_de(respuestas, pregunta_id)
    return de_esta[-1].respuesta if de_esta else None


def _respondida(respuestas: list[RespuestaFormulario], pregunta_id: str) -> bool:
    return _ultima(respuestas, pregunta_id) is not None


def _paso_bloque_repetible(
    respuestas: list[RespuestaFormulario], contenido_id: str, continuar_id: str,
) -> Optional[DefinicionPregunta]:
    """Estado de un bucle simple de una sola pregunta repetible (perfiles,
    funcionalidades, datos a recordar): pide contenido, luego pregunta si
    hay otro, y repite mientras la respuesta sea "Sí". Devuelve `None`
    cuando el bloque ya terminó (último "continuar" fue "No")."""
    n_contenido = len(_respuestas_de(respuestas, contenido_id))
    n_continuar = len(_respuestas_de(respuestas, continuar_id))

    if n_contenido == 0:
        return PREGUNTAS[contenido_id]
    if n_contenido > n_continuar:
        return PREGUNTAS[continuar_id]
    if _ultima(respuestas, continuar_id) == OPCION_SI:
        return PREGUNTAS[contenido_id]
    return None


def _paso_administradores(respuestas: list[RespuestaFormulario]) -> Optional[DefinicionPregunta]:
    """Estado del bucle de "tipos de persona administradora" (decisión 4):
    por cada iteración se pide nombre -> qué puede hacer -> (si marcó "Otra
    cosa") qué más puede hacer -> ¿hay otro tipo?. Más complejo que
    `_paso_bloque_repetible` porque tiene varios pasos por iteración."""
    respuestas_nombre = _respuestas_de(respuestas, "administrador_tipo_nombre")
    respuestas_acciones = _respuestas_de(respuestas, "administrador_tipo_acciones")
    respuestas_otra = _respuestas_de(respuestas, "administrador_tipo_otra")
    respuestas_continuar = _respuestas_de(respuestas, "administrador_tipo_continuar")

    if len(respuestas_nombre) == 0:
        return PREGUNTAS["administrador_tipo_nombre"]
    if len(respuestas_nombre) > len(respuestas_acciones):
        return PREGUNTAS["administrador_tipo_acciones"]

    # ¿cuántas iteraciones, hasta ahora, marcaron "Otra cosa"? — se compara
    # contra cuántas "otra" ya se respondieron, no contra el conteo bruto de
    # acciones, para no confundir una iteración que sí la necesitó con una
    # que no (el orden de las respuestas ya está garantizado por el llamador).
    pregunta_acciones = PREGUNTAS["administrador_tipo_acciones"]
    n_otra_esperadas = sum(
        1 for r in respuestas_acciones
        if OPCION_OTRA_COSA in deserializar_respuesta(pregunta_acciones, r.respuesta)
    )
    if n_otra_esperadas > len(respuestas_otra):
        return PREGUNTAS["administrador_tipo_otra"]

    if len(respuestas_acciones) > len(respuestas_continuar):
        return PREGUNTAS["administrador_tipo_continuar"]

    if _ultima(respuestas, "administrador_tipo_continuar") == OPCION_SI:
        return PREGUNTAS["administrador_tipo_nombre"]
    return None


def siguiente_pregunta(respuestas: list[RespuestaFormulario]) -> Optional[DefinicionPregunta]:
    """Siguiente pregunta a mostrar dado lo ya respondido, o `None` si el
    árbol se completó. `respuestas` debe venir ordenada ascendente (mismo
    contrato que `RepositorioRespuestasFormulario.listar()`)."""

    # Bloque 0 — punto de partida
    if not _respondida(respuestas, "nuevo_o_existente"):
        return PREGUNTAS["nuevo_o_existente"]
    es_existente = _ultima(respuestas, "nuevo_o_existente") == OPCION_EXISTENTE

    if es_existente and not _respondida(respuestas, "referencia_proyecto_existente"):
        return PREGUNTAS["referencia_proyecto_existente"]

    # Bloque 1 — identidad y objetivo
    if not _respondida(respuestas, "nombre_proyecto"):
        return PREGUNTAS["nombre_proyecto"]
    if not _respondida(respuestas, "problema_objetivo"):
        return PREGUNTAS["problema_objetivo"]
    if es_existente and not _respondida(respuestas, "objetivo_proyecto_existente"):
        return PREGUNTAS["objetivo_proyecto_existente"]

    # Bloque 2 — plataformas
    if not _respondida(respuestas, "plataforma"):
        return PREGUNTAS["plataforma"]
    plataforma = _ultima(respuestas, "plataforma")

    if plataforma == OPCION_PLATAFORMA_VARIAS and not _respondida(respuestas, "plataforma_detalle"):
        return PREGUNTAS["plataforma_detalle"]

    incluye_celular = plataforma == OPCION_PLATAFORMA_CELULAR or (
        plataforma == OPCION_PLATAFORMA_VARIAS
        and OPCION_DETALLE_CELULAR in deserializar_respuesta(
            PREGUNTAS["plataforma_detalle"], _ultima(respuestas, "plataforma_detalle")
        )
    )
    if incluye_celular and not _respondida(respuestas, "plataforma_offline"):
        return PREGUNTAS["plataforma_offline"]

    # Bloque 3a — perfiles de usuario
    paso = _paso_bloque_repetible(respuestas, "perfil_usuario", "perfil_usuario_continuar")
    if paso is not None:
        return paso

    # Bloque 3b — administración (independiente de cuántos perfiles hubo — decisión 4)
    if not _respondida(respuestas, "administracion_cantidad"):
        return PREGUNTAS["administracion_cantidad"]
    if _ultima(respuestas, "administracion_cantidad") == OPCION_VARIAS_PERSONAS:
        if not _respondida(respuestas, "administracion_diferencias"):
            return PREGUNTAS["administracion_diferencias"]
        if _ultima(respuestas, "administracion_diferencias") == OPCION_SI:
            paso = _paso_administradores(respuestas)
            if paso is not None:
                return paso

    # Bloque 4 — funcionalidad declarada
    paso = _paso_bloque_repetible(respuestas, "funcionalidad_declarada", "funcionalidad_declarada_continuar")
    if paso is not None:
        return paso

    # Bloque 5 — monetización
    if not _respondida(respuestas, "monetizacion"):
        return PREGUNTAS["monetizacion"]
    if _ultima(respuestas, "monetizacion") == OPCION_MONETIZACION_SI:
        if not _respondida(respuestas, "monetizacion_forma"):
            return PREGUNTAS["monetizacion_forma"]

    # Bloque 6 — información que maneja
    if not _respondida(respuestas, "dato_recordar"):
        return PREGUNTAS["dato_recordar"]
    if _ultima(respuestas, "dato_recordar") == OPCION_SI:
        paso = _paso_bloque_repetible(respuestas, "dato_recordar_detalle", "dato_recordar_detalle_continuar")
        if paso is not None:
            return paso

    # Bloque 7 — restricciones y preferencias (secuenciales, sin ramas)
    if not _respondida(respuestas, "restriccion_tecnica"):
        return PREGUNTAS["restriccion_tecnica"]
    if not _respondida(respuestas, "restriccion_tiempo_presupuesto"):
        return PREGUNTAS["restriccion_tiempo_presupuesto"]
    if not _respondida(respuestas, "restriccion_negocio"):
        return PREGUNTAS["restriccion_negocio"]

    # Cierre
    if not _respondida(respuestas, "cierre_libre"):
        return PREGUNTAS["cierre_libre"]

    return None
