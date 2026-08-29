"""TF-0008 — Lógica de seguridad aislada.

Protección CSRF manual basada en la biblioteca estándar: un token aleatorio por
sesión que se compara en tiempo constante con el valor enviado en el formulario.
Sin dependencias externas.

TF-0012 — endurecimiento de la sesión:
  * ``obtener_secret_key()`` falla en producción si falta ``TASKFLOW_SECRET_KEY``.
  * ``cookie_secure_activada()`` controla ``SESSION_COOKIE_SECURE``.
"""
import hmac
import os
import secrets

SECRET_KEY_ENV = "TASKFLOW_SECRET_KEY"
ENV_VAR = "TASKFLOW_ENV"
COOKIE_SECURE_ENV = "TASKFLOW_COOKIE_SECURE"
CSRF_TOKEN_BYTES = 32

_VERDADEROS = ("1", "true", "yes", "on")


def generar_token():
    """Devuelve un token CSRF nuevo, url-safe y criptográficamente aleatorio."""
    return secrets.token_urlsafe(CSRF_TOKEN_BYTES)


def token_valido(enviado, esperado):
    """Compara el token enviado con el esperado en tiempo constante.

    Devuelve ``False`` si el esperado está vacío o si no coinciden.
    """
    if not esperado or not enviado:
        return False
    return hmac.compare_digest(str(enviado), str(esperado))


def es_produccion():
    """True si ``TASKFLOW_ENV`` vale exactamente ``production``."""
    return os.environ.get(ENV_VAR, "").strip().lower() == "production"


def cookie_secure_activada():
    """True si ``TASKFLOW_COOKIE_SECURE`` está activada.

    Por defecto ``False`` (desarrollo local sobre HTTP). En despliegue tras TLS
    debe ponerse a ``1`` para que la cookie de sesión lleve el atributo Secure.
    """
    return os.environ.get(COOKIE_SECURE_ENV, "").strip().lower() in _VERDADEROS


def obtener_secret_key(logger=None):
    """Resuelve la clave de firma de sesión.

    - Si ``TASKFLOW_SECRET_KEY`` está definida, se usa.
    - Si no y ``TASKFLOW_ENV=production``: se lanza ``RuntimeError`` (fail-fast);
      el proceso no debe arrancar con una clave efímera en producción.
    - Si no y NO es producción: se genera una clave efímera aleatoria y se avisa
      (apaño solo para desarrollo; las sesiones no persisten entre reinicios).
    """
    clave = os.environ.get(SECRET_KEY_ENV)
    if clave:
        return clave
    if es_produccion():
        raise RuntimeError(
            f"{SECRET_KEY_ENV} es obligatoria cuando {ENV_VAR}=production; "
            "el proceso no arranca con una clave de sesión efímera en producción."
        )
    mensaje = (
        f"{SECRET_KEY_ENV} no está definida; se usa una clave efímera aleatoria. "
        "Válido solo para desarrollo: en despliegue define esta variable."
    )
    if logger is not None:
        logger.warning(mensaje)
    return secrets.token_hex(32)
