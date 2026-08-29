"""TF-0008 — Pruebas unitarias de la lógica CSRF (sin Flask ni base de datos)."""
from src.seguridad import generar_token, obtener_secret_key, token_valido


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
        assert obtener_secret_key() != obtener_secret_key()
