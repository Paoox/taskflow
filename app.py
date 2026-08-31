# app.py
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
