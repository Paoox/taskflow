"""TF-0028 — Pruebas del agente Descubridor.

Cubre: construcción del prompt (patrón de `Documentador`), `parsear()` como
passthrough puro, contenido del prompt real, integración con `ejecutar_agente()`
y con `ejecutar_orquestador()` (agente real, sin dobles), y aislamiento
respecto a proveedores de IA concretos.
"""
import ast
import json
from pathlib import Path

import pytest

from src.agentes.contrato import EntradaAgente, Meta, SalidaAgente
from src.agentes.descubridor import Descubridor
from src.agentes.runner import ejecutar_agente
from src.ai.cliente import ClienteEco, RespuestaIA
from src.ai.prompts import cargar_prompt
from src.orquestador.contrato import AccionOrquestador
from src.orquestador.orquestador import ejecutar_orquestador
from src.repositorios.acciones import COMPLETADA, RepositorioAcciones
from src.repositorios.expedientes import RepositorioExpedientes

_RAIZ = Path(__file__).resolve().parents[1]


def _entrada(ticket="PROY-001", **kw):
    base = dict(objetivo="Descubrimiento de los campos raíz de PROJECT_STATE",
                contexto="- identidad: ¿Cuál es el nombre del proyecto?",
                restricciones=["r1"], criterios_aceptacion=["c1"],
                archivos_relevantes=["f1"])
    base.update(kw)
    return EntradaAgente(ticket=ticket, **base)


def _resp(texto):
    return RespuestaIA(texto=texto, tokens_entrada=1, tokens_salida=1, modelo="x")


# --- construir_prompt -------------------------------------------------

class TestConstruirPrompt:
    def test_incluye_prompt_base_y_campos_de_entrada(self):
        p = Descubridor().construir_prompt(_entrada(objetivo="OBJ-X"))
        assert cargar_prompt("descubridor").rstrip() in p
        assert "- ticket: PROY-001" in p
        assert "- objetivo: OBJ-X" in p
        assert "- identidad: ¿Cuál es el nombre del proyecto?" in p
        assert "- r1" in p and "- c1" in p and "- f1" in p

    def test_determinista(self):
        e = _entrada()
        assert Descubridor().construir_prompt(e) == Descubridor().construir_prompt(e)

    def test_listas_vacias_muestran_ninguno(self):
        p = Descubridor().construir_prompt(
            _entrada(restricciones=[], criterios_aceptacion=[], archivos_relevantes=[]))
        assert p.count("(ninguno)") == 3

    def test_contexto_vacio_muestra_marcador(self):
        p = Descubridor().construir_prompt(_entrada(contexto="   "))
        assert "(sin contexto)" in p

    def test_contexto_con_varias_preguntas_aparece_literal(self):
        contexto = "\n".join([
            "- identidad: ¿Cuál es el nombre del proyecto?",
            "- tipo_proyecto: ¿Qué tipo de proyecto es?",
            "- objetivo: ¿Cuál es el objetivo principal?",
        ])
        p = Descubridor().construir_prompt(_entrada(contexto=contexto))
        assert contexto in p


# --- parsear: passthrough puro -----------------------------------------

class TestParsear:
    @pytest.mark.parametrize("texto", [
        "",
        "esto no es json",
        json.dumps({"hallazgos": []}),
        json.dumps({"hallazgos": [
            {"campo": "identidad", "valor": "Taskflow", "estado": "confirmed",
             "origen": "file", "confianza": "ALTA", "notas": "detectado en pyproject.toml"},
        ]}),
        json.dumps({"forma": "inesperada"}),
    ])
    def test_resultado_es_el_texto_verbatim(self, texto):
        s = Descubridor().parsear(_resp(texto), _entrada())
        assert s.resultado == texto

    def test_meta_la_rellena_el_runner_no_el_agente(self):
        s = Descubridor().parsear(_resp("x"), _entrada())
        assert s.meta == Meta()

    def test_no_produce_artefactos_cambios_ni_problemas_propios(self):
        s = Descubridor().parsear(_resp("x"), _entrada())
        assert s.artefactos == []
        assert s.cambios == []
        assert s.problemas == []

    def test_no_hace_ningun_parseo_hibrido_tipo_documentador(self):
        """A diferencia de `Documentador`, un JSON con clave `resultado` NO
        se reinterpreta aquí: el contrato de este agente usa `hallazgos`, no
        `resultado`. `parsear()` debe devolver el texto crudo igual, para que
        sea `fusion.parsear_hallazgos()` quien decida qué hacer con él.
        """
        texto = json.dumps({"resultado": "esto no es un hallazgo, es una trampa"})
        s = Descubridor().parsear(_resp(texto), _entrada())
        assert s.resultado == texto


# --- prompt real ---------------------------------------------------------

class TestPrompt:
    def test_no_vacio_y_sin_logica(self):
        txt = cargar_prompt("descubridor")
        assert isinstance(txt, str) and txt.strip()
        for marca in ("{{", "%(", "import ", "```python"):
            assert marca not in txt

    def test_prohibe_origen_user(self):
        txt = cargar_prompt("descubridor")
        assert '"user"' in txt  # se menciona para prohibirlo explícitamente
        assert "nunca puede ser" in txt.lower()

    def test_prohibe_not_applicable_y_pending_decision_como_salida(self):
        txt = cargar_prompt("descubridor").lower()
        assert "no uses `not_applicable`" in txt or "no uses `not_applicable` ni `pending_decision`" in txt
        assert "pending_decision" in txt

    def test_menciona_los_6_estados_permitidos(self):
        txt = cargar_prompt("descubridor")
        for estado in ("confirmed", "discovered", "inferred", "unknown", "not_found", "incomplete"):
            assert f"`{estado}`" in txt

    def test_instruye_distinguir_evidencia_de_inferencia(self):
        txt = cargar_prompt("descubridor").lower()
        assert "evidencia directa" in txt
        assert "inferred" in txt

    def test_instruye_no_inventar(self):
        txt = cargar_prompt("descubridor").lower()
        assert "no inventes" in txt

    def test_instruye_contradicciones_en_notas(self):
        txt = cargar_prompt("descubridor").lower()
        assert "contradic" in txt
        assert "notas" in txt

    def test_instruye_formato_de_salida_unico(self):
        txt = cargar_prompt("descubridor")
        assert '"hallazgos"' in txt
        assert "únicamente" in txt.lower()


# --- integración con ejecutar_agente() -----------------------------------

class TestIntegracionConRunner:
    def test_con_cliente_eco(self, db):
        entrada = _entrada()
        salida = ejecutar_agente(entrada, ClienteEco(), Descubridor())
        assert salida.resultado.startswith("[eco] ")
        assert salida.meta.modelo == "eco"
        assert salida.problemas == []

    def test_con_cliente_que_devuelve_hallazgos_validos(self, db):
        texto = json.dumps({"hallazgos": [
            {"campo": "identidad", "valor": "Taskflow", "estado": "confirmed",
             "origen": "file", "confianza": "ALTA"},
        ]})

        class _ClienteFalso:
            def completar(self, prompt, opciones):
                return _resp(texto)

        salida = ejecutar_agente(_entrada(), _ClienteFalso(), Descubridor())
        assert salida.resultado == texto

    def test_registra_accion_con_su_propio_tipo_accion(self, db):
        repo_acc = RepositorioAcciones()
        ejecutar_agente(_entrada(ticket="PROY-777"), ClienteEco(), Descubridor(), repositorio=repo_acc)
        acciones = repo_acc.listar(ticket="PROY-777")
        assert len(acciones) == 1
        assert acciones[0]["actor"] == "agente:descubridor"
        assert acciones[0]["tipo"] == "descubrimiento_proyecto"
        assert acciones[0]["estado"] == COMPLETADA


# --- integración real con ejecutar_orquestador() (Descubridor real) ------

class TestIntegracionConOrquestador:
    def test_ciclo_completo_aplica_hallazgos_reales(self, db):
        """Descubridor() real (no un doble) + un ClienteIA de prueba que
        devuelve hallazgos válidos, a través de ejecutar_orquestador() real:
        cierra el círculo TF-0027 <-> TF-0028 sin dobles del agente.
        """
        class _ClienteFalso:
            def completar(self, prompt, opciones):
                # Responde solo al campo que efectivamente se le preguntó.
                assert "identidad" in prompt or "tipo_proyecto" in prompt
                return _resp(json.dumps({"hallazgos": [
                    {"campo": "identidad", "valor": "Taskflow",
                     "estado": "confirmed", "origen": "file", "confianza": "ALTA"},
                    {"campo": "tipo_proyecto", "valor": "SaaS",
                     "estado": "discovered", "origen": "repository", "confianza": "MEDIA"},
                ]}))

        repo_exp = RepositorioExpedientes()
        repo_acc = RepositorioAcciones()
        codigo = repo_exp.crear("Demo")

        resultado = ejecutar_orquestador(codigo, _ClienteFalso(), Descubridor(),
                                          repo_expedientes=repo_exp, repo_acciones=repo_acc)

        assert resultado.accion == AccionOrquestador.INVESTIGAR
        assert resultado.hallazgos_aplicados == 2
        assert resultado.problemas == []

        expediente = repo_exp.obtener(codigo)
        assert expediente.descubrimiento["identidad"].valor == "Taskflow"
        assert expediente.descubrimiento["identidad"].estado.value == "confirmed"
        assert expediente.descubrimiento["tipo_proyecto"].valor == "SaaS"
        assert expediente.descubrimiento["tipo_proyecto"].estado.value == "discovered"

    def test_hallazgo_con_origen_user_del_agente_se_sanea_a_agent(self, db):
        """Si el modelo, pese a la instrucción del prompt, devolviera
        origen="user", `fusion.py` (TF-0027, sin cambios) ya lo sanea a
        `AGENT` — se verifica end-to-end con el agente real.
        """
        class _ClienteQueIgnoraLaInstruccion:
            def completar(self, prompt, opciones):
                return _resp(json.dumps({"hallazgos": [
                    {"campo": "identidad", "valor": "Taskflow", "estado": "confirmed",
                     "origen": "user", "confianza": "ALTA"},
                ]}))

        repo_exp = RepositorioExpedientes()
        repo_acc = RepositorioAcciones()
        codigo = repo_exp.crear("Demo")

        resultado = ejecutar_orquestador(codigo, _ClienteQueIgnoraLaInstruccion(), Descubridor(),
                                          repo_expedientes=repo_exp, repo_acciones=repo_acc)

        assert resultado.hallazgos_aplicados == 1
        expediente = repo_exp.obtener(codigo)
        assert expediente.descubrimiento["identidad"].origen.value == "agent"
        assert any("forzado a agent" in p for p in resultado.problemas)


# --- Aislamiento: sin acoplamiento a proveedores concretos -----------------

_MODULOS = ["src/agentes/descubridor.py"]


def _imports(rel):
    arbol = ast.parse((_RAIZ / rel).read_text(encoding="utf-8"), filename=rel)
    mods = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            mods.add(n.module or "")
    return mods


class TestSinAcoplamiento:
    def test_no_importa_proveedores_ni_flask_ni_orquestador_ni_bd(self):
        prohibidos = {
            "flask", "app", "src.app",
            "src.ai.ollama", "src.ai.factory", "src.ai.registro",
            "src.orquestador", "src.proyectos", "src.repositorios", "src.database",
            "urllib", "urllib.request", "http", "http.client", "socket", "sqlite3",
        }
        for rel in _MODULOS:
            mods = _imports(rel)
            for m in mods:
                assert m not in prohibidos, f"{rel} importa {m!r}"
                assert not m.startswith(("flask.", "src.ai.ollama", "src.orquestador.",
                                          "src.proyectos.", "src.repositorios.")), \
                    f"{rel} importa {m!r}"

    def test_ollama_qwen_no_aparecen_en_el_codigo_fuente(self):
        texto = (_RAIZ / "src/agentes/descubridor.py").read_text(encoding="utf-8").lower()
        assert "ollama" not in texto
        assert "qwen" not in texto
