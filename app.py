# app.py
from flask import Flask, render_template, request, redirect, url_for
from src.database import DBManager
from src.modelos import Tarea, Proyecto
from src.validaciones import validar_datos_tarea

# Inicialización de la aplicación Flask
app = Flask(__name__)
# Instancia de nuestro gestor de la DB (se conecta o crea las tablas)
db_manager = DBManager()

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

    if request.method == 'POST':
        # 1. Validación server-side de los datos del formulario (TF-0007)
        datos, errores = validar_datos_tarea(
            request.form, {p['id'] for p in proyectos})

        if errores:
            # Re-render del formulario con los mensajes y los valores enviados.
            return render_template('formulario_tarea.html',
                                   proyectos=proyectos,
                                   errores=errores,
                                   valores=request.form.to_dict()), 400

        # 2. Creación del objeto de POO y guardado (CRUD Create)
        db_manager.crear_tarea(Tarea(**datos))

        # Después de la creación exitosa, redirigimos al inicio
        return redirect(url_for('index'))

    # Si la solicitud es GET, simplemente mostramos el formulario
    return render_template('formulario_tarea.html',
                           proyectos=proyectos,
                           errores={},
                           valores={})

if __name__ == '__main__':
    # Aseguramos que la DB esté inicializada y corremos el servidor
    print("Iniciando servidor Flask...")
    app.run(debug=True)