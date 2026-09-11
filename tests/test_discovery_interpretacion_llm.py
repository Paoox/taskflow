"""Pruebas de `src.discovery.interpretacion_llm` (TF-0030).

`construir_contexto` y `parsear_entidades` son funciones puras: no tocan
base de datos ni ningún `ClienteIA`. Mismo helper `_responder` que
`tests/test_formulario_arbol.py` para construir listas de
`RespuestaFormulario` a mano.
"""
import json

from src.discovery.interpretacion_llm import construir_contexto, parsear_entidades
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


# --- construir_contexto -----------------------------------------------

class TestConstruirContexto:
    def test_texto_libre_llega_al_contexto(self):
        r = _responder([], "problema_objetivo", "Quiero organizar los pedidos de mi cafetería.")
        contexto, ids = construir_contexto(r)
        assert "Quiero organizar los pedidos de mi cafetería." in contexto
        assert r[0].pregunta_texto in contexto
        assert ids == {r[0].id}

    def test_administrador_tipo_acciones_llega_deserializado_y_legible(self):
        r = _responder([], "administrador_tipo_acciones", ["Ver información", "Agregar cosas nuevas"])
        contexto, ids = construir_contexto(r)
        assert "Ver información" in contexto
        assert "Agregar cosas nuevas" in contexto
        assert "[" not in contexto  # nunca JSON crudo en el contexto
        assert ids == {r[0].id}

    def test_nombre_proyecto_excluido_del_contexto(self):
        r = _responder([], "nombre_proyecto", "Cafecito")
        contexto, ids = construir_contexto(r)
        assert contexto == ""
        assert ids == set()

    def test_deterministas_excluidas_del_contexto(self):
        r = _responder([], "plataforma", "Desde un navegador web")
        r = _responder(r, "monetizacion", "Sí, de alguna forma")
        r = _responder(r, "monetizacion_forma", "Una sola vez")
        contexto, ids = construir_contexto(r)
        assert contexto == ""
        assert ids == set()

    def test_controles_de_flujo_y_compuertas_excluidos_del_contexto(self):
        r = _responder([], "perfil_usuario_continuar", "No")
        r = _responder(r, "nuevo_o_existente", "Es un proyecto nuevo")
        r = _responder(r, "dato_recordar", "No")
        contexto, ids = construir_contexto(r)
        assert contexto == ""
        assert ids == set()

    def test_ningun_texto_libre_devuelve_contexto_vacio(self):
        assert construir_contexto([]) == ("", set())

    def test_cada_bloque_incluye_su_id(self):
        r = _responder([], "problema_objetivo", "Algo")
        r = _responder(r, "cierre_libre", "Nada más")
        contexto, ids = construir_contexto(r)
        assert f"(id={r[0].id})" in contexto
        assert f"(id={r[1].id})" in contexto
        assert ids == {r[0].id, r[1].id}


# --- parsear_entidades --------------------------------------------------

def _linea(**kw) -> str:
    return json.dumps(kw, ensure_ascii=False)


class TestParsearEntidadesJsonValido:
    def test_requisito_valido(self):
        ids = {1}
        texto = _linea(tipo="requisito", respuesta_id=1, descripcion="Registrar pedidos nuevos")
        entidades, problemas = parsear_entidades(texto, ids)
        assert problemas == []
        assert len(entidades) == 1
        e = entidades[0]
        assert e.tipo == "requisito"
        assert e.campos == {"descripcion": "Registrar pedidos nuevos"}
        assert e.confianza == NivelConfianza.MEDIA
        assert e.respuesta_id == 1

    def test_perfil_valido(self):
        ids = {5}
        texto = _linea(tipo="perfil", respuesta_id=5, nombre="Meseros", descripcion="Atienden mesas")
        entidades, problemas = parsear_entidades(texto, ids)
        assert problemas == []
        assert entidades[0].campos == {"nombre": "Meseros", "descripcion": "Atienden mesas"}

    def test_restriccion_valida_mapea_tipo_restriccion_a_tipo(self):
        ids = {7}
        texto = _linea(tipo="restriccion", respuesta_id=7, tipo_restriccion="tecnica", descripcion="Reusar Sheets")
        entidades, problemas = parsear_entidades(texto, ids)
        assert problemas == []
        assert entidades[0].campos == {"tipo": "tecnica", "descripcion": "Reusar Sheets"}

    def test_dato_valido_con_opcionales_nulos(self):
        ids = {9}
        texto = _linea(tipo="dato", respuesta_id=9, descripcion="Historial de pedidos",
                        temporalidad=None, sensibilidad=None)
        entidades, problemas = parsear_entidades(texto, ids)
        assert problemas == []
        assert entidades[0].campos == {
            "descripcion": "Historial de pedidos", "temporalidad": None, "sensibilidad": None,
        }

    def test_dato_valido_con_opcionales_presentes(self):
        ids = {9}
        texto = _linea(tipo="dato", respuesta_id=9, descripcion="Historial de pedidos",
                        temporalidad="permanente", sensibilidad="baja")
        entidades, _ = parsear_entidades(texto, ids)
        assert entidades[0].campos["temporalidad"] == "permanente"
        assert entidades[0].campos["sensibilidad"] == "baja"

    def test_varias_lineas_validas(self):
        ids = {1, 2}
        texto = "\n".join([
            _linea(tipo="requisito", respuesta_id=1, descripcion="a"),
            _linea(tipo="perfil", respuesta_id=2, nombre="x", descripcion="y"),
        ])
        entidades, problemas = parsear_entidades(texto, ids)
        assert len(entidades) == 2
        assert problemas == []

    def test_lineas_vacias_al_borde_se_ignoran(self):
        ids = {1}
        texto = "\n\n" + _linea(tipo="requisito", respuesta_id=1, descripcion="a") + "\n\n"
        entidades, problemas = parsear_entidades(texto, ids)
        assert len(entidades) == 1
        assert problemas == []

    def test_linea_vacia_entre_dos_validas_se_ignora(self):
        ids = {1, 2}
        texto = "\n".join([
            _linea(tipo="requisito", respuesta_id=1, descripcion="a"),
            "",
            _linea(tipo="requisito", respuesta_id=2, descripcion="b"),
        ])
        entidades, problemas = parsear_entidades(texto, ids)
        assert len(entidades) == 2
        assert problemas == []

    def test_texto_vacio_no_produce_nada(self):
        assert parsear_entidades("", set()) == ([], [])

    def test_bloque_markdown_se_desenvuelve(self):
        ids = {1}
        cuerpo = _linea(tipo="requisito", respuesta_id=1, descripcion="a")
        texto = f"```json\n{cuerpo}\n```"
        entidades, problemas = parsear_entidades(texto, ids)
        assert len(entidades) == 1
        assert problemas == []


class TestParsearEntidadesJsonInvalido:
    """JSON inválido -> error controlado: nunca lanza, se reporta en
    `problemas` y no detiene el parseo de las demás líneas."""

    def test_linea_no_json_se_descarta_sin_lanzar(self):
        entidades, problemas = parsear_entidades("esto no es json", {1})
        assert entidades == []
        assert len(problemas) == 1
        assert "línea 1" in problemas[0]

    def test_json_no_es_objeto_se_descarta(self):
        entidades, problemas = parsear_entidades("[1, 2, 3]", {1})
        assert entidades == []
        assert len(problemas) == 1

    def test_tipo_no_reconocido_se_descarta(self):
        texto = _linea(tipo="capacidad", respuesta_id=1, descripcion="a")
        entidades, problemas = parsear_entidades(texto, {1})
        assert entidades == []
        assert "no reconocido" in problemas[0]

    def test_falta_campo_requerido_se_descarta(self):
        texto = json.dumps({"tipo": "perfil", "respuesta_id": 1, "nombre": "x"})  # falta descripcion
        entidades, problemas = parsear_entidades(texto, {1})
        assert entidades == []
        assert len(problemas) == 1

    def test_una_linea_rota_no_invalida_las_demas(self):
        ids = {1, 2}
        texto = "\n".join([
            "esto no es json",
            _linea(tipo="requisito", respuesta_id=2, descripcion="sobrevive"),
        ])
        entidades, problemas = parsear_entidades(texto, ids)
        assert len(entidades) == 1
        assert entidades[0].campos["descripcion"] == "sobrevive"
        assert len(problemas) == 1


class TestInformacionInventadaNoSePersiste:
    """`respuesta_id` fuera de `ids_validos` = información sin fundamento en
    lo que la persona declaró (regla 18 del ticket): se descarta, nunca
    llega a `entidades`."""

    def test_respuesta_id_desconocido_se_descarta(self):
        texto = _linea(tipo="requisito", respuesta_id=999, descripcion="inventado")
        entidades, problemas = parsear_entidades(texto, {1, 2})
        assert entidades == []
        assert "inventada" in problemas[0]

    def test_respuesta_id_de_una_pregunta_determinista_tambien_se_descarta(self):
        """Un `respuesta_id` que nunca se mostró en el contexto (porque
        pertenecía a una pregunta ya consumida deterministamente, o a un
        control de flujo) tampoco es válido: `ids_validos` es exactamente
        el conjunto que devolvió `construir_contexto`."""
        entidades, problemas = parsear_entidades(
            _linea(tipo="requisito", respuesta_id=1, descripcion="x"), set(),
        )
        assert entidades == []
        assert len(problemas) == 1

    def test_falta_respuesta_id_se_descarta(self):
        texto = json.dumps({"tipo": "requisito", "descripcion": "sin id"})
        entidades, problemas = parsear_entidades(texto, {1})
        assert entidades == []

    def test_respuesta_id_no_entero_se_descarta(self):
        texto = json.dumps({"tipo": "requisito", "respuesta_id": "1", "descripcion": "x"})
        entidades, problemas = parsear_entidades(texto, {1})
        assert entidades == []


class TestConfianzaSiempreMedia:
    def test_toda_entidad_parseada_es_confianza_media(self):
        ids = {1, 2, 3, 4}
        texto = "\n".join([
            _linea(tipo="requisito", respuesta_id=1, descripcion="a"),
            _linea(tipo="perfil", respuesta_id=2, nombre="x", descripcion="y"),
            _linea(tipo="restriccion", respuesta_id=3, tipo_restriccion="t", descripcion="z"),
            _linea(tipo="dato", respuesta_id=4, descripcion="w", temporalidad=None, sensibilidad=None),
        ])
        entidades, _ = parsear_entidades(texto, ids)
        assert len(entidades) == 4
        assert all(e.confianza == NivelConfianza.MEDIA for e in entidades)
