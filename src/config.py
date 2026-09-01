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
# TF-0024 — runtime de IA (el único punto donde TaskFlow conoce el proveedor).
AI_PROVIDER_ENV = "TASKFLOW_AI_PROVIDER"
AI_BASE_URL_ENV = "TASKFLOW_AI_BASE_URL"
AI_MODEL_ENV = "TASKFLOW_AI_MODEL"
AI_TIMEOUT_ENV = "TASKFLOW_AI_TIMEOUT"
AI_API_KEY_ENV = "TASKFLOW_AI_API_KEY"
AI_MAX_RETRIES_ENV = "TASKFLOW_AI_MAX_RETRIES"

# --- Valores por defecto (idénticos a los previos a TF-0019) --------------
DB_POR_DEFECTO = "tareas.db"
HOST_POR_DEFECTO = "127.0.0.1"
PORT_POR_DEFECTO = 5000
LOG_LEVEL_POR_DEFECTO = "INFO"  # TF-0020
AI_PROVIDER_POR_DEFECTO = "eco"     # TF-0024 — doble determinista sin red
AI_TIMEOUT_POR_DEFECTO = 120.0      # TF-0024 — generación local puede ser lenta
AI_MAX_RETRIES_POR_DEFECTO = 0      # TF-0024 — Ollama local: fail fast, sin backoff

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


# --- Runtime de IA (TF-0024) ---------------------------------------------
# El único consumidor es la capa ``src.ai`` (factoría / adaptadores). El runner
# y los agentes no leen estas variables: reciben un ``ClienteIA`` ya construido.


def proveedor_ia():
    """Nombre del proveedor/runtime de IA (``TASKFLOW_AI_PROVIDER``; por defecto
    ``eco``). Normalizado con ``strip`` + minúsculas. Late binding.
    """
    return os.environ.get(AI_PROVIDER_ENV, AI_PROVIDER_POR_DEFECTO).strip().lower()


def ai_base_url():
    """URL base del proveedor de IA (``TASKFLOW_AI_BASE_URL``; ``""`` por
    defecto). No la usa ``eco``; a partir de TF-0025 el adaptador de red la
    consumirá (p. ej. ``http://localhost:11434`` para Ollama).
    """
    return os.environ.get(AI_BASE_URL_ENV, "").strip()


def ai_model():
    """Identificador del modelo (``TASKFLOW_AI_MODEL``; ``""`` por defecto).

    El modelo concreto es **configuración**, nunca se fija en el código.
    """
    return os.environ.get(AI_MODEL_ENV, "").strip()


def ai_timeout():
    """Timeout en segundos para llamadas al proveedor (``TASKFLOW_AI_TIMEOUT``;
    por defecto ``120``). Un valor no numérico lanza ``ValueError`` (igual que
    ``puerto()``).
    """
    return float(os.environ.get(AI_TIMEOUT_ENV, str(AI_TIMEOUT_POR_DEFECTO)))


def ai_api_key():
    """Clave del proveedor de IA (``TASKFLOW_AI_API_KEY``; ``None`` si no está
    definida). Slot reservado: ni ``eco`` ni Ollama local la usan.
    """
    return os.environ.get(AI_API_KEY_ENV)


def ai_max_retries():
    """Reintentos máximos ante fallo transitorio del proveedor
    (``TASKFLOW_AI_MAX_RETRIES``; por defecto ``0``). Con Ollama local se prefiere
    *fail fast*; sin backoff exponencial ni manejo de rate-limit. Un valor no
    numérico lanza ``ValueError``.
    """
    return int(os.environ.get(AI_MAX_RETRIES_ENV, str(AI_MAX_RETRIES_POR_DEFECTO)))
