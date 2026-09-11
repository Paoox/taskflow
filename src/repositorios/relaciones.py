"""Repositorio de `Relacion` — tabla `relaciones`. Una sola tabla genérica de
aristas tipadas (`requiere`/`depende_de`/`opera_sobre`/`agrupa`), aprobada
como solución **definitiva** mientras no exista una necesidad real de
integridad referencial específica por tipo (checkpoint de persistencia
mínima) — no crea `requisito_requiere_capacidad`, `capacidad_depende_de`,
`capacidad_opera_sobre_dato` ni `funcionalidad_agrupa_requisito` por
separado.

Es el grafo completo sobre el que el futuro cálculo de criticidad (D5)
recorrerá alcanzabilidad — este repositorio solo lo persiste y lo consulta
con filtros simples; no implementa ningún algoritmo de recorrido (eso es
responsabilidad del Orquestador Discovery, fuera de alcance aquí).

`origen_tipo`/`destino_tipo` son texto libre corto ("requisito", "capacidad",
"funcionalidad", "dato") — sin FK posible hacia una tabla concreta porque el
destino puede ser de tipos distintos según `tipo` de relación (asociación
polimórfica; SQLite no la soporta con una FK real, y forzarla dividiendo la
tabla es justo lo que esta decisión evita).
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.database import get_connection
from src.expediente.modelo import Relacion, TipoRelacion

__all__ = ["RepositorioRelaciones"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_relacion(fila) -> Relacion:
    return Relacion(
        id=fila["id"],
        codigo=fila["codigo"],
        tipo=TipoRelacion(fila["tipo"]),
        origen_tipo=fila["origen_tipo"],
        origen_id=fila["origen_id"],
        destino_tipo=fila["destino_tipo"],
        destino_id=fila["destino_id"],
        creado_en=fila["creado_en"],
    )


class RepositorioRelaciones:
    """Acceso a la tabla `relaciones`. Una conexión por operación por defecto."""

    def crear(
        self,
        codigo: str,
        tipo: TipoRelacion,
        origen_tipo: str,
        origen_id: int,
        destino_tipo: str,
        destino_id: int,
        *,
        conn=None,
    ) -> Relacion:
        conexion = conn or get_connection()
        ahora = _ahora()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """
                INSERT INTO relaciones
                    (codigo, tipo, origen_tipo, origen_id, destino_tipo, destino_id, creado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (codigo, tipo.value, origen_tipo, origen_id, destino_tipo, destino_id, ahora),
            )
            id_ = cursor.lastrowid
            if conn is None:
                conexion.commit()
            return Relacion(
                id=id_, codigo=codigo, tipo=tipo, origen_tipo=origen_tipo,
                origen_id=origen_id, destino_tipo=destino_tipo, destino_id=destino_id,
                creado_en=ahora,
            )
        finally:
            if conn is None:
                conexion.close()

    def listar(
        self,
        codigo: str,
        *,
        tipo: Optional[TipoRelacion] = None,
        origen_tipo: Optional[str] = None,
        origen_id: Optional[int] = None,
    ) -> list:
        """Todas las relaciones de `codigo`, con filtros opcionales. Sin
        recorrido de grafo: cada llamada devuelve solo las aristas que
        coinciden directamente, en el mismo sentido que ya existe
        `RepositorioAcciones.listar(ticket=...)`."""
        condiciones = ["codigo = ?"]
        parametros: list = [codigo]
        if tipo is not None:
            condiciones.append("tipo = ?")
            parametros.append(tipo.value)
        if origen_tipo is not None:
            condiciones.append("origen_tipo = ?")
            parametros.append(origen_tipo)
        if origen_id is not None:
            condiciones.append("origen_id = ?")
            parametros.append(origen_id)

        conexion = get_connection()
        filas = conexion.execute(
            f"SELECT * FROM relaciones WHERE {' AND '.join(condiciones)} ORDER BY id ASC",
            parametros,
        ).fetchall()
        conexion.close()
        return [_fila_a_relacion(f) for f in filas]
