"""Catálogo de preguntas del formulario — datos puros, sin lógica de árbol.

TF-0033 — "Discovery Inteligente": reemplaza el árbol lineal de 27
preguntas por el catálogo de 16 dominios con puerta propia, especificado en
`docs/tickets/TF-0033.md`. La secuencia/dependencias entre preguntas vive en
`src.formulario.arbol`, no aquí (separación deliberada: catálogo vs.
navegación, decisión ya cerrada desde TF-0030).

Reutiliza `TipoPregunta` de `src.expediente.modelo` sin agregar un tercer
valor. Como ese enum solo distingue `OPCION_CERRADA`/`TEXTO_LIBRE`, las
categorías conceptuales "número" y "archivo/recurso" de la especificación
se representan como `TEXTO_LIBRE` (sin validación numérica ni de adjuntos
todavía — ampliar el tipo es una decisión de esquema fuera de este ticket).

`pregunta_id` estables reutilizados verbatim del catálogo anterior (mismo
identificador, texto actualizado donde el contrato de TF-0033 lo pide) para
no romper `src.discovery.interpretacion_directa`,
`src.discovery.reglas_consecuencia` ni `src.discovery.catalogo_dominios`,
que dependen de estos literales: `nuevo_o_existente`,
`referencia_proyecto_existente`, `objetivo_proyecto_existente`,
`nombre_proyecto`, `problema_objetivo`, `plataforma`/`plataforma_detalle`/
`plataforma_offline`, `perfil_usuario`/`perfil_usuario_continuar`,
`funcionalidad_declarada`/`funcionalidad_declarada_continuar`,
`monetizacion`/`monetizacion_forma`, `dato_recordar`/
`dato_recordar_detalle`/`dato_recordar_detalle_continuar`,
`restriccion_tecnica`/`restriccion_tiempo_presupuesto`/
`restriccion_negocio`, `cierre_libre`.

Retirados de este catálogo (dominio 06 los reemplaza con su propio
mecanismo, ver `arbol.py`): `administracion_cantidad`,
`administracion_diferencias`, `administrador_tipo_nombre`,
`administrador_tipo_acciones`, `administrador_tipo_otra`,
`administrador_tipo_continuar`.

`01b` (narrativa/frecuencia/primera vez) y el Gate B de `05` ya tienen
redacción final (revisión posterior a la primera entrega de TF-0033, que los
dejó con contenido provisional). `sintesis_confirmacion` (dominio `14`) ya
no tiene texto estático aquí: `src.formulario.arbol` construye su `texto`
dinámicamente a partir del estado acumulado (ver
`arbol._construir_sintesis`) — el valor de `_LISTA` es solo un texto base de
respaldo, nunca el que ve la persona. Las 4 excepciones universales de `14`
(`sintesis_abandono`/`reanudacion`/`concurrencia`/`peor_caso`) siguen
marcadas `[contenido pendiente de redacción]`: no se pidió redactarlas en
esta revisión.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.expediente.modelo import TipoPregunta

__all__ = [
    "DefinicionPregunta", "PREGUNTAS", "PENDIENTE_DE_REDACCION",
    "OPCION_NUEVO", "OPCION_EXISTENTE",
    "OPCION_SI", "OPCION_NO", "OPCION_NO_SE",
    "OPCION_PLATAFORMA_NAVEGADOR", "OPCION_PLATAFORMA_CELULAR",
    "OPCION_PLATAFORMA_COMPUTADORA", "OPCION_PLATAFORMA_VARIAS",
    "OPCION_PLATAFORMA_NO_SEGURO", "OPCION_DETALLE_CELULAR",
    "OPCION_OTRA_COSA",
    "OPCION_MONETIZACION_NO", "OPCION_MONETIZACION_SI", "OPCION_MONETIZACION_NO_DECIDIDO",
    "OPCION_PAGA_A_OTROS_NO", "OPCION_PAGA_A_OTROS_SI",
    "OPCION_PERSONAS_VARIAS", "OPCION_PERSONAS_SOLO", "OPCION_PERSONAS_INCIERTO",
    "OPCION_ADMINISTRA_TODO",
]

PENDIENTE_DE_REDACCION = "[contenido pendiente de redacción] "


@dataclass(frozen=True)
class DefinicionPregunta:
    """Una pregunta del árbol, tal como se muestra a la persona.

    `opciones` solo aplica a `tipo_pregunta=OPCION_CERRADA` (`None` para
    texto libre). `multiple` solo puede ser `True` si `tipo_pregunta` es
    `OPCION_CERRADA` — una pregunta de texto libre nunca es "múltiple".
    `obligatoria` es informativa para una futura UI (qué no se puede saltar
    sin responder algo, aunque sea "no sé"); la navegación del árbol
    (`arbol.py`) no la necesita para decidir la siguiente pregunta.
    """

    pregunta_id: str
    texto: str
    tipo_pregunta: TipoPregunta
    opciones: Optional[tuple[str, ...]] = None
    multiple: bool = False
    obligatoria: bool = False

    def __post_init__(self):
        if self.multiple and self.tipo_pregunta != TipoPregunta.OPCION_CERRADA:
            raise ValueError(
                f"{self.pregunta_id!r}: multiple=True requiere tipo_pregunta=OPCION_CERRADA"
            )
        if self.tipo_pregunta == TipoPregunta.OPCION_CERRADA and not self.opciones:
            raise ValueError(f"{self.pregunta_id!r}: OPCION_CERRADA requiere 'opciones' no vacío")
        if self.tipo_pregunta == TipoPregunta.TEXTO_LIBRE and self.opciones:
            raise ValueError(f"{self.pregunta_id!r}: TEXTO_LIBRE no admite 'opciones'")


# --- Constantes de opciones reutilizadas por arbol.py para ramificar -------

OPCION_NUEVO = "Nuevo"
OPCION_EXISTENTE = "Ya existe algo"

OPCION_SI = "Sí"
OPCION_NO = "No"
OPCION_NO_SE = "No sé"

OPCION_PLATAFORMA_NAVEGADOR = "Desde un navegador web"
OPCION_PLATAFORMA_CELULAR = "Desde el celular"
OPCION_PLATAFORMA_COMPUTADORA = "Desde una computadora (programa instalado)"
OPCION_PLATAFORMA_VARIAS = "En varios de estos lugares"
OPCION_PLATAFORMA_NO_SEGURO = "No estoy seguro todavía"
OPCION_DETALLE_CELULAR = "Celular"

OPCION_OTRA_COSA = "Otra cosa"

OPCION_MONETIZACION_NO = "No, es gratis"
OPCION_MONETIZACION_SI = "Sí, de alguna forma"
OPCION_MONETIZACION_NO_DECIDIDO = "Todavía no lo he decidido"

# Dominio 05, Gate B (saliente) — tri-state propio, orientado a "pagar" en
# vez de "cobrar" (Gate A). "Todavía no lo he decidido" se reutiliza tal
# cual: es neutral, no menciona cobro ni pago.
OPCION_PAGA_A_OTROS_NO = "No, no le paga a nadie"
OPCION_PAGA_A_OTROS_SI = "Sí, le paga a alguien"

# Dominio 01 — puerta de Personas (Q1.1).
OPCION_PERSONAS_VARIAS = "Varias personas con roles distintos"
OPCION_PERSONAS_SOLO = "Yo solo / todos igual"
OPCION_PERSONAS_INCIERTO = "No estoy seguro"

# Checklist catch-all de 01b (Q1b.permisos_residual) — una de las opciones
# es la señal determinista que activa el dominio 06 (disparador elegido en
# esta implementación: ver `arbol.py`, `_activa_administracion`).
OPCION_ADMINISTRA_TODO = "Controlar/administrar todo el proyecto"


def _cerrada(pregunta_id, texto, opciones, *, multiple=False, obligatoria=False):
    return DefinicionPregunta(
        pregunta_id=pregunta_id, texto=texto, tipo_pregunta=TipoPregunta.OPCION_CERRADA,
        opciones=tuple(opciones), multiple=multiple, obligatoria=obligatoria,
    )


def _libre(pregunta_id, texto, *, obligatoria=False):
    return DefinicionPregunta(
        pregunta_id=pregunta_id, texto=texto, tipo_pregunta=TipoPregunta.TEXTO_LIBRE,
        obligatoria=obligatoria,
    )


# --- Catálogo completo (16 dominios, TF-0033) -------------------------------

_LISTA: tuple[DefinicionPregunta, ...] = (

    # === Dominio 00 — Identidad y propósito =================================
    _cerrada(
        "nuevo_o_existente", "¿Es un proyecto nuevo o ya existe algo construido?",
        [OPCION_NUEVO, OPCION_EXISTENTE], obligatoria=True,
    ),
    _libre("referencia_proyecto_existente", "¿Dónde está?", obligatoria=True),
    _libre(
        "objetivo_proyecto_existente",
        "¿Qué quieres lograr ahora: continuar igual, cambiar de rumbo, o algo más?",
        obligatoria=True,
    ),
    _libre("nombre_proyecto", "¿Cómo se llama tu proyecto?"),
    _cerrada(
        "nombre_proyecto_estado",
        "¿Ya tienes el nombre definido, tienes una idea, o necesitas ayuda para definirlo?",
        ["Nombre definido", "Tengo una idea", "Necesito ayuda para definirlo"],
    ),
    _libre(
        "problema_objetivo",
        "En pocas palabras, ¿qué problema resuelve o qué logra tu proyecto?",
        obligatoria=True,
    ),
    _libre(
        "problema_objetivo_desglose",
        "Mencionaste varias cosas — ¿cuál es la más importante para el primer lanzamiento?",
    ),

    # === Dominio 01 — Personas (solo nombrar) ===============================
    _cerrada(
        "personas_gate",
        "¿Habrá distintos tipos de personas que usarán el proyecto o será solo para ti?",
        [OPCION_PERSONAS_VARIAS, OPCION_PERSONAS_SOLO, OPCION_PERSONAS_INCIERTO],
        obligatoria=True,
    ),
    _cerrada(
        "personas_gate_incierto", "¿Habrá algún administrador distinto de los demás?",
        [OPCION_SI, OPCION_NO, OPCION_NO_SE],
    ),
    _libre("perfil_usuario", "Nombra un tipo de persona (ej. \"clientes\", \"vendedores\")"),
    _cerrada(
        "perfil_usuario_continuar", "¿Hay otro tipo de persona?", [OPCION_SI, OPCION_NO],
    ),

    # === Dominio 01b — Cómo vive el proyecto cada persona ===================
    # Narrativa entrelazada llega -> ve -> hace -> obtiene (decisión cerrada
    # de la especificación, §02.2): una sola pregunta abierta que pide la
    # historia completa, en vez de un checklist separado de permisos primero.
    _libre(
        "experiencia_persona_narrativa",
        "Cuéntame, paso a paso, cómo esta persona vive tu proyecto de principio a fin: "
        "¿cómo llega o entra?, ¿qué es lo primero que ve?, ¿qué puede hacer una vez adentro?, "
        "y al terminar, ¿qué obtiene o consigue?",
    ),
    _cerrada(
        "experiencia_persona_frecuencia",
        "¿Esta persona usa tu proyecto una sola vez, o vuelve a usarlo regularmente?",
        ["Una sola vez", "Regularmente"],
    ),
    _libre(
        "experiencia_persona_primera_vez",
        "La primera vez que esta persona usa tu proyecto, ¿es distinta de las veces "
        "siguientes (por ejemplo, un registro, un tutorial o una bienvenida)? Cuéntame cómo.",
    ),
    # Pregunta residual — texto cerrado, literal de la especificación.
    _cerrada(
        "experiencia_persona_permisos_residual",
        "¿Algo más que pueda hacer, aparte de lo que ya me contaste?",
        [
            "Ver información", "Agregar cosas nuevas", "Cambiar lo que ya existe",
            "Eliminar cosas", "Aprobar o rechazar cosas de otros", "Comunicarse con otros",
            "Recibir pagos", OPCION_ADMINISTRA_TODO, OPCION_OTRA_COSA,
        ],
        multiple=True,
    ),
    _libre("experiencia_persona_permisos_otra", "Cuéntame qué más puede hacer."),

    # === Dominio 02 — Funcionalidades =======================================
    _libre(
        "funcionalidad_declarada",
        "Aparte de lo ya mencionado por tipo de usuario, ¿algo más que el proyecto deba hacer?",
    ),
    _cerrada(
        "funcionalidad_prioridad", "¿Es indispensable ahora, o puede esperar?",
        ["Indispensable", "Importante, puede esperar", "No urgente"],
    ),
    _libre("funcionalidad_ejemplo", "¿Me das un ejemplo concreto de cómo se usaría esto?"),
    _cerrada(
        "funcionalidad_declarada_continuar", "¿Algo más que deba poder hacer?",
        [OPCION_SI, OPCION_NO],
    ),
    _libre(
        "funcionalidad_prohibida",
        "¿Hay algo que el proyecto NO deba hacer, aunque parezca obvio que sí?",
    ),

    # === Dominio 03 — Contenido ==============================================
    _cerrada(
        "contenido_gate", "¿Tu proyecto organiza, publica o administra contenido?",
        [OPCION_SI, OPCION_NO, "No estoy seguro"], obligatoria=True,
    ),
    _cerrada(
        "contenido_tipo", "¿Qué tipo(s) de contenido?",
        ["Texto", "Video", "Audio", "Imágenes", "Archivos", "Cursos/lecciones", "Productos con precio"],
        multiple=True,
    ),
    _cerrada(
        "contenido_creador", "¿Quién puede crear o subir esto?",
        ["Solo admin", "Cualquier registrado", "Ciertos tipos de usuario"],
    ),
    _cerrada("contenido_curso_modulos", "¿Se organiza en módulos?", [OPCION_SI, OPCION_NO]),
    _cerrada(
        "contenido_curso_orden", "¿El orden de los módulos es obligatorio o libre?",
        ["Orden obligatorio", "Orden libre"],
    ),
    _cerrada("contenido_curso_examenes", "¿Hay exámenes?", [OPCION_SI, OPCION_NO]),
    _libre("contenido_curso_calificacion_minima", "¿Cuál es la calificación mínima para aprobar?"),
    _cerrada(
        "contenido_aprobacion", "¿Necesita aprobación antes de publicarse?",
        [OPCION_SI, OPCION_NO],
    ),

    # === Dominio 04 — Datos a conservar ======================================
    _cerrada(
        "dato_recordar", "¿Tu proyecto necesita recordar información entre visitas?",
        [OPCION_SI, OPCION_NO, "No estoy seguro"], obligatoria=True,
    ),
    _libre("dato_recordar_detalle", "¿Qué debe recordar?"),
    _cerrada(
        "dato_sensible", "¿Es información sensible (contraseñas, pagos, salud)?",
        [OPCION_SI, OPCION_NO, OPCION_NO_SE],
    ),
    _libre("dato_retencion", "¿Para siempre, o puede borrarse después de un tiempo?"),
    _libre("dato_quien_ve", "¿Quién puede ver este dato?"),
    _libre("dato_quien_modifica", "¿Quién puede modificar este dato?"),
    _cerrada(
        "dato_recordar_detalle_continuar", "¿Hay otro dato?", [OPCION_SI, OPCION_NO],
    ),

    # === Dominio 05 — Monetización y pagos (dos gates independientes) =======
    # Gate A — entrante.
    _cerrada(
        "monetizacion", "¿Tu proyecto va a cobrar algo, de cualquier forma?",
        [OPCION_MONETIZACION_NO, OPCION_MONETIZACION_SI, OPCION_MONETIZACION_NO_DECIDIDO],
        obligatoria=True,
    ),
    _cerrada(
        "monetizacion_forma", "¿Cómo cobra?",
        [
            "Pago único", "Suscripción", "Según uso", "Comisión",
            "Anuncios", "Donaciones", "Combinación",
        ],
    ),
    _libre("monetizacion_planes_n", "¿Cuántos planes de suscripción tienes?"),
    _libre("monetizacion_plan_detalle", "Nombre del plan y qué incluye"),
    _cerrada("monetizacion_plan_continuar", "¿Hay otro plan?", [OPCION_SI, OPCION_NO]),
    _cerrada("monetizacion_prueba_gratis", "¿Hay prueba gratis?", [OPCION_SI, OPCION_NO]),
    _libre("monetizacion_impago", "¿Qué pasa si la persona deja de pagar?"),
    _cerrada(
        "monetizacion_autogestion", "¿El usuario puede cambiar o cancelar su plan por su cuenta?",
        [OPCION_SI, OPCION_NO],
    ),
    _libre("monetizacion_pago_unico_detalle", "¿Qué se paga exactamente?"),
    _cerrada("monetizacion_reembolso", "¿Hay reembolso?", [OPCION_SI, OPCION_NO]),
    _cerrada(
        "monetizacion_factura", "¿Necesitas emitir factura o comprobante?",
        [OPCION_SI, OPCION_NO],
    ),
    # Gate B — saliente, independiente de Gate A (D5). Opciones propias,
    # orientadas a "pagar" (nunca reutiliza el vocabulario de "cobrar" del
    # Gate A) — el resto del sub-árbol reutiliza contenido ya cerrado en D5
    # (modelo parametrizado, incumplimiento, control de cambios).
    _cerrada(
        "monetizacion_salida",
        "¿Tu proyecto le paga o le entrega dinero a otras personas, proveedores o "
        "participantes (por ejemplo: comisiones, sueldos, repartos de lo cobrado)?",
        [OPCION_PAGA_A_OTROS_NO, OPCION_PAGA_A_OTROS_SI, OPCION_MONETIZACION_NO_DECIDIDO],
    ),
    _cerrada(
        "monetizacion_salida_forma", "¿Cómo se le paga?",
        [
            "Pago único", "Suscripción", "Según uso", "Comisión",
            "Anuncios", "Donaciones", "Combinación",
        ],
    ),
    _libre("monetizacion_salida_incumplimiento", "¿Qué pasa si hay incumplimiento en este pago?"),
    _libre("monetizacion_salida_control", "¿Quién controla los cambios en este acuerdo?"),

    # === Dominio 06 — Administración y operación ============================
    _cerrada(
        "admin_acciones", "¿Qué puede hacer el administrador respecto a otros usuarios?",
        ["Consultar", "Crear", "Modificar datos", "Suspender", "Eliminar", "Cambiar roles"],
        multiple=True,
    ),
    _cerrada(
        "admin_que_mas", "¿Qué más administra?",
        ["Contenido", "Pagos", "Configuración", "Reportes"], multiple=True,
    ),
    _libre("admin_reportes_detalle", "¿Qué necesitas ver de un vistazo?"),
    _cerrada(
        "admin_reportes_continuar", "¿Algo más que necesites ver de un vistazo?",
        [OPCION_SI, OPCION_NO],
    ),
    _cerrada(
        "admin_niveles", "¿Habrá varios niveles de administración distintos entre sí?",
        [OPCION_SI, OPCION_NO],
    ),
    _libre("admin_notificaciones", "¿Necesita notificaciones de algo específico?"),
    _cerrada(
        "admin_notificaciones_canal", "¿Por qué canal?",
        ["Correo", "Dentro del sistema", "No sé"],
    ),
    _cerrada(
        "admin_notificaciones_continuar", "¿Otra notificación que necesites?",
        [OPCION_SI, OPCION_NO],
    ),

    # === Dominio 07 — Interacción / experiencia ==============================
    _cerrada(
        "plataforma", "¿Dónde quieres que la gente use tu proyecto?",
        [
            OPCION_PLATAFORMA_NAVEGADOR, OPCION_PLATAFORMA_CELULAR,
            OPCION_PLATAFORMA_COMPUTADORA, OPCION_PLATAFORMA_VARIAS,
            OPCION_PLATAFORMA_NO_SEGURO,
        ],
        obligatoria=True,
    ),
    _cerrada(
        "plataforma_detalle", "¿Cuáles, específicamente?",
        [OPCION_PLATAFORMA_NAVEGADOR, OPCION_DETALLE_CELULAR, OPCION_PLATAFORMA_COMPUTADORA],
        multiple=True,
    ),
    _cerrada(
        "plataforma_offline", "¿Debe funcionar sin conexión a internet?",
        [OPCION_SI, OPCION_NO, OPCION_NO_SE],
    ),
    _cerrada(
        "interaccion_cuenta",
        "¿Necesita cuenta para lo esencial, puede probar sin cuenta, o nunca necesita cuenta?",
        ["Necesita cuenta para lo esencial", "Puede probar sin cuenta", "Nunca necesita cuenta"],
    ),
    _libre(
        "interaccion_resultado_valor",
        "En una frase: ¿qué logra la persona al terminar de usar tu proyecto exitosamente?",
    ),

    # === Dominio 08 — Automatización e IA ====================================
    _cerrada(
        "automatizacion_gate", "¿El proyecto debe hacer algo automáticamente, sin que nadie lo pida?",
        [OPCION_SI, OPCION_NO, OPCION_NO_SE],
    ),
    _libre("automatizacion_que", "¿Qué debe pasar automáticamente?"),
    _cerrada(
        "automatizacion_cuando", "¿En qué momento ocurre?",
        ["Momento fijo", "Cuando pasa algo específico"],
    ),
    _cerrada(
        "ia_producto_gate",
        "¿Tu proyecto necesita IA como parte de lo que ofrece a sus usuarios "
        "(recomendaciones, generación de contenido, un chat que responda)?",
        [OPCION_SI, OPCION_NO, OPCION_NO_SE],
    ),

    # === Dominio 09 — Seguridad funcional =====================================
    _cerrada(
        "seguridad_aislamiento", "¿Es crítico que una persona nunca pueda ver información de otra?",
        ["Crítico", "Depende", "No es importante"],
    ),
    _cerrada(
        "seguridad_verificacion",
        "¿Necesitas verificar que la persona es quien dice ser (correo, identificación)?",
        [OPCION_SI, OPCION_NO],
    ),
    _cerrada(
        "seguridad_sensible",
        "¿Involucra menores de edad, salud, o información financiera delicada?",
        [OPCION_SI, OPCION_NO],
    ),

    # === Dominio 10 — Integraciones ============================================
    _cerrada(
        "integraciones_gate",
        "¿Necesitas que tu proyecto se conecte con algo que ya usas "
        "(correo, WhatsApp, redes, pagos, otro programa)?",
        [OPCION_SI, OPCION_NO, "No lo sé"],
    ),
    _libre("integraciones_con_que", "¿Con qué?"),
    _libre("integraciones_para_que", "¿Para qué?"),
    _cerrada("integraciones_continuar", "¿Otra integración?", [OPCION_SI, OPCION_NO]),

    # === Dominio 11 — Restricciones y preferencias ============================
    _libre(
        "restriccion_tecnica",
        "¿Tu equipo ya sabe trabajar con alguna tecnología en particular, "
        "o ya tienen algo funcionando que prefieran reusar?",
    ),
    _libre(
        "restriccion_tiempo_presupuesto",
        "¿Hay algún límite de tiempo o presupuesto que debamos tener en cuenta?",
    ),
    _libre(
        "restriccion_negocio",
        "¿Hay algo que el proyecto NO deba hacer, o alguna regla legal o de negocio que debamos respetar?",
    ),
    _cerrada(
        "restriccion_legal",
        "¿Alguna ley o norma que ya sepas que debas cumplir, aunque no conozcas el detalle técnico?",
        [OPCION_SI, OPCION_NO, OPCION_NO_SE],
    ),

    # === Dominio 12 — Identidad de marca (independiente del orden principal) =
    _cerrada(
        "marca_gate", "¿Ya tienes identidad visual (nombre, logo, colores)?",
        ["Tengo todo", "Tengo algunas cosas", "No tengo nada", "Necesito ayuda para definirlo"],
    ),
    _cerrada(
        "marca_prioridad", "¿Es prioridad para ti definir esto ahora?",
        [OPCION_SI, OPCION_NO],
    ),
    _cerrada(
        "marca_estilo", "¿Qué estilo se acerca más?",
        ["Minimalista", "Moderno", "Corporativo", "Divertido", "Aún no sé"],
    ),
    _cerrada("marca_logo", "¿Ya tienes logo?", [OPCION_SI, OPCION_NO]),
    _cerrada(
        "marca_logo_conservar", "¿Quieres conservarlo o estás abierto a rediseñarlo?",
        ["Conservarlo", "Abierto a rediseñarlo"],
    ),
    _libre("marca_colores", "¿Colores definidos, o cuáles te gustan/no te gustan?"),
    _libre("marca_tipografias", "¿Tipografías definidas?"),
    _cerrada("marca_manual", "¿Tienes un manual de marca?", [OPCION_SI, OPCION_NO]),
    _libre("marca_referencias", "¿Alguna referencia visual que te guste?"),
    _cerrada(
        "marca_tono", "¿Qué tono de comunicación prefieres?",
        ["Formal", "Cercano", "Técnico", "Divertido"],
    ),
    _libre(
        "marca_continuidad",
        "¿Ya tienes un dominio/URL comprado o un usuario de redes que quieras mantener consistente?",
    ),
    _cerrada(
        "marca_paraguas", "¿Este proyecto es independiente o es una extensión de una marca que ya tienes?",
        ["Independiente", "Extensión de una marca existente"],
    ),

    # === Dominio 13 — Cierre / alcance del MVP ================================
    _libre("cierre_exito", "¿Cómo sabrías que esta primera versión fue un éxito?"),
    _cerrada(
        "cierre_confirmar_diferido",
        "¿Confirmas que esto NO es necesario para el primer lanzamiento?",
        [OPCION_SI, OPCION_NO],
    ),
    _libre("cierre_libre", "¿Algo más que quieras agregar?"),

    # === Dominio 14 — Cómo funciona (síntesis tardía) =========================
    # SLOT sin texto cerrado: la presentación de la síntesis y las 4
    # excepciones universales se implementan con contenido provisional.
    _cerrada(
        "sintesis_confirmacion",
        PENDIENTE_DE_REDACCION + "Esto es lo que entendimos que pasa en tu proyecto, "
        "de principio a fin — ¿es correcto?",
        [OPCION_SI, OPCION_NO],
    ),
    _libre(
        "sintesis_abandono",
        PENDIENTE_DE_REDACCION + "¿Qué pasa si alguien abandona a la mitad de este flujo?",
    ),
    _libre(
        "sintesis_reanudacion",
        PENDIENTE_DE_REDACCION + "¿Puede retomar donde se quedó?",
    ),
    _libre(
        "sintesis_concurrencia",
        PENDIENTE_DE_REDACCION + "¿Qué pasa si dos personas hacen lo mismo al mismo tiempo?",
    ),
    _libre(
        "sintesis_peor_caso",
        PENDIENTE_DE_REDACCION + "¿Qué pasa en el peor caso (falla un pago, vence un acceso)?",
    ),
)

PREGUNTAS: dict[str, DefinicionPregunta] = {p.pregunta_id: p for p in _LISTA}
