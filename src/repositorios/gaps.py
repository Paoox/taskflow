"""Repositorio de `Gap` — tabla `gaps`. Genérico (D2): referencia cualquier
tipo de entidad del modelo, nunca una tabla `GapRequisito`/`GapCapacidad`/...

`bloquea` se persiste como JSON (`[{"tipo": ..., "id": ...}, ...]`) —
decisión aprobada del checkpoint de persistencia mínima, en vez de una
tabla hija `gap_bloquea`.

`criticidad` es un campo de **lectura cacheada**: este repositorio solo la
almacena y la actualiza cuando se le pide (`actualizar_criticidad`) — el
cálculo determinista en sí (D5: alcanzabilidad en `relaciones` desde un
Requisito declarado) es responsabilidad del Orquestador Discovery, fuera de
alcance de este checkpoint de persistencia.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from src.database import get_connection
from src.expediente.modelo import EstadoGap, Gap

__all__ = ["RepositorioGaps"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_gap(fila) -> Gap:
    return Gap(
        id=fila["id"],
        codigo=fila["codigo"],
        entidad_afectada_tipo=fila["entidad_afectada_tipo"],
        entidad_afectada_id=fila["entidad_afectada_id"],
        campo_o_concepto=fila["campo_o_concepto"],
        motivo=fila["motivo"],
        bloquea=json.loads(fila["bloquea"]),
        criticidad=fila["criticidad"],
        estado=EstadoGap(fila["estado"]),
        creado_en=fila["creado_en"],
        resuelto_en=fila["resuelto_en"],
    )


class RepositorioGaps:
    """Acceso a la tabla `gaps`. Una conexión por operación por defecto."""

    def crear(
        self,
        codigo: str,
        entidad_afectada_tipo: str,
        campo_o_concepto: str,
        *,
        entidad_afectada_id: Optional[int] = None,
        motivo: Optional[str] = None,
        bloquea: Optional[list] = None,
        criticidad: Optional[str] = None,
        conn=None,
    ) -> Gap:
        bloquea = bloquea or []
        conexion = conn or get_connection()
        ahora = _ahora()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """
                INSERT INTO gaps
                    (codigo, entidad_afectada_tipo, entidad_afectada_id, campo_o_concepto,
                     motivo, bloquea, criticidad, estado, creado_en, resuelto_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, NULL)
                """,
                (
                    codigo, entidad_afectada_tipo, entidad_afectada_id, campo_o_concepto,
                    motivo, json.dumps(bloquea, ensure_ascii=False), criticidad,
                    EstadoGap.ABIERTO.value, ahora,
                ),
            )
            id_ = cursor.lastrowid
            if conn is None:
                conexion.commit()
            return Gap(
                id=id_, codigo=codigo, entidad_afectada_tipo=entidad_afectada_tipo,
                entidad_afectada_id=entidad_afectada_id, campo_o_concepto=campo_o_concepto,
                motivo=motivo, bloquea=bloquea, criticidad=criticidad,
                estado=EstadoGap.ABIERTO, creado_en=ahora, resuelto_en=None,
            )
        finally:
            if conn is None:
                conexion.close()

    def obtener(self, gap_id: int) -> Optional[Gap]:
        conexion = get_connection()
        fila = conexion.execute("SELECT * FROM gaps WHERE id = ?", (gap_id,)).fetchone()
        conexion.close()
        return _fila_a_gap(fila) if fila is not None else None

    def listar(self, codigo: str) -> list:
        conexion = get_connection()
        filas = conexion.execute(
            "SELECT * FROM gaps WHERE codigo = ? ORDER BY id ASC", (codigo,)
        ).fetchall()
        conexion.close()
        return [_fila_a_gap(f) for f in filas]

    def actualizar_criticidad(self, gap_id: int, criticidad: str, *, conn=None) -> bool:
        """Actualiza el valor cacheado. Nunca lo calcula — ver docstring del módulo."""
        conexion = conn or get_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                "UPDATE gaps SET criticidad = ? WHERE id = ?", (criticidad, gap_id),
            )
            afectadas = cursor.rowcount
            if conn is None:
                conexion.commit()
            return afectadas > 0
        finally:
            if conn is None:
                conexion.close()

    def marcar_estado(self, gap_id: int, estado: EstadoGap, *, conn=None) -> bool:
        conexion = conn or get_connection()
        try:
            cursor = conexion.cursor()
            resuelto_en = _ahora() if estado != EstadoGap.ABIERTO else None
            cursor.execute(
                "UPDATE gaps SET estado = ?, resuelto_en = ? WHERE id = ?",
                (estado.value, resuelto_en, gap_id),
            )
            afectadas = cursor.rowcount
            if conn is None:
                conexion.commit()
            return afectadas > 0
        finally:
            if conn is None:
                conexion.close()
