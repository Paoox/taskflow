"""Repositorio de `Perfil` — tabla `perfiles`.

Quién usa el sistema, funcionalmente (D1 — no confundir con rol/permisos,
que queda fuera de este primer corte). Mismo patrón que el resto de
`src.repositorios`: una conexión por operación por defecto; los métodos de
escritura aceptan un `conn` opcional para participar en un
`LoteDescubrimiento` (ver ese módulo).

Fuente de verdad exclusiva del modelo conceptual nuevo: no importa nada de
`src.proyectos.estado`/`checklist` salvo el vocabulario puro `OrigenDato`/
`NivelConfianza` (ver `src.expediente.modelo`).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.database import get_connection
from src.expediente.modelo import FuenteDirecta, NaturalezaInformacion, Perfil
from src.proyectos.estado import NivelConfianza, OrigenDato

__all__ = ["RepositorioPerfiles"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_perfil(fila) -> Perfil:
    return Perfil(
        id=fila["id"],
        codigo=fila["codigo"],
        nombre=fila["nombre"],
        descripcion=fila["descripcion"],
        naturaleza=NaturalezaInformacion(fila["naturaleza"]),
        origen=OrigenDato(fila["origen"]),
        confianza=NivelConfianza(fila["confianza"]),
        accion_id_origen=fila["accion_id_origen"],
        fuente_directa=FuenteDirecta.from_json(fila["fuente_directa"]),
        creado_en=fila["creado_en"],
    )


class RepositorioPerfiles:
    """Acceso a la tabla `perfiles`. Una conexión por operación por defecto."""

    def crear(
        self,
        codigo: str,
        nombre: str,
        descripcion: str,
        naturaleza: NaturalezaInformacion,
        origen: OrigenDato,
        confianza: NivelConfianza,
        *,
        accion_id_origen: Optional[int] = None,
        fuente_directa: Optional[FuenteDirecta] = None,
        conn=None,
    ) -> Perfil:
        conexion = conn or get_connection()
        ahora = _ahora()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """
                INSERT INTO perfiles
                    (codigo, nombre, descripcion, naturaleza, origen, confianza,
                     accion_id_origen, fuente_directa, creado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    codigo, nombre, descripcion, naturaleza.value, origen.value,
                    confianza.value, accion_id_origen,
                    fuente_directa.to_json() if fuente_directa else None, ahora,
                ),
            )
            id_ = cursor.lastrowid
            if conn is None:
                conexion.commit()
            return Perfil(
                id=id_, codigo=codigo, nombre=nombre, descripcion=descripcion,
                naturaleza=naturaleza, origen=origen, confianza=confianza,
                accion_id_origen=accion_id_origen, fuente_directa=fuente_directa,
                creado_en=ahora,
            )
        finally:
            if conn is None:
                conexion.close()

    def obtener(self, perfil_id: int) -> Optional[Perfil]:
        conexion = get_connection()
        fila = conexion.execute(
            "SELECT * FROM perfiles WHERE id = ?", (perfil_id,)
        ).fetchone()
        conexion.close()
        return _fila_a_perfil(fila) if fila is not None else None

    def listar(self, codigo: str) -> list:
        conexion = get_connection()
        filas = conexion.execute(
            "SELECT * FROM perfiles WHERE codigo = ? ORDER BY id ASC", (codigo,)
        ).fetchall()
        conexion.close()
        return [_fila_a_perfil(f) for f in filas]
