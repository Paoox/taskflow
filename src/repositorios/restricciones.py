"""Repositorio de `Restriccion` (límite siempre declarado) — tabla
`restricciones`.

Validación propia (checkpoint de consolidación): una `Restriccion` solo
existe si alguien la declaró — nunca se deduce ni se propone. `crear()`
fuerza `naturaleza=DECLARADO` por defecto y rechaza con `NaturalezaInvalida`
cualquier otro valor explícito — es la garantía de código que reemplaza a
`stack_declarado` del modelo antiguo: ninguna preferencia tecnológica del
Orquestador puede colarse aquí como si el usuario la hubiera pedido.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.database import get_connection
from src.expediente.errores import NaturalezaInvalida
from src.expediente.modelo import FuenteDirecta, NaturalezaInformacion, Restriccion
from src.proyectos.estado import OrigenDato

__all__ = ["RepositorioRestricciones"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_restriccion(fila) -> Restriccion:
    return Restriccion(
        id=fila["id"],
        codigo=fila["codigo"],
        tipo=fila["tipo"],
        descripcion=fila["descripcion"],
        naturaleza=NaturalezaInformacion(fila["naturaleza"]),
        origen=OrigenDato(fila["origen"]),
        accion_id_origen=fila["accion_id_origen"],
        fuente_directa=FuenteDirecta.from_json(fila["fuente_directa"]),
        creado_en=fila["creado_en"],
    )


class RepositorioRestricciones:
    """Acceso a la tabla `restricciones`. Una conexión por operación por defecto."""

    def crear(
        self,
        codigo: str,
        tipo: str,
        descripcion: str,
        origen: OrigenDato,
        *,
        naturaleza: NaturalezaInformacion = NaturalezaInformacion.DECLARADO,
        accion_id_origen: Optional[int] = None,
        fuente_directa: Optional[FuenteDirecta] = None,
        conn=None,
    ) -> Restriccion:
        if naturaleza != NaturalezaInformacion.DECLARADO:
            raise NaturalezaInvalida(
                f"una Restriccion no puede tener naturaleza={naturaleza.value!r}; "
                f"por definición solo existe si alguien la declaró — nunca se "
                f"deduce ni se propone"
            )
        conexion = conn or get_connection()
        ahora = _ahora()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """
                INSERT INTO restricciones
                    (codigo, tipo, descripcion, naturaleza, origen,
                     accion_id_origen, fuente_directa, creado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    codigo, tipo, descripcion, naturaleza.value, origen.value,
                    accion_id_origen,
                    fuente_directa.to_json() if fuente_directa else None, ahora,
                ),
            )
            id_ = cursor.lastrowid
            if conn is None:
                conexion.commit()
            return Restriccion(
                id=id_, codigo=codigo, tipo=tipo, descripcion=descripcion,
                naturaleza=naturaleza, origen=origen,
                accion_id_origen=accion_id_origen, fuente_directa=fuente_directa,
                creado_en=ahora,
            )
        finally:
            if conn is None:
                conexion.close()

    def obtener(self, restriccion_id: int) -> Optional[Restriccion]:
        conexion = get_connection()
        fila = conexion.execute(
            "SELECT * FROM restricciones WHERE id = ?", (restriccion_id,)
        ).fetchone()
        conexion.close()
        return _fila_a_restriccion(fila) if fila is not None else None

    def listar(self, codigo: str) -> list:
        conexion = get_connection()
        filas = conexion.execute(
            "SELECT * FROM restricciones WHERE codigo = ? ORDER BY id ASC", (codigo,)
        ).fetchall()
        conexion.close()
        return [_fila_a_restriccion(f) for f in filas]
