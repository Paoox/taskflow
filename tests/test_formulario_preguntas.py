"""Pruebas del catálogo de preguntas (`src.formulario.preguntas`).

Sanity checks estructurales: cada pregunta es consistente consigo misma
(OPCION_CERRADA siempre trae opciones, TEXTO_LIBRE nunca las trae,
`multiple` solo aplica a OPCION_CERRADA) y el catálogo no repite
`pregunta_id`. No requiere base de datos.
"""
import pytest

from src.expediente.modelo import TipoPregunta
from src.formulario.preguntas import (
    OPCION_PAGA_A_OTROS_NO, OPCION_PAGA_A_OTROS_SI, PENDIENTE_DE_REDACCION,
    PREGUNTAS, DefinicionPregunta,
)


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

    def test_experiencia_persona_permisos_residual_es_multiple(self):
        assert PREGUNTAS["experiencia_persona_permisos_residual"].multiple is True
        assert "Otra cosa" in PREGUNTAS["experiencia_persona_permisos_residual"].opciones

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


class TestRedaccionDe01b:
    """La redacción final debe respetar el flujo llega -> ve -> hace ->
    obtiene (decisión cerrada de la especificación, §02.2) — no basta con
    que el texto no esté vacío, tiene que nombrar las 4 etapas."""

    def test_ninguna_de_las_tres_conserva_el_placeholder(self):
        for pid in (
            "experiencia_persona_narrativa", "experiencia_persona_frecuencia",
            "experiencia_persona_primera_vez",
        ):
            assert PENDIENTE_DE_REDACCION not in PREGUNTAS[pid].texto, pid

    def test_narrativa_nombra_las_cuatro_etapas_del_flujo(self):
        texto = PREGUNTAS["experiencia_persona_narrativa"].texto.lower()
        for etapa in ("llega", "ve", "hacer", "obtiene"):
            assert etapa in texto, f"falta la etapa {etapa!r} en la narrativa"

    def test_frecuencia_sigue_siendo_tri_state_una_vez_o_regular(self):
        p = PREGUNTAS["experiencia_persona_frecuencia"]
        assert p.tipo_pregunta == TipoPregunta.OPCION_CERRADA
        assert p.opciones == ("Una sola vez", "Regularmente")

    def test_primera_vez_pregunta_por_la_diferencia_con_usos_posteriores(self):
        texto = PREGUNTAS["experiencia_persona_primera_vez"].texto.lower()
        assert "primera vez" in texto
        assert "siguientes" in texto or "posteriores" in texto


class TestRedaccionDeGateB:
    """Gate B debe estar orientado a "pagar", nunca reutilizar el
    vocabulario de "cobrar" del Gate A (contrato explícito de la revisión)."""

    def test_puerta_no_tiene_placeholder(self):
        assert PENDIENTE_DE_REDACCION not in PREGUNTAS["monetizacion_salida"].texto

    def test_puerta_menciona_pagar_no_cobrar(self):
        texto = PREGUNTAS["monetizacion_salida"].texto.lower()
        assert "paga" in texto or "entrega dinero" in texto
        # La pregunta central (el verbo principal) debe ser "pagar", nunca
        # "cobrar" — "cobrado" puede aparecer solo como referencia a dinero
        # YA recibido por el Gate A que luego se reparte (ej. comisiones).
        assert texto.startswith("¿tu proyecto le paga") or texto.startswith("¿tu proyecto le entrega dinero")

    def test_opciones_son_propias_no_las_del_gate_a(self):
        opciones = PREGUNTAS["monetizacion_salida"].opciones
        assert OPCION_PAGA_A_OTROS_SI in opciones
        assert OPCION_PAGA_A_OTROS_NO in opciones
        # Ninguna opción reutiliza el texto de cobro del Gate A.
        assert "gratis" not in " ".join(opciones).lower()

    def test_gate_a_conserva_su_propio_vocabulario_de_cobro(self):
        """Verificación negativa: el Gate A no se vio afectado por el
        cambio de opciones del Gate B."""
        opciones_gate_a = PREGUNTAS["monetizacion"].opciones
        assert "No, es gratis" in opciones_gate_a
        assert "Sí, de alguna forma" in opciones_gate_a

    def test_resto_del_sub_arbol_de_gate_b_ya_estaba_orientado_a_pagar(self):
        """`monetizacion_salida_forma`/`incumplimiento`/`control` no eran
        SLOT — se conservan tal cual, sin placeholder."""
        for pid in (
            "monetizacion_salida_forma", "monetizacion_salida_incumplimiento",
            "monetizacion_salida_control",
        ):
            assert PENDIENTE_DE_REDACCION not in PREGUNTAS[pid].texto


class TestSintesisTodaviaTienePendientesFueraDeAlcance:
    """Esta revisión implementó el mecanismo de síntesis (dominio 14), pero
    no redactó las 4 excepciones universales — no se pidió en este ticket,
    así que deben seguir marcadas explícitamente (evita que alguien crea
    que ya tienen contenido final)."""

    def test_las_4_excepciones_siguen_con_placeholder(self):
        for pid in (
            "sintesis_abandono", "sintesis_reanudacion",
            "sintesis_concurrencia", "sintesis_peor_caso",
        ):
            assert PENDIENTE_DE_REDACCION in PREGUNTAS[pid].texto, pid
