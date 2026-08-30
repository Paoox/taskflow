"""TF-0019 — Pruebas de la configuración central (`src/config.py`).

Sin Flask ni base de datos. Cubren:

  * `flag_activado()` — parser booleano único; incluye los 13 casos trasladados
    de la antigua `tests/test_app.py::TestFlagEntorno` (TF-0017), ahora contra
    `config.flag_activado()`;
  * cada accessor con la variable definida y sin definir (valor por defecto);
  * `puerto()` con valor no numérico -> `ValueError`;
  * late binding: los accessors leen `os.environ` en cada llamada.
"""
import pytest

from src import config


# --- flag_activado -------------------------------------------------------------

class TestFlagActivado:
    """Reemplaza a `tests/test_app.py::TestFlagEntorno`; misma cobertura,
    ahora sobre `config.flag_activado()`."""

    @pytest.mark.parametrize("valor", ["1", "true", "TRUE", "yes", "on", " on "])
    def test_valores_de_activacion_explicitos(self, valor, monkeypatch):
        monkeypatch.setenv("TASKFLOW_DEBUG", valor)
        assert config.flag_activado("TASKFLOW_DEBUG") is True

    @pytest.mark.parametrize("valor", ["", "0", "false", "no", "off", "x"])
    def test_valor_falso_o_vacio_no_activa(self, valor, monkeypatch):
        monkeypatch.setenv("TASKFLOW_DEBUG", valor)
        assert config.flag_activado("TASKFLOW_DEBUG") is False

    def test_variable_ausente_es_false(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_DEBUG", raising=False)
        assert config.flag_activado("TASKFLOW_DEBUG") is False

    @pytest.mark.parametrize("valor", ["basura", "2", "verdadero", "si", "-1"])
    def test_otros_valores_no_reconocidos_son_false(self, valor, monkeypatch):
        monkeypatch.setenv("TASKFLOW_DEBUG", valor)
        assert config.flag_activado("TASKFLOW_DEBUG") is False

    def test_funciona_con_cualquier_nombre_de_variable(self, monkeypatch):
        monkeypatch.setenv("UNA_VARIABLE_CUALQUIERA", "on")
        assert config.flag_activado("UNA_VARIABLE_CUALQUIERA") is True


# --- Accessors: valor por defecto y valor explícito -------------------------

class TestRutaDb:
    def test_default(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_DB", raising=False)
        assert config.ruta_db() == "tareas.db"

    def test_valor_explicito(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_DB", "/tmp/otra.db")
        assert config.ruta_db() == "/tmp/otra.db"


class TestSecretKey:
    def test_ausente_es_none(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_SECRET_KEY", raising=False)
        assert config.secret_key() is None

    def test_valor_explicito(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_SECRET_KEY", "clave-x")
        assert config.secret_key() == "clave-x"


class TestEntorno:
    def test_default_es_cadena_vacia(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_ENV", raising=False)
        assert config.entorno() == ""

    @pytest.mark.parametrize("valor,esperado", [
        ("production", "production"),
        (" Production ", "production"),
        ("PRODUCTION", "production"),
        ("dev", "dev"),
    ])
    def test_normaliza_strip_y_minusculas(self, valor, esperado, monkeypatch):
        monkeypatch.setenv("TASKFLOW_ENV", valor)
        assert config.entorno() == esperado


class TestCookieSecure:
    def test_default_desactivada(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_COOKIE_SECURE", raising=False)
        assert config.cookie_secure() is False

    @pytest.mark.parametrize("valor", ["1", "true", " on "])
    def test_activada(self, valor, monkeypatch):
        monkeypatch.setenv("TASKFLOW_COOKIE_SECURE", valor)
        assert config.cookie_secure() is True


class TestHost:
    def test_default(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_HOST", raising=False)
        assert config.host() == "127.0.0.1"

    def test_valor_explicito(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_HOST", "0.0.0.0")
        assert config.host() == "0.0.0.0"


class TestPuerto:
    def test_default_es_5000_int(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_PORT", raising=False)
        assert config.puerto() == 5000
        assert isinstance(config.puerto(), int)

    def test_valor_explicito_se_convierte_a_int(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_PORT", "8080")
        assert config.puerto() == 8080

    def test_valor_no_numerico_lanza_valueerror(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_PORT", "abc")
        with pytest.raises(ValueError):
            config.puerto()


class TestDebugActivado:
    def test_default_desactivado(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_DEBUG", raising=False)
        assert config.debug_activado() is False

    def test_activado_con_valor_explicito(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_DEBUG", "1")
        assert config.debug_activado() is True


# --- Late binding -----------------------------------------------------------

class TestLateBinding:
    def test_accessor_refleja_cambios_de_entorno_en_runtime(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_HOST", "primero")
        assert config.host() == "primero"
        monkeypatch.setenv("TASKFLOW_HOST", "segundo")
        assert config.host() == "segundo"

    def test_flag_refleja_cambios_de_entorno_en_runtime(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_DEBUG", raising=False)
        assert config.debug_activado() is False
        monkeypatch.setenv("TASKFLOW_DEBUG", "on")
        assert config.debug_activado() is True
