"""TF-0024 — Errores del runtime de IA.

Jerarquía única para el límite entre TaskFlow y cualquier proveedor/runtime de
modelo. El resto del sistema captura `ErrorIA` (o lo deja subir) sin conocer el
proveedor concreto.

Los mensajes deben quedar **saneados**: nunca incluyen valores de `os.environ`,
claves (`TASKFLOW_AI_API_KEY`) ni cuerpos completos de petición/respuesta.

Sin dependencias externas. No importa Flask, `src.agentes`, `src.config` ni red.
"""

__all__ = [
    "ErrorIA",
    "ErrorConfiguracionIA",
    "ErrorProveedorNoDisponible",
    "ErrorRespuestaIA",
]


class ErrorIA(Exception):
    """Base de todos los errores del runtime de IA."""


class ErrorConfiguracionIA(ErrorIA):
    """Configuración inválida del runtime: proveedor no registrado, nombre
    duplicado, valor de `TASKFLOW_AI_*` inaceptable.
    """


class ErrorProveedorNoDisponible(ErrorIA):
    """El proveedor/runtime no responde o es inalcanzable.

    Lo lanzarán los adaptadores de red a partir de TF-0025; aquí solo se define
    el tipo para que el resto del sistema pueda capturarlo desde ya.
    """


class ErrorRespuestaIA(ErrorIA):
    """La respuesta del proveedor es ilegible, incompleta o quedó truncada por el
    límite de tokens.

    Lo lanzarán los adaptadores de red a partir de TF-0025 (decisión DA-3:
    truncado -> error tipado -> ejecución FALLIDA, sin cambiar `RespuestaIA`).
    """
