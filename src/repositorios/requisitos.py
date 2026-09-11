"""Repositorio de `Requisito` (QUÉ debe cumplir el sistema) — tabla `requisitos`.

Mismo patrón que el resto de `src.repositorios`: una conexión por operación
por defecto (`conn=None`); los métodos de escritura aceptan un `conn`
opcional para participar en un `LoteDescubrimiento`.

Fuente de verdad exclusiva del modelo conceptual nuevo: no lee ni escribe
nada de `src.proyectos.estado`/`checklist` (el checklist raíz antiguo).
`naturaleza` acepta los 3 valores de `NaturalezaInformacion` sin
restricción adicional aquí: a diferencia de `Restriccion`/`FeaturePropuesta`,
un `Requisito` puede ser declarado, observado o deducido por igual — la
única garantía estructural es que el enum mismo no tiene un valor
"propuesto" (ver `src.expediente.modelo`).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.database import get_connection
from src.expediente.modelo import (
    EstadoRequisito, FuenteDirecta, NaturalezaInformacion, Requisito,
)
from src.proyectos.estado import NivelConfianza, OrigenDato

__all__ = ["RepositorioRequisitos"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_requisito(fila) -> Requisito:
    return Requisito(
        id=fila["id"],
        codigo=fila["codigo"],
        descripcion=fila["descripcion"],
        naturaleza=NaturalezaInformacion(fila["naturaleza"]),
        origen=OrigenDato(fila["origen"]),
        confianza=NivelConfianza(fila["confianza"]),
        estado=EstadoRequisito(fila["estado"]),
        accion_id_origen=fila["accion_id_origen"],
        fuente_directa=FuenteDirecta.from_json(fila["fuente_directa"]),
        creado_en=fila["creado_en"],
        actualizado_en=fila["actualizado_en"],
    )


class RepositorioRequisitos:
    """Acceso a la tabla `requisitos`. Una conexión por operación por defecto."""

    def crear(
        self,
        codigo: str,
        descripcion: str,
        naturaleza: NaturalezaInformacion,
        origen: OrigenDato,
        confianza: NivelConfianza,
        *,
        accion_id_origen: Optional[int] = None,
        fuente_directa: Optional[FuenteDirecta] = None,
        conn=None,
    ) -> Requisito:
        """Crea un `Requisito` en estado `ACTIVO` y lo devuelve."""
        conexion = conn or get_connection()
        ahora = _ahora()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """
                INSERT INTO requisitos
                    (codigo, descripcion, naturaleza, origen, confianza, estado,
                     accion_id_origen, fuente_directa, creado_en, actualizado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    codigo, descripcion, naturaleza.value, origen.value, confianza.value,
                    EstadoRequisito.ACTIVO.value, accion_id_origen,
                    fuente_directa.to_json() if fuente_directa else None,
                    ahora, ahora,
                ),
            )
            id_ = cursor.lastrowid
            if conn is None:
                conexion.commit()
            return Requisito(
                id=id_, codigo=codigo, descripcion=descripcion, naturaleza=naturaleza,
                origen=origen, confianza=confianza, estado=EstadoRequisito.ACTIVO,
                accion_id_origen=accion_id_origen, fuente_directa=fuente_directa,
                creado_en=ahora, actualizado_en=ahora,
            )
        finally:
            if conn is None:
                conexion.close()

    def obtener(self, requisito_id: int) -> Optional[Requisito]:
        conexion = get_connection()
        fila = conexion.execute(
            "SELECT * FROM requisitos WHERE id = ?", (requisito_id,)
        ).fetchone()
        conexion.close()
        return _fila_a_requisito(fila) if fila is not None else None

    def listar(self, codigo: str) -> list:
        conexion = get_connection()
        filas = conexion.execute(
            "SELECT * FROM requisitos WHERE codigo = ? ORDER BY id ASC", (codigo,)
        ).fetchall()
        conexion.close()
        return [_fila_a_requisito(f) for f in filas]

    def descartar(self, requisito_id: int, *, conn=None) -> bool:
        """Marca un `Requisito` como `DESCARTADO` (nunca se borra la fila).
        Devuelve `True` si el id existía."""
        conexion = conn or get_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                "UPDATE requisitos SET estado = ?, actualizado_en = ? WHERE id = ?",
                (EstadoRequisito.DESCARTADO.value, _ahora(), requisito_id),
            )
            afectadas = cursor.rowcount
            if conn is None:
                conexion.commit()
            return afectadas > 0
        finally:
            if conn is None:
                conexion.close()
