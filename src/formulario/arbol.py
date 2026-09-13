"""Árbol de decisión determinista: `siguiente_pregunta()`.

TF-0033 — "Discovery Inteligente": 16 dominios con puerta propia, en vez del
árbol lineal de 27 preguntas. Dada la lista de respuestas ya registradas
para un expediente (en el orden en que se dieron — mismo contrato que
`RepositorioRespuestasFormulario.listar()`), decide cuál es la siguiente
pregunta a mostrar, o `None` si el árbol ya se completó. Función pura: no
abre conexión a la base de datos, no llama a ningún proveedor de IA, no
interpreta el significado de ninguna respuesta más allá de las heurísticas
sintácticas baratas de `src.formulario.heuristicas` (D3: Qwen nunca decide
el flujo del formulario).

Orden de dominios (EXPERIMENTAL — D1 de la especificación, no una
arquitectura definitiva): 00, 01, 01b, 07, 03, 04, 05, 06, 09, 10, 08, 14,
12, 02, 11, 13. El dominio `07` (Interacción/experiencia) no aparece en el
orden dado en el contrato de este ticket (omisión, no una decisión
deliberada); se inserta aquí justo después de `01b`, por ser un dominio
corto y siempre-presente sin dependencias declaradas — señalado
explícitamente en el reporte de esta implementación, no decidido en
silencio.

Dominio 06 (Administración) se activa por una señal determinista, no por su
propia puerta: cualquier persona de `01b` cuyo checklist de permisos
residuales incluya "Controlar/administrar todo el proyecto", o una
confirmación explícita en `personas_gate_incierto` — mecanismo elegido en
esta implementación para el `SLOT:06.disparador` de la especificación (no
es una pregunta nueva, es cableado de una señal ya capturada).

Dominio 06 no recursa automáticamente varios "niveles" de administración
completos en esta primera implementación (simplificación deliberada,
documentada en `docs/tickets/TF-0033.md`): `admin_niveles` se registra como
dato, sin re-disparar el sub-árbol completo — evolución incremental futura,
no una limitación oculta.

Dominio 04 (Datos): la confirmación cruzada frente a una suscripción ya
declarada ("Q4.1x" de la especificación) NO se implementa como rama
síncrona de este árbol — en el orden vigente, `05` se pregunta después de
`04`, así que la contradicción solo puede detectarse más tarde. Se resuelve
enteramente con el mecanismo ya existente de TF-0032
(`src.discovery.reglas_consecuencia` + `Gap`/`Contradiccion` +
`procesar_reapertura`, sin tocar): la regla `_regla_suscripcion_sin_dato` ya
opera sobre los mismos `pregunta_id` (`monetizacion`, `dato_recordar`), que
este catálogo conserva verbatim.

Dominio 14 (Cómo funciona): `_construir_sintesis()` arma, de forma
determinista y sin IA, un resumen del flujo a partir de lo ya respondido en
00/01/01b/07/03/04/05/06/09/10/08 (los únicos dominios ya cerrados quando
`14` corre — `02`/`11` van después en el orden vigente, D1, así que sus
datos **no existen todavía** en este punto y quedan fuera de la síntesis;
limitación real del orden experimental, documentada aquí y en
`docs/tickets/TF-0033.md`, no un olvido). El texto de `sintesis_confirmacion`
se construye dinámicamente (`dataclasses.replace` sobre la definición base)
para incluir esa síntesis junto con la pregunta de confirmación.

Si `sintesis_confirmacion` es "No", este árbol **no** decide por sí mismo
qué dominio reabrir (no inventa una inferencia semántica): el árbol solo
captura la respuesta. Es una nueva regla determinista en
`src.discovery.reglas_consecuencia` (`_regla_sintesis_rechazada`, evaluada
por `evaluar_reglas()` exactamente igual que `_regla_suscripcion_sin_dato`,
sin tocar `discovery.py`) la que registra un `Gap` explícito
(`sintesis.flujo_rechazado`) — **sin** `pregunta_id` resoluble en
`catalogo_dominios` a propósito, para que quede visible en
`/resultado` y en el estado de la corrida sin fingir saber qué reabrir.

El llamador (fuera de este paquete: `app.py`, o un script) es quien:
  1. obtiene `RepositorioRespuestasFormulario().listar(codigo)`;
  2. le pasa esa lista a `siguiente_pregunta()`;
  3. muestra la pregunta devuelta;
  4. valida+serializa la respuesta (`src.formulario.respuestas`) y la
     persiste con `RepositorioRespuestasFormulario().registrar(...)`.

Este módulo nunca importa `src.repositorios` ni escribe nada. Tampoco crea
`Requisito`/`Capacidad`/etc.: esa interpretación es responsabilidad
exclusiva de Discovery.
"""
from __future__ import annotations

import dataclasses
from typing import Optional

from src.expediente.modelo import RespuestaFormulario
from src.formulario.heuristicas import es_respuesta_vaga, sugiere_enumeracion
from src.formulario.preguntas import (
    OPCION_ADMINISTRA_TODO, OPCION_EXISTENTE, OPCION_MONETIZACION_SI,
    OPCION_OTRA_COSA, OPCION_PAGA_A_OTROS_SI, OPCION_PERSONAS_INCIERTO,
    OPCION_PERSONAS_VARIAS, OPCION_PLATAFORMA_CELULAR, OPCION_PLATAFORMA_VARIAS,
    OPCION_DETALLE_CELULAR, OPCION_SI, PREGUNTAS, DefinicionPregunta,
)
from src.formulario.respuestas import deserializar_respuesta

__all__ = ["siguiente_pregunta"]


def _respuestas_de(respuestas: list[RespuestaFormulario], pregunta_id: str) -> list[RespuestaFormulario]:
    return [r for r in respuestas if r.pregunta_id == pregunta_id]


def _ultima(respuestas: list[RespuestaFormulario], pregunta_id: str) -> Optional[str]:
    de_esta = _respuestas_de(respuestas, pregunta_id)
    return de_esta[-1].respuesta if de_esta else None


def _respondida(respuestas: list[RespuestaFormulario], pregunta_id: str) -> bool:
    return _ultima(respuestas, pregunta_id) is not None


def _multiple(respuestas: list[RespuestaFormulario], pregunta_id: str) -> list:
    valor = _ultima(respuestas, pregunta_id)
    if valor is None:
        return []
    return deserializar_respuesta(PREGUNTAS[pregunta_id], valor)


def _paso_bloque_repetible(
    respuestas: list[RespuestaFormulario], contenido_id: str, continuar_id: str,
) -> Optional[DefinicionPregunta]:
    """Bucle simple de una sola pregunta repetible: pide contenido, pregunta
    si hay otro, repite mientras la respuesta sea "Sí". `None` cuando el
    bloque ya terminó (último "continuar" fue "No")."""
    n_contenido = len(_respuestas_de(respuestas, contenido_id))
    n_continuar = len(_respuestas_de(respuestas, continuar_id))

    if n_contenido == 0:
        return PREGUNTAS[contenido_id]
    if n_contenido > n_continuar:
        return PREGUNTAS[continuar_id]
    if _ultima(respuestas, continuar_id) == OPCION_SI:
        return PREGUNTAS[contenido_id]
    return None


def _paso_bloque_repetible_3(
    respuestas: list[RespuestaFormulario], id_a: str, id_b: str, continuar_id: str,
) -> Optional[DefinicionPregunta]:
    """Igual que `_paso_bloque_repetible`, con un paso intermedio fijo
    (`id_a` -> `id_b` -> ¿continuar?) antes de repetir."""
    r_a = _respuestas_de(respuestas, id_a)
    r_b = _respuestas_de(respuestas, id_b)
    r_continuar = _respuestas_de(respuestas, continuar_id)

    if len(r_a) == 0:
        return PREGUNTAS[id_a]
    if len(r_a) > len(r_b):
        return PREGUNTAS[id_b]
    if len(r_b) > len(r_continuar):
        return PREGUNTAS[continuar_id]
    if _ultima(respuestas, continuar_id) == OPCION_SI:
        return PREGUNTAS[id_a]
    return None


def _paso_experiencia_por_persona(
    respuestas: list[RespuestaFormulario], n_personas: int,
) -> Optional[DefinicionPregunta]:
    """Dominio 01b: un sub-recorrido por cada persona nombrada en `01`
    (`n_personas` = cuántas ya se nombraron, decisión ya cerrada en ese
    dominio). Narrativa -> frecuencia -> primera vez -> permisos residuales
    -> (si marcó "Otra cosa") detalle de esos permisos — se repite
    exactamente `n_personas` veces, sin pregunta de continuación propia (el
    conteo ya lo fija `01`)."""
    if n_personas == 0:
        return None

    r_narrativa = _respuestas_de(respuestas, "experiencia_persona_narrativa")
    r_frecuencia = _respuestas_de(respuestas, "experiencia_persona_frecuencia")
    r_primera_vez = _respuestas_de(respuestas, "experiencia_persona_primera_vez")
    r_permisos = _respuestas_de(respuestas, "experiencia_persona_permisos_residual")
    r_otra = _respuestas_de(respuestas, "experiencia_persona_permisos_otra")

    if len(r_narrativa) > len(r_frecuencia):
        return PREGUNTAS["experiencia_persona_frecuencia"]
    if len(r_frecuencia) > len(r_primera_vez):
        return PREGUNTAS["experiencia_persona_primera_vez"]
    if len(r_primera_vez) > len(r_permisos):
        return PREGUNTAS["experiencia_persona_permisos_residual"]

    pregunta_permisos = PREGUNTAS["experiencia_persona_permisos_residual"]
    n_otra_esperadas = sum(
        1 for r in r_permisos
        if OPCION_OTRA_COSA in deserializar_respuesta(pregunta_permisos, r.respuesta)
    )
    if n_otra_esperadas > len(r_otra):
        return PREGUNTAS["experiencia_persona_permisos_otra"]

    if len(r_narrativa) < n_personas:
        return PREGUNTAS["experiencia_persona_narrativa"]
    return None


def _activa_administracion(respuestas: list[RespuestaFormulario]) -> bool:
    """`SLOT:06.disparador` resuelto: alguna persona marcó explícitamente
    que administra/controla todo el proyecto (checklist de `01b`), o se
    confirmó un administrador distinto vía `personas_gate_incierto`."""
    if _ultima(respuestas, "personas_gate_incierto") == OPCION_SI:
        return True
    pregunta_permisos = PREGUNTAS["experiencia_persona_permisos_residual"]
    for r in _respuestas_de(respuestas, "experiencia_persona_permisos_residual"):
        if OPCION_ADMINISTRA_TODO in deserializar_respuesta(pregunta_permisos, r.respuesta):
            return True
    return False


def _paso_notificaciones(respuestas: list[RespuestaFormulario]) -> Optional[DefinicionPregunta]:
    r_notif = _respuestas_de(respuestas, "admin_notificaciones")
    r_canal = _respuestas_de(respuestas, "admin_notificaciones_canal")
    r_continuar = _respuestas_de(respuestas, "admin_notificaciones_continuar")

    if len(r_notif) == 0:
        return PREGUNTAS["admin_notificaciones"]
    if len(r_notif) > len(r_canal):
        return PREGUNTAS["admin_notificaciones_canal"]
    if len(r_canal) > len(r_continuar):
        return PREGUNTAS["admin_notificaciones_continuar"]
    if _ultima(respuestas, "admin_notificaciones_continuar") == OPCION_SI:
        return PREGUNTAS["admin_notificaciones"]
    return None


def _paso_datos(respuestas: list[RespuestaFormulario]) -> Optional[DefinicionPregunta]:
    r_detalle = _respuestas_de(respuestas, "dato_recordar_detalle")
    r_sensible = _respuestas_de(respuestas, "dato_sensible")
    r_retencion = _respuestas_de(respuestas, "dato_retencion")
    r_ve = _respuestas_de(respuestas, "dato_quien_ve")
    r_modifica = _respuestas_de(respuestas, "dato_quien_modifica")
    r_continuar = _respuestas_de(respuestas, "dato_recordar_detalle_continuar")

    if len(r_detalle) == 0:
        return PREGUNTAS["dato_recordar_detalle"]
    if len(r_detalle) > len(r_sensible):
        return PREGUNTAS["dato_sensible"]
    if len(r_sensible) > len(r_retencion):
        return PREGUNTAS["dato_retencion"]
    if len(r_retencion) > len(r_ve):
        return PREGUNTAS["dato_quien_ve"]
    if len(r_ve) > len(r_modifica):
        return PREGUNTAS["dato_quien_modifica"]
    if len(r_modifica) > len(r_continuar):
        return PREGUNTAS["dato_recordar_detalle_continuar"]
    if _ultima(respuestas, "dato_recordar_detalle_continuar") == OPCION_SI:
        return PREGUNTAS["dato_recordar_detalle"]
    return None


def _paso_funcionalidades(respuestas: list[RespuestaFormulario]) -> Optional[DefinicionPregunta]:
    r_decl = _respuestas_de(respuestas, "funcionalidad_declarada")
    r_prio = _respuestas_de(respuestas, "funcionalidad_prioridad")
    r_ejemplo = _respuestas_de(respuestas, "funcionalidad_ejemplo")
    r_continuar = _respuestas_de(respuestas, "funcionalidad_declarada_continuar")

    if len(r_decl) == 0:
        return PREGUNTAS["funcionalidad_declarada"]
    if len(r_decl) > len(r_prio):
        return PREGUNTAS["funcionalidad_prioridad"]

    n_vagas_esperadas = sum(1 for r in r_decl[:len(r_prio)] if es_respuesta_vaga(r.respuesta))
    if n_vagas_esperadas > len(r_ejemplo):
        return PREGUNTAS["funcionalidad_ejemplo"]

    if len(r_prio) > len(r_continuar):
        return PREGUNTAS["funcionalidad_declarada_continuar"]
    if _ultima(respuestas, "funcionalidad_declarada_continuar") == OPCION_SI:
        return PREGUNTAS["funcionalidad_declarada"]
    return None


def _paso_confirmar_diferidos(respuestas: list[RespuestaFormulario]) -> Optional[DefinicionPregunta]:
    n_diferidos = sum(
        1 for r in _respuestas_de(respuestas, "funcionalidad_prioridad")
        if r.respuesta == "Importante, puede esperar"
    )
    r_confirmar = _respuestas_de(respuestas, "cierre_confirmar_diferido")
    if len(r_confirmar) < n_diferidos:
        return PREGUNTAS["cierre_confirmar_diferido"]
    return None


def _construir_sintesis(respuestas: list[RespuestaFormulario]) -> str:
    """Dominio 14, síntesis determinista (sección 3.1 de la especificación):
    arma un resumen del flujo del proyecto citando literalmente lo ya
    respondido — nunca infiere ni completa nada que no esté en `respuestas`.
    Código puro, sin IA (D3): el único "procesamiento" es formatear texto ya
    dado por la persona.

    Cubre 00/01/01b/07/03/04/05/06/09/10/08 — los únicos dominios ya
    cerrados en el momento en que `14` corre. **No cubre `02`
    (funcionalidades) ni `11` (restricciones)**: en el orden vigente (D1,
    experimental) esos dominios se recorren DESPUÉS de `14`, así que sus
    respuestas todavía no existen — limitación real del estado actual,
    documentada aquí y en `docs/tickets/TF-0033.md`, no un olvido.
    """
    partes: list[str] = []

    nombre = _ultima(respuestas, "nombre_proyecto")
    problema = _ultima(respuestas, "problema_objetivo")
    if nombre or problema:
        frag = f"«{nombre}»" if nombre else "Tu proyecto"
        if problema:
            frag += f" busca resolver: {problema}"
        partes.append(frag + ".")

    # Personas + experiencia por persona (misma posición = misma persona,
    # decisión ya cerrada de `_paso_experiencia_por_persona`).
    nombres_persona = _respuestas_de(respuestas, "perfil_usuario")
    if nombres_persona:
        narrativas = _respuestas_de(respuestas, "experiencia_persona_narrativa")
        frecuencias = _respuestas_de(respuestas, "experiencia_persona_frecuencia")
        primeras = _respuestas_de(respuestas, "experiencia_persona_primera_vez")
        permisos = _respuestas_de(respuestas, "experiencia_persona_permisos_residual")
        pregunta_permisos = PREGUNTAS["experiencia_persona_permisos_residual"]
        bloques_persona = []
        for i, fila_persona in enumerate(nombres_persona):
            frag = fila_persona.respuesta
            if i < len(narrativas):
                frag += f": {narrativas[i].respuesta}"
            if i < len(permisos):
                lista_permisos = deserializar_respuesta(pregunta_permisos, permisos[i].respuesta)
                if lista_permisos:
                    frag += f" (además puede: {', '.join(lista_permisos)})"
            if i < len(frecuencias):
                frag += f". Frecuencia de uso: {frecuencias[i].respuesta.lower()}"
            if i < len(primeras):
                frag += f". Primera vez: {primeras[i].respuesta}"
            bloques_persona.append(frag)
        partes.append("Personas — " + " | ".join(bloques_persona) + ".")
    elif _ultima(respuestas, "personas_gate") is not None:
        partes.append("Un único tipo de usuario general, sin roles diferenciados.")

    plataforma = _ultima(respuestas, "plataforma")
    resultado_valor = _ultima(respuestas, "interaccion_resultado_valor")
    if plataforma or resultado_valor:
        frag = "Interacción"
        if plataforma:
            frag += f" — se usa {plataforma.lower()}"
        if resultado_valor:
            frag += f"; al terminar, la persona logra: {resultado_valor}"
        partes.append(frag + ".")

    if _ultima(respuestas, "contenido_gate") == OPCION_SI:
        tipos = _multiple(respuestas, "contenido_tipo")
        creador = _ultima(respuestas, "contenido_creador")
        frag = "Contenido — " + (", ".join(tipos) if tipos else "tipo no especificado")
        if creador:
            frag += f"; lo crea: {creador.lower()}"
        if _ultima(respuestas, "contenido_curso_examenes") == OPCION_SI:
            calificacion = _ultima(respuestas, "contenido_curso_calificacion_minima")
            frag += "; los cursos tienen examen"
            if calificacion:
                frag += f" (calificación mínima: {calificacion})"
        partes.append(frag + ".")

    if _ultima(respuestas, "dato_recordar") == OPCION_SI:
        detalles = _respuestas_de(respuestas, "dato_recordar_detalle")
        sensibles = _respuestas_de(respuestas, "dato_sensible")
        bloques_dato = []
        for i, fila in enumerate(detalles):
            frag = fila.respuesta
            if i < len(sensibles) and sensibles[i].respuesta == OPCION_SI:
                frag += " (sensible)"
            bloques_dato.append(frag)
        if bloques_dato:
            partes.append("Datos que recuerda — " + ", ".join(bloques_dato) + ".")

    if _ultima(respuestas, "monetizacion") == OPCION_MONETIZACION_SI:
        forma = _ultima(respuestas, "monetizacion_forma")
        frag = "Cobra dinero"
        if forma:
            frag += f", mediante: {forma.lower()}"
        partes.append(frag + ".")

    if _ultima(respuestas, "monetizacion_salida") == OPCION_PAGA_A_OTROS_SI:
        forma_salida = _ultima(respuestas, "monetizacion_salida_forma")
        frag = "Le paga o le entrega dinero a otras personas/proveedores"
        if forma_salida:
            frag += f", mediante: {forma_salida.lower()}"
        partes.append(frag + ".")

    if _activa_administracion(respuestas):
        acciones = _multiple(respuestas, "admin_acciones")
        if acciones:
            partes.append(
                "Administración — puede " + ", ".join(a.lower() for a in acciones)
                + " sobre otros usuarios."
            )

    if _ultima(respuestas, "automatizacion_gate") == OPCION_SI:
        que = _ultima(respuestas, "automatizacion_que")
        if que:
            partes.append(f"Sucede automáticamente: {que}.")
    if _ultima(respuestas, "ia_producto_gate") == OPCION_SI:
        partes.append("Usa IA como parte de lo que ofrece a sus usuarios.")

    aislamiento = _ultima(respuestas, "seguridad_aislamiento")
    if aislamiento and aislamiento != "No es importante":
        partes.append(f"Seguridad — el aislamiento entre usuarios es: {aislamiento.lower()}.")

    con_que = _respuestas_de(respuestas, "integraciones_con_que")
    if con_que:
        partes.append("Se integra con: " + ", ".join(f.respuesta for f in con_que) + ".")

    if not partes:
        return "Todavía no hay suficiente información capturada para armar una síntesis del flujo."

    return "Con lo que respondiste hasta ahora, así entendemos que funciona tu proyecto: " + " ".join(partes)


def _pregunta_sintesis_confirmacion(respuestas: list[RespuestaFormulario]) -> DefinicionPregunta:
    """Construye la pregunta de confirmación con la síntesis ya incrustada
    en `texto` (`dataclasses.replace` sobre la definición base — el catálogo
    solo guarda un texto de respaldo, nunca el que ve la persona). La
    pregunta de confirmación se refiere explícitamente al flujo mostrado
    (sección 3.2 de la especificación)."""
    sintesis = _construir_sintesis(respuestas)
    texto = f"{sintesis} ¿Es correcto este flujo, tal como lo resumimos arriba?"
    return dataclasses.replace(PREGUNTAS["sintesis_confirmacion"], texto=texto)


def siguiente_pregunta(respuestas: list[RespuestaFormulario]) -> Optional[DefinicionPregunta]:
    """Siguiente pregunta a mostrar dado lo ya respondido, o `None` si el
    árbol se completó. `respuestas` debe venir ordenada ascendente (mismo
    contrato que `RepositorioRespuestasFormulario.listar()`)."""

    # === Dominio 00 — Identidad y propósito =================================
    if not _respondida(respuestas, "nuevo_o_existente"):
        return PREGUNTAS["nuevo_o_existente"]
    existente = _ultima(respuestas, "nuevo_o_existente") == OPCION_EXISTENTE

    if existente and not _respondida(respuestas, "referencia_proyecto_existente"):
        return PREGUNTAS["referencia_proyecto_existente"]
    if existente and not _respondida(respuestas, "objetivo_proyecto_existente"):
        return PREGUNTAS["objetivo_proyecto_existente"]
    if not _respondida(respuestas, "nombre_proyecto"):
        return PREGUNTAS["nombre_proyecto"]
    if not _respondida(respuestas, "nombre_proyecto_estado"):
        return PREGUNTAS["nombre_proyecto_estado"]
    if not _respondida(respuestas, "problema_objetivo"):
        return PREGUNTAS["problema_objetivo"]
    if (
        sugiere_enumeracion(_ultima(respuestas, "problema_objetivo") or "")
        and not _respondida(respuestas, "problema_objetivo_desglose")
    ):
        return PREGUNTAS["problema_objetivo_desglose"]

    # === Dominio 01 — Personas (solo nombrar) ===============================
    if not _respondida(respuestas, "personas_gate"):
        return PREGUNTAS["personas_gate"]
    gate_personas = _ultima(respuestas, "personas_gate")

    if gate_personas == OPCION_PERSONAS_INCIERTO and not _respondida(respuestas, "personas_gate_incierto"):
        return PREGUNTAS["personas_gate_incierto"]

    n_personas = 0
    if gate_personas == OPCION_PERSONAS_VARIAS:
        paso = _paso_bloque_repetible(respuestas, "perfil_usuario", "perfil_usuario_continuar")
        if paso is not None:
            return paso
        n_personas = len(_respuestas_de(respuestas, "perfil_usuario"))

    # === Dominio 01b — Cómo vive el proyecto cada persona ===================
    paso = _paso_experiencia_por_persona(respuestas, n_personas)
    if paso is not None:
        return paso

    # === Dominio 07 — Interacción / experiencia =============================
    # (orden no especificado en el contrato de TF-0033 — insertado aquí, ver
    # docstring del módulo.)
    if not _respondida(respuestas, "plataforma"):
        return PREGUNTAS["plataforma"]
    plataforma = _ultima(respuestas, "plataforma")
    if plataforma == OPCION_PLATAFORMA_VARIAS and not _respondida(respuestas, "plataforma_detalle"):
        return PREGUNTAS["plataforma_detalle"]
    incluye_celular = plataforma == OPCION_PLATAFORMA_CELULAR or (
        plataforma == OPCION_PLATAFORMA_VARIAS
        and OPCION_DETALLE_CELULAR in _multiple(respuestas, "plataforma_detalle")
    )
    if incluye_celular and not _respondida(respuestas, "plataforma_offline"):
        return PREGUNTAS["plataforma_offline"]
    if not _respondida(respuestas, "interaccion_cuenta"):
        return PREGUNTAS["interaccion_cuenta"]
    if not _respondida(respuestas, "interaccion_resultado_valor"):
        return PREGUNTAS["interaccion_resultado_valor"]

    # === Dominio 03 — Contenido ==============================================
    if not _respondida(respuestas, "contenido_gate"):
        return PREGUNTAS["contenido_gate"]
    if _ultima(respuestas, "contenido_gate") == OPCION_SI:
        if not _respondida(respuestas, "contenido_tipo"):
            return PREGUNTAS["contenido_tipo"]
        if not _respondida(respuestas, "contenido_creador"):
            return PREGUNTAS["contenido_creador"]
        if "Cursos/lecciones" in _multiple(respuestas, "contenido_tipo"):
            if not _respondida(respuestas, "contenido_curso_modulos"):
                return PREGUNTAS["contenido_curso_modulos"]
            if not _respondida(respuestas, "contenido_curso_orden"):
                return PREGUNTAS["contenido_curso_orden"]
            if not _respondida(respuestas, "contenido_curso_examenes"):
                return PREGUNTAS["contenido_curso_examenes"]
            if (
                _ultima(respuestas, "contenido_curso_examenes") == OPCION_SI
                and not _respondida(respuestas, "contenido_curso_calificacion_minima")
            ):
                return PREGUNTAS["contenido_curso_calificacion_minima"]
        if not _respondida(respuestas, "contenido_aprobacion"):
            return PREGUNTAS["contenido_aprobacion"]

    # === Dominio 04 — Datos a conservar ======================================
    if not _respondida(respuestas, "dato_recordar"):
        return PREGUNTAS["dato_recordar"]
    if _ultima(respuestas, "dato_recordar") == OPCION_SI:
        paso = _paso_datos(respuestas)
        if paso is not None:
            return paso

    # === Dominio 05 — Monetización y pagos (dos gates independientes) ======
    if not _respondida(respuestas, "monetizacion"):
        return PREGUNTAS["monetizacion"]
    if _ultima(respuestas, "monetizacion") == OPCION_MONETIZACION_SI:
        if not _respondida(respuestas, "monetizacion_forma"):
            return PREGUNTAS["monetizacion_forma"]
        forma = _ultima(respuestas, "monetizacion_forma")
        if forma == "Suscripción":
            if not _respondida(respuestas, "monetizacion_planes_n"):
                return PREGUNTAS["monetizacion_planes_n"]
            paso = _paso_bloque_repetible(
                respuestas, "monetizacion_plan_detalle", "monetizacion_plan_continuar",
            )
            if paso is not None:
                return paso
            if not _respondida(respuestas, "monetizacion_prueba_gratis"):
                return PREGUNTAS["monetizacion_prueba_gratis"]
            if not _respondida(respuestas, "monetizacion_impago"):
                return PREGUNTAS["monetizacion_impago"]
            if not _respondida(respuestas, "monetizacion_autogestion"):
                return PREGUNTAS["monetizacion_autogestion"]
        elif forma == "Pago único":
            if not _respondida(respuestas, "monetizacion_pago_unico_detalle"):
                return PREGUNTAS["monetizacion_pago_unico_detalle"]
            if not _respondida(respuestas, "monetizacion_reembolso"):
                return PREGUNTAS["monetizacion_reembolso"]
        if not _respondida(respuestas, "monetizacion_factura"):
            return PREGUNTAS["monetizacion_factura"]

    if not _respondida(respuestas, "monetizacion_salida"):
        return PREGUNTAS["monetizacion_salida"]
    if _ultima(respuestas, "monetizacion_salida") == OPCION_PAGA_A_OTROS_SI:
        if not _respondida(respuestas, "monetizacion_salida_forma"):
            return PREGUNTAS["monetizacion_salida_forma"]
        if not _respondida(respuestas, "monetizacion_salida_incumplimiento"):
            return PREGUNTAS["monetizacion_salida_incumplimiento"]
        if not _respondida(respuestas, "monetizacion_salida_control"):
            return PREGUNTAS["monetizacion_salida_control"]

    # === Dominio 06 — Administración y operación ============================
    if _activa_administracion(respuestas):
        if not _respondida(respuestas, "admin_acciones"):
            return PREGUNTAS["admin_acciones"]
        if not _respondida(respuestas, "admin_que_mas"):
            return PREGUNTAS["admin_que_mas"]
        if "Reportes" in _multiple(respuestas, "admin_que_mas"):
            paso = _paso_bloque_repetible(respuestas, "admin_reportes_detalle", "admin_reportes_continuar")
            if paso is not None:
                return paso
        if not _respondida(respuestas, "admin_niveles"):
            return PREGUNTAS["admin_niveles"]
        paso = _paso_notificaciones(respuestas)
        if paso is not None:
            return paso

    # === Dominio 09 — Seguridad funcional =====================================
    if not _respondida(respuestas, "seguridad_aislamiento"):
        return PREGUNTAS["seguridad_aislamiento"]
    if not _respondida(respuestas, "seguridad_verificacion"):
        return PREGUNTAS["seguridad_verificacion"]
    if not _respondida(respuestas, "seguridad_sensible"):
        return PREGUNTAS["seguridad_sensible"]

    # === Dominio 10 — Integraciones ============================================
    if not _respondida(respuestas, "integraciones_gate"):
        return PREGUNTAS["integraciones_gate"]
    if _ultima(respuestas, "integraciones_gate") == OPCION_SI:
        paso = _paso_bloque_repetible_3(
            respuestas, "integraciones_con_que", "integraciones_para_que", "integraciones_continuar",
        )
        if paso is not None:
            return paso

    # === Dominio 08 — Automatización e IA ======================================
    if not _respondida(respuestas, "automatizacion_gate"):
        return PREGUNTAS["automatizacion_gate"]
    if _ultima(respuestas, "automatizacion_gate") == OPCION_SI:
        if not _respondida(respuestas, "automatizacion_que"):
            return PREGUNTAS["automatizacion_que"]
        if not _respondida(respuestas, "automatizacion_cuando"):
            return PREGUNTAS["automatizacion_cuando"]
    if not _respondida(respuestas, "ia_producto_gate"):
        return PREGUNTAS["ia_producto_gate"]

    # === Dominio 14 — Cómo funciona (síntesis tardía) =========================
    if not _respondida(respuestas, "sintesis_confirmacion"):
        return _pregunta_sintesis_confirmacion(respuestas)
    if not _respondida(respuestas, "sintesis_abandono"):
        return PREGUNTAS["sintesis_abandono"]
    if not _respondida(respuestas, "sintesis_reanudacion"):
        return PREGUNTAS["sintesis_reanudacion"]
    if not _respondida(respuestas, "sintesis_concurrencia"):
        return PREGUNTAS["sintesis_concurrencia"]
    if not _respondida(respuestas, "sintesis_peor_caso"):
        return PREGUNTAS["sintesis_peor_caso"]

    # === Dominio 12 — Identidad de marca (independiente del orden) ==========
    if not _respondida(respuestas, "marca_gate"):
        return PREGUNTAS["marca_gate"]
    marca = _ultima(respuestas, "marca_gate")
    if marca == "No tengo nada":
        if not _respondida(respuestas, "marca_prioridad"):
            return PREGUNTAS["marca_prioridad"]
        if _ultima(respuestas, "marca_prioridad") == OPCION_SI and not _respondida(respuestas, "marca_estilo"):
            return PREGUNTAS["marca_estilo"]
    elif marca == "Necesito ayuda para definirlo":
        if not _respondida(respuestas, "marca_estilo"):
            return PREGUNTAS["marca_estilo"]
    else:  # "Tengo todo" / "Tengo algunas cosas"
        if not _respondida(respuestas, "marca_logo"):
            return PREGUNTAS["marca_logo"]
        if _ultima(respuestas, "marca_logo") == OPCION_SI and not _respondida(respuestas, "marca_logo_conservar"):
            return PREGUNTAS["marca_logo_conservar"]
        if not _respondida(respuestas, "marca_colores"):
            return PREGUNTAS["marca_colores"]
        if not _respondida(respuestas, "marca_tipografias"):
            return PREGUNTAS["marca_tipografias"]
        if not _respondida(respuestas, "marca_manual"):
            return PREGUNTAS["marca_manual"]
        if not _respondida(respuestas, "marca_referencias"):
            return PREGUNTAS["marca_referencias"]
        if not _respondida(respuestas, "marca_tono"):
            return PREGUNTAS["marca_tono"]
        if not _respondida(respuestas, "marca_continuidad"):
            return PREGUNTAS["marca_continuidad"]
        if not _respondida(respuestas, "marca_paraguas"):
            return PREGUNTAS["marca_paraguas"]

    # === Dominio 02 — Funcionalidades =========================================
    paso = _paso_funcionalidades(respuestas)
    if paso is not None:
        return paso
    if not _respondida(respuestas, "funcionalidad_prohibida"):
        return PREGUNTAS["funcionalidad_prohibida"]

    # === Dominio 11 — Restricciones y preferencias ============================
    if not _respondida(respuestas, "restriccion_tecnica"):
        return PREGUNTAS["restriccion_tecnica"]
    if not _respondida(respuestas, "restriccion_tiempo_presupuesto"):
        return PREGUNTAS["restriccion_tiempo_presupuesto"]
    if not _respondida(respuestas, "restriccion_negocio"):
        return PREGUNTAS["restriccion_negocio"]
    if not _respondida(respuestas, "restriccion_legal"):
        return PREGUNTAS["restriccion_legal"]

    # === Dominio 13 — Cierre / alcance del MVP ================================
    if not _respondida(respuestas, "cierre_exito"):
        return PREGUNTAS["cierre_exito"]
    paso = _paso_confirmar_diferidos(respuestas)
    if paso is not None:
        return paso
    if not _respondida(respuestas, "cierre_libre"):
        return PREGUNTAS["cierre_libre"]

    return None
