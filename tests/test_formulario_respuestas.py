"""Pruebas de validación/(de)serialización (`src.formulario.respuestas`).

Foco especial en la decisión cerrada: selección múltiple se guarda como
JSON válido, nunca como texto separado por comas. No requiere base de
datos: funciones puras.
"""
import json

import pytest

from src.formulario.preguntas import PREGUNTAS
from src.formulario.respuestas import (
    RespuestaInvalida, deserializar_respuesta, serializar_respuesta, validar_respuesta,
)

_PREGUNTA_LIBRE = PREGUNTAS["problema_objetivo"]
_PREGUNTA_CERRADA_UNICA = PREGUNTAS["monetizacion"]
_PREGUNTA_CERRADA_MULTIPLE = PREGUNTAS["experiencia_persona_permisos_residual"]


class TestValidarTextoLibre:
    def test_acepta_cualquier_texto(self):
        validar_respuesta(_PREGUNTA_LIBRE, "controlar mis gastos personales")  # no lanza

    def test_acepta_texto_vacio(self):
        validar_respuesta(_PREGUNTA_LIBRE, "")  # no lanza — el formulario no interpreta

    def test_rechaza_no_texto(self):
        with pytest.raises(RespuestaInvalida):
            validar_respuesta(_PREGUNTA_LIBRE, ["no", "es", "texto"])


class TestValidarOpcionUnica:
    def test_acepta_opcion_valida(self):
        validar_respuesta(_PREGUNTA_CERRADA_UNICA, "No, es gratis")  # no lanza

    def test_rechaza_opcion_no_permitida(self):
        with pytest.raises(RespuestaInvalida):
            validar_respuesta(_PREGUNTA_CERRADA_UNICA, "algo que no es una opción")

    def test_rechaza_lista_en_pregunta_de_opcion_unica(self):
        with pytest.raises(RespuestaInvalida):
            validar_respuesta(_PREGUNTA_CERRADA_UNICA, ["No, es gratis"])


class TestValidarOpcionMultiple:
    def test_acepta_lista_de_opciones_validas(self):
        validar_respuesta(_PREGUNTA_CERRADA_MULTIPLE, ["Ver información", "Eliminar cosas"])  # no lanza

    def test_rechaza_string_suelto(self):
        with pytest.raises(RespuestaInvalida):
            validar_respuesta(_PREGUNTA_CERRADA_MULTIPLE, "Ver información")

    def test_rechaza_opcion_invalida_dentro_de_la_lista(self):
        with pytest.raises(RespuestaInvalida):
            validar_respuesta(_PREGUNTA_CERRADA_MULTIPLE, ["Ver información", "volar"])

    def test_acepta_lista_vacia(self):
        """No se fuerza a elegir al menos una opción a nivel de validación —
        es una decisión de UI/contenido, no de la forma del dato."""
        validar_respuesta(_PREGUNTA_CERRADA_MULTIPLE, [])


class TestSerializarYDeserializar:
    def test_texto_libre_se_guarda_tal_cual(self):
        assert serializar_respuesta(_PREGUNTA_LIBRE, "hola") == "hola"

    def test_opcion_unica_se_guarda_tal_cual(self):
        assert serializar_respuesta(_PREGUNTA_CERRADA_UNICA, "No, es gratis") == "No, es gratis"

    def test_multiple_se_guarda_como_json_valido(self):
        guardado = serializar_respuesta(_PREGUNTA_CERRADA_MULTIPLE, ["Ver información", "Eliminar cosas"])
        assert json.loads(guardado) == ["Ver información", "Eliminar cosas"]  # JSON válido, no CSV

    def test_multiple_no_se_guarda_separado_por_comas(self):
        guardado = serializar_respuesta(_PREGUNTA_CERRADA_MULTIPLE, ["Ver información", "Eliminar cosas"])
        assert guardado != "Ver información,Eliminar cosas"

    def test_serializar_rechaza_respuesta_invalida(self):
        with pytest.raises(RespuestaInvalida):
            serializar_respuesta(_PREGUNTA_CERRADA_UNICA, "no es una opción")

    def test_deserializar_multiple_reconstruye_la_lista(self):
        guardado = serializar_respuesta(_PREGUNTA_CERRADA_MULTIPLE, ["Ver información"])
        assert deserializar_respuesta(_PREGUNTA_CERRADA_MULTIPLE, guardado) == ["Ver información"]

    def test_deserializar_no_multiple_devuelve_el_texto_tal_cual(self):
        assert deserializar_respuesta(_PREGUNTA_LIBRE, "hola") == "hola"

    def test_round_trip_preserva_el_valor_original(self):
        original = ["Ver información", "Agregar cosas nuevas", "Otra cosa"]
        guardado = serializar_respuesta(_PREGUNTA_CERRADA_MULTIPLE, original)
        assert deserializar_respuesta(_PREGUNTA_CERRADA_MULTIPLE, guardado) == original
