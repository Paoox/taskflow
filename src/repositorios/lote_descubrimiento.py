"""Lote atómico de escritura para una etapa del Orquestador Discovery.

Una etapa que genera varias entidades/relaciones relacionadas (p. ej. un
`Requisito` + sus `Capacidad` + las `relaciones` `requiere` entre ambos) debe
persistirse como una sola unidad: o se escribe todo, o no se escribe nada —
nunca un `Requisito` creado con sus `Capacidad`/relaciones a medias.

Los repositorios de `src.expediente` (`RepositorioRequisitos`, `Repositorio
Capacidades`, `RepositorioRelaciones`, ...) aceptan un parámetro `conn`
opcional en sus métodos de escritura: sin él (`conn=None`, el caso por
defecto), abren/comitean/cierran su propia conexión — mismo patrón "una
conexión por operación" que ya usa el resto de TaskFlow. Con un `conn`
externo, NO comitean ni cierran nada — delegan esa responsabilidad a quien
abrió la conexión, que es exactamente lo que este contexto hace.

Uso:

    with LoteDescubrimiento() as lote:
        req = repo_requisitos.crear(..., conn=lote.conexion)
        cap = repo_capacidades.crear(..., conn=lote.conexion)
        repo_relaciones.crear(..., conn=lote.conexion)
    # commit automático al salir sin excepción; rollback completo de TODO
    # el lote si cualquier escritura lanza.

No sustituye el patrón "una conexión por operación" del resto de TaskFlow
(CLAUDE.md §17/§30): es una unidad transaccional explícita, exclusiva para
el caso de un lote de escritura de una etapa de Discovery — el resto de
`src.repositorios` sigue funcionando exactamente igual que antes.

No depende de `sqlite3` directamente: reutiliza `src.database.get_connection()`
(mismo `PRAGMA foreign_keys = ON`, mismo `DATABASE_NAME`).
"""
from __future__ import annotations

from src.database import get_connection

__all__ = ["LoteDescubrimiento"]


class LoteDescubrimiento:
    """Contexto transaccional: una conexión, un commit o un rollback completo."""

    def __init__(self):
        self.conexion = None

    def __enter__(self) -> "LoteDescubrimiento":
        self.conexion = get_connection()
        return self

    def __exit__(self, exc_type, exc, tb) -> bool:
        if exc_type is None:
            self.conexion.commit()
        else:
            self.conexion.rollback()
        self.conexion.close()
        return False  # nunca silencia la excepción original
