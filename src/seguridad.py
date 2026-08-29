"""TF-0008 — Lógica de seguridad aislada.

Protección CSRF manual basada en la biblioteca estándar: un token aleatorio por
sesión que se compara en tiempo constante con el valor enviado en el formulario.
Sin dependencias externas.
"""
import hmac
import os
import secrets

SECRET_KEY_ENV = "TASKFLOW_SECRET_KEY"
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


def obtener_secret_key(logger=None):
    """Resuelve la clave de firma de sesión.

    Usa ``TASKFLOW_SECRET_KEY`` si está definida. Si no, genera una clave efímera
    aleatoria y avisa: es un apaño solo para desarrollo. En despliegue la variable
    DEBE estar definida (las sesiones no persisten entre reinicios ni entre
    procesos con claves distintas).
    """
    clave = os.environ.get(SECRET_KEY_ENV)
    if clave:
        return clave
    mensaje = (
        f"{SECRET_KEY_ENV} no está definida; se usa una clave efímera aleatoria. "
        "Válido solo para desarrollo: en despliegue define esta variable."
    )
    if logger is not None:
        logger.warning(mensaje)
    return secrets.token_hex(32)
