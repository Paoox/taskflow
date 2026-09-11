"""Repositorio de `RespuestaFormulario` — tabla `respuestas_formulario`.

Captura la pregunta+respuesta **cruda**, antes de que se interprete en
cualquier entidad del modelo (`Requisito`/`Dato`/...). El árbol de decisión
en sí es código (una función determinista, no datos) — lo único que se
persiste aquí es la instancia de ejecución: qué pregunta concreta se mostró
y qué respondió el usuario. `pregunta_id` es texto libre mantenido por el
código del árbol (sin catálogo todavía — decisión aprobada del checkpoint de
persistencia mínima).

Cada fila es el destino natural de un `FuenteDirecta(tipo="formulario",
referencia=<id de esta fila>)` en la entidad que se derive de ella.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.database import get_connection
from src.expediente.modelo import RespuestaFormulario, TipoPregunta

__all__ = ["RepositorioRespuestasFormulario"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_respuesta(fila) -> RespuestaFormulario:
    return RespuestaFormulario(
        id=fila["id"],
        codigo=fila["codigo"],
        pregunta_id=fila["pregunta_id"],
        pregunta_texto=fila["pregunta_texto"],
        tipo_pregunta=TipoPregunta(fila["tipo_pregunta"]),
        respuesta=fila["respuesta"],
        respondido_en=fila["respondido_en"],
        accion_id_origen=fila["accion_id_origen"],
    )


class RepositorioRespuestasFormulario:
    """Acceso a la tabla `respuestas_formulario`. Una conexión por operación
    por defecto."""

    def registrar(
        self,
        codigo: str,
        pregunta_id: str,
        pregunta_texto: str,
        tipo_pregunta: TipoPregunta,
        respuesta: str,
        *,
        accion_id_origen: Optional[int] = None,
        conn=None,
    ) -> RespuestaFormulario:
        conexion = conn or get_connection()
        ahora = _ahora()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """
                INSERT INTO respuestas_formulario
                    (codigo, pregunta_id, pregunta_texto, tipo_pregunta, respuesta,
                     respondido_en, accion_id_origen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    codigo, pregunta_id, pregunta_texto, tipo_pregunta.value,
                    respuesta, ahora, accion_id_origen,
                ),
            )
            id_ = cursor.lastrowid
            if conn is None:
                conexion.commit()
            return RespuestaFormulario(
                id=id_, codigo=codigo, pregunta_id=pregunta_id, pregunta_texto=pregunta_texto,
                tipo_pregunta=tipo_pregunta, respuesta=respuesta,
                respondido_en=ahora, accion_id_origen=accion_id_origen,
            )
        finally:
            if conn is None:
                conexion.close()

    def obtener(self, respuesta_id: int) -> Optional[RespuestaFormulario]:
        conexion = get_connection()
        fila = conexion.execute(
            "SELECT * FROM respuestas_formulario WHERE id = ?", (respuesta_id,)
        ).fetchone()
        conexion.close()
        return _fila_a_respuesta(fila) if fila is not None else None

    def listar(self, codigo: str) -> list:
        """Todas las respuestas de `codigo`, en el orden en que se
        respondieron."""
        conexion = get_connection()
        filas = conexion.execute(
            "SELECT * FROM respuestas_formulario WHERE codigo = ? ORDER BY id ASC",
            (codigo,),
        ).fetchall()
        conexion.close()
        return [_fila_a_respuesta(f) for f in filas]
