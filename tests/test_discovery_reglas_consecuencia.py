"""Pruebas de `src.discovery.reglas_consecuencia` (TF-0032, A2/A3).

Funciones puras: no tocan base de datos ni ningún `ClienteIA`. Mismo helper
`_responder` que el resto de `tests/test_discovery_*.py`.
"""
from src.discovery.reglas_consecuencia import (
    HallazgoConsecuencia, evaluar_reglas,
)
from src.expediente.modelo import RespuestaFormulario
from src.formulario.preguntas import PREGUNTAS
from src.formulario.respuestas import serializar_respuesta


def _responder(respuestas: list, pregunta_id: str, valor) -> list:
    pregunta = PREGUNTAS[pregunta_id]
    texto = serializar_respuesta(pregunta, valor)
    nueva = RespuestaFormulario(
        id=len(respuestas) + 1, codigo="PROY-001", pregunta_id=pregunta_id,
        pregunta_texto=pregunta.texto, tipo_pregunta=pregunta.tipo_pregunta,
        respuesta=texto, respondido_en="2026-09-11 10:00:00", accion_id_origen=None,
    )
    return respuestas + [nueva]


class TestReglaSuscripcionSinDato:
    """Caso real ya auditado: cobra + "no hay que recordar nada"."""

    def test_detecta_la_contradiccion(self):
        r = _responder([], "monetizacion", "Sí, de alguna forma")
        r = _responder(r, "dato_recordar", "No")
        hallazgos = evaluar_reglas("PROY-001", r)
        assert len(hallazgos) == 1
        h = hallazgos[0]
        assert isinstance(h, HallazgoConsecuencia)
        assert h.tipo == "contradiccion"
        assert h.dominio == "datos"
        assert h.etiqueta == "existencia_de_dato"
        assert len(h.afirmaciones) == 2

    def test_no_dispara_si_no_cobra(self):
        r = _responder([], "monetizacion", "No, es gratis")
        r = _responder(r, "dato_recordar", "No")
        assert evaluar_reglas("PROY-001", r) == []

    def test_no_dispara_si_dato_recordar_es_si(self):
        """Ya reconoce que sí hay que guardar algo: sin conflicto."""
        r = _responder([], "monetizacion", "Sí, de alguna forma")
        r = _responder(r, "dato_recordar", "Sí")
        assert evaluar_reglas("PROY-001", r) == []

    def test_no_dispara_sin_ambas_respuestas(self):
        r = _responder([], "monetizacion", "Sí, de alguna forma")
        assert evaluar_reglas("PROY-001", r) == []

    def test_afirmaciones_referencian_las_filas_reales(self):
        r = _responder([], "monetizacion", "Sí, de alguna forma")
        r = _responder(r, "dato_recordar", "No")
        h = evaluar_reglas("PROY-001", r)[0]
        assert h.respuestas_relacionadas == [r[0].id, r[1].id]
        origenes = {a["origen"] for a in h.afirmaciones}
        assert origenes == {f"respuesta_formulario#{r[0].id}", f"respuesta_formulario#{r[1].id}"}


class TestReglaDeOroA2:
    """Ninguna regla infiere una regla de negocio no forzosa (ej. "admin
    aprueba/rechaza" -> "existe aprobación previa a publicar") — la
    corrección explícita de A2. El catálogo actual ni siquiera tiene una
    pregunta de "aprobación de contenido", así que esta prueba confirma
    que evaluar_reglas() nunca produce un hallazgo a partir únicamente de
    `administrador_tipo_acciones`."""

    def test_permisos_de_administrador_nunca_generan_un_hallazgo_por_si_solos(self):
        r = _responder([], "administrador_tipo_nombre", "el dueño")
        r = _responder(r, "administrador_tipo_acciones", ["Ver información", "Controlar/administrar todo el proyecto"])
        assert evaluar_reglas("PROY-001", r) == []


class TestEvaluarReglasNuncaLanza:
    def test_lista_vacia(self):
        assert evaluar_reglas("PROY-001", []) == []
