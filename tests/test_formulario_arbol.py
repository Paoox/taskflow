"""Pruebas del árbol de decisión determinista (`src.formulario.arbol`).

`siguiente_pregunta()` es una función pura sobre una lista de
`RespuestaFormulario` — estas pruebas no tocan base de datos, construyen la
lista a mano con un helper (`_responder`) que serializa igual que lo haría
el llamador real.
"""
from src.expediente.modelo import RespuestaFormulario
from src.formulario.arbol import siguiente_pregunta
from src.formulario.preguntas import (
    OPCION_DETALLE_CELULAR, OPCION_PLATAFORMA_NAVEGADOR, PREGUNTAS,
)
from src.formulario.respuestas import serializar_respuesta


def _responder(respuestas: list, pregunta_id: str, valor) -> list:
    """Devuelve una NUEVA lista con una respuesta más añadida (no muta la
    entrada), serializando igual que haría el llamador real."""
    pregunta = PREGUNTAS[pregunta_id]
    texto = serializar_respuesta(pregunta, valor)
    nueva = RespuestaFormulario(
        id=len(respuestas) + 1, codigo="PROY-001", pregunta_id=pregunta_id,
        pregunta_texto=pregunta.texto, tipo_pregunta=pregunta.tipo_pregunta,
        respuesta=texto, respondido_en="2026-09-11 10:00:00", accion_id_origen=None,
    )
    return respuestas + [nueva]


class TestArranque:
    def test_lista_vacia_devuelve_primera_pregunta(self):
        assert siguiente_pregunta([]).pregunta_id == "nuevo_o_existente"

    def test_nuevo_no_activa_preguntas_de_proyecto_existente(self):
        r = _responder([], "nuevo_o_existente", "Es un proyecto nuevo")
        siguiente = siguiente_pregunta(r)
        assert siguiente.pregunta_id != "referencia_proyecto_existente"

    def test_nombre_proyecto_activa_problema_objetivo(self):
        r = _responder([], "nuevo_o_existente", "Es un proyecto nuevo")
        r = _responder(r, "nombre_proyecto", "Calculadora Pro")
        assert siguiente_pregunta(r).pregunta_id == "problema_objetivo"

    def test_existente_activa_referencia_y_objetivo_existente(self):
        r = _responder([], "nuevo_o_existente", "Ya tengo algo construido")
        assert siguiente_pregunta(r).pregunta_id == "referencia_proyecto_existente"
        r = _responder(r, "referencia_proyecto_existente", "github.com/x/y")
        r = _responder(r, "nombre_proyecto", "")
        r = _responder(r, "problema_objetivo", "algo")
        assert siguiente_pregunta(r).pregunta_id == "objetivo_proyecto_existente"


def _avanzar_hasta_plataforma(existente: bool = False) -> list:
    r = _responder([], "nuevo_o_existente", "Ya tengo algo construido" if existente else "Es un proyecto nuevo")
    if existente:
        r = _responder(r, "referencia_proyecto_existente", "github.com/x/y")
    r = _responder(r, "nombre_proyecto", "")
    r = _responder(r, "problema_objetivo", "algo")
    if existente:
        r = _responder(r, "objetivo_proyecto_existente", "cambiar de rumbo")
    assert siguiente_pregunta(r).pregunta_id == "plataforma"
    return r


class TestPlataformas:
    def test_celular_directo_activa_offline_sin_pasar_por_detalle(self):
        r = _avanzar_hasta_plataforma()
        r = _responder(r, "plataforma", "Desde el celular")
        assert siguiente_pregunta(r).pregunta_id == "plataforma_offline"

    def test_navegador_no_activa_ni_detalle_ni_offline(self):
        r = _avanzar_hasta_plataforma()
        r = _responder(r, "plataforma", "Desde un navegador web")
        siguiente = siguiente_pregunta(r)
        assert siguiente.pregunta_id not in ("plataforma_detalle", "plataforma_offline")

    def test_varios_lugares_activa_detalle(self):
        r = _avanzar_hasta_plataforma()
        r = _responder(r, "plataforma", "En varios de estos lugares")
        assert siguiente_pregunta(r).pregunta_id == "plataforma_detalle"

    def test_varios_lugares_con_celular_en_detalle_activa_offline(self):
        r = _avanzar_hasta_plataforma()
        r = _responder(r, "plataforma", "En varios de estos lugares")
        r = _responder(r, "plataforma_detalle", [OPCION_PLATAFORMA_NAVEGADOR, OPCION_DETALLE_CELULAR])
        assert siguiente_pregunta(r).pregunta_id == "plataforma_offline"

    def test_varios_lugares_sin_celular_en_detalle_no_activa_offline(self):
        r = _avanzar_hasta_plataforma()
        r = _responder(r, "plataforma", "En varios de estos lugares")
        r = _responder(r, "plataforma_detalle", [OPCION_PLATAFORMA_NAVEGADOR])
        siguiente = siguiente_pregunta(r)
        assert siguiente.pregunta_id != "plataforma_offline"


def _avanzar_hasta_perfiles() -> list:
    r = _avanzar_hasta_plataforma()
    r = _responder(r, "plataforma", "No estoy seguro todavía")
    assert siguiente_pregunta(r).pregunta_id == "perfil_usuario"
    return r


class TestBucleSimplePerfiles:
    def test_primera_vez_pide_contenido(self):
        r = _avanzar_hasta_perfiles()
        assert siguiente_pregunta(r).pregunta_id == "perfil_usuario"

    def test_despues_de_contenido_pide_continuar(self):
        r = _avanzar_hasta_perfiles()
        r = _responder(r, "perfil_usuario", "público general")
        assert siguiente_pregunta(r).pregunta_id == "perfil_usuario_continuar"

    def test_continuar_si_repite_contenido(self):
        r = _avanzar_hasta_perfiles()
        r = _responder(r, "perfil_usuario", "público general")
        r = _responder(r, "perfil_usuario_continuar", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "perfil_usuario"

    def test_continuar_no_avanza_al_siguiente_bloque(self):
        r = _avanzar_hasta_perfiles()
        r = _responder(r, "perfil_usuario", "público general")
        r = _responder(r, "perfil_usuario_continuar", "No")
        assert siguiente_pregunta(r).pregunta_id == "administracion_cantidad"


def _avanzar_hasta_administracion() -> list:
    r = _avanzar_hasta_perfiles()
    r = _responder(r, "perfil_usuario", "público general")
    r = _responder(r, "perfil_usuario_continuar", "No")
    assert siguiente_pregunta(r).pregunta_id == "administracion_cantidad"
    return r


class TestAdministracion:
    def test_una_sola_persona_no_activa_diferencias(self):
        r = _avanzar_hasta_administracion()
        r = _responder(r, "administracion_cantidad", "Una sola persona")
        siguiente = siguiente_pregunta(r)
        assert siguiente.pregunta_id not in ("administracion_diferencias", "administrador_tipo_nombre")
        assert siguiente.pregunta_id == "funcionalidad_declarada"

    def test_varias_personas_activa_diferencias(self):
        r = _avanzar_hasta_administracion()
        r = _responder(r, "administracion_cantidad", "Varias personas")
        assert siguiente_pregunta(r).pregunta_id == "administracion_diferencias"

    def test_no_funciona_como_2_o_mas_perfiles_ya_no_activa_nada_por_si_solo(self):
        """Decisión 4: no asumir que 2+ perfiles implica roles diferentes —
        `administracion_cantidad` se pregunta igual sin importar Q5."""
        r = _avanzar_hasta_perfiles()
        r = _responder(r, "perfil_usuario", "clientes")
        r = _responder(r, "perfil_usuario_continuar", "Sí")
        r = _responder(r, "perfil_usuario", "empleados")
        r = _responder(r, "perfil_usuario_continuar", "No")
        # aun con 2 perfiles descritos, la siguiente pregunta es la de
        # administración — nunca se salta directo a "administrador_tipo_nombre"
        assert siguiente_pregunta(r).pregunta_id == "administracion_cantidad"

    def test_diferencias_no_no_activa_el_bucle_de_administradores(self):
        r = _avanzar_hasta_administracion()
        r = _responder(r, "administracion_cantidad", "Varias personas")
        r = _responder(r, "administracion_diferencias", "No")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_declarada"

    def test_diferencias_si_activa_el_bucle_de_administradores(self):
        r = _avanzar_hasta_administracion()
        r = _responder(r, "administracion_cantidad", "Varias personas")
        r = _responder(r, "administracion_diferencias", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "administrador_tipo_nombre"


def _avanzar_hasta_administradores() -> list:
    r = _avanzar_hasta_administracion()
    r = _responder(r, "administracion_cantidad", "Varias personas")
    r = _responder(r, "administracion_diferencias", "Sí")
    assert siguiente_pregunta(r).pregunta_id == "administrador_tipo_nombre"
    return r


class TestBucleAdministradores:
    def test_nombre_luego_acciones(self):
        r = _avanzar_hasta_administradores()
        r = _responder(r, "administrador_tipo_nombre", "el dueño")
        assert siguiente_pregunta(r).pregunta_id == "administrador_tipo_acciones"

    def test_acciones_con_otra_cosa_activa_pregunta_otra(self):
        r = _avanzar_hasta_administradores()
        r = _responder(r, "administrador_tipo_nombre", "el dueño")
        r = _responder(r, "administrador_tipo_acciones", ["Controlar/administrar todo el proyecto", "Otra cosa"])
        assert siguiente_pregunta(r).pregunta_id == "administrador_tipo_otra"

    def test_acciones_sin_otra_cosa_salta_directo_a_continuar(self):
        r = _avanzar_hasta_administradores()
        r = _responder(r, "administrador_tipo_nombre", "el dueño")
        r = _responder(r, "administrador_tipo_acciones", ["Ver información"])
        assert siguiente_pregunta(r).pregunta_id == "administrador_tipo_continuar"

    def test_continuar_si_pide_otro_nombre(self):
        r = _avanzar_hasta_administradores()
        r = _responder(r, "administrador_tipo_nombre", "el dueño")
        r = _responder(r, "administrador_tipo_acciones", ["Ver información"])
        r = _responder(r, "administrador_tipo_continuar", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "administrador_tipo_nombre"

    def test_continuar_no_termina_el_bloque(self):
        r = _avanzar_hasta_administradores()
        r = _responder(r, "administrador_tipo_nombre", "el dueño")
        r = _responder(r, "administrador_tipo_acciones", ["Ver información"])
        r = _responder(r, "administrador_tipo_continuar", "No")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_declarada"

    def test_iteraciones_mixtas_de_otra_cosa_no_confunden_el_conteo(self):
        """Caso más delicado del árbol: la 1ª iteración marca "Otra cosa",
        la 2ª no. El conteo de "otra" pendientes debe seguir siendo correcto
        para la 2ª iteración."""
        r = _avanzar_hasta_administradores()
        # iteración 1: con "Otra cosa"
        r = _responder(r, "administrador_tipo_nombre", "el dueño")
        r = _responder(r, "administrador_tipo_acciones", ["Controlar/administrar todo el proyecto", "Otra cosa"])
        assert siguiente_pregunta(r).pregunta_id == "administrador_tipo_otra"
        r = _responder(r, "administrador_tipo_otra", "también exporta reportes")
        assert siguiente_pregunta(r).pregunta_id == "administrador_tipo_continuar"
        r = _responder(r, "administrador_tipo_continuar", "Sí")
        # iteración 2: sin "Otra cosa" — no debe volver a pedir "otra"
        assert siguiente_pregunta(r).pregunta_id == "administrador_tipo_nombre"
        r = _responder(r, "administrador_tipo_nombre", "el vendedor")
        r = _responder(r, "administrador_tipo_acciones", ["Ver información"])
        assert siguiente_pregunta(r).pregunta_id == "administrador_tipo_continuar"
        r = _responder(r, "administrador_tipo_continuar", "No")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_declarada"


class TestBloquesRestantes:
    def _hasta_funcionalidad(self):
        r = _avanzar_hasta_administracion()
        r = _responder(r, "administracion_cantidad", "Una sola persona")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_declarada"
        return r

    def test_funcionalidad_es_bucle_simple(self):
        r = self._hasta_funcionalidad()
        r = _responder(r, "funcionalidad_declarada", "sumar")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_declarada_continuar"
        r = _responder(r, "funcionalidad_declarada_continuar", "No")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion"

    def test_monetizacion_no_gratis_salta_forma(self):
        r = self._hasta_funcionalidad()
        r = _responder(r, "funcionalidad_declarada", "sumar")
        r = _responder(r, "funcionalidad_declarada_continuar", "No")
        r = _responder(r, "monetizacion", "No, es gratis")
        assert siguiente_pregunta(r).pregunta_id == "dato_recordar"

    def test_monetizacion_si_activa_forma(self):
        r = self._hasta_funcionalidad()
        r = _responder(r, "funcionalidad_declarada", "sumar")
        r = _responder(r, "funcionalidad_declarada_continuar", "No")
        r = _responder(r, "monetizacion", "Sí, de alguna forma")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_forma"

    def test_dato_recordar_no_salta_detalle(self):
        r = self._hasta_funcionalidad()
        r = _responder(r, "funcionalidad_declarada", "sumar")
        r = _responder(r, "funcionalidad_declarada_continuar", "No")
        r = _responder(r, "monetizacion", "No, es gratis")
        r = _responder(r, "dato_recordar", "No")
        assert siguiente_pregunta(r).pregunta_id == "restriccion_tecnica"

    def test_dato_recordar_si_activa_bucle_de_detalle(self):
        r = self._hasta_funcionalidad()
        r = _responder(r, "funcionalidad_declarada", "sumar")
        r = _responder(r, "funcionalidad_declarada_continuar", "No")
        r = _responder(r, "monetizacion", "No, es gratis")
        r = _responder(r, "dato_recordar", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "dato_recordar_detalle"
        r = _responder(r, "dato_recordar_detalle", "historial de operaciones")
        r = _responder(r, "dato_recordar_detalle_continuar", "No")
        assert siguiente_pregunta(r).pregunta_id == "restriccion_tecnica"

    def test_restricciones_son_secuenciales(self):
        r = self._hasta_funcionalidad()
        r = _responder(r, "funcionalidad_declarada", "sumar")
        r = _responder(r, "funcionalidad_declarada_continuar", "No")
        r = _responder(r, "monetizacion", "No, es gratis")
        r = _responder(r, "dato_recordar", "No")
        assert siguiente_pregunta(r).pregunta_id == "restriccion_tecnica"
        r = _responder(r, "restriccion_tecnica", "")
        assert siguiente_pregunta(r).pregunta_id == "restriccion_tiempo_presupuesto"
        r = _responder(r, "restriccion_tiempo_presupuesto", "")
        assert siguiente_pregunta(r).pregunta_id == "restriccion_negocio"
        r = _responder(r, "restriccion_negocio", "")
        assert siguiente_pregunta(r).pregunta_id == "cierre_libre"
        r = _responder(r, "cierre_libre", "")
        assert siguiente_pregunta(r) is None


class TestArbolCompleto:
    def test_camino_minimo_termina_en_none(self):
        """Escenario A, todo lo opcional se deja vacío/"no sé" — el árbol
        debe poder completarse igual, sin bloquear nunca."""
        r = []
        r = _responder(r, "nuevo_o_existente", "Es un proyecto nuevo")
        r = _responder(r, "nombre_proyecto", "")
        r = _responder(r, "problema_objetivo", "una calculadora")
        r = _responder(r, "plataforma", "No estoy seguro todavía")
        r = _responder(r, "perfil_usuario", "cualquiera")
        r = _responder(r, "perfil_usuario_continuar", "No")
        r = _responder(r, "administracion_cantidad", "Todavía no lo sé")
        r = _responder(r, "funcionalidad_declarada", "sumar")
        r = _responder(r, "funcionalidad_declarada_continuar", "No")
        r = _responder(r, "monetizacion", "Todavía no lo he decidido")
        r = _responder(r, "dato_recordar", "No estoy seguro")
        r = _responder(r, "restriccion_tecnica", "")
        r = _responder(r, "restriccion_tiempo_presupuesto", "")
        r = _responder(r, "restriccion_negocio", "")
        r = _responder(r, "cierre_libre", "")
        assert siguiente_pregunta(r) is None
