"""Repositorio de `Contradiccion` — tabla `contradicciones`. Genérico (D2):
relación entre 2+ afirmaciones en conflicto, nunca un estado de una entidad
individual.

`afirmaciones` se persiste como JSON (`[{"valor": ..., "origen": ...,
"naturaleza": ...}, ...]`) — decisión aprobada del checkpoint de
persistencia mínima, en vez de una tabla hija `contradiccion_afirmaciones`.

Solo una persona resuelve una contradicción (`resolver()`, con
`resolucion_accion_id` apuntando a la acción que registró esa decisión) —
mismo criterio que `responder_pregunta()` en el modelo antiguo: el sistema
nunca elige por su cuenta cuál de las dos afirmaciones en conflicto es la
correcta.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from src.database import get_connection
from src.expediente.modelo import Contradiccion, EstadoContradiccion

__all__ = ["RepositorioContradicciones"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_contradiccion(fila) -> Contradiccion:
    return Contradiccion(
        id=fila["id"],
        codigo=fila["codigo"],
        entidad_tipo=fila["entidad_tipo"],
        concepto=fila["concepto"],
        afirmaciones=json.loads(fila["afirmaciones"]),
        estado=EstadoContradiccion(fila["estado"]),
        resolucion_valor=fila["resolucion_valor"],
        resolucion_accion_id=fila["resolucion_accion_id"],
        creado_en=fila["creado_en"],
        resuelto_en=fila["resuelto_en"],
    )


class RepositorioContradicciones:
    """Acceso a la tabla `contradicciones`. Una conexión por operación por defecto."""

    def crear(
        self,
        codigo: str,
        entidad_tipo: str,
        concepto: str,
        afirmaciones: list,
        *,
        conn=None,
    ) -> Contradiccion:
        if len(afirmaciones) < 2:
            raise ValueError(
                "una Contradiccion necesita al menos 2 afirmaciones en conflicto"
            )
        conexion = conn or get_connection()
        ahora = _ahora()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """
                INSERT INTO contradicciones
                    (codigo, entidad_tipo, concepto, afirmaciones, estado,
                     resolucion_valor, resolucion_accion_id, creado_en, resuelto_en)
                VALUES (?, ?, ?, ?, ?, NULL, NULL, ?, NULL)
                """,
                (
                    codigo, entidad_tipo, concepto,
                    json.dumps(afirmaciones, ensure_ascii=False),
                    EstadoContradiccion.ABIERTA.value, ahora,
                ),
            )
            id_ = cursor.lastrowid
            if conn is None:
                conexion.commit()
            return Contradiccion(
                id=id_, codigo=codigo, entidad_tipo=entidad_tipo, concepto=concepto,
                afirmaciones=afirmaciones, estado=EstadoContradiccion.ABIERTA,
                resolucion_valor=None, resolucion_accion_id=None,
                creado_en=ahora, resuelto_en=None,
            )
        finally:
            if conn is None:
                conexion.close()

    def obtener(self, contradiccion_id: int) -> Optional[Contradiccion]:
        conexion = get_connection()
        fila = conexion.execute(
            "SELECT * FROM contradicciones WHERE id = ?", (contradiccion_id,)
        ).fetchone()
        conexion.close()
        return _fila_a_contradiccion(fila) if fila is not None else None

    def listar(self, codigo: str) -> list:
        conexion = get_connection()
        filas = conexion.execute(
            "SELECT * FROM contradicciones WHERE codigo = ? ORDER BY id ASC", (codigo,)
        ).fetchall()
        conexion.close()
        return [_fila_a_contradiccion(f) for f in filas]

    def resolver(
        self, contradiccion_id: int, resolucion_valor: str, resolucion_accion_id: int,
        *, conn=None,
    ) -> bool:
        """Registra la resolución de una persona (nunca el sistema por su
        cuenta). Devuelve `True` si el id existía."""
        conexion = conn or get_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """
                UPDATE contradicciones
                   SET estado = ?, resolucion_valor = ?, resolucion_accion_id = ?, resuelto_en = ?
                 WHERE id = ?
                """,
                (
                    EstadoContradiccion.RESUELTA.value, resolucion_valor,
                    resolucion_accion_id, _ahora(), contradiccion_id,
                ),
            )
            afectadas = cursor.rowcount
            if conn is None:
                conexion.commit()
            return afectadas > 0
        finally:
            if conn is None:
                conexion.close()
