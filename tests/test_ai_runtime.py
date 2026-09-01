"""TF-0024 — Pruebas del runtime de IA: factoría, registro, errores, config.

Sin red, sin sockets. `ClienteEco` (proveedor "eco") es el único cliente real
usado; los proveedores de prueba se registran y se limpian por test.
"""
import ast
import dataclasses
import inspect
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src import config
from src.agentes.contrato import EntradaAgente
from src.agentes.documentador import Documentador
from src.agentes.runner import ejecutar_agente
from src.ai import (
    ClienteEco,
    ClienteIA,
    ErrorConfiguracionIA,
    ErrorIA,
    ErrorProveedorNoDisponible,
    ErrorRespuestaIA,
    crear_cliente,
    nombres,
    registrar,
)
from src.ai import registro
from src.ai.cliente import OpcionesIA, RespuestaIA

_RAIZ = Path(__file__).resolve().parents[1]
_MODULOS_NUEVOS = ["src/ai/errores.py", "src/ai/registro.py", "src/ai/factory.py"]


@pytest.fixture(autouse=True)
def _registro_aislado():
    """Restaura el registro de proveedores tras cada test."""
    snapshot = dict(registro._REGISTRO)
    yield
    registro._REGISTRO.clear()
    registro._REGISTRO.update(snapshot)


@pytest.fixture(autouse=True)
def _sin_env_ai(monkeypatch):
    """Cada test empieza sin ninguna TASKFLOW_AI_* salvo que la fije."""
    for var in ("TASKFLOW_AI_PROVIDER", "TASKFLOW_AI_BASE_URL", "TASKFLOW_AI_MODEL",
                "TASKFLOW_AI_TIMEOUT", "TASKFLOW_AI_API_KEY", "TASKFLOW_AI_MAX_RETRIES"):
        monkeypatch.delenv(var, raising=False)


def _imports(rel):
    arbol = ast.parse((_RAIZ / rel).read_text(encoding="utf-8"), filename=rel)
    mods = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            mods.add(n.module or "")
    return mods


# --- Factoría -----------------------------------------------------------

class TestCrearCliente:
    def test_por_defecto_es_clienteeco(self):
        cliente = crear_cliente()
        assert isinstance(cliente, ClienteEco)
        assert isinstance(cliente, ClienteIA)

    @pytest.mark.parametrize("valor", ["eco", "ECO", "  eco  ", " ECO "])
    def test_normaliza_el_nombre_de_proveedor(self, valor, monkeypatch):
        monkeypatch.setenv("TASKFLOW_AI_PROVIDER", valor)
        assert isinstance(crear_cliente(), ClienteEco)

    def test_proveedor_desconocido_lanza_errorconfiguracion(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_AI_PROVIDER", "inexistente")
        with pytest.raises(ErrorConfiguracionIA) as exc:
            crear_cliente()
        assert isinstance(exc.value, ErrorIA)
        assert "inexistente" in str(exc.value)
        assert "eco" in str(exc.value)  # lista los disponibles

    def test_no_expone_valores_de_entorno(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_AI_PROVIDER", "inexistente")
        monkeypatch.setenv("TASKFLOW_AI_API_KEY", "clave-super-secreta")
        with pytest.raises(ErrorConfiguracionIA) as exc:
            crear_cliente()
        assert "clave-super-secreta" not in str(exc.value)

    def test_usa_la_fabrica_registrada_y_late_binding(self, monkeypatch):
        centinela = ClienteEco()
        registrar("fijo", lambda: centinela)
        assert isinstance(crear_cliente(), ClienteEco)          # aún "eco"
        monkeypatch.setenv("TASKFLOW_AI_PROVIDER", "fijo")
        assert crear_cliente() is centinela                     # resuelto por el valor nuevo


# --- Registro ---------------------------------------------------------

class TestRegistro:
    def test_eco_registrado_al_importar(self):
        assert "eco" in nombres()

    def test_registrar_y_obtener_con_normalizacion(self):
        def f():
            return ClienteEco()

        registrar("X", f)
        assert registro.obtener("x") is f
        assert registro.obtener("  X  ") is f

    def test_nombre_duplicado_lanza(self):
        registrar("dup", lambda: ClienteEco())
        with pytest.raises(ErrorConfiguracionIA):
            registrar("dup", lambda: ClienteEco())
        with pytest.raises(ErrorConfiguracionIA):
            registrar("eco", lambda: ClienteEco())

    def test_obtener_ausente_lanza(self):
        with pytest.raises(ErrorConfiguracionIA):
            registro.obtener("no-existe")

    def test_quitar(self):
        registrar("temp", lambda: ClienteEco())
        assert "temp" in nombres()
        registro.quitar("  TEMP ")
        assert "temp" not in nombres()
        registro.quitar("temp")  # no-op, no lanza

    def test_nombres_es_tupla_en_orden_de_alta(self):
        registrar("z1", lambda: ClienteEco())
        assert isinstance(nombres(), tuple)
        assert nombres()[0] == "eco"
        assert nombres()[-1] == "z1"


# --- Errores --------------------------------------------------------

class TestErrores:
    def test_jerarquia(self):
        assert issubclass(ErrorIA, Exception)
        for sub in (ErrorConfiguracionIA, ErrorProveedorNoDisponible, ErrorRespuestaIA):
            assert issubclass(sub, ErrorIA)

    def test_instanciables_con_mensaje(self):
        e = ErrorRespuestaIA("respuesta truncada por límite de tokens")
        assert isinstance(e, ErrorIA)
        assert "truncada" in str(e)
        assert isinstance(ErrorProveedorNoDisponible("x"), ErrorIA)
        assert isinstance(ErrorConfiguracionIA("x"), ErrorIA)


# --- config.TASKFLOW_AI_* ----------------------------------------

class TestConfigAI:
    def test_proveedor_default_y_normalizacion(self, monkeypatch):
        assert config.proveedor_ia() == "eco"
        monkeypatch.setenv("TASKFLOW_AI_PROVIDER", "  OLLAMA ")
        assert config.proveedor_ia() == "ollama"

    def test_base_url(self, monkeypatch):
        assert config.ai_base_url() == ""
        monkeypatch.setenv("TASKFLOW_AI_BASE_URL", " http://localhost:11434 ")
        assert config.ai_base_url() == "http://localhost:11434"

    def test_model(self, monkeypatch):
        assert config.ai_model() == ""
        monkeypatch.setenv("TASKFLOW_AI_MODEL", " qwen2.5-coder:7b ")
        assert config.ai_model() == "qwen2.5-coder:7b"

    def test_timeout_default_y_valor(self, monkeypatch):
        assert config.ai_timeout() == 120.0
        assert isinstance(config.ai_timeout(), float)
        monkeypatch.setenv("TASKFLOW_AI_TIMEOUT", "30")
        assert config.ai_timeout() == 30.0

    def test_timeout_no_numerico_lanza_valueerror(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_AI_TIMEOUT", "abc")
        with pytest.raises(ValueError):
            config.ai_timeout()

    def test_api_key(self, monkeypatch):
        assert config.ai_api_key() is None
        monkeypatch.setenv("TASKFLOW_AI_API_KEY", "k")
        assert config.ai_api_key() == "k"

    def test_max_retries_default_y_valor(self, monkeypatch):
        assert config.ai_max_retries() == 0
        monkeypatch.setenv("TASKFLOW_AI_MAX_RETRIES", "1")
        assert config.ai_max_retries() == 1

    def test_max_retries_no_numerico_lanza_valueerror(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_AI_MAX_RETRIES", "x")
        with pytest.raises(ValueError):
            config.ai_max_retries()

    def test_late_binding(self, monkeypatch):
        monkeypatch.setenv("TASKFLOW_AI_MODEL", "a")
        assert config.ai_model() == "a"
        monkeypatch.setenv("TASKFLOW_AI_MODEL", "b")
        assert config.ai_model() == "b"


# --- No-regresión del runner (TF-0023) -------------------------

class TestNoRegresionRunner:
    @staticmethod
    def _sin_meta_volatil(salida):
        d = salida.to_dict()
        d["meta"].pop("duracion_s", None)
        d["meta"].pop("correlation_id", None)
        return d

    def test_runner_con_crear_cliente_igual_que_con_clienteeco(self, db):
        entrada = EntradaAgente(
            ticket="TF-9999", objetivo="probar el runtime", contexto="x",
            restricciones=["r"], criterios_aceptacion=["c"],
            archivos_relevantes=["f"],
        )
        s_eco = ejecutar_agente(entrada, ClienteEco(), Documentador())
        s_factory = ejecutar_agente(entrada, crear_cliente(), Documentador())
        assert self._sin_meta_volatil(s_eco) == self._sin_meta_volatil(s_factory)
        assert s_factory.artefactos[0].ruta == "docs/tickets/TF-9999.md"


# --- Acoplamiento / contrato congelado / sin red -----------

class TestSinAcoplamiento:
    def test_modulos_nuevos_no_importan_flask_app_agentes_ni_red(self):
        prohibidos = {"flask", "app", "src.app", "httpx", "requests",
                      "urllib", "urllib.request", "http", "http.client", "socket"}
        prefijos = ("flask.", "src.agentes.", "src.app.")
        for rel in _MODULOS_NUEVOS:
            mods = _imports(rel)
            for m in mods:
                assert m not in prohibidos, f"{rel} importa {m!r}"
                assert not m.startswith(prefijos), f"{rel} importa {m!r}"

    def test_contrato_de_cliente_congelado(self):
        assert [f.name for f in dataclasses.fields(OpcionesIA)] == [
            "modelo", "max_tokens", "temperatura", "timeout"]
        assert [f.name for f in dataclasses.fields(RespuestaIA)] == [
            "texto", "tokens_entrada", "tokens_salida", "modelo", "coste_estimado"]
        assert list(inspect.signature(ClienteEco.completar).parameters) == [
            "self", "prompt", "opciones"]
        assert isinstance(ClienteEco(), ClienteIA)

    def test_import_aislado_sin_red_ni_flask(self):
        codigo = (
            "import sys\n"
            "import src.ai\n"
            "malo = [m for m in sys.modules if m in "
            "('flask','app','httpx','requests') or m.startswith('flask.')]\n"
            "assert not malo, malo\n"
            "assert 'src.ai' in sys.modules and 'eco' in src.ai.nombres()\n"
            "print('ok')\n"
        )
        r = subprocess.run(
            [sys.executable, "-c", codigo], cwd=str(_RAIZ),
            capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(_RAIZ)},
        )
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip().endswith("ok")
