import sqlite3
from .modelos import Tarea, Proyecto
import os

# Ruta configurable via entorno para permitir montar un volumen en Docker
# (CLAUDE.md 25.5). Por defecto mantiene el comportamiento local previo.
DATABASE_NAME = os.environ.get('TASKFLOW_DB', 'tareas.db')


def get_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    return conn


def crear_tablas():
    conn = get_connection()
    cursor = conn.cursor()

    # Tabla proyectos
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS proyectos (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre TEXT NOT NULL,
            descripcion TEXT,
            fecha_inicio TEXT,
            estado TEXT
        )
    """)

    # Tabla tareas
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS tareas (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            titulo TEXT NOT NULL,
            descripcion TEXT,
            fecha_creacion TEXT,
            fecha_limite TEXT,
            prioridad TEXT,
            estado TEXT,
            proyecto_id INTEGER,
            FOREIGN KEY (proyecto_id) REFERENCES proyectos(id)
        )
    """)

    try:
        cursor.execute(
            "INSERT INTO proyectos (id, nombre, descripcion, estado) VALUES (0, 'Tareas Generales', 'Tareas sin clasificar', 'Activo')")
    except sqlite3.IntegrityError:
        pass

    conn.commit()
    conn.close()


class DBManager:

    def __init__(self):
        crear_tablas()

    def crear_tarea(self, tarea: Tarea) -> Tarea:
        conn = get_connection()
        cursor = conn.cursor()

        cursor.execute("""
            INSERT INTO tareas(titulo, descripcion, fecha_creacion, fecha_limite, prioridad, estado, proyecto_id)
            VALUES(?, ?, ?, ?, ?, ?, ?)
        """, (tarea._titulo, tarea._descripcion, tarea._fecha_creacion, tarea._fecha_limite, tarea._prioridad, tarea._estado, tarea._proyecto_id))

        tarea.id = cursor.lastrowid
        conn.commit()
        conn.close()
        return tarea

    def marcar_tarea_completada(self, tarea_id):
        """Marca una tarea como 'Completada' (TF-0013).

        Devuelve True si actualizó una fila, False si el id no existe.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE tareas SET estado = 'Completada' WHERE id = ?", (tarea_id,))
        conn.commit()
        afectadas = cursor.rowcount
        conn.close()
        return afectadas > 0

    def obtener_tarea(self, tarea_id):
        """Devuelve la Tarea con ese id, o None si no existe (TF-0014).

        Preserva fecha_creacion y estado (coherente con TF-0009).
        """
        conn = get_connection()
        cursor = conn.cursor()
        fila = cursor.execute(
            "SELECT * FROM tareas WHERE id = ?", (tarea_id,)).fetchone()
        conn.close()
        if fila is None:
            return None
        return Tarea(
            titulo=fila['titulo'],
            fecha_limite=fila['fecha_limite'],
            prioridad=fila['prioridad'],
            proyecto_id=fila['proyecto_id'],
            descripcion=fila['descripcion'],
            id=fila['id'],
            estado=fila['estado'],
            fecha_creacion=fila['fecha_creacion'],
        )

    def actualizar_tarea(self, tarea_id, datos):
        """Actualiza los campos editables de una tarea (TF-0014).

        No modifica `estado` ni `fecha_creacion`. `datos` debe venir ya saneado
        por `validar_datos_tarea` (mismo contrato que `crear_tarea`).
        Devuelve True si actualizó una fila, False si el id no existe.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("""
            UPDATE tareas
               SET titulo = ?, descripcion = ?, fecha_limite = ?,
                   prioridad = ?, proyecto_id = ?
             WHERE id = ?
        """, (datos['titulo'], datos['descripcion'], datos['fecha_limite'],
              datos['prioridad'], datos['proyecto_id'], tarea_id))
        conn.commit()
        afectadas = cursor.rowcount
        conn.close()
        return afectadas > 0

    def obtener_proyectos(self):
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("SELECT * FROM proyectos")
        filas = cursor.fetchall()
        conn.close()

        proyectos = [
            Proyecto(nombre=fila['nombre'], descripcion=fila['descripcion'],
                     id=fila['id'], estado=fila['estado'])
            for fila in filas
        ]
        return proyectos

    def obtener_tareas(self, estado=None):
        """
        Obtiene tareas de la DB. Aplica un algoritmo de ordenamiento y filtrado.
        """
        conn = get_connection()
        cursor = conn.cursor()
        
        sql = "SELECT * FROM tareas"
        params = []
        
        # Algoritmo de Filtrado: Si se pasa un estado, filtramos
        if estado:
            sql += " WHERE estado = ?"
            params.append(estado)

        # Algoritmo de Ordenamiento: Ordenamos por fecha límite (ASCENDENTE)
        sql += " ORDER BY fecha_limite ASC" 

        cursor.execute(sql, params)
        filas = cursor.fetchall()
        conn.close()
        
        # Convertimos filas SQL (diccionarios gracias a row_factory) a objetos Tarea (POO)
        tareas = []
        for fila in filas:
            # Recreamos el objeto Tarea a partir de los datos de la DB
            t = Tarea(
                titulo=fila['titulo'],
                fecha_limite=fila['fecha_limite'],
                prioridad=fila['prioridad'],
                proyecto_id=fila['proyecto_id'],
                descripcion=fila['descripcion'],
                id=fila['id'],
                estado=fila['estado'],
                fecha_creacion=fila['fecha_creacion']  # TF-0009: preservar el valor almacenado
            )
            tareas.append(t)
        return tareas



if __name__ == '__main__':
    # Bloque de prueba para la clase
    if os.path.exists(DATABASE_NAME):
        os.remove(DATABASE_NAME)
        print(f"Base de datos {DATABASE_NAME} eliminada.")

    crear_tablas()
    print(
        f"Base de datos {DATABASE_NAME} y tablas inicializadas correctamente.")

    # Prueba del CRUD (CREATE)
    manager = DBManager()
    tarea_prueba = Tarea(
        titulo="Completar Ejercicio de CRUD",
        fecha_limite="2025-10-30",
        prioridad="Alta",
        proyecto_id=0,
        descripcion="Implementar el módulo database.py"
    )

    tarea_creada = manager.crear_tarea(tarea_prueba)
    print(f"Tarea creada y ID asignado: {tarea_creada.id}")