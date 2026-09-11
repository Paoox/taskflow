"""Pruebas del agente InterpreteFormulario (TF-0030).

Mismo patrón que `tests/test_descubridor.py`: construcción del prompt,
`parsear()` como passthrough puro, e integración con `ejecutar_agente()`
usando un `ClienteIA` de prueba (sin red, sin proveedor real).
"""
from pathlib import Path

from src.agentes.contrato import EntradaAgente
from src.agentes.interprete_formulario import InterpreteFormulario
from src.agentes.runner import ejecutar_agente
from src.ai.cliente import RespuestaIA
from src.ai.prompts import cargar_prompt
from src.repositorios.acciones import COMPLETADA, RepositorioAcciones

_RAIZ = Path(__file__).resolve().parents[1]


def _entrada(ticket="PROY-001", **kw):
    base = dict(
        objetivo="Interpretar las respuestas de texto libre del formulario de Discovery",
        contexto="(id=1) ¿Qué problema quieres resolver?\nOrganizar pedidos de mi cafetería.",
    )
    base.update(kw)
    return EntradaAgente(ticket=ticket, **base)


def _resp(texto):
    return RespuestaIA(texto=texto, tokens_entrada=1, tokens_salida=1, modelo="x")


class TestPromptExiste:
    def test_archivo_de_prompt_existe(self):
        ruta = _RAIZ / "src" / "ai" / "prompts" / "interprete_formulario.md"
        assert ruta.is_file()

    def test_cargar_prompt_no_lanza(self):
        assert "InterpreteFormulario" in cargar_prompt("interprete_formulario")


class TestConstruirPrompt:
    def test_incluye_instrucciones_base_y_contexto_de_entrada(self):
        p = InterpreteFormulario().construir_prompt(_entrada())
        assert "## 1. TAREA" in p
        assert "## 8. AHORA GENERA" in p
        assert "Organizar pedidos de mi cafetería." in p

    def test_contexto_va_entre_las_marcas(self):
        p = InterpreteFormulario().construir_prompt(_entrada())
        # Las marcas también se mencionan en la prosa de instrucciones (entre
        # comillas invertidas) — se busca la línea propia de la marca real,
        # no esa mención, mismo criterio que `tests/test_descubridor.py`.
        ini = p.index("\n<<<RESPUESTAS_DEL_FORMULARIO\n")
        fin = p.index("\nRESPUESTAS_DEL_FORMULARIO>>>\n")
        ctx = p.index("Organizar pedidos de mi cafetería.")
        assert ini < ctx < fin

    def test_ticket_no_aparece_en_la_zona_de_respuestas(self):
        codigo_fuga = "PROY-777"
        p = InterpreteFormulario().construir_prompt(_entrada(ticket=codigo_fuga))
        ini = p.index("\n<<<RESPUESTAS_DEL_FORMULARIO\n")
        fin = p.index("\nRESPUESTAS_DEL_FORMULARIO>>>\n")
        zona = p[ini:fin]
        assert codigo_fuga not in zona

    def test_contexto_vacio_no_rompe_el_prompt(self):
        p = InterpreteFormulario().construir_prompt(_entrada(contexto=""))
        assert "<<<RESPUESTAS_DEL_FORMULARIO" in p
        assert "RESPUESTAS_DEL_FORMULARIO>>>" in p


class TestParsear:
    def test_parsear_es_passthrough(self):
        salida = InterpreteFormulario().parsear(_resp('{"tipo": "requisito"}'), _entrada())
        assert salida.resultado == '{"tipo": "requisito"}'
        assert salida.problemas == []
        assert salida.cambios == []

    def test_parsear_no_interpreta_json(self):
        """La interpretación real vive en
        `src.discovery.interpretacion_llm.parsear_entidades` — este método
        nunca la duplica, ni siquiera para detectar JSON inválido."""
        salida = InterpreteFormulario().parsear(_resp("esto no es json"), _entrada())
        assert salida.resultado == "esto no es json"


class TestIntegracionConRunner:
    def test_ejecutar_agente_completa_y_registra_accion(self, db):
        repo = RepositorioAcciones()
        entrada = _entrada()
        salida = ejecutar_agente(
            entrada,
            cliente=_ClienteFalso('{"tipo": "requisito", "respuesta_id": 1, "descripcion": "x"}'),
            definicion=InterpreteFormulario(),
            repositorio=repo,
        )
        assert salida.resultado == '{"tipo": "requisito", "respuesta_id": 1, "descripcion": "x"}'
        acciones = repo.listar(ticket="PROY-001")
        assert len(acciones) == 1
        assert acciones[0]["estado"] == COMPLETADA
        assert acciones[0]["tipo"] == "interpretar_formulario"
        assert acciones[0]["actor"] == "agente:interprete_formulario"


class _ClienteFalso:
    def __init__(self, texto):
        self._texto = texto

    def completar(self, prompt, opciones):
        return RespuestaIA(texto=self._texto, tokens_entrada=1, tokens_salida=1, modelo="fake")
