"""Pruebas de `src.discovery.interpretacion_directa` (TF-0030).

Función pura sobre una lista de `RespuestaFormulario` — igual estilo que
`tests/test_formulario_arbol.py`: se construye la lista a mano con un
helper (`_responder`) que serializa igual que lo haría el llamador real. No
toca base de datos ni ningún `ClienteIA`.
"""
from src.discovery.interpretacion_directa import EntidadPropuesta, interpretar_directo
from src.expediente.modelo import RespuestaFormulario
from src.formulario.preguntas import PREGUNTAS
from src.formulario.respuestas import serializar_respuesta
from src.proyectos.estado import NivelConfianza


def _responder(respuestas: list, pregunta_id: str, valor) -> list:
    pregunta = PREGUNTAS[pregunta_id]
    texto = serializar_respuesta(pregunta, valor)
    nueva = RespuestaFormulario(
        id=len(respuestas) + 1, codigo="PROY-001", pregunta_id=pregunta_id,
        pregunta_texto=pregunta.texto, tipo_pregunta=pregunta.tipo_pregunta,
        respuesta=texto, respondido_en="2026-09-11 10:00:00", accion_id_origen=None,
    )
    return respuestas + [nueva]


class TestNuncaLlamaAlLLM:
    def test_la_funcion_no_recibe_ningun_cliente_ia(self):
        """La prueba más fuerte de "nunca llama al LLM": la propia firma de
        `interpretar_directo` no acepta un `ClienteIA` — no hay forma de que
        este módulo dispare una llamada al proveedor."""
        import inspect
        firma = inspect.signature(interpretar_directo)
        assert list(firma.parameters) == ["respuestas"]


class TestPlataforma:
    def test_navegador_directo_genera_un_requisito(self):
        r = _responder([], "plataforma", "Desde un navegador web")
        propuestas = interpretar_directo(r)
        assert len(propuestas) == 1
        p = propuestas[0]
        assert p.tipo == "requisito"
        assert "navegador web" in p.campos["descripcion"]
        assert p.confianza == NivelConfianza.ALTA
        assert p.respuesta_id == r[0].id

    def test_no_estoy_seguro_no_genera_nada(self):
        r = _responder([], "plataforma", "No estoy seguro todavía")
        assert interpretar_directo(r) == []

    def test_varias_con_detalle_genera_un_requisito_por_seleccion(self):
        r = _responder([], "plataforma", "En varios de estos lugares")
        r = _responder(r, "plataforma_detalle", ["Celular", "Desde un navegador web"])
        propuestas = interpretar_directo(r)
        descripciones = {p.campos["descripcion"] for p in propuestas}
        assert len(propuestas) == 2
        assert any("celular" in d for d in descripciones)
        assert any("navegador web" in d for d in descripciones)
        # La fuente de cada uno es la fila de `plataforma_detalle`, no la de
        # `plataforma` (es la fila donde de verdad se declaró cuál).
        assert all(p.respuesta_id == r[-1].id for p in propuestas)

    def test_varias_sin_detalle_aun_no_genera_nada(self):
        r = _responder([], "plataforma", "En varios de estos lugares")
        assert interpretar_directo(r) == []

    def test_sin_responder_no_genera_nada(self):
        assert interpretar_directo([]) == []


class TestPlataformaOffline:
    def test_si_genera_requisito_offline(self):
        r = _responder([], "plataforma_offline", "Sí")
        propuestas = interpretar_directo(r)
        assert len(propuestas) == 1
        assert "sin conexión" in propuestas[0].campos["descripcion"]
        assert propuestas[0].confianza == NivelConfianza.ALTA

    def test_no_no_genera_nada(self):
        r = _responder([], "plataforma_offline", "No")
        assert interpretar_directo(r) == []

    def test_no_se_no_genera_nada(self):
        r = _responder([], "plataforma_offline", "No sé")
        assert interpretar_directo(r) == []


class TestMonetizacion:
    def test_si_genera_requisito_de_cobro(self):
        r = _responder([], "monetizacion", "Sí, de alguna forma")
        propuestas = interpretar_directo(r)
        assert len(propuestas) == 1
        assert "cobrar" in propuestas[0].campos["descripcion"]

    def test_no_no_genera_nada(self):
        r = _responder([], "monetizacion", "No, es gratis")
        assert interpretar_directo(r) == []

    def test_no_decidido_no_genera_nada(self):
        r = _responder([], "monetizacion", "Todavía no lo he decidido")
        assert interpretar_directo(r) == []

    def test_si_mas_forma_genera_dos_requisitos(self):
        r = _responder([], "monetizacion", "Sí, de alguna forma")
        r = _responder(r, "monetizacion_forma", "Suscripción")
        propuestas = interpretar_directo(r)
        assert len(propuestas) == 2
        descripciones = " ".join(p.campos["descripcion"] for p in propuestas)
        assert "suscripción" in descripciones.lower()

    def test_las_7_formas_de_monetizacion_tienen_texto_fijo_mapeado(self):
        """TF-0033 amplió `monetizacion_forma` de 4 a 7 opciones — todas
        siguen siendo autocontenidas, ninguna queda sin requisito fijo."""
        from src.formulario.preguntas import PREGUNTAS
        for opcion in PREGUNTAS["monetizacion_forma"].opciones:
            r = _responder([], "monetizacion", "Sí, de alguna forma")
            r = _responder(r, "monetizacion_forma", opcion)
            propuestas = interpretar_directo(r)
            assert len(propuestas) == 2, f"opción {opcion!r} no generó su segundo requisito"


class TestControlesDeFlujoYCompuertas:
    """Los controles `*_continuar` y las "compuertas" del árbol nunca
    generan entidades (regla 16 del ticket)."""

    def test_continuar_no_genera_nada(self):
        r = _responder([], "perfil_usuario_continuar", "No")
        r = _responder(r, "funcionalidad_declarada_continuar", "Sí")
        r = _responder(r, "monetizacion_plan_continuar", "No")
        r = _responder(r, "dato_recordar_detalle_continuar", "No")
        assert interpretar_directo(r) == []

    def test_compuertas_no_generan_nada(self):
        r = _responder([], "nuevo_o_existente", "Nuevo")
        r = _responder(r, "personas_gate", "Yo solo / todos igual")
        r = _responder(r, "contenido_gate", "No")
        r = _responder(r, "dato_recordar", "No")
        assert interpretar_directo(r) == []

    def test_experiencia_persona_permisos_residual_por_si_sola_no_genera_nada(self):
        """Requiere ir emparejada con texto libre — se delega entera al LLM
        (`src.discovery.interpretacion_llm`), no se interpreta aquí."""
        r = _responder([], "experiencia_persona_permisos_residual", ["Ver información", "Agregar cosas nuevas"])
        assert interpretar_directo(r) == []


class TestConfianzaSiempreAlta:
    def test_todas_las_propuestas_directas_son_confianza_alta(self):
        r = _responder([], "plataforma", "Desde el celular")
        r = _responder(r, "plataforma_offline", "Sí")
        r = _responder(r, "monetizacion", "Sí, de alguna forma")
        r = _responder(r, "monetizacion_forma", "Pago único")
        propuestas = interpretar_directo(r)
        # plataforma + offline + monetizacion + monetizacion_forma = 4 propuestas.
        assert len(propuestas) == 4
        assert all(p.confianza == NivelConfianza.ALTA for p in propuestas)
        assert all(isinstance(p, EntidadPropuesta) for p in propuestas)
