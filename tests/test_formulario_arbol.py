"""Pruebas del árbol de decisión determinista (`src.formulario.arbol`).

TF-0033 — "Discovery Inteligente": 16 dominios con puerta propia.
`siguiente_pregunta()` es una función pura sobre una lista de
`RespuestaFormulario` — estas pruebas no tocan base de datos, construyen la
lista a mano con un helper (`_responder`) que serializa igual que lo haría
el llamador real.
"""
from src.expediente.modelo import RespuestaFormulario
from src.formulario.arbol import siguiente_pregunta
from src.formulario.preguntas import (
    OPCION_ADMINISTRA_TODO, OPCION_DETALLE_CELULAR, OPCION_OTRA_COSA,
    OPCION_PLATAFORMA_NAVEGADOR, PREGUNTAS,
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


class TestHelperMultiple:
    def test_devuelve_lista_vacia_si_la_pregunta_no_se_ha_respondido(self):
        from src.formulario.arbol import _multiple
        assert _multiple([], "plataforma_detalle") == []


class TestDominio00Identidad:
    def test_lista_vacia_devuelve_primera_pregunta(self):
        assert siguiente_pregunta([]).pregunta_id == "nuevo_o_existente"

    def test_nuevo_no_activa_preguntas_de_proyecto_existente(self):
        r = _responder([], "nuevo_o_existente", "Nuevo")
        assert siguiente_pregunta(r).pregunta_id != "referencia_proyecto_existente"

    def test_existente_activa_referencia_y_objetivo_existente(self):
        r = _responder([], "nuevo_o_existente", "Ya existe algo")
        assert siguiente_pregunta(r).pregunta_id == "referencia_proyecto_existente"
        r = _responder(r, "referencia_proyecto_existente", "github.com/x/y")
        assert siguiente_pregunta(r).pregunta_id == "objetivo_proyecto_existente"

    def test_nombre_pide_su_estado_antes_de_problema(self):
        r = _responder([], "nuevo_o_existente", "Nuevo")
        r = _responder(r, "nombre_proyecto", "Calculadora Pro")
        assert siguiente_pregunta(r).pregunta_id == "nombre_proyecto_estado"
        r = _responder(r, "nombre_proyecto_estado", "Nombre definido")
        assert siguiente_pregunta(r).pregunta_id == "problema_objetivo"

    def test_enumeracion_en_problema_dispara_desglose(self):
        r = _responder([], "nuevo_o_existente", "Nuevo")
        r = _responder(r, "nombre_proyecto", "X")
        r = _responder(r, "nombre_proyecto_estado", "Nombre definido")
        r = _responder(r, "problema_objetivo", "Vender cursos, también cobrar suscripciones.")
        assert siguiente_pregunta(r).pregunta_id == "problema_objetivo_desglose"

    def test_problema_simple_no_dispara_desglose(self):
        r = _responder([], "nuevo_o_existente", "Nuevo")
        r = _responder(r, "nombre_proyecto", "X")
        r = _responder(r, "nombre_proyecto_estado", "Nombre definido")
        r = _responder(r, "problema_objetivo", "Llevar el control de mis gastos.")
        assert siguiente_pregunta(r).pregunta_id != "problema_objetivo_desglose"


def _avanzar_hasta_personas_gate() -> list:
    r = _responder([], "nuevo_o_existente", "Nuevo")
    r = _responder(r, "nombre_proyecto", "X")
    r = _responder(r, "nombre_proyecto_estado", "Nombre definido")
    r = _responder(r, "problema_objetivo", "Llevar el control de mis gastos.")
    assert siguiente_pregunta(r).pregunta_id == "personas_gate"
    return r


class TestDominio01Personas:
    def test_solo_salta_directo_a_experiencia_sin_nombrar_a_nadie(self):
        r = _avanzar_hasta_personas_gate()
        r = _responder(r, "personas_gate", "Yo solo / todos igual")
        siguiente = siguiente_pregunta(r)
        assert siguiente.pregunta_id not in ("perfil_usuario", "experiencia_persona_narrativa")

    def test_incierto_pregunta_si_hay_administrador(self):
        r = _avanzar_hasta_personas_gate()
        r = _responder(r, "personas_gate", "No estoy seguro")
        assert siguiente_pregunta(r).pregunta_id == "personas_gate_incierto"

    def test_varias_activa_el_bucle_de_nombrar_personas(self):
        r = _avanzar_hasta_personas_gate()
        r = _responder(r, "personas_gate", "Varias personas con roles distintos")
        assert siguiente_pregunta(r).pregunta_id == "perfil_usuario"
        r = _responder(r, "perfil_usuario", "clientes")
        assert siguiente_pregunta(r).pregunta_id == "perfil_usuario_continuar"
        r = _responder(r, "perfil_usuario_continuar", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "perfil_usuario"
        r = _responder(r, "perfil_usuario", "vendedores")
        r = _responder(r, "perfil_usuario_continuar", "No")
        # cierra 01, entra a 01b
        assert siguiente_pregunta(r).pregunta_id == "experiencia_persona_narrativa"


def _avanzar_con_una_persona() -> list:
    r = _avanzar_hasta_personas_gate()
    r = _responder(r, "personas_gate", "Varias personas con roles distintos")
    r = _responder(r, "perfil_usuario", "clientes")
    r = _responder(r, "perfil_usuario_continuar", "No")
    assert siguiente_pregunta(r).pregunta_id == "experiencia_persona_narrativa"
    return r


class TestDominio01bExperienciaPorPersona:
    def test_recorre_narrativa_frecuencia_primera_vez_permisos(self):
        r = _avanzar_con_una_persona()
        r = _responder(r, "experiencia_persona_narrativa", "llega, ve, hace, obtiene")
        assert siguiente_pregunta(r).pregunta_id == "experiencia_persona_frecuencia"
        r = _responder(r, "experiencia_persona_frecuencia", "Regularmente")
        assert siguiente_pregunta(r).pregunta_id == "experiencia_persona_primera_vez"
        r = _responder(r, "experiencia_persona_primera_vez", "distinta")
        assert siguiente_pregunta(r).pregunta_id == "experiencia_persona_permisos_residual"

    def test_otra_cosa_dispara_pregunta_de_detalle(self):
        r = _avanzar_con_una_persona()
        r = _responder(r, "experiencia_persona_narrativa", "x")
        r = _responder(r, "experiencia_persona_frecuencia", "Una sola vez")
        r = _responder(r, "experiencia_persona_primera_vez", "x")
        r = _responder(r, "experiencia_persona_permisos_residual", ["Ver información", OPCION_OTRA_COSA])
        assert siguiente_pregunta(r).pregunta_id == "experiencia_persona_permisos_otra"

    def test_sin_otra_cosa_no_pide_detalle(self):
        r = _avanzar_con_una_persona()
        r = _responder(r, "experiencia_persona_narrativa", "x")
        r = _responder(r, "experiencia_persona_frecuencia", "Una sola vez")
        r = _responder(r, "experiencia_persona_primera_vez", "x")
        r = _responder(r, "experiencia_persona_permisos_residual", ["Ver información"])
        assert siguiente_pregunta(r).pregunta_id != "experiencia_persona_permisos_otra"

    def test_se_repite_exactamente_una_vez_por_persona_nombrada(self):
        r = _avanzar_hasta_personas_gate()
        r = _responder(r, "personas_gate", "Varias personas con roles distintos")
        r = _responder(r, "perfil_usuario", "clientes")
        r = _responder(r, "perfil_usuario_continuar", "Sí")
        r = _responder(r, "perfil_usuario", "vendedores")
        r = _responder(r, "perfil_usuario_continuar", "No")

        for _ in range(2):
            assert siguiente_pregunta(r).pregunta_id == "experiencia_persona_narrativa"
            r = _responder(r, "experiencia_persona_narrativa", "x")
            r = _responder(r, "experiencia_persona_frecuencia", "Una sola vez")
            r = _responder(r, "experiencia_persona_primera_vez", "x")
            r = _responder(r, "experiencia_persona_permisos_residual", ["Ver información"])
        # ya recorrió a las 2 personas — no vuelve a pedir narrativa
        assert siguiente_pregunta(r).pregunta_id != "experiencia_persona_narrativa"


def _avanzar_hasta_plataforma() -> list:
    r = _avanzar_con_una_persona()
    r = _responder(r, "experiencia_persona_narrativa", "x")
    r = _responder(r, "experiencia_persona_frecuencia", "Una sola vez")
    r = _responder(r, "experiencia_persona_primera_vez", "x")
    r = _responder(r, "experiencia_persona_permisos_residual", ["Ver información"])
    assert siguiente_pregunta(r).pregunta_id == "plataforma"
    return r


class TestDominio07Plataforma:
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

    def test_despues_de_offline_sigue_interaccion(self):
        r = _avanzar_hasta_plataforma()
        r = _responder(r, "plataforma", "Desde un navegador web")
        assert siguiente_pregunta(r).pregunta_id == "interaccion_cuenta"
        r = _responder(r, "interaccion_cuenta", "Nunca necesita cuenta")
        assert siguiente_pregunta(r).pregunta_id == "interaccion_resultado_valor"


def _avanzar_hasta_contenido() -> list:
    r = _avanzar_hasta_plataforma()
    r = _responder(r, "plataforma", "Desde un navegador web")
    r = _responder(r, "interaccion_cuenta", "Nunca necesita cuenta")
    r = _responder(r, "interaccion_resultado_valor", "termina su tarea")
    assert siguiente_pregunta(r).pregunta_id == "contenido_gate"
    return r


class TestDominio03Contenido:
    def test_no_cierra_de_inmediato(self):
        r = _avanzar_hasta_contenido()
        r = _responder(r, "contenido_gate", "No")
        assert siguiente_pregunta(r).pregunta_id == "dato_recordar"

    def test_si_activa_tipo_y_creador(self):
        r = _avanzar_hasta_contenido()
        r = _responder(r, "contenido_gate", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "contenido_tipo"
        r = _responder(r, "contenido_tipo", ["Texto"])
        assert siguiente_pregunta(r).pregunta_id == "contenido_creador"

    def test_cursos_activa_sub_arbol_de_curso_sin_examenes(self):
        r = _avanzar_hasta_contenido()
        r = _responder(r, "contenido_gate", "Sí")
        r = _responder(r, "contenido_tipo", ["Cursos/lecciones"])
        r = _responder(r, "contenido_creador", "Solo admin")
        assert siguiente_pregunta(r).pregunta_id == "contenido_curso_modulos"
        r = _responder(r, "contenido_curso_modulos", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "contenido_curso_orden"
        r = _responder(r, "contenido_curso_orden", "Orden libre")
        assert siguiente_pregunta(r).pregunta_id == "contenido_curso_examenes"
        r = _responder(r, "contenido_curso_examenes", "No")
        assert siguiente_pregunta(r).pregunta_id == "contenido_aprobacion"

    def test_cursos_con_examenes_pide_calificacion_minima(self):
        r = _avanzar_hasta_contenido()
        r = _responder(r, "contenido_gate", "Sí")
        r = _responder(r, "contenido_tipo", ["Cursos/lecciones"])
        r = _responder(r, "contenido_creador", "Solo admin")
        r = _responder(r, "contenido_curso_modulos", "No")
        r = _responder(r, "contenido_curso_orden", "Orden obligatorio")
        r = _responder(r, "contenido_curso_examenes", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "contenido_curso_calificacion_minima"
        r = _responder(r, "contenido_curso_calificacion_minima", "70")
        assert siguiente_pregunta(r).pregunta_id == "contenido_aprobacion"

    def test_aprobacion_siempre_se_pregunta_nunca_se_infiere(self):
        """Corrección A2: ni siquiera si alguien ya puede 'aprobar/rechazar'
        en 01b se infiere la respuesta — siempre se pregunta."""
        r = _avanzar_hasta_contenido()
        r = _responder(r, "contenido_gate", "Sí")
        r = _responder(r, "contenido_tipo", ["Texto"])
        r = _responder(r, "contenido_creador", "Solo admin")
        assert siguiente_pregunta(r).pregunta_id == "contenido_aprobacion"


def _avanzar_hasta_datos() -> list:
    r = _avanzar_hasta_contenido()
    r = _responder(r, "contenido_gate", "No")
    assert siguiente_pregunta(r).pregunta_id == "dato_recordar"
    return r


class TestDominio04Datos:
    def test_no_cierra_de_inmediato(self):
        r = _avanzar_hasta_datos()
        r = _responder(r, "dato_recordar", "No")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion"

    def test_si_activa_bucle_de_5_pasos_por_dato(self):
        r = _avanzar_hasta_datos()
        r = _responder(r, "dato_recordar", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "dato_recordar_detalle"
        r = _responder(r, "dato_recordar_detalle", "historial")
        assert siguiente_pregunta(r).pregunta_id == "dato_sensible"
        r = _responder(r, "dato_sensible", "No")
        assert siguiente_pregunta(r).pregunta_id == "dato_retencion"
        r = _responder(r, "dato_retencion", "para siempre")
        assert siguiente_pregunta(r).pregunta_id == "dato_quien_ve"
        r = _responder(r, "dato_quien_ve", "el dueño")
        assert siguiente_pregunta(r).pregunta_id == "dato_quien_modifica"
        r = _responder(r, "dato_quien_modifica", "el dueño")
        assert siguiente_pregunta(r).pregunta_id == "dato_recordar_detalle_continuar"
        r = _responder(r, "dato_recordar_detalle_continuar", "No")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion"

    def test_dato_recordar_detalle_continuar_si_repite_el_bucle(self):
        r = _avanzar_hasta_datos()
        r = _responder(r, "dato_recordar", "Sí")
        r = _responder(r, "dato_recordar_detalle", "historial")
        r = _responder(r, "dato_sensible", "No")
        r = _responder(r, "dato_retencion", "para siempre")
        r = _responder(r, "dato_quien_ve", "el dueño")
        r = _responder(r, "dato_quien_modifica", "el dueño")
        r = _responder(r, "dato_recordar_detalle_continuar", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "dato_recordar_detalle"


def _avanzar_hasta_monetizacion() -> list:
    r = _avanzar_hasta_datos()
    r = _responder(r, "dato_recordar", "No")
    assert siguiente_pregunta(r).pregunta_id == "monetizacion"
    return r


class TestDominio05MonetizacionDosGates:
    def test_gate_a_no_gratis_salta_directo_a_gate_b(self):
        r = _avanzar_hasta_monetizacion()
        r = _responder(r, "monetizacion", "No, es gratis")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_salida"

    def test_gate_a_si_activa_forma(self):
        r = _avanzar_hasta_monetizacion()
        r = _responder(r, "monetizacion", "Sí, de alguna forma")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_forma"

    def test_gate_a_suscripcion_activa_planes(self):
        r = _avanzar_hasta_monetizacion()
        r = _responder(r, "monetizacion", "Sí, de alguna forma")
        r = _responder(r, "monetizacion_forma", "Suscripción")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_planes_n"
        r = _responder(r, "monetizacion_planes_n", "1")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_plan_detalle"
        r = _responder(r, "monetizacion_plan_detalle", "básico")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_plan_continuar"
        r = _responder(r, "monetizacion_plan_continuar", "No")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_prueba_gratis"
        r = _responder(r, "monetizacion_prueba_gratis", "No")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_impago"
        r = _responder(r, "monetizacion_impago", "pierde acceso")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_autogestion"
        r = _responder(r, "monetizacion_autogestion", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_factura"

    def test_gate_a_pago_unico_activa_su_propia_rama(self):
        r = _avanzar_hasta_monetizacion()
        r = _responder(r, "monetizacion", "Sí, de alguna forma")
        r = _responder(r, "monetizacion_forma", "Pago único")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_pago_unico_detalle"
        r = _responder(r, "monetizacion_pago_unico_detalle", "una calculadora")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_reembolso"
        r = _responder(r, "monetizacion_reembolso", "No")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_factura"

    def test_gate_b_es_independiente_de_gate_a(self):
        """D5: Gate B siempre se pregunta, sin importar la respuesta de Gate A."""
        r = _avanzar_hasta_monetizacion()
        r = _responder(r, "monetizacion", "No, es gratis")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_salida"
        r = _responder(r, "monetizacion_salida", "Sí, le paga a alguien")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_salida_forma"
        r = _responder(r, "monetizacion_salida_forma", "Comisión")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_salida_incumplimiento"
        r = _responder(r, "monetizacion_salida_incumplimiento", "se retiene")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_salida_control"

    def test_gate_b_no_reutiliza_las_preguntas_del_gate_a(self):
        r = _avanzar_hasta_monetizacion()
        r = _responder(r, "monetizacion", "Sí, de alguna forma")
        r = _responder(r, "monetizacion_forma", "Pago único")
        r = _responder(r, "monetizacion_pago_unico_detalle", "x")
        r = _responder(r, "monetizacion_reembolso", "No")
        r = _responder(r, "monetizacion_factura", "No")
        assert siguiente_pregunta(r).pregunta_id == "monetizacion_salida"
        r = _responder(r, "monetizacion_salida", "No, no le paga a nadie")
        # el gate B en "No" no debe reabrir nada del gate A
        assert siguiente_pregunta(r).pregunta_id not in (
            "monetizacion_forma", "monetizacion_pago_unico_detalle",
        )


def _avanzar_sin_monetizacion() -> list:
    r = _avanzar_hasta_monetizacion()
    r = _responder(r, "monetizacion", "No, es gratis")
    r = _responder(r, "monetizacion_salida", "No, no le paga a nadie")
    return r


class TestDominio06Administracion:
    def test_sin_senal_de_admin_se_salta_el_dominio(self):
        r = _avanzar_sin_monetizacion()
        siguiente = siguiente_pregunta(r)
        assert siguiente.pregunta_id not in ("admin_acciones", "admin_que_mas")

    def test_permiso_administra_todo_activa_el_dominio(self):
        r = _avanzar_hasta_personas_gate()
        r = _responder(r, "personas_gate", "Varias personas con roles distintos")
        r = _responder(r, "perfil_usuario", "dueño")
        r = _responder(r, "perfil_usuario_continuar", "No")
        r = _responder(r, "experiencia_persona_narrativa", "x")
        r = _responder(r, "experiencia_persona_frecuencia", "Regularmente")
        r = _responder(r, "experiencia_persona_primera_vez", "x")
        r = _responder(r, "experiencia_persona_permisos_residual", [OPCION_ADMINISTRA_TODO])
        r = _responder(r, "plataforma", "Desde un navegador web")
        r = _responder(r, "interaccion_cuenta", "Nunca necesita cuenta")
        r = _responder(r, "interaccion_resultado_valor", "x")
        r = _responder(r, "contenido_gate", "No")
        r = _responder(r, "dato_recordar", "No")
        r = _responder(r, "monetizacion", "No, es gratis")
        r = _responder(r, "monetizacion_salida", "No, no le paga a nadie")
        assert siguiente_pregunta(r).pregunta_id == "admin_acciones"
        r = _responder(r, "admin_acciones", ["Consultar"])
        assert siguiente_pregunta(r).pregunta_id == "admin_que_mas"
        r = _responder(r, "admin_que_mas", ["Configuración"])
        assert siguiente_pregunta(r).pregunta_id == "admin_niveles"
        r = _responder(r, "admin_niveles", "No")
        assert siguiente_pregunta(r).pregunta_id == "admin_notificaciones"
        r = _responder(r, "admin_notificaciones", "pago nuevo")
        assert siguiente_pregunta(r).pregunta_id == "admin_notificaciones_canal"
        r = _responder(r, "admin_notificaciones_canal", "Correo")
        assert siguiente_pregunta(r).pregunta_id == "admin_notificaciones_continuar"
        r = _responder(r, "admin_notificaciones_continuar", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "admin_notificaciones"
        r = _responder(r, "admin_notificaciones", "usuario nuevo")
        r = _responder(r, "admin_notificaciones_canal", "Dentro del sistema")
        r = _responder(r, "admin_notificaciones_continuar", "No")
        assert siguiente_pregunta(r).pregunta_id == "seguridad_aislamiento"

    def test_administrador_incierto_confirmado_tambien_activa_el_dominio(self):
        r = _avanzar_hasta_personas_gate()
        r = _responder(r, "personas_gate", "No estoy seguro")
        r = _responder(r, "personas_gate_incierto", "Sí")
        r = _responder(r, "plataforma", "Desde un navegador web")
        r = _responder(r, "interaccion_cuenta", "Nunca necesita cuenta")
        r = _responder(r, "interaccion_resultado_valor", "x")
        r = _responder(r, "contenido_gate", "No")
        r = _responder(r, "dato_recordar", "No")
        r = _responder(r, "monetizacion", "No, es gratis")
        r = _responder(r, "monetizacion_salida", "No, no le paga a nadie")
        assert siguiente_pregunta(r).pregunta_id == "admin_acciones"

    def test_reportes_activa_su_bucle(self):
        r = _avanzar_hasta_personas_gate()
        r = _responder(r, "personas_gate", "No estoy seguro")
        r = _responder(r, "personas_gate_incierto", "Sí")
        r = _responder(r, "plataforma", "Desde un navegador web")
        r = _responder(r, "interaccion_cuenta", "Nunca necesita cuenta")
        r = _responder(r, "interaccion_resultado_valor", "x")
        r = _responder(r, "contenido_gate", "No")
        r = _responder(r, "dato_recordar", "No")
        r = _responder(r, "monetizacion", "No, es gratis")
        r = _responder(r, "monetizacion_salida", "No, no le paga a nadie")
        r = _responder(r, "admin_acciones", ["Consultar"])
        r = _responder(r, "admin_que_mas", ["Reportes"])
        assert siguiente_pregunta(r).pregunta_id == "admin_reportes_detalle"
        r = _responder(r, "admin_reportes_detalle", "ingresos")
        assert siguiente_pregunta(r).pregunta_id == "admin_reportes_continuar"
        r = _responder(r, "admin_reportes_continuar", "No")
        assert siguiente_pregunta(r).pregunta_id == "admin_niveles"


def _avanzar_hasta_seguridad() -> list:
    r = _avanzar_sin_monetizacion()
    siguiente = siguiente_pregunta(r)
    assert siguiente.pregunta_id == "seguridad_aislamiento"
    return r


class TestDominios09a08:
    def test_seguridad_es_secuencial(self):
        r = _avanzar_hasta_seguridad()
        r = _responder(r, "seguridad_aislamiento", "Crítico")
        assert siguiente_pregunta(r).pregunta_id == "seguridad_verificacion"
        r = _responder(r, "seguridad_verificacion", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "seguridad_sensible"
        r = _responder(r, "seguridad_sensible", "No")
        assert siguiente_pregunta(r).pregunta_id == "integraciones_gate"

    def _hasta_integraciones(self):
        r = _avanzar_hasta_seguridad()
        r = _responder(r, "seguridad_aislamiento", "No es importante")
        r = _responder(r, "seguridad_verificacion", "No")
        r = _responder(r, "seguridad_sensible", "No")
        assert siguiente_pregunta(r).pregunta_id == "integraciones_gate"
        return r

    def test_integraciones_no_cierra_de_inmediato(self):
        r = self._hasta_integraciones()
        r = _responder(r, "integraciones_gate", "No")
        assert siguiente_pregunta(r).pregunta_id == "automatizacion_gate"

    def test_integraciones_si_activa_bucle(self):
        r = self._hasta_integraciones()
        r = _responder(r, "integraciones_gate", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "integraciones_con_que"
        r = _responder(r, "integraciones_con_que", "WhatsApp")
        assert siguiente_pregunta(r).pregunta_id == "integraciones_para_que"
        r = _responder(r, "integraciones_para_que", "avisar")
        assert siguiente_pregunta(r).pregunta_id == "integraciones_continuar"
        r = _responder(r, "integraciones_continuar", "No")
        assert siguiente_pregunta(r).pregunta_id == "automatizacion_gate"

    def test_integraciones_continuar_si_repite_el_bucle(self):
        r = self._hasta_integraciones()
        r = _responder(r, "integraciones_gate", "Sí")
        r = _responder(r, "integraciones_con_que", "WhatsApp")
        r = _responder(r, "integraciones_para_que", "avisar")
        r = _responder(r, "integraciones_continuar", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "integraciones_con_que"

    def test_automatizacion_y_ia_son_gates_independientes(self):
        r = self._hasta_integraciones()
        r = _responder(r, "integraciones_gate", "No")
        r = _responder(r, "automatizacion_gate", "No")
        assert siguiente_pregunta(r).pregunta_id == "ia_producto_gate"
        r = _responder(r, "ia_producto_gate", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "sintesis_confirmacion"

    def test_automatizacion_si_activa_que_y_cuando(self):
        r = self._hasta_integraciones()
        r = _responder(r, "integraciones_gate", "No")
        r = _responder(r, "automatizacion_gate", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "automatizacion_que"
        r = _responder(r, "automatizacion_que", "emitir un recordatorio")
        assert siguiente_pregunta(r).pregunta_id == "automatizacion_cuando"
        r = _responder(r, "automatizacion_cuando", "Momento fijo")
        assert siguiente_pregunta(r).pregunta_id == "ia_producto_gate"


def _avanzar_hasta_sintesis() -> list:
    r = _avanzar_hasta_seguridad()
    r = _responder(r, "seguridad_aislamiento", "No es importante")
    r = _responder(r, "seguridad_verificacion", "No")
    r = _responder(r, "seguridad_sensible", "No")
    r = _responder(r, "integraciones_gate", "No")
    r = _responder(r, "automatizacion_gate", "No")
    r = _responder(r, "ia_producto_gate", "No")
    assert siguiente_pregunta(r).pregunta_id == "sintesis_confirmacion"
    return r


class TestDominio14Sintesis:
    def test_no_hace_preguntas_primarias_pide_confirmacion_y_excepciones(self):
        r = _avanzar_hasta_sintesis()
        r = _responder(r, "sintesis_confirmacion", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "sintesis_abandono"
        r = _responder(r, "sintesis_abandono", "x")
        assert siguiente_pregunta(r).pregunta_id == "sintesis_reanudacion"
        r = _responder(r, "sintesis_reanudacion", "x")
        assert siguiente_pregunta(r).pregunta_id == "sintesis_concurrencia"
        r = _responder(r, "sintesis_concurrencia", "x")
        assert siguiente_pregunta(r).pregunta_id == "sintesis_peor_caso"
        r = _responder(r, "sintesis_peor_caso", "x")
        assert siguiente_pregunta(r).pregunta_id == "marca_gate"

    def test_no_repite_ninguna_pregunta_de_01b_03_o_05(self):
        r = _avanzar_hasta_sintesis()
        ids_ya_respondidos = {resp.pregunta_id for resp in r}
        r = _responder(r, "sintesis_confirmacion", "No")
        r = _responder(r, "sintesis_abandono", "x")
        r = _responder(r, "sintesis_reanudacion", "x")
        r = _responder(r, "sintesis_concurrencia", "x")
        r = _responder(r, "sintesis_peor_caso", "x")
        nuevas = {resp.pregunta_id for resp in r} - ids_ya_respondidos
        interseccion_prohibida = nuevas & {
            "experiencia_persona_narrativa", "contenido_gate", "monetizacion",
        }
        assert interseccion_prohibida == set()


class TestSintesisDinamica:
    """Dominio 14, §3.1/§3.2: la síntesis se construye con el estado
    acumulado y la UI la presenta junto a la pregunta de confirmación."""

    def test_la_pregunta_de_confirmacion_cita_datos_reales_ya_respondidos(self):
        r = _avanzar_hasta_sintesis()
        pregunta = siguiente_pregunta(r)
        assert pregunta.pregunta_id == "sintesis_confirmacion"
        texto = pregunta.texto
        # Datos concretos ya respondidos en el recorrido hasta aquí
        # (`_avanzar_hasta_sintesis` -> ... -> `_avanzar_con_una_persona`):
        # el nombre del proyecto y el/la primera persona nombrada.
        assert "clientes" in texto  # perfil_usuario respondido en el camino
        assert "¿Es correcto este flujo" in texto

    def test_la_pregunta_no_conserva_el_texto_base_estatico(self):
        r = _avanzar_hasta_sintesis()
        pregunta = siguiente_pregunta(r)
        assert pregunta.texto != PREGUNTAS["sintesis_confirmacion"].texto

    def test_dos_recorridos_distintos_producen_sintesis_distintas(self):
        """No es un texto fijo: dos estados acumulados distintos deben
        producir una síntesis distinta (prueba de que de verdad lee el
        estado, no solo antepone una frase genérica)."""
        r_solo = _avanzar_hasta_personas_gate()
        r_solo = _responder(r_solo, "personas_gate", "Yo solo / todos igual")
        r_solo = _responder(r_solo, "plataforma", "Desde un navegador web")
        r_solo = _responder(r_solo, "interaccion_cuenta", "Nunca necesita cuenta")
        r_solo = _responder(r_solo, "interaccion_resultado_valor", "x")
        r_solo = _responder(r_solo, "contenido_gate", "No")
        r_solo = _responder(r_solo, "dato_recordar", "No")
        r_solo = _responder(r_solo, "monetizacion", "No, es gratis")
        r_solo = _responder(r_solo, "monetizacion_salida", "No, no le paga a nadie")
        r_solo = _responder(r_solo, "seguridad_aislamiento", "No es importante")
        r_solo = _responder(r_solo, "seguridad_verificacion", "No")
        r_solo = _responder(r_solo, "seguridad_sensible", "No")
        r_solo = _responder(r_solo, "integraciones_gate", "No")
        r_solo = _responder(r_solo, "automatizacion_gate", "No")
        r_solo = _responder(r_solo, "ia_producto_gate", "No")

        texto_solo = siguiente_pregunta(r_solo).pregunta_id
        assert texto_solo == "sintesis_confirmacion"
        sintesis_solo = siguiente_pregunta(r_solo).texto

        sintesis_con_personas = siguiente_pregunta(_avanzar_hasta_sintesis()).texto

        assert sintesis_solo != sintesis_con_personas
        assert "Un único tipo de usuario general" in sintesis_solo
        assert "clientes" in sintesis_con_personas

    def test_confirmar_si_continua_hacia_las_cuatro_excepciones(self):
        r = _avanzar_hasta_sintesis()
        r = _responder(r, "sintesis_confirmacion", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "sintesis_abandono"

    def test_confirmar_no_no_se_ignora_genera_gap_explicito(self, ):
        """§3.4: "No" no debe ignorarse — debe activar el mecanismo de
        Gap/reapertura YA existente de TF-0032 (`reglas_consecuencia`), sin
        inventar uno nuevo. La navegación en sí sigue igual (las 4
        excepciones se preguntan siempre, sección 3.3/3.5): el efecto de
        "No" vive en `reglas_consecuencia`, no en `arbol.py`."""
        from src.discovery.reglas_consecuencia import evaluar_reglas

        r = _avanzar_hasta_sintesis()
        r = _responder(r, "sintesis_confirmacion", "No")
        assert siguiente_pregunta(r).pregunta_id == "sintesis_abandono"

        hallazgos = evaluar_reglas("PROY-001", r)
        gaps_sintesis = [h for h in hallazgos if h.dominio == "sintesis"]
        assert len(gaps_sintesis) == 1
        assert gaps_sintesis[0].etiqueta == "flujo_rechazado"
        assert gaps_sintesis[0].tipo == "gap"


class TestConstruirSintesisNoInventaFueraDeAlcance:
    """Unidad directa sobre `_construir_sintesis` (mismo criterio que
    `TestHelperMultiple`): confirma la limitación documentada — `02`
    (funcionalidades) y `11` (restricciones) nunca aparecen, ni siquiera si
    ya hubiera filas para esas preguntas en `respuestas` (irían fuera de
    orden en el recorrido real, pero la función ni siquiera las lee)."""

    def test_ignora_funcionalidad_y_restricciones_aunque_existan_filas(self):
        from src.formulario.arbol import _construir_sintesis

        r = _avanzar_hasta_sintesis()
        r = _responder(r, "funcionalidad_declarada", "un secreto que no debería aparecer")
        r = _responder(r, "restriccion_tecnica", "otro secreto que no debería aparecer")
        sintesis = _construir_sintesis(r)
        assert "secreto" not in sintesis

    def test_sin_ninguna_respuesta_lo_dice_explicitamente(self):
        from src.formulario.arbol import _construir_sintesis
        assert _construir_sintesis([]) == (
            "Todavía no hay suficiente información capturada para armar una síntesis del flujo."
        )

    def test_cubre_contenido_datos_ambos_gates_admin_automatizacion_seguridad_integraciones(self):
        """Escenario "maximal": cada sección opcional de la síntesis tiene
        al menos una señal positiva, para comprobar que de verdad las lee
        (no solo las secciones ya cubiertas por los escenarios mínimos)."""
        from src.formulario.arbol import _construir_sintesis

        r = []
        r = _responder(r, "plataforma", "Desde el celular")
        r = _responder(r, "interaccion_resultado_valor", "Termina su compra.")
        r = _responder(r, "contenido_gate", "Sí")
        r = _responder(r, "contenido_tipo", ["Cursos/lecciones"])
        r = _responder(r, "contenido_creador", "Solo admin")
        r = _responder(r, "contenido_curso_examenes", "Sí")
        r = _responder(r, "contenido_curso_calificacion_minima", "80")
        r = _responder(r, "dato_recordar", "Sí")
        r = _responder(r, "dato_recordar_detalle", "Historial de compras")
        r = _responder(r, "dato_sensible", "Sí")
        r = _responder(r, "monetizacion", "Sí, de alguna forma")
        r = _responder(r, "monetizacion_forma", "Comisión")
        r = _responder(r, "monetizacion_salida", "Sí, le paga a alguien")
        r = _responder(r, "monetizacion_salida_forma", "Suscripción")
        r = _responder(r, "experiencia_persona_permisos_residual", [OPCION_ADMINISTRA_TODO])
        r = _responder(r, "admin_acciones", ["Suspender"])
        r = _responder(r, "automatizacion_gate", "Sí")
        r = _responder(r, "automatizacion_que", "enviar un recordatorio")
        r = _responder(r, "ia_producto_gate", "Sí")
        r = _responder(r, "seguridad_aislamiento", "Crítico")
        r = _responder(r, "integraciones_con_que", "WhatsApp")

        sintesis = _construir_sintesis(r)

        assert "Cursos/lecciones" in sintesis and "calificación mínima: 80" in sintesis
        assert "Historial de compras" in sintesis and "(sensible)" in sintesis
        assert "Cobra dinero" in sintesis and "comisión" in sintesis.lower()
        assert "Le paga o le entrega dinero" in sintesis and "suscripción" in sintesis.lower()
        assert "Administración" in sintesis and "suspender" in sintesis.lower()
        assert "enviar un recordatorio" in sintesis
        assert "Usa IA" in sintesis
        assert "aislamiento entre usuarios es: crítico" in sintesis.lower()
        assert "WhatsApp" in sintesis


def _avanzar_hasta_marca() -> list:
    r = _avanzar_hasta_sintesis()
    r = _responder(r, "sintesis_confirmacion", "Sí")
    r = _responder(r, "sintesis_abandono", "x")
    r = _responder(r, "sintesis_reanudacion", "x")
    r = _responder(r, "sintesis_concurrencia", "x")
    r = _responder(r, "sintesis_peor_caso", "x")
    assert siguiente_pregunta(r).pregunta_id == "marca_gate"
    return r


class TestDominio12MarcaIndependiente:
    def test_nada_no_es_prioridad_cierra_de_inmediato(self):
        r = _avanzar_hasta_marca()
        r = _responder(r, "marca_gate", "No tengo nada")
        assert siguiente_pregunta(r).pregunta_id == "marca_prioridad"
        r = _responder(r, "marca_prioridad", "No")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_declarada"

    def test_nada_pero_prioridad_pide_estilo(self):
        r = _avanzar_hasta_marca()
        r = _responder(r, "marca_gate", "No tengo nada")
        r = _responder(r, "marca_prioridad", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "marca_estilo"

    def test_necesito_ayuda_pide_estilo_directo(self):
        r = _avanzar_hasta_marca()
        r = _responder(r, "marca_gate", "Necesito ayuda para definirlo")
        assert siguiente_pregunta(r).pregunta_id == "marca_estilo"
        r = _responder(r, "marca_estilo", "Moderno")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_declarada"

    def test_tengo_todo_recorre_todo_el_sub_arbol(self):
        r = _avanzar_hasta_marca()
        r = _responder(r, "marca_gate", "Tengo todo")
        assert siguiente_pregunta(r).pregunta_id == "marca_logo"
        r = _responder(r, "marca_logo", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "marca_logo_conservar"
        r = _responder(r, "marca_logo_conservar", "Conservarlo")
        assert siguiente_pregunta(r).pregunta_id == "marca_colores"
        r = _responder(r, "marca_colores", "azul")
        assert siguiente_pregunta(r).pregunta_id == "marca_tipografias"
        r = _responder(r, "marca_tipografias", "sans")
        assert siguiente_pregunta(r).pregunta_id == "marca_manual"
        r = _responder(r, "marca_manual", "No")
        assert siguiente_pregunta(r).pregunta_id == "marca_referencias"
        r = _responder(r, "marca_referencias", "x")
        assert siguiente_pregunta(r).pregunta_id == "marca_tono"
        r = _responder(r, "marca_tono", "Cercano")
        assert siguiente_pregunta(r).pregunta_id == "marca_continuidad"
        r = _responder(r, "marca_continuidad", "x")
        assert siguiente_pregunta(r).pregunta_id == "marca_paraguas"
        r = _responder(r, "marca_paraguas", "Independiente")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_declarada"

    def test_tengo_logo_sin_conservarlo_no_pide_logo_conservar_dos_veces(self):
        r = _avanzar_hasta_marca()
        r = _responder(r, "marca_gate", "Tengo algunas cosas")
        r = _responder(r, "marca_logo", "No")
        assert siguiente_pregunta(r).pregunta_id == "marca_colores"


def _avanzar_hasta_funcionalidad() -> list:
    r = _avanzar_hasta_marca()
    r = _responder(r, "marca_gate", "No tengo nada")
    r = _responder(r, "marca_prioridad", "No")
    assert siguiente_pregunta(r).pregunta_id == "funcionalidad_declarada"
    return r


class TestDominio02Funcionalidades:
    def test_bucle_simple_con_prioridad(self):
        r = _avanzar_hasta_funcionalidad()
        r = _responder(r, "funcionalidad_declarada", "registrar pedidos")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_prioridad"
        r = _responder(r, "funcionalidad_prioridad", "Indispensable")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_declarada_continuar"
        r = _responder(r, "funcionalidad_declarada_continuar", "No")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_prohibida"

    def test_respuesta_vaga_dispara_pedido_de_ejemplo(self):
        r = _avanzar_hasta_funcionalidad()
        r = _responder(r, "funcionalidad_declarada", "administrar")
        r = _responder(r, "funcionalidad_prioridad", "Indispensable")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_ejemplo"
        r = _responder(r, "funcionalidad_ejemplo", "un ejemplo concreto")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_declarada_continuar"

    def test_respuesta_concreta_no_dispara_ejemplo(self):
        r = _avanzar_hasta_funcionalidad()
        r = _responder(r, "funcionalidad_declarada", "registrar un pedido nuevo con productos")
        r = _responder(r, "funcionalidad_prioridad", "Indispensable")
        assert siguiente_pregunta(r).pregunta_id != "funcionalidad_ejemplo"

    def test_prohibida_se_pregunta_una_sola_vez_tras_el_bucle(self):
        r = _avanzar_hasta_funcionalidad()
        r = _responder(r, "funcionalidad_declarada", "a")
        r = _responder(r, "funcionalidad_prioridad", "Indispensable")
        r = _responder(r, "funcionalidad_declarada_continuar", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_declarada"
        r = _responder(r, "funcionalidad_declarada", "b")
        r = _responder(r, "funcionalidad_prioridad", "No urgente")
        r = _responder(r, "funcionalidad_declarada_continuar", "No")
        assert siguiente_pregunta(r).pregunta_id == "funcionalidad_prohibida"
        r = _responder(r, "funcionalidad_prohibida", "nada")
        assert siguiente_pregunta(r).pregunta_id == "restriccion_tecnica"


def _avanzar_hasta_restricciones() -> list:
    r = _avanzar_hasta_funcionalidad()
    r = _responder(r, "funcionalidad_declarada", "a")
    r = _responder(r, "funcionalidad_prioridad", "Indispensable")
    r = _responder(r, "funcionalidad_declarada_continuar", "No")
    r = _responder(r, "funcionalidad_prohibida", "nada")
    assert siguiente_pregunta(r).pregunta_id == "restriccion_tecnica"
    return r


class TestDominio11y13RestriccionesYCierre:
    def test_restricciones_son_secuenciales(self):
        r = _avanzar_hasta_restricciones()
        r = _responder(r, "restriccion_tecnica", "")
        assert siguiente_pregunta(r).pregunta_id == "restriccion_tiempo_presupuesto"
        r = _responder(r, "restriccion_tiempo_presupuesto", "")
        assert siguiente_pregunta(r).pregunta_id == "restriccion_negocio"
        r = _responder(r, "restriccion_negocio", "")
        assert siguiente_pregunta(r).pregunta_id == "restriccion_legal"
        r = _responder(r, "restriccion_legal", "No")
        assert siguiente_pregunta(r).pregunta_id == "cierre_exito"

    def test_diferido_en_funcionalidades_exige_confirmacion_en_cierre(self):
        r = _avanzar_hasta_funcionalidad()
        r = _responder(r, "funcionalidad_declarada", "reportes avanzados")
        r = _responder(r, "funcionalidad_prioridad", "Importante, puede esperar")
        r = _responder(r, "funcionalidad_declarada_continuar", "No")
        r = _responder(r, "funcionalidad_prohibida", "nada")
        r = _responder(r, "restriccion_tecnica", "")
        r = _responder(r, "restriccion_tiempo_presupuesto", "")
        r = _responder(r, "restriccion_negocio", "")
        r = _responder(r, "restriccion_legal", "No")
        r = _responder(r, "cierre_exito", "que funcione")
        assert siguiente_pregunta(r).pregunta_id == "cierre_confirmar_diferido"
        r = _responder(r, "cierre_confirmar_diferido", "Sí")
        assert siguiente_pregunta(r).pregunta_id == "cierre_libre"

    def test_sin_diferidos_no_pide_confirmacion(self):
        r = _avanzar_hasta_restricciones()
        r = _responder(r, "restriccion_tecnica", "")
        r = _responder(r, "restriccion_tiempo_presupuesto", "")
        r = _responder(r, "restriccion_negocio", "")
        r = _responder(r, "restriccion_legal", "No")
        r = _responder(r, "cierre_exito", "x")
        assert siguiente_pregunta(r).pregunta_id == "cierre_libre"
        r = _responder(r, "cierre_libre", "")
        assert siguiente_pregunta(r) is None


class TestArbolCompleto:
    def test_camino_minimo_termina_en_none(self):
        """Todo lo condicional se deja en su rama más corta — el árbol debe
        poder completarse igual, sin bloquear nunca."""
        r = []
        r = _responder(r, "nuevo_o_existente", "Nuevo")
        r = _responder(r, "nombre_proyecto", "")
        r = _responder(r, "nombre_proyecto_estado", "Necesito ayuda para definirlo")
        r = _responder(r, "problema_objetivo", "una calculadora")
        r = _responder(r, "personas_gate", "Yo solo / todos igual")
        r = _responder(r, "plataforma", "No estoy seguro todavía")
        r = _responder(r, "interaccion_cuenta", "Nunca necesita cuenta")
        r = _responder(r, "interaccion_resultado_valor", "x")
        r = _responder(r, "contenido_gate", "No estoy seguro")
        r = _responder(r, "dato_recordar", "No estoy seguro")
        r = _responder(r, "monetizacion", "Todavía no lo he decidido")
        r = _responder(r, "monetizacion_salida", "Todavía no lo he decidido")
        r = _responder(r, "seguridad_aislamiento", "No es importante")
        r = _responder(r, "seguridad_verificacion", "No")
        r = _responder(r, "seguridad_sensible", "No")
        r = _responder(r, "integraciones_gate", "No lo sé")
        r = _responder(r, "automatizacion_gate", "No sé")
        r = _responder(r, "ia_producto_gate", "No sé")
        r = _responder(r, "sintesis_confirmacion", "Sí")
        r = _responder(r, "sintesis_abandono", "")
        r = _responder(r, "sintesis_reanudacion", "")
        r = _responder(r, "sintesis_concurrencia", "")
        r = _responder(r, "sintesis_peor_caso", "")
        r = _responder(r, "marca_gate", "No tengo nada")
        r = _responder(r, "marca_prioridad", "No")
        r = _responder(r, "funcionalidad_declarada", "sumar")
        r = _responder(r, "funcionalidad_prioridad", "Indispensable")
        r = _responder(r, "funcionalidad_declarada_continuar", "No")
        r = _responder(r, "funcionalidad_prohibida", "")
        r = _responder(r, "restriccion_tecnica", "")
        r = _responder(r, "restriccion_tiempo_presupuesto", "")
        r = _responder(r, "restriccion_negocio", "")
        r = _responder(r, "restriccion_legal", "No sé")
        r = _responder(r, "cierre_exito", "")
        r = _responder(r, "cierre_libre", "")
        assert siguiente_pregunta(r) is None
