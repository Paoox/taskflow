"""TF-0025 — Pruebas de `ClienteOllama`.

Sin red, sin sockets: `urllib.request.urlopen` se mockea en cada test. El
smoke test contra un servidor Ollama real es manual y queda fuera de esta
suite (DA-10).
"""
import io
import json
import urllib.error

import pytest

from src.ai import ollama
from src.ai.cliente import OpcionesIA, RespuestaIA
from src.ai.errores import (
    ErrorConfiguracionIA,
    ErrorIA,
    ErrorProveedorNoDisponible,
    ErrorRespuestaIA,
)
from src.ai.ollama import ClienteOllama
from src.ai.registro import _REGISTRO


@pytest.fixture(autouse=True)
def _registro_aislado():
    """El registro global ya trae "ollama" de importar `src.ai.ollama` a nivel
    de módulo (una sola vez, por proceso). Se restaura tras cada test por si
    algún caso lo manipula.
    """
    snapshot = dict(_REGISTRO)
    yield
    _REGISTRO.clear()
    _REGISTRO.update(snapshot)


class _RespuestaFalsa:
    """Doble de la respuesta de `urlopen`: contexto + `.read()`."""

    def __init__(self, cuerpo: bytes):
        self._cuerpo = cuerpo

    def __enter__(self):
        return self

    def __exit__(self, *exc):
        return False

    def read(self):
        return self._cuerpo


def _cuerpo_ok(**overrides):
    datos = {
        "response": "hola desde ollama",
        "done": True,
        "done_reason": "stop",
        "prompt_eval_count": 3,
        "eval_count": 5,
    }
    datos.update(overrides)
    return json.dumps(datos).encode("utf-8")


# --- Registro -------------------------------------------------------------

class TestRegistro:
    def test_importar_el_modulo_registra_ollama(self):
        assert "ollama" in _REGISTRO

    def test_importar_src_ai_a_secas_no_registra_ollama(self):
        codigo = (
            "import sys\n"
            "import src.ai\n"
            "assert 'ollama' not in src.ai.nombres(), src.ai.nombres()\n"
            "assert 'src.ai.ollama' not in sys.modules\n"
            "print('ok')\n"
        )
        import os
        import subprocess
        import sys as _sys
        from pathlib import Path

        raiz = Path(__file__).resolve().parents[1]
        r = subprocess.run(
            [_sys.executable, "-c", codigo], cwd=str(raiz),
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(raiz)},
        )
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip().endswith("ok")


# --- Construcción -----------------------------------------------------

class TestConstruccion:
    @pytest.mark.parametrize("base_url", ["", "   "])
    def test_base_url_vacia_lanza_errorconfiguracion(self, base_url):
        with pytest.raises(ErrorConfiguracionIA):
            ClienteOllama(base_url=base_url, modelo="llama3", timeout=5.0)

    @pytest.mark.parametrize("modelo", ["", "   "])
    def test_modelo_vacio_lanza_errorconfiguracion(self, modelo):
        with pytest.raises(ErrorConfiguracionIA):
            ClienteOllama(base_url="http://localhost:11434", modelo=modelo,
                           timeout=5.0)

    def test_recorta_barra_final_de_base_url(self, monkeypatch):
        capturado = {}

        def fake_urlopen(peticion, timeout):
            capturado["url"] = peticion.full_url
            return _RespuestaFalsa(_cuerpo_ok())

        monkeypatch.setattr(ollama.urllib.request, "urlopen", fake_urlopen)
        cliente = ClienteOllama(base_url="http://localhost:11434/", modelo="m",
                                 timeout=5.0)
        cliente.completar("hola", OpcionesIA())
        assert capturado["url"] == "http://localhost:11434/api/generate"

    def test_errorconfiguracion_es_subclase_de_erroria(self):
        assert issubclass(ErrorConfiguracionIA, ErrorIA)


# --- completar() — camino feliz ----------------------------------------

class TestCompletarExitoso:
    def _cliente(self, monkeypatch, fake_urlopen, **kwargs):
        monkeypatch.setattr(ollama.urllib.request, "urlopen", fake_urlopen)
        params = dict(base_url="http://localhost:11434", modelo="llama3",
                      timeout=42.0, reintentos=0)
        params.update(kwargs)
        return ClienteOllama(**params)

    def test_devuelve_respuestaia_con_datos_del_proveedor(self, monkeypatch):
        cliente = self._cliente(
            monkeypatch, lambda p, timeout: _RespuestaFalsa(_cuerpo_ok()))
        r = cliente.completar("hola", OpcionesIA())
        assert isinstance(r, RespuestaIA)
        assert r.texto == "hola desde ollama"
        assert r.tokens_entrada == 3
        assert r.tokens_salida == 5
        assert r.modelo == "llama3"
        assert r.coste_estimado == 0.0

    def test_ignora_modelo_y_timeout_de_opciones(self, monkeypatch):
        capturado = {}

        def fake_urlopen(peticion, timeout):
            capturado["timeout"] = timeout
            capturado["payload"] = json.loads(peticion.data.decode("utf-8"))
            return _RespuestaFalsa(_cuerpo_ok())

        cliente = self._cliente(monkeypatch, fake_urlopen, timeout=42.0)
        cliente.completar("hola", OpcionesIA(modelo="otro-modelo", timeout=1.0))
        assert capturado["timeout"] == 42.0
        assert capturado["payload"]["model"] == "llama3"

    def test_envia_max_tokens_y_temperatura_de_opciones(self, monkeypatch):
        capturado = {}

        def fake_urlopen(peticion, timeout):
            capturado["payload"] = json.loads(peticion.data.decode("utf-8"))
            return _RespuestaFalsa(_cuerpo_ok())

        cliente = self._cliente(monkeypatch, fake_urlopen)
        cliente.completar(
            "hola", OpcionesIA(max_tokens=256, temperatura=0.7))
        assert capturado["payload"]["options"] == {
            "temperature": 0.7, "num_predict": 256}

    def test_payload_incluye_stream_false_y_metodo_post(self, monkeypatch):
        capturado = {}

        def fake_urlopen(peticion, timeout):
            capturado["peticion"] = peticion
            return _RespuestaFalsa(_cuerpo_ok())

        cliente = self._cliente(monkeypatch, fake_urlopen)
        cliente.completar("hola", OpcionesIA())
        payload = json.loads(capturado["peticion"].data.decode("utf-8"))
        assert payload["stream"] is False
        assert payload["prompt"] == "hola"
        assert capturado["peticion"].get_method() == "POST"


# --- completar() — errores de transporte --------------------------------

class TestErroresTransporte:
    def test_httperror_lanza_errorproveedornodisponible_sin_reintentar(
            self, monkeypatch):
        llamadas = []

        def fake_urlopen(peticion, timeout):
            llamadas.append(1)
            raise urllib.error.HTTPError(
                peticion.full_url, 500, "boom", {}, io.BytesIO(b""))

        monkeypatch.setattr(ollama.urllib.request, "urlopen", fake_urlopen)
        cliente = ClienteOllama(base_url="http://localhost:11434", modelo="m",
                                 timeout=5.0, reintentos=3)
        with pytest.raises(ErrorProveedorNoDisponible) as exc:
            cliente.completar("hola", OpcionesIA())
        assert len(llamadas) == 1
        assert "500" in str(exc.value)

    def test_httperror_no_expone_cuerpo_ni_url(self, monkeypatch):
        def fake_urlopen(peticion, timeout):
            raise urllib.error.HTTPError(
                "http://localhost:11434/api/generate", 404, "not found", {},
                io.BytesIO(b""))

        monkeypatch.setattr(ollama.urllib.request, "urlopen", fake_urlopen)
        cliente = ClienteOllama(base_url="http://localhost:11434", modelo="m",
                                 timeout=5.0)
        with pytest.raises(ErrorProveedorNoDisponible) as exc:
            cliente.completar("hola", OpcionesIA())
        assert "localhost" not in str(exc.value)

    def test_urlerror_agota_reintentos_y_lanza_errorproveedornodisponible(
            self, monkeypatch):
        llamadas = []

        def fake_urlopen(peticion, timeout):
            llamadas.append(1)
            raise urllib.error.URLError("connection refused")

        monkeypatch.setattr(ollama.urllib.request, "urlopen", fake_urlopen)
        cliente = ClienteOllama(base_url="http://localhost:11434", modelo="m",
                                 timeout=5.0, reintentos=2)
        with pytest.raises(ErrorProveedorNoDisponible):
            cliente.completar("hola", OpcionesIA())
        assert len(llamadas) == 3  # 1 intento inicial + 2 reintentos

    def test_urlerror_no_expone_detalle_de_conexion(self, monkeypatch):
        def fake_urlopen(peticion, timeout):
            raise urllib.error.URLError("[Errno 111] Connection refused")

        monkeypatch.setattr(ollama.urllib.request, "urlopen", fake_urlopen)
        cliente = ClienteOllama(base_url="http://localhost:11434", modelo="m",
                                 timeout=5.0)
        with pytest.raises(ErrorProveedorNoDisponible) as exc:
            cliente.completar("hola", OpcionesIA())
        assert "Errno" not in str(exc.value)
        assert "Connection refused" not in str(exc.value)

    def test_recupera_si_un_reintento_tiene_exito(self, monkeypatch):
        llamadas = []

        def fake_urlopen(peticion, timeout):
            llamadas.append(1)
            if len(llamadas) == 1:
                raise urllib.error.URLError("temporal")
            return _RespuestaFalsa(_cuerpo_ok())

        monkeypatch.setattr(ollama.urllib.request, "urlopen", fake_urlopen)
        cliente = ClienteOllama(base_url="http://localhost:11434", modelo="m",
                                 timeout=5.0, reintentos=1)
        r = cliente.completar("hola", OpcionesIA())
        assert r.texto == "hola desde ollama"
        assert len(llamadas) == 2

    def test_sin_reintentos_falla_al_primer_intento(self, monkeypatch):
        llamadas = []

        def fake_urlopen(peticion, timeout):
            llamadas.append(1)
            raise urllib.error.URLError("nope")

        monkeypatch.setattr(ollama.urllib.request, "urlopen", fake_urlopen)
        cliente = ClienteOllama(base_url="http://localhost:11434", modelo="m",
                                 timeout=5.0, reintentos=0)
        with pytest.raises(ErrorProveedorNoDisponible):
            cliente.completar("hola", OpcionesIA())
        assert len(llamadas) == 1


# --- completar() — errores de respuesta ---------------------------------

class TestErroresRespuesta:
    def _cliente(self, monkeypatch, fake_urlopen):
        monkeypatch.setattr(ollama.urllib.request, "urlopen", fake_urlopen)
        return ClienteOllama(base_url="http://localhost:11434", modelo="m",
                              timeout=5.0)

    def test_json_invalido_lanza_errorrespuestaia(self, monkeypatch):
        cliente = self._cliente(
            monkeypatch, lambda p, timeout: _RespuestaFalsa(b"no es json"))
        with pytest.raises(ErrorRespuestaIA):
            cliente.completar("hola", OpcionesIA())

    def test_respuesta_no_es_un_objeto_json_lanza_errorrespuestaia(
            self, monkeypatch):
        cuerpo = json.dumps(["no", "es", "un", "dict"]).encode("utf-8")
        cliente = self._cliente(
            monkeypatch, lambda p, timeout: _RespuestaFalsa(cuerpo))
        with pytest.raises(ErrorRespuestaIA):
            cliente.completar("hola", OpcionesIA())

    def test_sin_campo_response_lanza_errorrespuestaia(self, monkeypatch):
        cuerpo = json.dumps({"done": True}).encode("utf-8")
        cliente = self._cliente(
            monkeypatch, lambda p, timeout: _RespuestaFalsa(cuerpo))
        with pytest.raises(ErrorRespuestaIA):
            cliente.completar("hola", OpcionesIA())

    def test_campo_response_vacio_lanza_errorrespuestaia(self, monkeypatch):
        cliente = self._cliente(
            monkeypatch,
            lambda p, timeout: _RespuestaFalsa(_cuerpo_ok(response="")))
        with pytest.raises(ErrorRespuestaIA):
            cliente.completar("hola", OpcionesIA())

    def test_truncada_por_limite_de_tokens_lanza_errorrespuestaia(
            self, monkeypatch):
        cliente = self._cliente(
            monkeypatch,
            lambda p, timeout: _RespuestaFalsa(
                _cuerpo_ok(done_reason="length")))
        with pytest.raises(ErrorRespuestaIA):
            cliente.completar("hola", OpcionesIA())

    def test_campos_de_tokens_ausentes_no_rompen(self, monkeypatch):
        cuerpo = json.dumps({"response": "ok", "done_reason": "stop"}).encode(
            "utf-8")
        cliente = self._cliente(
            monkeypatch, lambda p, timeout: _RespuestaFalsa(cuerpo))
        r = cliente.completar("hola", OpcionesIA())
        assert r.tokens_entrada == 0
        assert r.tokens_salida == 0


# --- Acoplamiento / contrato -------------------------------------------

class TestContrato:
    def test_completar_satisface_la_firma_de_clienteia(self):
        import inspect

        assert list(inspect.signature(ClienteOllama.completar).parameters) == [
            "self", "prompt", "opciones"]

    def test_no_toca_sockets_reales(self, monkeypatch):
        """Ningún test de este archivo debe abrir un socket real: si algo
        olvida mockear `urlopen`, debe fallar por `OSError`/timeout de
        conexión, no colgarse."""
        import socket

        def _no_sockets(*a, **k):
            raise AssertionError("intento de abrir un socket real")

        monkeypatch.setattr(socket, "socket", _no_sockets)
        cliente = ClienteOllama(base_url="http://localhost:11434", modelo="m",
                                 timeout=1.0)
        with pytest.raises(AssertionError):
            cliente.completar("hola", OpcionesIA())


# --- Integración con crear_cliente() / config ---------------------------

class TestIntegracionFactory:
    @pytest.fixture(autouse=True)
    def _sin_env_ai(self, monkeypatch):
        for var in ("TASKFLOW_AI_PROVIDER", "TASKFLOW_AI_BASE_URL",
                    "TASKFLOW_AI_MODEL", "TASKFLOW_AI_TIMEOUT",
                    "TASKFLOW_AI_API_KEY", "TASKFLOW_AI_MAX_RETRIES"):
            monkeypatch.delenv(var, raising=False)

    def test_crear_cliente_con_provider_ollama_usa_config(self, monkeypatch):
        from src.ai import crear_cliente

        monkeypatch.setenv("TASKFLOW_AI_PROVIDER", "ollama")
        monkeypatch.setenv("TASKFLOW_AI_BASE_URL", "http://localhost:11434")
        monkeypatch.setenv("TASKFLOW_AI_MODEL", "llama3")

        cliente = crear_cliente()
        assert isinstance(cliente, ClienteOllama)

        capturado = {}

        def fake_urlopen(peticion, timeout):
            capturado["payload"] = json.loads(peticion.data.decode("utf-8"))
            capturado["timeout"] = timeout
            return _RespuestaFalsa(_cuerpo_ok())

        monkeypatch.setattr(ollama.urllib.request, "urlopen", fake_urlopen)
        r = cliente.completar("hola", OpcionesIA())
        assert r.modelo == "llama3"
        assert capturado["payload"]["model"] == "llama3"
        assert capturado["timeout"] == 120.0  # AI_TIMEOUT_POR_DEFECTO

    def test_crear_cliente_ollama_sin_base_url_lanza_errorconfiguracion(
            self, monkeypatch):
        from src.ai import crear_cliente

        monkeypatch.setenv("TASKFLOW_AI_PROVIDER", "ollama")
        monkeypatch.setenv("TASKFLOW_AI_MODEL", "llama3")
        with pytest.raises(ErrorConfiguracionIA):
            crear_cliente()

    def test_no_regresion_runner_no_se_ve_afectado_por_ollama_importado(self, db):
        """Importar `src.ai.ollama` no cambia el comportamiento del runner con
        el proveedor por defecto ("eco"): TF-0024 CA-7 sigue vigente.
        """
        from src.agentes.contrato import EntradaAgente
        from src.agentes.documentador import Documentador
        from src.agentes.runner import ejecutar_agente
        from src.ai import ClienteEco

        entrada = EntradaAgente(ticket="TF-9999", objetivo="probar",
                                 contexto="x", restricciones=[],
                                 criterios_aceptacion=[], archivos_relevantes=[])
        salida = ejecutar_agente(entrada, ClienteEco(), Documentador())
        assert salida.artefactos[0].ruta == "docs/tickets/TF-9999.md"
