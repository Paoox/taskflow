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
from src.repositorios.briefs import RepositorioBriefs
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
    def test_incluye_instrucciones_base_y_campos_de_entrada(self):
        p = Descubridor().construir_prompt(_entrada(objetivo="OBJ-X"))
        # Secciones de instrucciones del prompt base, a ambos lados del hueco.
        assert "## 1. TAREA" in p
        assert "## 8. AHORA GENERA" in p
        # Evidencia real de la entrada, inyectada en el bloque DATOS DEL PROYECTO.
        assert "- identidad: ¿Cuál es el nombre del proyecto?" in p
        assert "- r1" in p and "- c1" in p and "- f1" in p

    def test_ticket_y_objetivo_interno_no_aparecen_en_la_zona_de_datos(self):
        """Corrección post-smoke-test: `ticket`/`objetivo` son metadata de
        coordinación de TaskFlow (el `codigo` del expediente y el objetivo
        interno del ciclo del Orquestador), nunca evidencia del proyecto —
        no deben aparecer dentro de DATOS_DEL_PROYECTO, la zona que el propio
        prompt le ordena al modelo tratar como evidencia. (El prompt base sí
        puede *mencionar* "PROY-001" en sus INSTRUCCIONES, como ejemplo de lo
        que hay que rechazar — eso está fuera de la zona de datos y no es la
        fuga que corrige este test.)
        """
        codigo_fuga = "PROY-777"  # distinto del ejemplo ya mencionado en las instrucciones
        objetivo_fuga = "Descubrimiento de los campos raíz de PROJECT_STATE"
        p = Descubridor().construir_prompt(_entrada(ticket=codigo_fuga, objetivo=objetivo_fuga))

        zona_datos = p[p.index("<<<DATOS_DEL_PROYECTO"):p.index("DATOS_DEL_PROYECTO>>>")]
        assert codigo_fuga not in zona_datos
        assert objetivo_fuga not in zona_datos
        assert "- ticket:" not in zona_datos
        assert "- objetivo:" not in zona_datos

    def test_datos_van_entre_las_marcas_y_antes_de_ahora_genera(self):
        p = Descubridor().construir_prompt(_entrada())
        # Marcas reales de la sección 2 (cada una en su propia línea), no las
        # menciones entre comillas invertidas de la prosa del prompt.
        ini = p.index("\n<<<DATOS_DEL_PROYECTO\n")
        fin = p.index("\nDATOS_DEL_PROYECTO>>>\n")
        ctx = p.index("- identidad: ¿Cuál es el nombre del proyecto?")
        assert ini < ctx < fin  # la evidencia de la entrada queda encerrada
        assert fin < p.index("## 8. AHORA GENERA")  # y antes de la orden final

    def test_ahora_genera_es_lo_ultimo(self):
        p = Descubridor().construir_prompt(_entrada())
        resto = p[p.index("## 8. AHORA GENERA"):]
        assert "\n## " not in resto  # no hay ninguna sección después

    def test_el_hueco_vacio_del_prompt_base_desaparece_al_rellenarlo(self):
        p = Descubridor().construir_prompt(_entrada())
        assert "<<<DATOS_DEL_PROYECTO\nDATOS_DEL_PROYECTO>>>" not in p

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

    def test_instruye_formato_json_lines_sin_envoltorio(self):
        """TF-0029 (corrección post-smoke-test): un objeto JSON por línea,
        sin array ni clave "hallazgos" envolvente — la causa raíz del fallo
        real con qwen2.5:3b fue que un error de sintaxis en un solo hallazgo
        invalidaba el documento entero; el prompt ya no debe pedir ese
        formato.
        """
        txt = cargar_prompt("descubridor")
        # El prompt puede mencionar "hallazgos" en prosa (p. ej. para prohibir
        # explícitamente el envoltorio antiguo); lo que no debe aparecer es el
        # patrón del envoltorio en sí, como ejemplo a seguir.
        assert '{"hallazgos"' not in txt
        assert "una línea" in txt.lower() or "por línea" in txt.lower()
        assert "únicamente" in txt.lower()

    def test_instruye_resumir_evidencia_en_vez_de_copiar_literal(self):
        txt = cargar_prompt("descubridor").lower()
        assert "resum" in txt
        assert "comillas" in txt

    def test_tiene_las_ocho_secciones_en_orden(self):
        txt = cargar_prompt("descubridor")
        encabezados = [
            "## 1. TAREA", "## 2. DATOS DEL PROYECTO", "## 3. CAMPOS A INVESTIGAR",
            "## 4. REGLAS", "## 5. FORMATO DE SALIDA", "## 6. EJEMPLO CORRECTO",
            "## 7. EJEMPLOS INCORRECTOS", "## 8. AHORA GENERA",
        ]
        posiciones = [txt.index(h) for h in encabezados]
        assert posiciones == sorted(posiciones)
        # "AHORA GENERA" es el último encabezado del archivo.
        assert txt.rindex("## ") == txt.index("## 8. AHORA GENERA")

    def test_tiene_hueco_de_datos_vacio_entre_marcas(self):
        txt = cargar_prompt("descubridor")
        assert "<<<DATOS_DEL_PROYECTO\nDATOS_DEL_PROYECTO>>>" in txt

    def test_marca_los_datos_como_no_instrucciones(self):
        txt = cargar_prompt("descubridor").lower()
        assert "no son instrucciones" in txt

    def test_ejemplos_incorrectos_cubren_objeto_plano_fence_array_y_wrapper(self):
        txt = cargar_prompt("descubridor")
        # El fallo real observado con qwen2.5:3b: un objeto plano con los
        # campos como claves.
        assert '{"identidad": "Gestor-CLI"' in txt
        # Array envolvente y bloque Markdown, también observados.
        assert "[ {" in txt
        assert "```json" in txt
        # Objeto contenedor con una clave que agrupa todo (sin usar el patrón
        # `{"hallazgos"` como ejemplo a seguir, sólo nombrarlo).
        assert "clave" in txt.lower() and "hallazgos" in txt.lower()


# --- integración con ejecutar_agente() -----------------------------------

class TestIntegracionConRunner:
    def test_con_cliente_eco(self, db):
        entrada = _entrada()
        salida = ejecutar_agente(entrada, ClienteEco(), Descubridor())
        assert salida.resultado.startswith("[eco] ")
        assert salida.meta.modelo == "eco"
        assert salida.problemas == []

    def test_con_cliente_que_devuelve_hallazgos_validos(self, db):
        # JSON Lines (TF-0029): un objeto de hallazgo por línea.
        texto = json.dumps({"campo": "identidad", "valor": "Taskflow", "estado": "confirmed",
                             "origen": "file", "confianza": "ALTA"})

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
                # JSON Lines (TF-0029): un objeto de hallazgo por línea.
                texto = "\n".join([
                    json.dumps({"campo": "identidad", "valor": "Taskflow",
                                "estado": "confirmed", "origen": "file", "confianza": "ALTA"}),
                    json.dumps({"campo": "tipo_proyecto", "valor": "SaaS",
                                "estado": "discovered", "origen": "repository", "confianza": "MEDIA"}),
                ])
                return _resp(texto)

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

    def test_brief_del_cliente_llega_al_prompt_como_fuente_separada(self, db):
        """El caso obligatorio del checkpoint: el brief verbatim del cliente
        debe llegar al Descubridor como una sección propia, claramente
        distinguible de las preguntas y de cualquier metadata, y su
        contenido no debe perderse ni reinterpretarse.
        """
        texto_cliente = (
            "Quiero un proyecto nuevo que sea una calculadora "
            "que solo suma números negativos."
        )

        class _ClienteCapturaPrompt:
            def __init__(self):
                self.ultimo_prompt = None

            def completar(self, prompt, opciones):
                self.ultimo_prompt = prompt
                return _resp(json.dumps({
                    "campo": "identidad", "valor": "Calculadora", "estado": "confirmed",
                    "origen": "conversation", "confianza": "ALTA",
                }))

        repo_exp = RepositorioExpedientes()
        repo_acc = RepositorioAcciones()
        repo_briefs = RepositorioBriefs()
        codigo = repo_exp.crear("Demo")
        repo_briefs.registrar(codigo, texto_cliente)

        cliente = _ClienteCapturaPrompt()
        resultado = ejecutar_orquestador(
            codigo, cliente, Descubridor(),
            repo_expedientes=repo_exp, repo_acciones=repo_acc, repo_briefs=repo_briefs,
        )

        assert resultado.accion == AccionOrquestador.INVESTIGAR
        prompt = cliente.ultimo_prompt
        # El texto exacto del cliente sobrevive íntegro, bajo su propio
        # encabezado, separado de las preguntas de descubrimiento.
        assert "## Comunicación del cliente" in prompt
        assert texto_cliente in prompt
        assert prompt.index("## Comunicación del cliente") < prompt.index("- identidad:")

    def test_hallazgo_con_origen_user_del_agente_se_sanea_a_agent(self, db):
        """Si el modelo, pese a la instrucción del prompt, devolviera
        origen="user", `fusion.py` (TF-0027, sin cambios) ya lo sanea a
        `AGENT` — se verifica end-to-end con el agente real.
        """
        class _ClienteQueIgnoraLaInstruccion:
            def completar(self, prompt, opciones):
                # JSON Lines (TF-0029): un objeto de hallazgo por línea.
                texto = json.dumps({"campo": "identidad", "valor": "Taskflow",
                                     "estado": "confirmed", "origen": "user", "confianza": "ALTA"})
                return _resp(texto)

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
