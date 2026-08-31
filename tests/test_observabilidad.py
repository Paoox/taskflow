"""TF-0020 — Observabilidad: logging central + correlation_id.

Cubre los criterios de aceptación 1–8 del ticket y el accessor
``config.nivel_log()`` (D10: sus tests viven aquí; no se toca
``tests/test_config.py``).
"""
import io
import logging

import pytest

from src import config, observabilidad
from src.observabilidad import (
    _FALLBACK_CID,
    _FORMATO,
    _LOGGER_NAME,
    _resolver_nivel,
    configurar_logging,
    get_correlation_id,
    obtener_logger,
    reset_correlation_id,
    set_correlation_id,
)


@pytest.fixture(autouse=True)
def _cid_limpio():
    """Cada test empieza y termina con el correlation_id en el fallback."""
    reset_correlation_id(None)
    yield
    reset_correlation_id(None)


# --- config.nivel_log() (D10) --------------------------------------------

class TestNivelLog:
    def test_default_es_info(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_LOG_LEVEL", raising=False)
        assert config.nivel_log() == "INFO"

    @pytest.mark.parametrize("valor,esperado", [
        ("debug", "DEBUG"),
        (" Debug ", "DEBUG"),
        ("WARNING", "WARNING"),
        ("error", "ERROR"),
        ("cualquier-cosa", "CUALQUIER-COSA"),
    ])
    def test_normaliza_strip_y_mayusculas_sin_validar(self, valor, esperado, monkeypatch):
        monkeypatch.setenv("TASKFLOW_LOG_LEVEL", valor)
        assert config.nivel_log() == esperado

    def test_late_binding_sin_cache(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_LOG_LEVEL", "WARNING")
        assert config.nivel_log() == "WARNING"
        monkeypatch.setenv("TASKFLOW_LOG_LEVEL", "ERROR")
        assert config.nivel_log() == "ERROR"


# --- _resolver_nivel ----------------------------------------------------

class TestResolverNivel:
    @pytest.mark.parametrize("nombre,esperado", [
        ("DEBUG", logging.DEBUG),
        ("INFO", logging.INFO),
        ("WARNING", logging.WARNING),
        ("ERROR", logging.ERROR),
        ("CRITICAL", logging.CRITICAL),
        ("  debug  ", logging.DEBUG),
    ])
    def test_nombres_validos(self, nombre, esperado):
        assert _resolver_nivel(nombre) == esperado

    @pytest.mark.parametrize("nombre", ["BOGUS", "", "   ", "20", "WARN", "trace", None])
    def test_valor_invalido_cae_a_info(self, nombre):
        assert _resolver_nivel(nombre) == logging.INFO


# --- CA-1: configurar_logging() idempotente ---------------------------

class TestConfigurarLoggingIdempotente:
    def test_no_acumula_handlers_ni_filtros(self):
        logger = configurar_logging("INFO")
        n_handlers = len(logger.handlers)
        n_filtros = len(logger.filters)
        for _ in range(5):
            configurar_logging("INFO")
        assert len(logger.handlers) == n_handlers
        assert len(logger.filters) == n_filtros
        assert n_handlers >= 1 and n_filtros >= 1

    def test_no_cambia_propagate(self):
        assert configurar_logging("INFO").propagate is True

    def test_no_anade_handlers_al_root(self):
        root = logging.getLogger()
        antes = len(root.handlers)
        configurar_logging("INFO")
        assert len(root.handlers) == antes

    def test_segunda_llamada_actualiza_el_nivel(self):
        logger = logging.getLogger(_LOGGER_NAME)
        configurar_logging("INFO")
        assert logger.level == logging.INFO
        configurar_logging("DEBUG")
        assert logger.level == logging.DEBUG
        configurar_logging("INFO")  # se restaura para el resto de la suite
        assert logger.level == logging.INFO


# --- CA-2: nivel efectivo desde TASKFLOW_LOG_LEVEL -------------------

class TestNivelEfectivo:
    def test_toma_el_nivel_de_la_variable(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_LOG_LEVEL", "DEBUG")
        assert configurar_logging(config.nivel_log()).level == logging.DEBUG
        configurar_logging("INFO")

    def test_valor_invalido_cae_a_info_sin_excepcion(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_LOG_LEVEL", "no-es-nivel")
        assert configurar_logging(config.nivel_log()).level == logging.INFO

    def test_ausente_es_info(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_LOG_LEVEL", raising=False)
        assert configurar_logging(config.nivel_log()).level == logging.INFO


# --- CA-4: correlation_id fuera de petición -------------------------

class TestCorrelationIdFueraDeContexto:
    def test_fallback_estable_y_no_lanza(self):
        assert get_correlation_id() == _FALLBACK_CID == "-"

    def test_set_y_reset_vuelve_al_fallback(self):
        tok = set_correlation_id("abc")
        assert get_correlation_id() == "abc"
        reset_correlation_id(tok)
        assert get_correlation_id() == "-"

    def test_reset_con_none_no_lanza(self):
        set_correlation_id("x")
        reset_correlation_id(None)
        assert get_correlation_id() == "-"

    def test_reset_con_token_ya_usado_no_lanza(self):
        tok = set_correlation_id("x")
        reset_correlation_id(tok)
        reset_correlation_id(tok)  # token ya consumido -> se captura -> fallback
        assert get_correlation_id() == "-"

    def test_set_sin_valor_genera_hex_de_32(self):
        tok = set_correlation_id()
        try:
            cid = get_correlation_id()
            assert len(cid) == 32
            int(cid, 16)  # es hexadecimal
        finally:
            reset_correlation_id(tok)


# --- CA-3: un correlation_id por petición HTTP ---------------------

class TestCorrelationIdPorPeticion:
    @staticmethod
    def _cid_de_una_peticion(flask_app, path="/"):
        with flask_app.test_request_context(path):
            flask_app.preprocess_request()  # ejecuta los before_request
            return get_correlation_id()

    def test_id_distinto_entre_dos_peticiones(self):
        import app as app_module
        a = self._cid_de_una_peticion(app_module.app)
        b = self._cid_de_una_peticion(app_module.app)
        assert a != b
        assert a != "-" and b != "-"
        assert len(a) == 32 and len(b) == 32
        # al salir de cada contexto, teardown_request restauró el fallback
        assert get_correlation_id() == "-"

    def test_dos_get_reales_con_client_asignan_ids_distintos(self, client, monkeypatch):
        vistos = []
        real = observabilidad.set_correlation_id

        def espia(valor=None):
            token = real(valor)
            vistos.append(get_correlation_id())
            return token

        monkeypatch.setattr("app.set_correlation_id", espia)
        assert client.get("/").status_code == 200
        assert client.get("/crear").status_code == 200
        assert len(vistos) == 2
        assert vistos[0] != vistos[1]
        assert all(len(v) == 32 for v in vistos)
        # fuera de petición vuelve al fallback (no gotea entre peticiones)
        assert get_correlation_id() == "-"

    def test_linea_de_log_en_peticion_incluye_el_correlation_id(self):
        import app as app_module
        configurar_logging("INFO")
        logger = obtener_logger()
        buf = io.StringIO()
        handler = logging.StreamHandler(buf)
        handler.setFormatter(logging.Formatter(_FORMATO))
        logger.addHandler(handler)
        try:
            with app_module.app.test_request_context("/"):
                app_module.app.preprocess_request()
                cid = get_correlation_id()
                logger.info("dentro de la peticion")
        finally:
            logger.removeHandler(handler)
        salida = buf.getvalue()
        assert cid != "-"
        assert f"[{cid}]" in salida
        assert "dentro de la peticion" in salida


# --- regla 18: limpieza incluso ante excepción --------------------

class TestLimpiezaConExcepcion:
    def test_teardown_resetea_aunque_la_vista_lance(self):
        import app as app_module
        with app_module.app.test_request_context("/"):
            app_module.app.preprocess_request()
            assert get_correlation_id() != "-"
            app_module.app.do_teardown_request(RuntimeError("boom"))
            assert get_correlation_id() == "-"


# --- CA-5: warning de clave de sesión efímera --------------------

TEXTO_WARNING = (
    "TASKFLOW_SECRET_KEY no está definida; se usa una clave efímera aleatoria. "
    "Válido solo para desarrollo: en despliegue define esta variable."
)


class TestWarningClaveSesion:
    def test_texto_condicion_y_nivel_exactos_en_el_logger_central(self, monkeypatch, caplog):
        monkeypatch.delenv("TASKFLOW_SECRET_KEY", raising=False)
        monkeypatch.delenv("TASKFLOW_ENV", raising=False)
        configurar_logging("INFO")
        from src.seguridad import obtener_secret_key
        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            clave = obtener_secret_key()
        assert isinstance(clave, str) and clave
        avisos = [r for r in caplog.records
                  if r.name == _LOGGER_NAME and r.levelno == logging.WARNING]
        assert len(avisos) == 1
        assert avisos[0].getMessage() == TEXTO_WARNING

    def test_no_emite_si_hay_clave(self, monkeypatch, caplog):
        monkeypatch.setenv("TASKFLOW_SECRET_KEY", "clave-presente")
        from src.seguridad import obtener_secret_key
        with caplog.at_level(logging.WARNING, logger=_LOGGER_NAME):
            obtener_secret_key()
        assert [r for r in caplog.records if r.name == _LOGGER_NAME] == []

    def test_logger_inyectado_conserva_la_prioridad(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_SECRET_KEY", raising=False)
        monkeypatch.delenv("TASKFLOW_ENV", raising=False)
        from src.seguridad import obtener_secret_key
        capturados = []

        class _Fake:
            def warning(self, msg):
                capturados.append(msg)

        obtener_secret_key(_Fake())
        assert capturados == [TEXTO_WARNING]


# --- CA-6: sin cambios HTTP -------------------------------------

class TestSinCambiosHTTP:
    def test_endpoints_basicos_200_con_logging_activo(self, client):
        assert client.get("/").status_code == 200
        assert client.get("/crear").status_code == 200

    def test_post_valido_sigue_redirigiendo(self, client, csrf_token):
        data = {
            "titulo": "t", "descripcion": "d", "fecha_limite": "2026-09-01",
            "prioridad": "Alta", "proyecto_id": "0", "csrf_token": csrf_token,
        }
        assert client.post("/crear", data=data).status_code == 302


# --- CA-8: compatibilidad con caplog --------------------------

class TestCaplogCompatible:
    def test_caplog_captura_del_logger_taskflow(self, caplog):
        configurar_logging("INFO")
        with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
            obtener_logger().info("mensaje via caplog")
        assert "mensaje via caplog" in caplog.text
        rec = next(r for r in caplog.records if r.getMessage() == "mensaje via caplog")
        assert hasattr(rec, "correlation_id")
        assert rec.correlation_id == get_correlation_id()

    def test_filtro_en_logger_inyecta_el_id_activo(self, caplog):
        configurar_logging("INFO")
        tok = set_correlation_id("cid-fijo")
        try:
            with caplog.at_level(logging.INFO, logger=_LOGGER_NAME):
                obtener_logger().info("con cid fijo")
        finally:
            reset_correlation_id(tok)
        rec = next(r for r in caplog.records if r.getMessage() == "con cid fijo")
        assert rec.correlation_id == "cid-fijo"
