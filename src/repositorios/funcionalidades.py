"""Repositorio de `Funcionalidad` (agrupación organizativa de Requisitos) —
tabla `funcionalidades`.

Sin `naturaleza`/`origen`/`confianza`: una Funcionalidad no es un hecho
clasificable, es un agrupador — su "estado epistémico" se deriva siempre de
sus Requisitos (vía `relaciones`, tipo `AGRUPA`), nunca se declara aparte
(checkpoint de consolidación: evitar una fuente de verdad paralela).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.database import get_connection
from src.expediente.modelo import Funcionalidad

__all__ = ["RepositorioFuncionalidades"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_funcionalidad(fila) -> Funcionalidad:
    return Funcionalidad(
        id=fila["id"],
        codigo=fila["codigo"],
        nombre=fila["nombre"],
        descripcion=fila["descripcion"],
        tier=fila["tier"],
        creado_en=fila["creado_en"],
    )


class RepositorioFuncionalidades:
    """Acceso a la tabla `funcionalidades`. Una conexión por operación por defecto."""

    def crear(
        self,
        codigo: str,
        nombre: str,
        descripcion: str = "",
        *,
        tier: Optional[str] = None,
        conn=None,
    ) -> Funcionalidad:
        conexion = conn or get_connection()
        ahora = _ahora()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """
                INSERT INTO funcionalidades (codigo, nombre, descripcion, tier, creado_en)
                VALUES (?, ?, ?, ?, ?)
                """,
                (codigo, nombre, descripcion, tier, ahora),
            )
            id_ = cursor.lastrowid
            if conn is None:
                conexion.commit()
            return Funcionalidad(
                id=id_, codigo=codigo, nombre=nombre, descripcion=descripcion,
                tier=tier, creado_en=ahora,
            )
        finally:
            if conn is None:
                conexion.close()

    def obtener(self, funcionalidad_id: int) -> Optional[Funcionalidad]:
        conexion = get_connection()
        fila = conexion.execute(
            "SELECT * FROM funcionalidades WHERE id = ?", (funcionalidad_id,)
        ).fetchone()
        conexion.close()
        return _fila_a_funcionalidad(fila) if fila is not None else None

    def listar(self, codigo: str) -> list:
        conexion = get_connection()
        filas = conexion.execute(
            "SELECT * FROM funcionalidades WHERE codigo = ? ORDER BY id ASC", (codigo,)
        ).fetchall()
        conexion.close()
        return [_fila_a_funcionalidad(f) for f in filas]
