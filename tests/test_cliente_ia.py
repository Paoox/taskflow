"""TF-0021 — Pruebas de la interfaz `ClienteIA`, `ClienteEco` y `cargar_prompt`.

Sin Flask ni base de datos. Cubren: conformidad estructural de `ClienteEco` con
`ClienteIA`, determinismo, ausencia de red, metadatos con coste 0 y el helper
`cargar_prompt` (éxito y error tipado).
"""
import inspect
import socket

import pytest

from src.ai.cliente import _LIMITE_ECO, ClienteEco, ClienteIA, OpcionesIA, RespuestaIA
from src.ai.prompts import PromptNoEncontrado, cargar_prompt


# --- CA-4: conformidad -------------------------------------------

class TestConformidad:
    def test_clienteeco_satisface_clienteia(self):
        assert isinstance(ClienteEco(), ClienteIA)

    def test_conformidad_por_estructura_no_por_herencia(self):
        assert ClienteIA not in ClienteEco.__mro__

    def test_firma_de_completar(self):
        params = list(inspect.signature(ClienteEco.completar).parameters)
        assert params == ["self", "prompt", "opciones"]
        assert list(inspect.signature(ClienteIA.completar).parameters) == params

    def test_algo_sin_completar_no_es_clienteia(self):
        class NoCliente:
            pass

        assert not isinstance(NoCliente(), ClienteIA)


# --- CA-5: determinismo, sin red, coste 0 ---------------------

class TestClienteEco:
    def test_determinista(self):
        c = ClienteEco()
        o = OpcionesIA()
        assert c.completar("Hola  mundo\n", o) == c.completar("Hola  mundo\n", o)

    def test_devuelve_respuestaia(self):
        r = ClienteEco().completar("hola", OpcionesIA())
        assert isinstance(r, RespuestaIA)

    def test_eco_saneado_con_prefijo(self):
        r = ClienteEco().completar("  texto de prueba  ", OpcionesIA())
        assert r.texto == "[eco] texto de prueba"

    def test_recorta_al_limite(self):
        r = ClienteEco().completar("x" * (_LIMITE_ECO + 50), OpcionesIA())
        assert r.texto == "[eco] " + "x" * _LIMITE_ECO

    def test_metadatos_coherentes_y_coste_cero(self):
        r = ClienteEco().completar("uno dos tres", OpcionesIA(modelo="eco"))
        assert r.tokens_entrada == 3
        assert r.tokens_salida == len(r.texto.split())
        assert r.coste_estimado == 0.0
        assert r.modelo == "eco"

    def test_refleja_el_modelo_de_las_opciones(self):
        r = ClienteEco().completar("hola", OpcionesIA(modelo="otro"))
        assert r.modelo == "otro"

    def test_no_abre_sockets(self, monkeypatch):
        def _boom(*a, **k):
            raise AssertionError("ClienteEco no debe abrir sockets")

        monkeypatch.setattr(socket, "socket", _boom)
        ClienteEco().completar("sin red", OpcionesIA())

    def test_logger_opcional_recibe_una_traza_debug(self):
        trazas = []

        class _Log:
            def debug(self, *a):
                trazas.append(a)

        ClienteEco(logger=_Log()).completar("con logger", OpcionesIA())
        assert len(trazas) == 1

    def test_sin_logger_funciona_igual(self):
        assert ClienteEco().completar("x", OpcionesIA()).texto == "[eco] x"


# --- CA-6: cargar_prompt ------------------------------------

class TestCargarPrompt:
    def test_carga_el_ejemplo(self):
        contenido = cargar_prompt("ejemplo")
        assert isinstance(contenido, str) and contenido.strip()

    def test_prompt_inexistente_lanza_tipado(self):
        with pytest.raises(PromptNoEncontrado):
            cargar_prompt("no-existe-este-prompt")

    def test_excepcion_es_subclase_de_filenotfounderror(self):
        assert issubclass(PromptNoEncontrado, FileNotFoundError)

    @pytest.mark.parametrize("malo", [
        "../secreto", "a/b", "con espacio", "", "MAYUS", "punto.md",
    ])
    def test_nombre_invalido_lanza_tipado(self, malo):
        with pytest.raises(PromptNoEncontrado):
            cargar_prompt(malo)

    def test_nombre_no_str_lanza_tipado(self):
        with pytest.raises(PromptNoEncontrado):
            cargar_prompt(None)
