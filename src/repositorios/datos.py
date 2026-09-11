"""Repositorio de `Dato` (información que el sistema maneja) — tabla `datos`.

Sin restricción de `naturaleza`: a diferencia de `Capacidad`, un `Dato` sí
puede ser declarado, observado o deducido por igual (checkpoint de
consolidación). No confundir con `src.proyectos.estado.Dato` (modelo
antiguo) — mismo nombre de dominio, módulos y tablas distintos, sin
relación.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.database import get_connection
from src.expediente.modelo import Dato, FuenteDirecta, NaturalezaInformacion
from src.proyectos.estado import NivelConfianza, OrigenDato

__all__ = ["RepositorioDatos"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_dato(fila) -> Dato:
    return Dato(
        id=fila["id"],
        codigo=fila["codigo"],
        descripcion=fila["descripcion"],
        temporalidad=fila["temporalidad"],
        sensibilidad=fila["sensibilidad"],
        naturaleza=NaturalezaInformacion(fila["naturaleza"]),
        origen=OrigenDato(fila["origen"]),
        confianza=NivelConfianza(fila["confianza"]),
        accion_id_origen=fila["accion_id_origen"],
        fuente_directa=FuenteDirecta.from_json(fila["fuente_directa"]),
        creado_en=fila["creado_en"],
    )


class RepositorioDatos:
    """Acceso a la tabla `datos`. Una conexión por operación por defecto."""

    def crear(
        self,
        codigo: str,
        descripcion: str,
        naturaleza: NaturalezaInformacion,
        origen: OrigenDato,
        confianza: NivelConfianza,
        *,
        temporalidad: Optional[str] = None,
        sensibilidad: Optional[str] = None,
        accion_id_origen: Optional[int] = None,
        fuente_directa: Optional[FuenteDirecta] = None,
        conn=None,
    ) -> Dato:
        conexion = conn or get_connection()
        ahora = _ahora()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """
                INSERT INTO datos
                    (codigo, descripcion, temporalidad, sensibilidad, naturaleza,
                     origen, confianza, accion_id_origen, fuente_directa, creado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    codigo, descripcion, temporalidad, sensibilidad, naturaleza.value,
                    origen.value, confianza.value, accion_id_origen,
                    fuente_directa.to_json() if fuente_directa else None, ahora,
                ),
            )
            id_ = cursor.lastrowid
            if conn is None:
                conexion.commit()
            return Dato(
                id=id_, codigo=codigo, descripcion=descripcion,
                temporalidad=temporalidad, sensibilidad=sensibilidad,
                naturaleza=naturaleza, origen=origen, confianza=confianza,
                accion_id_origen=accion_id_origen, fuente_directa=fuente_directa,
                creado_en=ahora,
            )
        finally:
            if conn is None:
                conexion.close()

    def obtener(self, dato_id: int) -> Optional[Dato]:
        conexion = get_connection()
        fila = conexion.execute(
            "SELECT * FROM datos WHERE id = ?", (dato_id,)
        ).fetchone()
        conexion.close()
        return _fila_a_dato(fila) if fila is not None else None

    def listar(self, codigo: str) -> list:
        conexion = get_connection()
        filas = conexion.execute(
            "SELECT * FROM datos WHERE codigo = ? ORDER BY id ASC", (codigo,)
        ).fetchall()
        conexion.close()
        return [_fila_a_dato(f) for f in filas]
