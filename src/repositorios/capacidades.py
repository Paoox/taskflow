"""Repositorio de `Capacidad` (QUÉ HABILIDAD necesita el sistema) — tabla
`capacidades`.

Mismo patrón que el resto de `src.repositorios`: una conexión por operación
por defecto; los métodos de escritura aceptan un `conn` opcional para
participar en un `LoteDescubrimiento`.

Validación propia (checkpoint de consolidación): una `Capacidad` nunca es
"observada" directamente — se deduce de uno o más `Requisito`, o, en raras
ocasiones, el usuario la nombra directamente (`DECLARADO`). Si algo se
observó en un repositorio, la evidencia es un `Dato` o un `Requisito`, no
una `Capacidad` en sí misma. `crear()` rechaza `naturaleza=OBSERVADO` con
`NaturalezaInvalida` — no es solo una regla de prompt, es una validación de
código, mismo criterio que ya usa `fusion.py` para sanear `origen`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.database import get_connection
from src.expediente.errores import NaturalezaInvalida
from src.expediente.modelo import Capacidad, FuenteDirecta, NaturalezaInformacion
from src.proyectos.estado import NivelConfianza, OrigenDato

__all__ = ["RepositorioCapacidades"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"
_NATURALEZAS_PERMITIDAS = (NaturalezaInformacion.DECLARADO, NaturalezaInformacion.DEDUCIDO)


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_capacidad(fila) -> Capacidad:
    return Capacidad(
        id=fila["id"],
        codigo=fila["codigo"],
        descripcion=fila["descripcion"],
        tipo=fila["tipo"],
        naturaleza=NaturalezaInformacion(fila["naturaleza"]),
        origen=OrigenDato(fila["origen"]),
        confianza=NivelConfianza(fila["confianza"]),
        accion_id_origen=fila["accion_id_origen"],
        fuente_directa=FuenteDirecta.from_json(fila["fuente_directa"]),
        creado_en=fila["creado_en"],
    )


class RepositorioCapacidades:
    """Acceso a la tabla `capacidades`. Una conexión por operación por defecto."""

    def crear(
        self,
        codigo: str,
        descripcion: str,
        tipo: str,
        naturaleza: NaturalezaInformacion,
        origen: OrigenDato,
        confianza: NivelConfianza,
        *,
        accion_id_origen: Optional[int] = None,
        fuente_directa: Optional[FuenteDirecta] = None,
        conn=None,
    ) -> Capacidad:
        if naturaleza not in _NATURALEZAS_PERMITIDAS:
            raise NaturalezaInvalida(
                f"una Capacidad no puede tener naturaleza={naturaleza.value!r}; "
                f"debe ser 'declarado' o 'deducido' (una habilidad nunca es "
                f"'observada' directamente — la evidencia observada vive en "
                f"un Dato o un Requisito)"
            )
        conexion = conn or get_connection()
        ahora = _ahora()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """
                INSERT INTO capacidades
                    (codigo, descripcion, tipo, naturaleza, origen, confianza,
                     accion_id_origen, fuente_directa, creado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    codigo, descripcion, tipo, naturaleza.value, origen.value,
                    confianza.value, accion_id_origen,
                    fuente_directa.to_json() if fuente_directa else None, ahora,
                ),
            )
            id_ = cursor.lastrowid
            if conn is None:
                conexion.commit()
            return Capacidad(
                id=id_, codigo=codigo, descripcion=descripcion, tipo=tipo,
                naturaleza=naturaleza, origen=origen, confianza=confianza,
                accion_id_origen=accion_id_origen, fuente_directa=fuente_directa,
                creado_en=ahora,
            )
        finally:
            if conn is None:
                conexion.close()

    def obtener(self, capacidad_id: int) -> Optional[Capacidad]:
        conexion = get_connection()
        fila = conexion.execute(
            "SELECT * FROM capacidades WHERE id = ?", (capacidad_id,)
        ).fetchone()
        conexion.close()
        return _fila_a_capacidad(fila) if fila is not None else None

    def listar(self, codigo: str) -> list:
        conexion = get_connection()
        filas = conexion.execute(
            "SELECT * FROM capacidades WHERE codigo = ? ORDER BY id ASC", (codigo,)
        ).fetchall()
        conexion.close()
        return [_fila_a_capacidad(f) for f in filas]
