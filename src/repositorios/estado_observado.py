"""Repositorio de `EstadoObservado` — tabla `estado_observado_versiones`
(D3). Append-only: esta clase no expone ninguna operación de actualización
ni borrado sobre una versión ya registrada — mismo criterio que
`RepositorioBriefs`.

Evidencia técnica de un repositorio existente (Escenario B), siempre
separada de `requisitos` (lo deseado) — ninguna escritura de este
repositorio toca ninguna otra tabla del modelo. La comparación entre ambos
mundos (qué requisito ya está implementado) es responsabilidad del
Orquestador Discovery, fuera de alcance de este checkpoint de persistencia.

`version` se asigna de forma determinista (siguiente entero libre para ese
`codigo`) — mismo patrón exacto que `ronda` en `RepositorioBriefs`.
"""
from __future__ import annotations

import json
from datetime import datetime
from typing import Optional

from src.database import get_connection
from src.expediente.modelo import EstadoObservado

__all__ = ["RepositorioEstadoObservado"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_estado(fila) -> EstadoObservado:
    return EstadoObservado(
        id=fila["id"],
        codigo=fila["codigo"],
        version=fila["version"],
        capturado_en=fila["capturado_en"],
        tecnologias_detectadas=json.loads(fila["tecnologias_detectadas"] or "[]"),
        funcionalidades_detectadas=json.loads(fila["funcionalidades_detectadas"] or "[]"),
        aparenta_funcionar=fila["aparenta_funcionar"],
        accion_id_origen=fila["accion_id_origen"],
    )


class RepositorioEstadoObservado:
    """Acceso a la tabla `estado_observado_versiones`. Append-only."""

    def registrar(
        self,
        codigo: str,
        *,
        tecnologias_detectadas: Optional[list] = None,
        funcionalidades_detectadas: Optional[list] = None,
        aparenta_funcionar: Optional[str] = None,
        accion_id_origen: Optional[int] = None,
        conn=None,
    ) -> EstadoObservado:
        """Registra una nueva versión de evidencia para `codigo` y la
        devuelve. `version` la asigna este método (siguiente entero libre
        para `codigo`; nunca el llamador)."""
        tecnologias_detectadas = tecnologias_detectadas or []
        funcionalidades_detectadas = funcionalidades_detectadas or []
        conexion = conn or get_connection()
        try:
            cursor = conexion.cursor()
            fila_max = cursor.execute(
                "SELECT MAX(version) AS maxv FROM estado_observado_versiones WHERE codigo = ?",
                (codigo,),
            ).fetchone()
            version = (fila_max["maxv"] or 0) + 1
            ahora = _ahora()
            cursor.execute(
                """
                INSERT INTO estado_observado_versiones
                    (codigo, version, capturado_en, tecnologias_detectadas,
                     funcionalidades_detectadas, aparenta_funcionar, accion_id_origen)
                VALUES (?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    codigo, version, ahora,
                    json.dumps(tecnologias_detectadas, ensure_ascii=False),
                    json.dumps(funcionalidades_detectadas, ensure_ascii=False),
                    aparenta_funcionar, accion_id_origen,
                ),
            )
            id_ = cursor.lastrowid
            if conn is None:
                conexion.commit()
            return EstadoObservado(
                id=id_, codigo=codigo, version=version, capturado_en=ahora,
                tecnologias_detectadas=tecnologias_detectadas,
                funcionalidades_detectadas=funcionalidades_detectadas,
                aparenta_funcionar=aparenta_funcionar, accion_id_origen=accion_id_origen,
            )
        finally:
            if conn is None:
                conexion.close()

    def listar(self, codigo: str) -> list:
        """Todas las versiones de `codigo`, ordenadas por versión ascendente."""
        conexion = get_connection()
        filas = conexion.execute(
            "SELECT * FROM estado_observado_versiones WHERE codigo = ? ORDER BY version ASC",
            (codigo,),
        ).fetchall()
        conexion.close()
        return [_fila_a_estado(f) for f in filas]

    def ultima_version(self, codigo: str) -> Optional[EstadoObservado]:
        """La versión más reciente de `codigo`, o `None` si no hay ninguna —
        es contra esta versión que cualquier comparación futura debe
        calcularse (D3)."""
        conexion = get_connection()
        fila = conexion.execute(
            """
            SELECT * FROM estado_observado_versiones
             WHERE codigo = ? ORDER BY version DESC LIMIT 1
            """,
            (codigo,),
        ).fetchone()
        conexion.close()
        return _fila_a_estado(fila) if fila is not None else None
