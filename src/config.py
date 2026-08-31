"""TF-0019 — Configuración central de Taskflow.

Punto único de lectura y parseo de las variables de entorno ``TASKFLOW_*``.

Los accessors leen ``os.environ`` en CADA llamada (**late binding**): así siguen
funcionando el aislamiento de la suite (``conftest.py`` fija ``TASKFLOW_DB``
antes de importar ``src.database``) y los ``monkeypatch`` de ``os.environ`` en
tiempo de ejecución. No se cachea ningún snapshot en import.

Sin dependencias externas. Cuando en el futuro se añadan variables nuevas, su
nombre, su valor por defecto y su parseo se declaran aquí y en ningún otro sitio.
"""
import os

# --- Nombres de las variables de entorno (única fuente) --------------------
DB_ENV = "TASKFLOW_DB"
SECRET_KEY_ENV = "TASKFLOW_SECRET_KEY"
ENTORNO_ENV = "TASKFLOW_ENV"
COOKIE_SECURE_ENV = "TASKFLOW_COOKIE_SECURE"
HOST_ENV = "TASKFLOW_HOST"
PORT_ENV = "TASKFLOW_PORT"
DEBUG_ENV = "TASKFLOW_DEBUG"
LOG_LEVEL_ENV = "TASKFLOW_LOG_LEVEL"

# --- Valores por defecto (idénticos a los previos a TF-0019) --------------
DB_POR_DEFECTO = "tareas.db"
HOST_POR_DEFECTO = "127.0.0.1"
PORT_POR_DEFECTO = 5000
LOG_LEVEL_POR_DEFECTO = "INFO"  # TF-0020

# Valores que activan un flag booleano (con ``strip`` y en minúsculas).
_VALORES_ACTIVOS = ("1", "true", "yes", "on")


def flag_activado(nombre):
    """True si la variable de entorno ``nombre`` tiene un valor de activación
    explícito (``1`` / ``true`` / ``yes`` / ``on``, con ``strip`` y
    case-insensitive). Cualquier otro valor —incluido ``0``, vacío o ausente—
    devuelve False.
    """
    return os.environ.get(nombre, "").strip().lower() in _VALORES_ACTIVOS


def ruta_db():
    """Ruta del archivo SQLite (``TASKFLOW_DB``; por defecto ``tareas.db``)."""
    return os.environ.get(DB_ENV, DB_POR_DEFECTO)


def secret_key():
    """Valor crudo de ``TASKFLOW_SECRET_KEY`` (``None`` si no está definida)."""
    return os.environ.get(SECRET_KEY_ENV)


def entorno():
    """Valor normalizado de ``TASKFLOW_ENV`` (``strip`` + minúsculas; ``""`` por
    defecto).
    """
    return os.environ.get(ENTORNO_ENV, "").strip().lower()


def cookie_secure():
    """True si ``TASKFLOW_COOKIE_SECURE`` está activada."""
    return flag_activado(COOKIE_SECURE_ENV)


def host():
    """Interfaz de escucha del arranque local (``TASKFLOW_HOST``; por defecto
    ``127.0.0.1``).
    """
    return os.environ.get(HOST_ENV, HOST_POR_DEFECTO)


def puerto():
    """Puerto de escucha del arranque local (``TASKFLOW_PORT``; por defecto
    ``5000``).

    Mantiene la conversión a ``int``: un valor no numérico lanza ``ValueError``,
    igual que antes de TF-0019.
    """
    return int(os.environ.get(PORT_ENV, str(PORT_POR_DEFECTO)))


def debug_activado():
    """True si ``TASKFLOW_DEBUG`` tiene un valor de activación explícito.

    El parseo es el de ``flag_activado``; esta función es solo el accessor con
    nombre de la variable ``TASKFLOW_DEBUG``.
    """
    return flag_activado(DEBUG_ENV)


def nivel_log():
    """Nombre del nivel de logging (``TASKFLOW_LOG_LEVEL``; por defecto ``INFO``).

    Devuelve el valor con ``strip`` y en mayúsculas, **sin validar**: traducirlo a
    un nivel de ``logging`` y decidir el fallback a ``INFO`` ante un valor no
    reconocido es responsabilidad de ``src.observabilidad`` (TF-0020). Late
    binding: lee ``os.environ`` en cada llamada, sin cachear.
    """
    return os.environ.get(LOG_LEVEL_ENV, LOG_LEVEL_POR_DEFECTO).strip().upper()
