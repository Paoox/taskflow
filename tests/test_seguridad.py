"""Pruebas unitarias de la lógica de seguridad (sin Flask ni base de datos).

TF-0008 — tokens CSRF y resolución de la clave de sesión.
TF-0012 — fail-fast en producción y control de la cookie Secure.
"""
import pytest

from src.seguridad import (
    cookie_secure_activada,
    es_produccion,
    generar_token,
    obtener_secret_key,
    token_valido,
)


class TestGenerarToken:
    def test_devuelve_str_no_vacia(self):
        t = generar_token()
        assert isinstance(t, str) and len(t) >= 32

    def test_tokens_distintos_en_cada_llamada(self):
        assert generar_token() != generar_token()

    def test_url_safe(self):
        import string
        permitido = set(string.ascii_letters + string.digits + "-_")
        assert set(generar_token()) <= permitido


class TestTokenValido:
    def test_true_si_coinciden(self):
        t = generar_token()
        assert token_valido(t, t) is True

    def test_false_si_difieren(self):
        assert token_valido(generar_token(), generar_token()) is False

    def test_false_si_esperado_vacio(self):
        assert token_valido("algo", "") is False

    def test_false_si_enviado_vacio(self):
        assert token_valido("", "algo") is False

    def test_false_si_enviado_none(self):
        assert token_valido(None, "algo") is False


class TestObtenerSecretKey:
    def test_usa_la_variable_de_entorno_si_esta(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_SECRET_KEY", "clave-fija")
        assert obtener_secret_key() == "clave-fija"

    def test_fallback_efimero_y_warning_si_no_esta(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_SECRET_KEY", raising=False)
        avisos = []

        class _Logger:
            def warning(self, msg):
                avisos.append(msg)

        clave = obtener_secret_key(_Logger())
        assert clave and isinstance(clave, str)
        assert len(avisos) == 1
        assert "TASKFLOW_SECRET_KEY" in avisos[0]

    def test_fallback_distinto_en_cada_llamada(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_SECRET_KEY", raising=False)
        monkeypatch.delenv("TASKFLOW_ENV", raising=False)
        assert obtener_secret_key() != obtener_secret_key()


class TestFailFastProduccion:
    """TF-0012 — con TASKFLOW_ENV=production, la clave de sesión es obligatoria."""

    def test_lanza_runtimeerror_si_produccion_y_sin_clave(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_SECRET_KEY", raising=False)
        monkeypatch.setenv("TASKFLOW_ENV", "production")
        with pytest.raises(RuntimeError) as exc:
            obtener_secret_key()
        assert "TASKFLOW_SECRET_KEY" in str(exc.value)

    def test_devuelve_la_clave_si_produccion_y_clave_presente(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_ENV", "production")
        monkeypatch.setenv("TASKFLOW_SECRET_KEY", "clave-real")
        assert obtener_secret_key() == "clave-real"

    def test_sin_produccion_mantiene_el_fallback_efimero(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_SECRET_KEY", raising=False)
        monkeypatch.delenv("TASKFLOW_ENV", raising=False)
        assert isinstance(obtener_secret_key(), str)

    @pytest.mark.parametrize("valor", ["", "dev", "Production ", "PRODUCTION", "prod"])
    def test_es_produccion_solo_con_production_exacto(self, monkeypatch, valor):
        monkeypatch.setenv("TASKFLOW_ENV", valor)
        esperado = valor.strip().lower() == "production"
        assert es_produccion() is esperado


class TestCookieSecure:
    """TF-0012 — TASKFLOW_COOKIE_SECURE controla SESSION_COOKIE_SECURE."""

    @pytest.mark.parametrize("valor", ["1", "true", "TRUE", "yes", "on", " on "])
    def test_activada(self, monkeypatch, valor):
        monkeypatch.setenv("TASKFLOW_COOKIE_SECURE", valor)
        assert cookie_secure_activada() is True

    @pytest.mark.parametrize("valor", ["", "0", "false", "no", "off"])
    def test_desactivada(self, monkeypatch, valor):
        monkeypatch.setenv("TASKFLOW_COOKIE_SECURE", valor)
        assert cookie_secure_activada() is False

    def test_por_defecto_desactivada(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_COOKIE_SECURE", raising=False)
        assert cookie_secure_activada() is False
