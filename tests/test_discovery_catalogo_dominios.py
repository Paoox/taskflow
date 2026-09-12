"""Pruebas de `src.discovery.catalogo_dominios` (TF-0032, A1).

Funciones puras: no tocan base de datos. Mismo helper `_responder` que el
resto de `tests/test_discovery_*.py`.
"""
from src.discovery.catalogo_dominios import CATALOGO_DOMINIOS, dominios_activos, resolver_pregunta
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


class TestCatalogoDominios:
    def test_cubre_todas_las_preguntas_de_contenido_real(self):
        """No cubre los 4 controles de bucle puros (nunca tiene sentido
        reactivarlos) — el resto del catálogo de 27 preguntas sí."""
        controles_de_flujo = {
            "perfil_usuario_continuar", "administrador_tipo_continuar",
            "funcionalidad_declarada_continuar", "dato_recordar_detalle_continuar",
        }
        esperadas = set(PREGUNTAS) - controles_de_flujo
        assert set(CATALOGO_DOMINIOS) == esperadas

    def test_ninguna_entrada_apunta_a_un_control_de_flujo(self):
        assert "perfil_usuario_continuar" not in CATALOGO_DOMINIOS
        assert "administrador_tipo_continuar" not in CATALOGO_DOMINIOS
        assert "funcionalidad_declarada_continuar" not in CATALOGO_DOMINIOS
        assert "dato_recordar_detalle_continuar" not in CATALOGO_DOMINIOS


class TestDominiosActivos:
    def test_solo_incluye_dominios_de_preguntas_ya_respondidas(self):
        r = _responder([], "problema_objetivo", "algo")
        activos = dominios_activos(r)
        assert set(activos) == {"identidad"}
        assert "proposito" in activos["identidad"]

    def test_varios_dominios_a_la_vez(self):
        r = _responder([], "problema_objetivo", "algo")
        r = _responder(r, "dato_recordar_detalle", "el historial")
        activos = dominios_activos(r)
        assert set(activos) == {"identidad", "datos"}

    def test_sin_respuestas_no_hay_dominios_activos(self):
        assert dominios_activos([]) == {}

    def test_etiquetas_ordenadas_y_sin_duplicados(self):
        r = _responder([], "problema_objetivo", "algo")
        r = _responder(r, "objetivo_proyecto_existente", "otra cosa")  # misma etiqueta que arriba
        activos = dominios_activos(r)
        assert activos["identidad"].count("proposito") == 1


class TestResolverPregunta:
    def test_resuelve_una_combinacion_conocida(self):
        assert resolver_pregunta("datos", "existencia_de_dato") == "dato_recordar"

    def test_combinacion_desconocida_devuelve_none_sin_inventar(self):
        assert resolver_pregunta("marca", "logo") is None
        assert resolver_pregunta("identidad", "etiqueta_inventada") is None

    def test_proposito_resuelve_a_la_pregunta_universal(self):
        """('identidad', 'proposito') es compartida por problema_objetivo y
        objetivo_proyecto_existente — la canónica es la universal, no la
        condicional a "ya tengo algo construido"."""
        assert resolver_pregunta("identidad", "proposito") == "problema_objetivo"
