"""TF-0026 — Errores del dominio PROJECT_STATE.

Jerarquía única para los errores de `src.proyectos`. El resto del sistema
puede capturar `ErrorProyectos` (o dejarlo subir) sin conocer el detalle
interno. Todas las subclases heredan también de `ValueError` para que el
llamador pueda seguir capturando `ValueError` genérico si lo prefiere (mismo
criterio de tolerancia que ya usa `RepositorioAcciones.marcar`).

Sin dependencias externas. No importa Flask, `src.agentes`, `src.ai` ni red.
"""

__all__ = [
    "ErrorProyectos",
    "TransicionEstadoInvalida",
    "VersionChecklistNoEncontrada",
    "ExpedienteNoEncontrado",
]


class ErrorProyectos(Exception):
    """Base de todos los errores del dominio PROJECT_STATE."""


class TransicionEstadoInvalida(ErrorProyectos, ValueError):
    """Un cambio de `EstadoDato` viola una transición restringida.

    Ver `src.proyectos.estado.transicion_valida` / `TRANSICIONES_RESTRINGIDAS`.
    """


class VersionChecklistNoEncontrada(ErrorProyectos, ValueError):
    """No existe un checklist de coordinación registrado para la versión pedida."""


class ExpedienteNoEncontrado(ErrorProyectos, ValueError):
    """No existe ningún expediente con el `codigo` pedido.

    La lanzan `RepositorioExpedientes.guardar()` / `.guardar_salud()` cuando
    el `codigo` no corresponde a ninguna fila de `expedientes` — **antes** de
    escribir nada, para que el llamador no pueda confundir "no existía" con
    "se guardó correctamente" (a diferencia de `RepositorioAcciones.marcar`,
    aquí no basta un `bool`: llamar a `guardar()`/`guardar_salud()` sobre un
    `codigo` inexistente casi siempre es un error del llamador, no un caso de
    negocio válido a tolerar en silencio).
    """
