# app.py
from flask import Flask, render_template, request, redirect, url_for
from src.database import DBManager
from src.modelos import Tarea, Proyecto

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
                           tareas=tareas_pendientes, 
                           proyectos=proyectos)

@app.route('/crear', methods=['GET', 'POST'])
def crear_tarea_web():
    """Maneja la creación de una tarea."""
    
    proyectos = db_manager.obtener_proyectos() # Necesario para el selector de proyecto
    
    if request.method == 'POST':
        # 1. Recolección de datos del formulario web
        titulo = request.form.get('titulo')
        descripcion = request.form.get('descripcion')
        limite = request.form.get('fecha_limite')
        prioridad = request.form.get('prioridad')
        # Es vital convertir el ID del proyecto a entero, ya que viene como string
        proyecto_id = int(request.form.get('proyecto_id')) 
        
        # 2. Creación del objeto de POO
        nueva_tarea = Tarea(
            titulo=titulo, 
            descripcion=descripcion,
            fecha_limite=limite, 
            prioridad=prioridad, 
            proyecto_id=proyecto_id
        )
        
        # 3. Guardado en la Base de Datos (CRUD Create)
        db_manager.crear_tarea(nueva_tarea)
        
        # Después de la creación exitosa, redirigimos al inicio
        return redirect(url_for('index'))
    
    # Si la solicitud es GET, simplemente mostramos el formulario
    return render_template('formulario_tarea.html', proyectos=proyectos)

if __name__ == '__main__':
    # Aseguramos que la DB esté inicializada y corremos el servidor
    print("Iniciando servidor Flask...")
    app.run(debug=True)