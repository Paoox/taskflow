"""TF-0023 — Pruebas del agente Documentador (unitarias, sin runner)."""
import json
from pathlib import Path

import pytest

from src.agentes.contrato import Artefacto, EntradaAgente, Meta, SalidaAgente
from src.agentes.documentador import Documentador
from src.ai.cliente import RespuestaIA
from src.ai.prompts import cargar_prompt

_RAIZ = Path(__file__).resolve().parents[1]


def _entrada(ticket="TF-0023", **kw):
    base = dict(objetivo="obj", contexto="ctx", restricciones=["r1"],
                criterios_aceptacion=["c1"], archivos_relevantes=["f1"])
    base.update(kw)
    return EntradaAgente(ticket=ticket, **base)


def _resp(texto):
    return RespuestaIA(texto=texto, tokens_entrada=1, tokens_salida=1, modelo="x")


# --- construir_prompt (D6) ------------------------------------------

class TestConstruirPrompt:
    def test_incluye_prompt_base_y_campos_de_entrada(self):
        p = Documentador().construir_prompt(_entrada(objetivo="OBJ-X"))
        assert cargar_prompt("documentador").rstrip() in p
        assert "- ticket: TF-0023" in p
        assert "- objetivo: OBJ-X" in p
        assert "ctx" in p
        assert "- r1" in p and "- c1" in p and "- f1" in p

    def test_determinista(self):
        e = _entrada()
        assert Documentador().construir_prompt(e) == Documentador().construir_prompt(e)

    def test_listas_vacias_muestran_ninguno(self):
        p = Documentador().construir_prompt(
            _entrada(restricciones=[], criterios_aceptacion=[], archivos_relevantes=[]))
        assert p.count("(ninguno)") == 3

    def test_contexto_vacio_muestra_marcador(self):
        p = Documentador().construir_prompt(_entrada(contexto="   "))
        assert "(sin contexto)" in p


# --- parsear (D2 / D5) --------------------------------------------

class TestParsear:
    def test_texto_no_json_fallback_con_artefacto(self):
        s = Documentador().parsear(_resp("esto no es json"), _entrada("TF-1"))
        assert s.resultado == "esto no es json"
        assert s.meta == Meta()  # lo rellena el runner
        assert len(s.artefactos) == 1
        a = s.artefactos[0]
        assert (a.ruta, a.tipo, a.contenido) == (
            "docs/tickets/TF-1.md", "markdown", "esto no es json")

    def test_json_dict_con_resultado_sin_artefactos(self):
        datos = SalidaAgente(resultado="R", cambios=["x"]).to_dict()
        s = Documentador().parsear(_resp(json.dumps(datos)), _entrada("TF-2"))
        assert s.resultado == "R"
        assert s.cambios == ["x"]
        assert [a.ruta for a in s.artefactos] == ["docs/tickets/TF-2.md"]
        assert s.artefactos[0].contenido == "R"

    def test_json_dict_con_artefacto_propio_no_se_duplica(self):
        datos = SalidaAgente(
            resultado="R",
            artefactos=[Artefacto("docs/tickets/TF-3.md", "MODELO", "markdown")],
        ).to_dict()
        s = Documentador().parsear(_resp(json.dumps(datos)), _entrada("TF-3"))
        arts = [a for a in s.artefactos if a.ruta == "docs/tickets/TF-3.md"]
        assert len(arts) == 1 and arts[0].contenido == "MODELO"

    @pytest.mark.parametrize("texto", [
        "[1, 2]", '{"sin": "resultado"}', "null", "42", '"cadena"',
    ])
    def test_json_no_utilizable_va_a_fallback(self, texto):
        s = Documentador().parsear(_resp(texto), _entrada("TF-4"))
        assert s.resultado == texto
        assert s.artefactos[0].ruta == "docs/tickets/TF-4.md"
        assert s.artefactos[0].contenido == texto

    def test_no_anade_texto_propio_en_fallback(self):
        s = Documentador().parsear(_resp("contenido íntegro del modelo"), _entrada("TF-5"))
        assert s.resultado == "contenido íntegro del modelo"
        assert s.artefactos[0].contenido == "contenido íntegro del modelo"

    def test_no_escribe_en_disco(self):
        docs = _RAIZ / "docs" / "tickets"
        antes = sorted(p.name for p in docs.iterdir())
        Documentador().parsear(_resp("x"), _entrada("TF-9999"))
        assert sorted(p.name for p in docs.iterdir()) == antes
        assert not (docs / "TF-9999.md").exists()


# --- prompt real -------------------------------------------------

class TestPrompt:
    def test_no_vacio_y_sin_logica(self):
        txt = cargar_prompt("documentador")
        assert isinstance(txt, str) and txt.strip()
        for marca in ("{{", "%(", "import ", "```python"):
            assert marca not in txt

    def test_instruye_no_afirmar_escritura(self):
        txt = cargar_prompt("documentador").lower()
        assert "no afirmes que has escrito" in txt
