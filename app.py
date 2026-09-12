# app.py
import json
import uuid

from flask import Flask, render_template, request, redirect, url_for, session, abort, g
from src import config
from src.database import DBManager
from src.modelos import Tarea, Proyecto
from src.validaciones import validar_datos_tarea
from src.seguridad import (
    generar_token, token_valido, obtener_secret_key, cookie_secure_activada,
)
from src.observabilidad import (
    configurar_logging, set_correlation_id, reset_correlation_id,
)
# TF-0031 — UI de pruebas del Discovery nuevo. Solo consume APIs públicas ya
# aprobadas (TF-0030); no importa src.orquestador ni src.proyectos.
# TF-0032 añade la reapertura de preguntas cuando Gap/Contradiccion quedan
# ABIERTO/ABIERTA con un pregunta_id resoluble (A1/A4).
from src.ai.factory import crear_cliente
from src.discovery.catalogo_dominios import resolver_pregunta
from src.discovery.discovery import (
    TIPO_ACCION_DISCOVERY, FormularioIncompleto, ejecutar_discovery, procesar_reapertura,
)
from src.expediente.modelo import EstadoContradiccion, EstadoGap, TipoPregunta
from src.formulario.arbol import siguiente_pregunta
from src.formulario.preguntas import PREGUNTAS
from src.formulario.respuestas import (
    RespuestaInvalida, deserializar_respuesta, serializar_respuesta, validar_respuesta,
)
from src.repositorios.acciones import COMPLETADA, RepositorioAcciones
from src.repositorios.contradicciones import RepositorioContradicciones
from src.repositorios.datos import RepositorioDatos
from src.repositorios.gaps import RepositorioGaps
from src.repositorios.perfiles import RepositorioPerfiles
from src.repositorios.requisitos import RepositorioRequisitos
from src.repositorios.respuestas_formulario import RepositorioRespuestasFormulario
from src.repositorios.restricciones import RepositorioRestricciones

# Inicialización de la aplicación Flask
app = Flask(__name__)
# TF-0020: configuración única de logging. El nivel sale de TASKFLOW_LOG_LEVEL
# (vía src.config); un valor no reconocido cae a INFO. Idempotente: importar o
# re-ejecutar este módulo no acumula handlers.
configurar_logging(config.nivel_log())
# Clave de firma de sesión (TF-0008 / TF-0012). En despliegue debe venir de
# TASKFLOW_SECRET_KEY; con TASKFLOW_ENV=production su ausencia aborta el arranque.
# Sin esa señal, fallback efímero + warning (solo desarrollo); TF-0020: sin
# logger explícito el warning va al logger central.
app.secret_key = obtener_secret_key()
app.config["SESSION_COOKIE_SAMESITE"] = "Lax"
app.config["SESSION_COOKIE_HTTPONLY"] = True
# TF-0012: cookie de sesión con atributo Secure cuando se sirve tras TLS
# (TASKFLOW_COOKIE_SECURE=1). Por defecto False para desarrollo local sobre HTTP.
app.config["SESSION_COOKIE_SECURE"] = cookie_secure_activada()
# Instancia de nuestro gestor de la DB (se conecta o crea las tablas)
db_manager = DBManager()


@app.before_request
def asignar_correlation_id():
    """TF-0020: asigna un correlation_id único a la petición y guarda el token
    para restaurarlo en el teardown.

    Registrado antes de `proteccion_csrf` para que toda petición —incluida la
    que termina en `abort(403)`— tenga id y un teardown limpio. No emite log.
    """
    g._correlation_token = set_correlation_id()


@app.before_request
def proteccion_csrf():
    """Garantiza un token CSRF por sesión y lo exige en toda petición POST (TF-0008)."""
    session.setdefault("csrf_token", generar_token())
    if request.method == "POST":
        if not token_valido(request.form.get("csrf_token", ""), session.get("csrf_token", "")):
            abort(403)


@app.teardown_request
def limpiar_correlation_id(exc=None):
    """TF-0020: restaura el correlation_id al valor de fallback al terminar la
    petición.

    `teardown_request` se ejecuta siempre, también si la vista lanzó una
    excepción, así que el contextvar nunca queda "goteando" entre peticiones.
    """
    reset_correlation_id(g.pop("_correlation_token", None))


@app.context_processor
def inyectar_csrf_token():
    """Expone csrf_token a todas las plantillas."""
    return {"csrf_token": session.get("csrf_token", "")}

@app.route('/')
def index():
    """Ruta principal: Muestra la lista de tareas pendientes."""
    
    # LECTURA 1: Obtener las tareas Pendientes, ordenadas por fecha límite (CRUD Read)
    tareas_pendientes = db_manager.obtener_tareas(estado="Pendiente")
    
    # LECTURA 2: Obtener la lista de proyectos para mostrar en la interfaz
    proyectos = db_manager.obtener_proyectos()
    
    # Flask usa render_template para cargar el HTML y pasarle variables
    return render_template('index.html',
                           tareas=[t.to_dict() for t in tareas_pendientes],
                           proyectos=[p.to_dict() for p in proyectos])

@app.route('/crear', methods=['GET', 'POST'])
def crear_tarea_web():
    """Maneja la creación de una tarea."""

    proyectos = [p.to_dict() for p in db_manager.obtener_proyectos()]
    comun = dict(proyectos=proyectos,
                 accion=url_for('crear_tarea_web'),
                 titulo_pag='Nueva tarea',
                 boton='Crear tarea')

    if request.method == 'POST':
        # 1. Validación server-side de los datos del formulario (TF-0007)
        datos, errores = validar_datos_tarea(
            request.form, {p['id'] for p in proyectos})

        if errores:
            # Re-render del formulario con los mensajes y los valores enviados.
            return render_template('formulario_tarea.html',
                                   errores=errores,
                                   valores=request.form.to_dict(),
                                   **comun), 400

        # 2. Creación del objeto de POO y guardado (CRUD Create)
        db_manager.crear_tarea(Tarea(**datos))

        # Después de la creación exitosa, redirigimos al inicio
        return redirect(url_for('index'))

    # Si la solicitud es GET, simplemente mostramos el formulario
    return render_template('formulario_tarea.html',
                           errores={}, valores={}, **comun)


@app.route('/tareas/<int:tarea_id>/completar', methods=['POST'])
def completar_tarea(tarea_id):
    """Marca una tarea como completada (TF-0013). CSRF cubierto por before_request."""
    if not db_manager.marcar_tarea_completada(tarea_id):
        abort(404)
    return redirect(url_for('index'))


@app.route('/tareas/<int:tarea_id>/eliminar', methods=['POST'])
def eliminar_tarea(tarea_id):
    """Elimina una tarea (TF-0016). Borrado permanente. CSRF cubierto por before_request."""
    if not db_manager.eliminar_tarea(tarea_id):
        abort(404)
    return redirect(url_for('index'))


@app.route('/tareas/<int:tarea_id>/editar', methods=['GET', 'POST'])
def editar_tarea(tarea_id):
    """Edita los campos de una tarea (TF-0014). CSRF cubierto por before_request.

    No modifica `estado` ni `fecha_creacion`.
    """
    tarea = db_manager.obtener_tarea(tarea_id)
    if tarea is None:
        abort(404)

    proyectos = [p.to_dict() for p in db_manager.obtener_proyectos()]
    comun = dict(proyectos=proyectos,
                 accion=url_for('editar_tarea', tarea_id=tarea_id),
                 titulo_pag='Editar tarea',
                 boton='Guardar cambios')

    if request.method == 'POST':
        datos, errores = validar_datos_tarea(
            request.form, {p['id'] for p in proyectos})
        if errores:
            return render_template('formulario_tarea.html',
                                   errores=errores,
                                   valores=request.form.to_dict(),
                                   **comun), 400
        db_manager.actualizar_tarea(tarea_id, datos)
        return redirect(url_for('index'))

    d = tarea.to_dict()
    valores = {
        'titulo': d['titulo'],
        'descripcion': d['descripcion'] or '',
        'fecha_limite': d['fecha_limite'] or '',
        'prioridad': d['prioridad'] or '',
        # str: la plantilla compara con `proyecto.id|string`
        'proyecto_id': str(d['proyecto_id']),
    }
    return render_template('formulario_tarea.html',
                           errores={}, valores=valores, **comun)


# --- TF-0031: UI de pruebas del Discovery nuevo ---------------------------
#
# Flujo:
#
#   GET  /discovery/nuevo
#        -> genera un `codigo` de prueba y redirige al formulario
#   GET|POST /discovery/<codigo>/formulario
#        -> recorre el árbol pregunta por pregunta (src.formulario.arbol),
#           persiste cada respuesta vía RepositorioRespuestasFormulario;
#           al terminar el árbol muestra el botón "Ejecutar Discovery"
#   POST /discovery/<codigo>/ejecutar
#        -> ejecutar_discovery(codigo, crear_cliente()); nunca muestra el
#           resultado directamente — el estado de la corrida (éxito, fallo,
#           avisos) ya queda persistido en `acciones` por TF-0030, así que
#           /resultado es una vista de solo lectura sobre eso
#   GET  /discovery/<codigo>/resultado
#        -> Expediente Maestro generado (Perfiles/Requisitos/Restricciones/
#           Datos), o el estado "todavía no ejecutado" / el error registrado
#
# Interfaz de pruebas funcional, no diseño visual definitivo. `codigo` no
# tiene persistencia propia ni FK a nada: es solo el identificador de
# agrupación que ya usan `respuestas_formulario` y las tablas del Expediente
# Maestro (mismo criterio de acoplamiento flojo que el resto del repo).


def _historial_formulario(respuestas):
    """Lista `[{"pregunta_texto", "respuesta"}, ...]` legible para mostrar
    lo ya respondido; deserializa las respuestas de selección múltiple en
    vez de mostrar el JSON crudo almacenado."""
    historial = []
    for r in respuestas:
        pregunta = PREGUNTAS.get(r.pregunta_id)
        if pregunta is None:
            texto_respuesta = r.respuesta
        else:
            valor = deserializar_respuesta(pregunta, r.respuesta)
            texto_respuesta = ", ".join(valor) if isinstance(valor, list) else valor
        historial.append({"pregunta_texto": r.pregunta_texto, "respuesta": texto_respuesta})
    return historial


def _reapertura_pendiente(codigo):
    """TF-0032 — primer Gap/Contradiccion ABIERTO/ABIERTA de `codigo` con un
    `pregunta_id` resoluble (A1), o `None`. Gaps antes que Contradicciones,
    ambos por `id` ascendente — orden simple y determinista, no hay
    prioridad declarada entre hallazgos."""
    for gap in RepositorioGaps().listar(codigo):
        if gap.estado == EstadoGap.ABIERTO:
            dominio, _, etiqueta = gap.campo_o_concepto.partition(".")
            pregunta_id = resolver_pregunta(dominio, etiqueta)
            if pregunta_id is not None:
                return ("gap", gap.id, pregunta_id)
    for contradiccion in RepositorioContradicciones().listar(codigo):
        if contradiccion.estado == EstadoContradiccion.ABIERTA:
            dominio, _, etiqueta = contradiccion.concepto.partition(".")
            pregunta_id = resolver_pregunta(dominio, etiqueta)
            if pregunta_id is not None:
                return ("contradiccion", contradiccion.id, pregunta_id)
    return None


@app.route('/discovery/nuevo')
def discovery_nuevo():
    """Genera un código de prueba nuevo y arranca el formulario."""
    codigo = f"DISC-{uuid.uuid4().hex[:8]}"
    return redirect(url_for('discovery_formulario', codigo=codigo))


@app.route('/discovery/<codigo>/formulario', methods=['GET', 'POST'])
def discovery_formulario(codigo):
    """Recorre el árbol de decisión pregunta por pregunta (TF-0030,
    `src.formulario.arbol.siguiente_pregunta`), sin interpretar ni
    modificar su lógica: esta vista solo captura y persiste."""
    repo_respuestas = RepositorioRespuestasFormulario()

    if request.method == 'POST':
        pregunta_id = request.form.get('pregunta_id', '')
        pregunta = PREGUNTAS.get(pregunta_id)
        if pregunta is None:
            abort(400)

        valor = (
            request.form.getlist('respuesta') if pregunta.multiple
            else request.form.get('respuesta', '')
        )
        try:
            validar_respuesta(pregunta, valor)
        except RespuestaInvalida as exc:
            respuestas = repo_respuestas.listar(codigo)
            return render_template(
                'discovery_formulario.html', codigo=codigo, pregunta=pregunta,
                es_texto_libre=pregunta.tipo_pregunta == TipoPregunta.TEXTO_LIBRE,
                error=str(exc), valor_previo=valor,
                historial=_historial_formulario(respuestas),
            ), 400

        texto = serializar_respuesta(pregunta, valor)
        repo_respuestas.registrar(
            codigo, pregunta.pregunta_id, pregunta.texto, pregunta.tipo_pregunta, texto,
        )

        # TF-0032 — si esta era la pregunta de una reapertura pendiente,
        # resolverla ahora (nunca reprocesa el formulario completo).
        reapertura = _reapertura_pendiente(codigo)
        if reapertura is not None and reapertura[2] == pregunta.pregunta_id:
            tipo_hallazgo, hallazgo_id, _ = reapertura
            procesar_reapertura(codigo, tipo_hallazgo, hallazgo_id, crear_cliente())

        # PRG: evita reenviar la misma respuesta si se refresca la página.
        return redirect(url_for('discovery_formulario', codigo=codigo))

    respuestas = repo_respuestas.listar(codigo)
    reapertura = _reapertura_pendiente(codigo)
    if reapertura is not None:
        _, _, pregunta_id_reapertura = reapertura
        pregunta = PREGUNTAS[pregunta_id_reapertura]
        return render_template(
            'discovery_formulario.html', codigo=codigo, pregunta=pregunta,
            es_texto_libre=pregunta.tipo_pregunta == TipoPregunta.TEXTO_LIBRE,
            error=None, valor_previo=None, historial=_historial_formulario(respuestas),
            reapertura=True,
        )

    pregunta = siguiente_pregunta(respuestas)
    return render_template(
        'discovery_formulario.html', codigo=codigo, pregunta=pregunta,
        es_texto_libre=pregunta is not None and pregunta.tipo_pregunta == TipoPregunta.TEXTO_LIBRE,
        error=None, valor_previo=None, historial=_historial_formulario(respuestas),
        reapertura=False,
    )


@app.route('/discovery/<codigo>/ejecutar', methods=['POST'])
def discovery_ejecutar(codigo):
    """Dispara `ejecutar_discovery()` (TF-0030) y redirige al resultado.

    No muestra el resultado ni el error aquí: `ejecutar_discovery` ya deja
    todo lo necesario registrado en `acciones` (COMPLETADA o FALLIDA, con su
    `error` si aplica) — `/resultado` es quien lo lee.
    """
    respuestas = RepositorioRespuestasFormulario().listar(codigo)
    if siguiente_pregunta(respuestas) is not None:
        return redirect(url_for('discovery_formulario', codigo=codigo))

    try:
        ejecutar_discovery(codigo, crear_cliente())
    except FormularioIncompleto:
        pass  # carrera improbable; /resultado reflejará "no ejecutado todavía"
    except Exception:
        pass  # ya quedó registrado como FALLIDA por ejecutar_discovery

    return redirect(url_for('discovery_resultado', codigo=codigo))


@app.route('/discovery/<codigo>/resultado')
def discovery_resultado(codigo):
    """Vista de solo lectura sobre lo ya persistido: no vuelve a ejecutar
    Discovery ni guarda nada (`ejecutar_discovery` todavía no es idempotente
    — sin botón de "volver a ejecutar" en esta primera versión, para no
    invitar a duplicar entidades durante las pruebas)."""
    respuestas = RepositorioRespuestasFormulario().listar(codigo)
    if not respuestas:
        abort(404)

    completo = siguiente_pregunta(respuestas) is None

    acciones_discovery = [
        a for a in RepositorioAcciones().listar(ticket=codigo)
        if a['tipo'] == TIPO_ACCION_DISCOVERY
    ]
    ultima_accion = acciones_discovery[-1] if acciones_discovery else None
    ejecutado = ultima_accion is not None
    fallido = ejecutado and ultima_accion['estado'] != COMPLETADA
    resultado_accion = (
        json.loads(ultima_accion['resultado'])
        if ejecutado and ultima_accion['resultado'] else {}
    )

    entidades = None
    gaps = []
    contradicciones = []
    if ejecutado and not fallido:
        entidades = {
            'perfiles': RepositorioPerfiles().listar(codigo),
            'requisitos': RepositorioRequisitos().listar(codigo),
            'restricciones': RepositorioRestricciones().listar(codigo),
            'datos': RepositorioDatos().listar(codigo),
        }
        # TF-0032 — Gap/Contradiccion de esta corrida (A4).
        gaps = RepositorioGaps().listar(codigo)
        contradicciones = RepositorioContradicciones().listar(codigo)

    return render_template(
        'discovery_resultado.html', codigo=codigo, completo=completo,
        ejecutado=ejecutado, fallido=fallido,
        error=resultado_accion.get('error'), problemas=resultado_accion.get('problemas', []),
        estado_discovery=resultado_accion.get('estado'),
        entidades=entidades, gaps=gaps, contradicciones=contradicciones,
    )


if __name__ == '__main__':
    # Arranque para desarrollo local (TF-0017 / BL-10). Docker usa `flask run`
    # (ver Dockerfile), no este bloque. Configuración por entorno con defaults
    # seguros (vía src.config, TF-0019): sin debugger de Werkzeug y solo loopback
    # salvo opt-in explícito.
    app.run(
        host=config.host(),
        port=config.puerto(),
        debug=config.debug_activado(),
    )
