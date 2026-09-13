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
    corrección explícita de A2. `contenido_aprobacion` (dominio 03) siempre
    se pregunta explícitamente (ver `arbol.py`); esta prueba confirma que
    `evaluar_reglas()` nunca produce un hallazgo a partir únicamente de las
    señales de permisos de `01b`."""

    def test_permisos_residuales_nunca_generan_un_hallazgo_por_si_solos(self):
        r = _responder(
            [], "experiencia_persona_permisos_residual",
            ["Ver información", "Controlar/administrar todo el proyecto"],
        )
        assert evaluar_reglas("PROY-001", r) == []


class TestEvaluarReglasNuncaLanza:
    def test_lista_vacia(self):
        assert evaluar_reglas("PROY-001", []) == []


class TestReglaSintesisRechazada:
    """TF-0033, dominio 14 §3.4: `sintesis_confirmacion="No"` debe producir
    un `Gap` explícito, sin inventar a qué dominio pertenece el error."""

    def test_no_produce_un_gap_sin_pregunta_catalogada(self):
        from src.discovery.catalogo_dominios import resolver_pregunta

        r = _responder([], "sintesis_confirmacion", "No")
        hallazgos = evaluar_reglas("PROY-001", r)
        assert len(hallazgos) == 1
        h = hallazgos[0]
        assert h.tipo == "gap"
        assert h.dominio == "sintesis"
        assert h.etiqueta == "flujo_rechazado"
        # A1: nunca se inventa una pregunta para reactivar — esta combinación
        # deliberadamente no tiene entrada en CATALOGO_DOMINIOS.
        assert resolver_pregunta(h.dominio, h.etiqueta) is None

    def test_si_no_produce_ningun_hallazgo(self):
        r = _responder([], "sintesis_confirmacion", "Sí")
        assert evaluar_reglas("PROY-001", r) == []

    def test_sin_responder_no_produce_ningun_hallazgo(self):
        assert evaluar_reglas("PROY-001", []) == []

    def test_motivo_no_afirma_saber_que_dominio_fallo(self):
        """La regla de oro (A2) exige no inventar una inferencia semántica:
        el motivo debe ser honesto sobre la limitación, no señalar un
        dominio culpable inexistente."""
        r = _responder([], "sintesis_confirmacion", "No")
        h = evaluar_reglas("PROY-001", r)[0]
        assert "revisión humana" in h.motivo.lower()
