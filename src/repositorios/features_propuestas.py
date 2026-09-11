"""Repositorio de `FeaturePropuesta` — tabla `features_propuestas`.

Validación propia (checkpoint de consolidación): una propuesta es siempre
iniciativa del sistema. `crear()` fuerza `origen=AGENT` por defecto y
rechaza con `OrigenInvalido` cualquier otro valor explícito — si el usuario
pidió algo directamente, es un `Requisito`, nunca una `FeaturePropuesta`.

Tabla completamente distinta de `requisitos`, sin FK entre ambas:
`campo_relacionado_id` es puramente informativo (contexto de por qué se
propuso), nunca una dependencia real. Promover una propuesta a requisito
confirmado es una operación explícita de otro repositorio
(`RepositorioRequisitos.crear`, con `origen=USER`) — este repositorio no la
implementa: no existe ningún camino de escritura que mueva una fila de aquí
a `requisitos` automáticamente.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.database import get_connection
from src.expediente.errores import OrigenInvalido
from src.expediente.modelo import EstadoFeaturePropuesta, FeaturePropuesta
from src.proyectos.estado import NivelConfianza, OrigenDato

__all__ = ["RepositorioFeaturesPropuestas"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_feature(fila) -> FeaturePropuesta:
    return FeaturePropuesta(
        id=fila["id"],
        codigo=fila["codigo"],
        descripcion=fila["descripcion"],
        motivo=fila["motivo"],
        origen=OrigenDato(fila["origen"]),
        confianza=NivelConfianza(fila["confianza"]),
        impacto=fila["impacto"],
        estado=EstadoFeaturePropuesta(fila["estado"]),
        campo_relacionado_tipo=fila["campo_relacionado_tipo"],
        campo_relacionado_id=fila["campo_relacionado_id"],
        accion_id_origen=fila["accion_id_origen"],
        creado_en=fila["creado_en"],
        actualizado_en=fila["actualizado_en"],
    )


class RepositorioFeaturesPropuestas:
    """Acceso a la tabla `features_propuestas`. Una conexión por operación por defecto."""

    def crear(
        self,
        codigo: str,
        descripcion: str,
        motivo: str,
        confianza: NivelConfianza,
        *,
        origen: OrigenDato = OrigenDato.AGENT,
        impacto: Optional[str] = None,
        campo_relacionado_tipo: Optional[str] = None,
        campo_relacionado_id: Optional[int] = None,
        accion_id_origen: Optional[int] = None,
        conn=None,
    ) -> FeaturePropuesta:
        if origen != OrigenDato.AGENT:
            raise OrigenInvalido(
                f"una FeaturePropuesta no puede tener origen={origen.value!r}; "
                f"por definición es iniciativa del sistema — si el usuario la "
                f"pidió directamente, es un Requisito, no una propuesta"
            )
        conexion = conn or get_connection()
        ahora = _ahora()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                """
                INSERT INTO features_propuestas
                    (codigo, descripcion, motivo, origen, confianza, impacto, estado,
                     campo_relacionado_tipo, campo_relacionado_id, accion_id_origen,
                     creado_en, actualizado_en)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    codigo, descripcion, motivo, origen.value, confianza.value, impacto,
                    EstadoFeaturePropuesta.PROPUESTA.value,
                    campo_relacionado_tipo, campo_relacionado_id, accion_id_origen,
                    ahora, ahora,
                ),
            )
            id_ = cursor.lastrowid
            if conn is None:
                conexion.commit()
            return FeaturePropuesta(
                id=id_, codigo=codigo, descripcion=descripcion, motivo=motivo,
                origen=origen, confianza=confianza, impacto=impacto,
                estado=EstadoFeaturePropuesta.PROPUESTA,
                campo_relacionado_tipo=campo_relacionado_tipo,
                campo_relacionado_id=campo_relacionado_id,
                accion_id_origen=accion_id_origen, creado_en=ahora, actualizado_en=ahora,
            )
        finally:
            if conn is None:
                conexion.close()

    def obtener(self, feature_id: int) -> Optional[FeaturePropuesta]:
        conexion = get_connection()
        fila = conexion.execute(
            "SELECT * FROM features_propuestas WHERE id = ?", (feature_id,)
        ).fetchone()
        conexion.close()
        return _fila_a_feature(fila) if fila is not None else None

    def listar(self, codigo: str) -> list:
        conexion = get_connection()
        filas = conexion.execute(
            "SELECT * FROM features_propuestas WHERE codigo = ? ORDER BY id ASC", (codigo,)
        ).fetchall()
        conexion.close()
        return [_fila_a_feature(f) for f in filas]

    def marcar_estado(self, feature_id: int, estado: EstadoFeaturePropuesta, *, conn=None) -> bool:
        """Cambia `estado` (propuesta/aceptada/rechazada). Devuelve `True` si
        el id existía. NUNCA mueve la fila a `requisitos` — esa es una
        operación distinta, deliberadamente fuera de este repositorio."""
        conexion = conn or get_connection()
        try:
            cursor = conexion.cursor()
            cursor.execute(
                "UPDATE features_propuestas SET estado = ?, actualizado_en = ? WHERE id = ?",
                (estado.value, _ahora(), feature_id),
            )
            afectadas = cursor.rowcount
            if conn is None:
                conexion.commit()
            return afectadas > 0
        finally:
            if conn is None:
                conexion.close()
