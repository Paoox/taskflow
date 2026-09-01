"""TF-0023 — Pruebas del runner (`ejecutar_agente`).

Usan la fixture `db` de `conftest.py` (base SQLite temporal con la tabla
`acciones` ya creada) y `ClienteEco` como cliente por defecto; para los caminos
JSON y de excepción se usan dobles de `ClienteIA` propios. Un *spy* de
`RepositorioAcciones` verifica la única transición `EN_CURSO -> COMPLETADA/FALLIDA`.
"""
import ast
import inspect
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src import observabilidad as obs
from src.agentes.base import DefinicionAgente
from src.agentes.contrato import Artefacto, EntradaAgente, Meta, SalidaAgente
from src.agentes.documentador import Documentador
from src.agentes.runner import ejecutar_agente
from src.ai.cliente import ClienteEco, OpcionesIA, RespuestaIA
from src.repositorios.acciones import COMPLETADA, FALLIDA, RepositorioAcciones

_RAIZ = Path(__file__).resolve().parents[1]
_MODULOS_NUEVOS = [
    "src/agentes/base.py",
    "src/agentes/runner.py",
    "src/agentes/documentador.py",
]


# --- utilidades -------------------------------------------------------------

def _entrada(ticket="TF-9999"):
    return EntradaAgente(
        ticket=ticket,
        objetivo="probar el runner",
        contexto="contexto de prueba",
        restricciones=["r1", "r2"],
        criterios_aceptacion=["c1"],
        archivos_relevantes=["src/x.py"],
    )


def _sin_meta_volatil(salida):
    d = salida.to_dict()
    d["meta"].pop("duracion_s", None)
    d["meta"].pop("correlation_id", None)
    return d


class _ClienteJSON:
    """`ClienteIA` que devuelve un JSON de `SalidaAgente`."""

    def __init__(self, salida_dict, *, tokens_entrada=3, tokens_salida=5,
                 modelo="fake-json", coste=0.0):
        self._texto = json.dumps(salida_dict)
        self._te, self._ts, self._modelo, self._coste = (
            tokens_entrada, tokens_salida, modelo, coste)

    def completar(self, prompt, opciones):
        return RespuestaIA(texto=self._texto, tokens_entrada=self._te,
                           tokens_salida=self._ts, modelo=self._modelo,
                           coste_estimado=self._coste)


class _ClienteTexto:
    """`ClienteIA` que devuelve texto arbitrario."""

    def __init__(self, texto):
        self._texto = texto

    def completar(self, prompt, opciones):
        return RespuestaIA(texto=self._texto, tokens_entrada=2, tokens_salida=4,
                           modelo="fake-txt", coste_estimado=0.0)


class _ClienteExplota:
    def completar(self, prompt, opciones):
        raise RuntimeError("boom")


class _RepoEspia:
    """Delega en un `RepositorioAcciones` real y anota las llamadas."""

    def __init__(self, real):
        self._real = real
        self.llamadas = []

    def registrar(self, **kw):
        self.llamadas.append(("registrar", kw))
        return self._real.registrar(**kw)

    def marcar(self, accion_id, estado, resultado=None):
        self.llamadas.append(("marcar", accion_id, estado))
        return self._real.marcar(accion_id, estado, resultado=resultado)


@pytest.fixture
def cid_limpio():
    obs.reset_correlation_id(None)
    yield
    obs.reset_correlation_id(None)


def _imports(rel):
    arbol = ast.parse((_RAIZ / rel).read_text(encoding="utf-8"), filename=rel)
    mods = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            mods.add(n.module or "")
    return mods


# --- CA-1: conformidad ----------------------------------------------------

class TestConformidad:
    def test_documentador_satisface_definicion_agente(self):
        d = Documentador()
        assert isinstance(d, DefinicionAgente)
        assert d.nombre == "documentador"
        assert d.tipo_accion == "generar_doc_ticket"
        assert list(inspect.signature(Documentador.construir_prompt).parameters) == [
            "self", "entrada"]
        assert list(inspect.signature(Documentador.parsear).parameters) == [
            "self", "respuesta", "entrada"]


# --- CA-2 / CA-3: E2E ClienteEco, transición única -----------------------

class TestE2EClienteEco:
    def test_completada_determinista(self, db, cid_limpio):
        ent = _entrada()
        s1 = ejecutar_agente(ent, ClienteEco(), Documentador())
        s2 = ejecutar_agente(ent, ClienteEco(), Documentador())
        assert _sin_meta_volatil(s1) == _sin_meta_volatil(s2)
        assert s1.resultado.startswith("[eco] ")
        assert s1.artefactos[0].ruta == "docs/tickets/TF-9999.md"
        assert s1.artefactos[0].tipo == "markdown"
        assert s1.artefactos[0].contenido == s1.resultado

    def test_una_sola_transicion_a_completada(self, db, cid_limpio):
        real = RepositorioAcciones()
        espia = _RepoEspia(real)
        ent = _entrada()
        salida = ejecutar_agente(ent, ClienteEco(), Documentador(), repositorio=espia)

        assert [c[0] for c in espia.llamadas] == ["registrar", "marcar"]
        assert espia.llamadas[1][2] == COMPLETADA

        filas = real.listar(ticket="TF-9999")
        assert len(filas) == 1
        fila = filas[0]
        assert fila["actor"] == "agente:documentador"
        assert fila["tipo"] == "generar_doc_ticket"
        assert fila["estado"] == COMPLETADA
        assert fila["creado_en"] and fila["actualizado_en"]
        assert json.loads(fila["entrada"]) == ent.to_dict()
        assert json.loads(fila["resultado"]) == salida.to_dict()

    def test_repositorio_none_persiste(self, db, cid_limpio):
        ejecutar_agente(_entrada("TF-7777"), ClienteEco(), Documentador())
        filas = RepositorioAcciones().listar(ticket="TF-7777")
        assert len(filas) == 1 and filas[0]["estado"] == COMPLETADA

    def test_opciones_none_usa_modelo_eco(self, db, cid_limpio):
        salida = ejecutar_agente(_entrada(), ClienteEco(), Documentador())
        assert salida.meta.modelo == "eco"


# --- CA-4 / CA-5: camino JSON ------------------------------------------

class TestCaminoJSON:
    def test_sintetiza_artefacto_si_falta(self, db, cid_limpio):
        sd = SalidaAgente(resultado="documento generado", cambios=["a.md"]).to_dict()
        salida = ejecutar_agente(_entrada(), _ClienteJSON(sd), Documentador())
        assert salida.resultado == "documento generado"
        assert salida.cambios == ["a.md"]
        arts = [a for a in salida.artefactos if a.ruta == "docs/tickets/TF-9999.md"]
        assert len(arts) == 1
        assert arts[0].contenido == "documento generado"
        assert arts[0].tipo == "markdown"

    def test_no_duplica_artefacto_del_modelo(self, db, cid_limpio):
        sd = SalidaAgente(
            resultado="doc",
            artefactos=[Artefacto("docs/tickets/TF-9999.md", "contenido del modelo",
                                  "markdown")],
        ).to_dict()
        salida = ejecutar_agente(_entrada(), _ClienteJSON(sd), Documentador())
        arts = [a for a in salida.artefactos if a.ruta == "docs/tickets/TF-9999.md"]
        assert len(arts) == 1
        assert arts[0].contenido == "contenido del modelo"


# --- CA-6: fallback de texto ------------------------------------------

class TestFallbackTexto:
    @pytest.mark.parametrize("texto", [
        "texto plano no json", "[1, 2]", '{"x": 1}', "null", "123", '"cadena"',
    ])
    def test_completada_via_fallback(self, db, cid_limpio, texto):
        real = RepositorioAcciones()
        salida = ejecutar_agente(_entrada(), _ClienteTexto(texto), Documentador(),
                                 repositorio=real)
        assert salida.resultado == texto
        assert salida.artefactos[0].contenido == texto
        assert real.listar(ticket="TF-9999")[0]["estado"] == COMPLETADA


# --- CA-7 / CA-7-bis: Meta -------------------------------------------

class TestMeta:
    def test_completada(self, db, cid_limpio):
        sd = SalidaAgente(resultado="x").to_dict()
        cli = _ClienteJSON(sd, tokens_entrada=7, tokens_salida=11, modelo="m-1",
                           coste=1.5)
        salida = ejecutar_agente(_entrada(), cli, Documentador())
        assert salida.meta.modelo == "m-1"
        assert salida.meta.tokens == 18
        assert salida.meta.coste_estimado == 1.5
        assert isinstance(salida.meta.duracion_s, float)
        assert salida.meta.duracion_s >= 0.0
        assert salida.meta.correlation_id and salida.meta.correlation_id != "-"

    def test_fallida(self, db, cid_limpio):
        salida = ejecutar_agente(_entrada(), _ClienteExplota(), Documentador(),
                                 opciones=OpcionesIA(modelo="m-fail"))
        assert salida.meta.modelo == "m-fail"
        assert salida.meta.tokens == 0
        assert salida.meta.coste_estimado == 0.0
        assert salida.meta.duracion_s >= 0.0
        assert salida.meta.correlation_id and salida.meta.correlation_id != "-"


# --- CA-8: contrato de errores --------------------------------------

class TestContratoErrores:
    def test_excepcion_cliente_va_a_fallida_sin_relanzar(self, db, cid_limpio):
        real = RepositorioAcciones()
        espia = _RepoEspia(real)
        salida = ejecutar_agente(_entrada(), _ClienteExplota(), Documentador(),
                                 repositorio=espia)
        assert salida.resultado == ""
        assert salida.problemas == ["RuntimeError: boom"]
        assert salida.artefactos == []
        assert [c[0] for c in espia.llamadas] == ["registrar", "marcar"]
        assert espia.llamadas[1][2] == FALLIDA
        fila = real.listar(ticket="TF-9999")[0]
        assert fila["estado"] == FALLIDA
        assert json.loads(fila["resultado"]) == salida.to_dict()


# --- CA-10: correlation_id -----------------------------------------

class TestCorrelationId:
    def test_creado_y_restaurado(self, db, cid_limpio):
        assert obs.get_correlation_id() == "-"
        salida = ejecutar_agente(_entrada(), ClienteEco(), Documentador())
        assert len(salida.meta.correlation_id) == 32
        int(salida.meta.correlation_id, 16)  # es hexadecimal
        assert salida.meta.correlation_id != "-"
        assert obs.get_correlation_id() == "-"  # contexto restaurado

    def test_externo_se_reutiliza_y_no_se_resetea(self, db, cid_limpio):
        tok = obs.set_correlation_id("externo-123")
        try:
            salida = ejecutar_agente(_entrada(), ClienteEco(), Documentador())
            assert salida.meta.correlation_id == "externo-123"
            assert obs.get_correlation_id() == "externo-123"
        finally:
            obs.reset_correlation_id(tok)

    def test_restaurado_tambien_en_fallida(self, db, cid_limpio):
        assert obs.get_correlation_id() == "-"
        ejecutar_agente(_entrada(), _ClienteExplota(), Documentador())
        assert obs.get_correlation_id() == "-"

    def test_guardarrail_centinela(self, cid_limpio):
        import src.agentes.runner as runner_mod
        assert runner_mod._CID_AUSENTE == obs.get_correlation_id()


# --- CA-9: sin escritura en disco --------------------------------

class TestSinEscrituraEnDisco:
    def test_docs_tickets_intacto(self, db, cid_limpio):
        docs = _RAIZ / "docs" / "tickets"
        antes = sorted(p.name for p in docs.iterdir())
        ejecutar_agente(_entrada("TF-9999"), ClienteEco(), Documentador())
        assert sorted(p.name for p in docs.iterdir()) == antes
        assert not (docs / "TF-9999.md").exists()


# --- CA-11: sin acoplamiento ------------------------------------

class TestSinAcoplamiento:
    def test_no_importan_flask_ni_app(self):
        for rel in _MODULOS_NUEVOS:
            mods = _imports(rel)
            for prohibido in ("flask", "app", "src.app"):
                assert prohibido not in mods, f"{rel} importa {prohibido!r}"
            assert not any(m.startswith(("flask.", "src.app.")) for m in mods)

    def test_import_aislado_sin_flask_ni_app(self):
        codigo = (
            "import sys\n"
            "import src.agentes.base, src.agentes.runner, src.agentes.documentador\n"
            "malo = [m for m in sys.modules if m == 'flask' or m.startswith('flask.') "
            "or m == 'app']\n"
            "assert not malo, malo\n"
            "print('ok')\n"
        )
        r = subprocess.run(
            [sys.executable, "-c", codigo],
            cwd=str(_RAIZ), capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(_RAIZ)},
        )
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip().endswith("ok")
