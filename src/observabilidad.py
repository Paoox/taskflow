"""TF-0020 — Observabilidad: logging central + ``correlation_id`` por petición.

Solo biblioteca estándar (``logging``, ``contextvars``, ``uuid``); sin
dependencias nuevas y sin importar nada del proyecto (no hay ciclos de import).

Piezas:

  * ``configurar_logging(nivel)`` — configura el logger central ``"taskflow"``
    de forma **idempotente**: fija el nivel siempre y añade handler y filtro solo
    si no están ya. No toca ``logging.root`` ni ``propagate``; no llama a
    ``basicConfig()``. Compatible con ``caplog`` de pytest (el filtro va en el
    logger, así los records propagados al root también llevan ``correlation_id``).
  * Helpers de correlación sobre un ``ContextVar`` con valor de **fallback
    estable** (``"-"``): fuera de una petición nunca lanzan.

En esta etapa el único consumidor es la app web (un id por petición HTTP). El
helper es reutilizable, pero aquí **no** se construye trazabilidad específica de
agentes.
"""
import contextvars
import logging
import uuid

# --- Constantes ----------------------------------------------------------------
_LOGGER_NAME = "taskflow"
_FORMATO = "%(asctime)s %(levelname)s %(name)s [%(correlation_id)s] %(message)s"
# Atributo centinela para reconocer nuestro handler / filtro y no duplicarlos.
_MARCA = "_taskflow_obs"
# Valor del correlation_id cuando no hay petición en curso.
_FALLBACK_CID = "-"
# Nombres de nivel aceptados; cualquier otro se resuelve a INFO.
_NIVELES = {"CRITICAL", "ERROR", "WARNING", "INFO", "DEBUG"}

_correlation_id = contextvars.ContextVar(
    "taskflow_correlation_id", default=_FALLBACK_CID
)


# --- correlation_id ----------------------------------------------------------
def get_correlation_id():
    """Devuelve el ``correlation_id`` del contexto actual.

    Fuera de una petición devuelve el fallback estable (``"-"``); nunca lanza.
    """
    return _correlation_id.get()


def set_correlation_id(valor=None):
    """Fija el ``correlation_id`` del contexto actual y devuelve su ``Token``.

    Sin argumento genera uno nuevo con ``uuid.uuid4().hex`` (32 hex, sin
    guiones). El ``Token`` devuelto es lo que ``reset_correlation_id`` necesita
    para restaurar el valor anterior.
    """
    return _correlation_id.set(valor or uuid.uuid4().hex)


def reset_correlation_id(token):
    """Restaura el ``correlation_id`` anterior a partir del ``Token`` de
    ``set_correlation_id``.

    Si ``token`` es ``None`` (la petición no llegó a asignar id) o el ``reset``
    falla (token ya usado / de otro contexto), cae al fallback estable sin
    propagar la excepción.
    """
    if token is None:
        _correlation_id.set(_FALLBACK_CID)
        return
    try:
        _correlation_id.reset(token)
    except (ValueError, LookupError, RuntimeError):
        _correlation_id.set(_FALLBACK_CID)


# --- logging ---------------------------------------------------------------
class _FiltroCorrelation(logging.Filter):
    """Inyecta ``record.correlation_id`` en cada registro.

    Se engancha al **logger** (no al handler): así ``Logger.handle`` lo ejecuta
    antes de propagar al root, y el atributo también está disponible para los
    handlers que instala ``caplog``.
    """

    def filter(self, record):
        record.correlation_id = get_correlation_id()
        return True


def _resolver_nivel(nombre):
    """Traduce un nombre de nivel a la constante de ``logging``.

    Un valor no reconocido (o ``None``) devuelve ``logging.INFO`` sin lanzar.
    """
    n = str(nombre).strip().upper()
    return getattr(logging, n) if n in _NIVELES else logging.INFO


def obtener_logger():
    """Devuelve el logger central de Taskflow (``logging.getLogger("taskflow")``)."""
    return logging.getLogger(_LOGGER_NAME)


def configurar_logging(nivel="INFO"):
    """Configura el logger central de forma idempotente y lo devuelve.

    * Fija el nivel en cada llamada (permite reflejar un cambio de
      ``TASKFLOW_LOG_LEVEL``).
    * Añade el filtro de ``correlation_id`` y un ``StreamHandler`` con formato
      consistente **solo si no están ya** (marca por atributo centinela), de modo
      que importar ``app`` varias veces o re-ejecutarlo con ``runpy`` no acumula
      handlers.
    * No toca ``logging.root`` ni ``logger.propagate`` (queda en ``True``): la
      captura de ``caplog`` sigue funcionando.
    """
    logger = logging.getLogger(_LOGGER_NAME)
    logger.setLevel(_resolver_nivel(nivel))
    if not any(getattr(f, _MARCA, False) for f in logger.filters):
        filtro = _FiltroCorrelation()
        setattr(filtro, _MARCA, True)
        logger.addFilter(filtro)
    if not any(getattr(h, _MARCA, False) for h in logger.handlers):
        handler = logging.StreamHandler()
        setattr(handler, _MARCA, True)
        handler.setFormatter(logging.Formatter(_FORMATO))
        logger.addHandler(handler)
    return logger
