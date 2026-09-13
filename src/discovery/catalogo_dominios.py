"""TF-0032/TF-0033 — Metadata de dominio+etiqueta sobre el catálogo de
preguntas ya existente (`src.formulario.preguntas`), y su resolución hacia
un `pregunta_id` concreto (A1).

Qwen nunca ve el catálogo completo de preguntas: solo ve nombres de dominio
y, por dominio activo en la corrida, su vocabulario cerrado de etiquetas
(`dominios_activos()`). El mapeo etiqueta→`pregunta_id` concreto lo hace
únicamente este módulo (`resolver_pregunta()`), código puro — nunca Qwen.
Una combinación (dominio, etiqueta) sin match no produce ningún
`pregunta_id` (nunca se inventa uno): queda como hallazgo sin pregunta
catalogada, visible para revisión humana del catálogo.

TF-0033 amplía este mapeo de 27 a los ~90 `pregunta_id` del catálogo de 16
dominios ("Discovery Inteligente", ver `docs/tickets/TF-0033.md`). Los
nombres de dominio corresponden 1:1 a los 16 dominios de la especificación;
las etiquetas agrupan preguntas que describen la misma faceta dentro de un
dominio (mismo criterio que TF-0032: vocabulario cerrado y pequeño por
dominio, nunca una etiqueta por cada `pregunta_id`).

No cubre los controles de bucle puros (`*_continuar`): nunca tiene sentido
reactivar "¿hay otro?" como resolución de un hallazgo, solo la pregunta de
contenido real del bucle — mismo criterio que TF-0032.

Funciones puras: no abren conexión a BD, no llaman a ningún proveedor de IA.
"""
from __future__ import annotations

from typing import Optional

__all__ = ["CATALOGO_DOMINIOS", "dominios_activos", "resolver_pregunta"]

# pregunta_id -> (dominio, etiqueta).
CATALOGO_DOMINIOS: dict = {
    # --- 00 Identidad y propósito -----------------------------------------
    "nuevo_o_existente": ("identidad", "tipo_proyecto"),
    "referencia_proyecto_existente": ("identidad", "referencia_existente"),
    "nombre_proyecto": ("identidad", "nombre"),
    "nombre_proyecto_estado": ("identidad", "nombre"),
    # `problema_objetivo` declarada antes que `objetivo_proyecto_existente`
    # a propósito: ambas comparten ("identidad", "proposito") y la primera
    # en orden de declaración es la que `resolver_pregunta()` devuelve como
    # canónica — debe ser la pregunta universal, no la condicional a "ya
    # existe algo construido".
    "problema_objetivo": ("identidad", "proposito"),
    "problema_objetivo_desglose": ("identidad", "proposito"),
    "objetivo_proyecto_existente": ("identidad", "proposito"),

    # --- 01 / 01b Personas ---------------------------------------------------
    "personas_gate": ("personas", "tiene_roles"),
    "personas_gate_incierto": ("personas", "administrador_incierto"),
    "perfil_usuario": ("personas", "tipo_usuario"),
    "experiencia_persona_narrativa": ("personas", "experiencia"),
    "experiencia_persona_frecuencia": ("personas", "frecuencia"),
    "experiencia_persona_primera_vez": ("personas", "experiencia"),
    "experiencia_persona_permisos_residual": ("personas", "permisos"),
    "experiencia_persona_permisos_otra": ("personas", "permisos"),

    # --- 02 Funcionalidades ----------------------------------------------
    "funcionalidad_declarada": ("funcionalidad", "funcionalidad_faltante"),
    "funcionalidad_prioridad": ("funcionalidad", "prioridad"),
    "funcionalidad_ejemplo": ("funcionalidad", "funcionalidad_faltante"),
    "funcionalidad_prohibida": ("funcionalidad", "prohibida"),

    # --- 03 Contenido -------------------------------------------------------
    "contenido_gate": ("contenido", "existencia"),
    "contenido_tipo": ("contenido", "tipo"),
    "contenido_creador": ("contenido", "creador"),
    "contenido_curso_modulos": ("contenido", "estructura_curso"),
    "contenido_curso_orden": ("contenido", "estructura_curso"),
    "contenido_curso_examenes": ("contenido", "estructura_curso"),
    "contenido_curso_calificacion_minima": ("contenido", "estructura_curso"),
    "contenido_aprobacion": ("contenido", "aprobacion"),

    # --- 04 Datos a conservar -----------------------------------------------
    "dato_recordar": ("datos", "existencia_de_dato"),
    "dato_recordar_detalle": ("datos", "existencia_de_dato"),
    "dato_sensible": ("datos", "sensibilidad"),
    "dato_retencion": ("datos", "retencion"),
    "dato_quien_ve": ("datos", "acceso"),
    "dato_quien_modifica": ("datos", "acceso"),

    # --- 05 Monetización y pagos ---------------------------------------------
    "monetizacion": ("monetizacion", "modelo_cobro"),
    "monetizacion_forma": ("monetizacion", "modelo_cobro"),
    "monetizacion_planes_n": ("monetizacion", "planes"),
    "monetizacion_plan_detalle": ("monetizacion", "planes"),
    "monetizacion_prueba_gratis": ("monetizacion", "planes"),
    "monetizacion_impago": ("monetizacion", "incumplimiento"),
    "monetizacion_autogestion": ("monetizacion", "control_plan"),
    "monetizacion_pago_unico_detalle": ("monetizacion", "modelo_cobro"),
    "monetizacion_reembolso": ("monetizacion", "incumplimiento"),
    "monetizacion_factura": ("monetizacion", "comprobante"),
    "monetizacion_salida": ("monetizacion", "modelo_pago_salida"),
    "monetizacion_salida_forma": ("monetizacion", "modelo_pago_salida"),
    "monetizacion_salida_incumplimiento": ("monetizacion", "incumplimiento_salida"),
    "monetizacion_salida_control": ("monetizacion", "control_salida"),

    # --- 06 Administración y operación ---------------------------------------
    "admin_acciones": ("administracion", "permisos_admin"),
    "admin_que_mas": ("administracion", "alcance_admin"),
    "admin_reportes_detalle": ("administracion", "reportes"),
    "admin_niveles": ("administracion", "niveles"),
    "admin_notificaciones": ("administracion", "notificaciones"),
    "admin_notificaciones_canal": ("administracion", "notificaciones"),

    # --- 07 Interacción / experiencia -----------------------------------------
    "plataforma": ("interaccion", "alcance_plataforma"),
    "plataforma_detalle": ("interaccion", "alcance_plataforma"),
    "plataforma_offline": ("interaccion", "modo_offline"),
    "interaccion_cuenta": ("interaccion", "necesidad_cuenta"),
    "interaccion_resultado_valor": ("interaccion", "resultado_valor"),

    # --- 08 Automatización e IA -------------------------------------------------
    "automatizacion_gate": ("automatizacion", "automatizacion"),
    "automatizacion_que": ("automatizacion", "automatizacion"),
    "automatizacion_cuando": ("automatizacion", "automatizacion"),
    "ia_producto_gate": ("automatizacion", "ia_producto"),

    # --- 09 Seguridad funcional -----------------------------------------------
    "seguridad_aislamiento": ("seguridad", "aislamiento"),
    "seguridad_verificacion": ("seguridad", "verificacion_identidad"),
    "seguridad_sensible": ("seguridad", "informacion_delicada"),

    # --- 10 Integraciones -----------------------------------------------------
    "integraciones_gate": ("integraciones", "existencia"),
    "integraciones_con_que": ("integraciones", "con_que"),
    "integraciones_para_que": ("integraciones", "para_que"),

    # --- 11 Restricciones y preferencias ---------------------------------------
    "restriccion_tecnica": ("restricciones", "restriccion_tecnica"),
    "restriccion_tiempo_presupuesto": ("restricciones", "restriccion_tiempo"),
    "restriccion_negocio": ("restricciones", "restriccion_negocio"),
    "restriccion_legal": ("restricciones", "restriccion_legal"),

    # --- 12 Identidad de marca --------------------------------------------------
    "marca_gate": ("marca", "estado_identidad"),
    "marca_prioridad": ("marca", "prioridad"),
    "marca_estilo": ("marca", "estilo"),
    "marca_logo": ("marca", "logo"),
    "marca_logo_conservar": ("marca", "logo"),
    "marca_colores": ("marca", "estilo"),
    "marca_tipografias": ("marca", "estilo"),
    "marca_manual": ("marca", "manual"),
    "marca_referencias": ("marca", "estilo"),
    "marca_tono": ("marca", "tono"),
    "marca_continuidad": ("marca", "continuidad"),
    "marca_paraguas": ("marca", "continuidad"),

    # --- 13 Cierre / alcance del MVP ------------------------------------------
    "cierre_exito": ("cierre", "criterio_exito"),
    "cierre_confirmar_diferido": ("cierre", "alcance_mvp"),
    "cierre_libre": ("cierre", "informacion_adicional"),

    # --- 14 Cómo funciona (síntesis) --------------------------------------------
    "sintesis_confirmacion": ("sintesis", "confirmacion_flujo"),
    "sintesis_abandono": ("sintesis", "excepcion_universal"),
    "sintesis_reanudacion": ("sintesis", "excepcion_universal"),
    "sintesis_concurrencia": ("sintesis", "excepcion_universal"),
    "sintesis_peor_caso": ("sintesis", "excepcion_universal"),
}

# (dominio, etiqueta) -> pregunta_id "canónico" a reactivar. Se construye a
# partir de CATALOGO_DOMINIOS en su orden de declaración: la primera
# pregunta_id de cada combinación es la que se reactiva.
_MAPA_ETIQUETA_A_PREGUNTA: dict = {}
for _pregunta_id, _clave in CATALOGO_DOMINIOS.items():
    _MAPA_ETIQUETA_A_PREGUNTA.setdefault(_clave, _pregunta_id)


def dominios_activos(respuestas: list) -> dict:
    """Dominios presentes en `respuestas` (ya respondidas) -> tupla
    ordenada de sus etiquetas — el único vocabulario que ve Qwen, nunca el
    catálogo de preguntas en sí."""
    por_dominio: dict = {}
    ids_presentes = {r.pregunta_id for r in respuestas}
    for pregunta_id, (dominio, etiqueta) in CATALOGO_DOMINIOS.items():
        if pregunta_id in ids_presentes:
            por_dominio.setdefault(dominio, set()).add(etiqueta)
    return {dominio: tuple(sorted(etiquetas)) for dominio, etiquetas in por_dominio.items()}


def resolver_pregunta(dominio: str, etiqueta: str) -> Optional[str]:
    """`pregunta_id` a reactivar para `(dominio, etiqueta)`, o `None` si no
    hay ninguna registrada — nunca se inventa una."""
    return _MAPA_ETIQUETA_A_PREGUNTA.get((dominio, etiqueta))
