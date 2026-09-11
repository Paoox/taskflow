"""Validación y (de)serialización de una respuesta contra su `DefinicionPregunta`.

Checkpoint de diseño, decisión cerrada: una respuesta de selección múltiple
se almacena en la columna `TEXT` de `respuestas_formulario` como **JSON
válido serializado** (p. ej. `["ver", "agregar"]`), nunca como texto
separado por comas. Sin cambios de esquema: la columna `respuesta` ya
acepta cualquier texto.

Funciones puras, sin persistencia: no importan `src.repositorios` ni
`src.database`. El llamador (fuera de este paquete) es quien persiste el
resultado de `serializar_respuesta()` vía `RepositorioRespuestasFormulario`.
"""
from __future__ import annotations

import json
from typing import Union

from src.expediente.modelo import TipoPregunta
from src.formulario.preguntas import DefinicionPregunta

__all__ = ["RespuestaInvalida", "validar_respuesta", "serializar_respuesta", "deserializar_respuesta"]

ValorRespuesta = Union[str, list]


class RespuestaInvalida(ValueError):
    """El valor no corresponde a lo que `pregunta` permite (tipo incorrecto,
    o una opción fuera de `pregunta.opciones`)."""


def validar_respuesta(pregunta: DefinicionPregunta, valor: ValorRespuesta) -> None:
    """Lanza `RespuestaInvalida` si `valor` no es válido para `pregunta`.
    No lanza nada si es válido. No interpreta el contenido: solo comprueba
    forma y, si es cerrada, pertenencia al conjunto de opciones permitidas.
    """
    if pregunta.tipo_pregunta == TipoPregunta.TEXTO_LIBRE:
        if not isinstance(valor, str):
            raise RespuestaInvalida(
                f"{pregunta.pregunta_id!r}: se esperaba texto (str), se recibió {type(valor).__name__}"
            )
        return

    # OPCION_CERRADA
    if pregunta.multiple:
        if not isinstance(valor, list) or not all(isinstance(v, str) for v in valor):
            raise RespuestaInvalida(
                f"{pregunta.pregunta_id!r}: se esperaba una lista de opciones (list[str])"
            )
        invalidas = [v for v in valor if v not in pregunta.opciones]
        if invalidas:
            raise RespuestaInvalida(
                f"{pregunta.pregunta_id!r}: opción(es) no permitida(s): {invalidas!r}"
            )
    else:
        if not isinstance(valor, str):
            raise RespuestaInvalida(
                f"{pregunta.pregunta_id!r}: se esperaba una única opción (str), "
                f"se recibió {type(valor).__name__}"
            )
        if valor not in pregunta.opciones:
            raise RespuestaInvalida(
                f"{pregunta.pregunta_id!r}: opción no permitida: {valor!r} "
                f"(permitidas: {pregunta.opciones!r})"
            )


def serializar_respuesta(pregunta: DefinicionPregunta, valor: ValorRespuesta) -> str:
    """Convierte `valor` (ya validado) a lo que se guarda en
    `respuestas_formulario.respuesta`: JSON si `pregunta.multiple`, el texto
    tal cual en cualquier otro caso."""
    validar_respuesta(pregunta, valor)
    if pregunta.multiple:
        return json.dumps(valor, ensure_ascii=False)
    return valor


def deserializar_respuesta(pregunta: DefinicionPregunta, texto: str) -> ValorRespuesta:
    """Inversa de `serializar_respuesta`: reconstruye `list[str]` para una
    pregunta múltiple, o devuelve `texto` tal cual en cualquier otro caso.
    Determinista: nunca interpreta el contenido, solo deserializa la forma."""
    if pregunta.multiple:
        return json.loads(texto)
    return texto
