"""Pruebas del catálogo de preguntas (`src.formulario.preguntas`).

Sanity checks estructurales: cada pregunta es consistente consigo misma
(OPCION_CERRADA siempre trae opciones, TEXTO_LIBRE nunca las trae,
`multiple` solo aplica a OPCION_CERRADA) y el catálogo no repite
`pregunta_id`. No requiere base de datos.
"""
import pytest

from src.expediente.modelo import TipoPregunta
from src.formulario.preguntas import PREGUNTAS, DefinicionPregunta


class TestCatalogo:
    def test_no_esta_vacio(self):
        assert len(PREGUNTAS) > 0

    def test_todas_las_claves_coinciden_con_pregunta_id(self):
        for clave, pregunta in PREGUNTAS.items():
            assert clave == pregunta.pregunta_id

    def test_ninguna_pregunta_nombra_tecnologia_conocida(self):
        """Principio general del checkpoint: nunca preguntar conceptos
        técnicos. No es una prueba exhaustiva de "buen lenguaje", solo una
        red de seguridad contra términos obviamente técnicos coláandose."""
        prohibidos = [
            "API", "REST", "JWT", "SQL", "SPA", "microservicio", "Docker",
            "base de datos", "backend", "frontend", "framework", "React",
            "Angular", "endpoint",
        ]
        for pregunta in PREGUNTAS.values():
            texto_lower = pregunta.texto.lower()
            for termino in prohibidos:
                assert termino.lower() not in texto_lower, (
                    f"{pregunta.pregunta_id!r} menciona un término técnico: {termino!r}"
                )


class TestDefinicionPregunta:
    def test_opcion_cerrada_requiere_opciones(self):
        with pytest.raises(ValueError):
            DefinicionPregunta(
                pregunta_id="x", texto="¿x?", tipo_pregunta=TipoPregunta.OPCION_CERRADA,
            )

    def test_texto_libre_no_admite_opciones(self):
        with pytest.raises(ValueError):
            DefinicionPregunta(
                pregunta_id="x", texto="¿x?", tipo_pregunta=TipoPregunta.TEXTO_LIBRE,
                opciones=("a", "b"),
            )

    def test_multiple_requiere_opcion_cerrada(self):
        with pytest.raises(ValueError):
            DefinicionPregunta(
                pregunta_id="x", texto="¿x?", tipo_pregunta=TipoPregunta.TEXTO_LIBRE,
                multiple=True,
            )

    def test_pregunta_cerrada_valida_se_construye(self):
        p = DefinicionPregunta(
            pregunta_id="x", texto="¿x?", tipo_pregunta=TipoPregunta.OPCION_CERRADA,
            opciones=("a", "b"),
        )
        assert p.opciones == ("a", "b")


class TestPreguntasClave:
    def test_primera_pregunta_es_nuevo_o_existente(self):
        assert "nuevo_o_existente" in PREGUNTAS
        assert PREGUNTAS["nuevo_o_existente"].tipo_pregunta == TipoPregunta.OPCION_CERRADA
        assert PREGUNTAS["nuevo_o_existente"].obligatoria is True

    def test_administrador_tipo_acciones_es_multiple(self):
        assert PREGUNTAS["administrador_tipo_acciones"].multiple is True
        assert "Otra cosa" in PREGUNTAS["administrador_tipo_acciones"].opciones

    def test_plataforma_detalle_es_multiple(self):
        assert PREGUNTAS["plataforma_detalle"].multiple is True

    def test_problema_objetivo_es_obligatoria_y_libre(self):
        p = PREGUNTAS["problema_objetivo"]
        assert p.obligatoria is True
        assert p.tipo_pregunta == TipoPregunta.TEXTO_LIBRE

    def test_restriccion_tecnica_es_la_unica_via_de_stack_declarado(self):
        """No hay ninguna otra pregunta que solicite tecnología concreta."""
        preguntas_con_stack = [
            p for p in PREGUNTAS.values()
            if "tecnología" in p.texto.lower() or "tecnologia" in p.texto.lower()
        ]
        assert [p.pregunta_id for p in preguntas_con_stack] == ["restriccion_tecnica"]
