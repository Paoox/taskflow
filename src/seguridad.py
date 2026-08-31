"""TF-0008 — Lógica de seguridad aislada.

Protección CSRF manual basada en la biblioteca estándar: un token aleatorio por
sesión que se compara en tiempo constante con el valor enviado en el formulario.
Sin dependencias externas.

TF-0012 — endurecimiento de la sesión:
  * ``obtener_secret_key()`` falla en producción si falta ``TASKFLOW_SECRET_KEY``.
  * ``cookie_secure_activada()`` controla ``SESSION_COOKIE_SECURE``.

TF-0019 — la lectura y el parseo del entorno se delegan en ``src.config``; este
módulo conserva sus funciones públicas y su comportamiento.

TF-0020 — cuando no se inyecta un ``logger``, el warning de clave de sesión
efímera se emite al logger central (``src.observabilidad``). La firma pública, el
texto y la condición del warning no cambian.
"""
import hmac
import secrets

from . import config
from .observabilidad import obtener_logger

CSRF_TOKEN_BYTES = 32


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
    return config.entorno() == "production"


def cookie_secure_activada():
    """True si ``TASKFLOW_COOKIE_SECURE`` está activada.

    Por defecto ``False`` (desarrollo local sobre HTTP). En despliegue tras TLS
    debe ponerse a ``1`` para que la cookie de sesión lleve el atributo Secure.
    """
    return config.cookie_secure()


def obtener_secret_key(logger=None):
    """Resuelve la clave de firma de sesión.

    - Si ``TASKFLOW_SECRET_KEY`` está definida, se usa.
    - Si no y ``TASKFLOW_ENV=production``: se lanza ``RuntimeError`` (fail-fast);
      el proceso no debe arrancar con una clave efímera en producción.
    - Si no y NO es producción: se genera una clave efímera aleatoria y se avisa
      (apaño solo para desarrollo; las sesiones no persisten entre reinicios).
    """
    clave = config.secret_key()
    if clave:
        return clave
    if es_produccion():
        raise RuntimeError(
            f"{config.SECRET_KEY_ENV} es obligatoria cuando {config.ENTORNO_ENV}=production; "
            "el proceso no arranca con una clave de sesión efímera en producción."
        )
    mensaje = (
        f"{config.SECRET_KEY_ENV} no está definida; se usa una clave efímera aleatoria. "
        "Válido solo para desarrollo: en despliegue define esta variable."
    )
    (logger if logger is not None else obtener_logger()).warning(mensaje)
    return secrets.token_hex(32)
