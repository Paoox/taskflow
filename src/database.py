import sqlite3
from .modelos import Tarea, Proyecto
from . import config

# Ruta configurable via entorno para permitir montar un volumen en Docker
# (CLAUDE.md 25.5). Resuelta en import vía config (TF-0019); el valor por
# defecto conserva el comportamiento local previo.
DATABASE_NAME = config.ruta_db()


def get_connection():
    conn = sqlite3.connect(DATABASE_NAME)
    conn.row_factory = sqlite3.Row
    # TF-0015: SQLite no fuerza las claves foráneas salvo que se active por
    # conexión (el pragma no se persiste en el archivo). Como primera sentencia
    # tras connect(), fuera de cualquier transacción.
    conn.execute("PRAGMA foreign_keys = ON")
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

    # Tabla acciones (TF-0022): registro persistente de ejecuciones para la
    # trazabilidad de CLAUDE.md §28. Es infraestructura de trazabilidad, no parte
    # del dominio de tareas: sin FK (el `ticket` es un identificador textual
    # TF-XXXX, no una fila de tareas/proyectos) y sin índices (§30).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS acciones (
            id             INTEGER PRIMARY KEY AUTOINCREMENT,
            ticket         TEXT,
            actor          TEXT NOT NULL,
            tipo           TEXT NOT NULL,
            entrada        TEXT,
            resultado      TEXT,
            estado         TEXT NOT NULL,
            creado_en      TEXT NOT NULL,
            actualizado_en TEXT
        )
    """)

    # Tabla expedientes (TF-0026): PROJECT_STATE, el expediente maestro de un
    # proyecto de software orquestado (`src.proyectos.estado.ExpedienteProyecto`).
    # Es un dominio distinto y sin relación con `proyectos` (el agrupador de
    # tareas del CRUD): sin FK entre ambas tablas. `contenido`/`salud` guardan
    # JSON (mismo criterio que `acciones.entrada`/`resultado`); `codigo`
    # ("PROY-XXX") se deriva del `id` autoincremental, no se almacena aparte.
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS expedientes (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            nombre           TEXT NOT NULL,
            checklist_version TEXT NOT NULL,
            contenido        TEXT NOT NULL,
            salud            TEXT,
            readiness        TEXT,
            estado_general   REAL,
            creado_en        TEXT NOT NULL,
            actualizado_en   TEXT,
            last_analyzed_at TEXT
        )
    """)

    # Tabla briefs: comunicación original del cliente (brief inicial +
    # rondas posteriores), separada de `expedientes` (PROJECT_STATE) y de
    # `acciones` (trazabilidad de ejecuciones). Corrección arquitectónica
    # aprobada tras los smoke tests de TF-0028/TF-0029: la metadata de
    # coordinación de TaskFlow no debe mezclarse con la evidencia del
    # proyecto, y el brief del cliente necesita su propia fuente de primera
    # clase (`src.proyectos.brief.EntradaBrief`). Sin FK (mismo criterio que
    # `acciones.ticket`: `codigo` es un identificador textual "PROY-XXX", no
    # una fila de otra tabla) y sin índices (§30 CLAUDE.md).
    cursor.execute("""
        CREATE TABLE IF NOT EXISTS briefs (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo      TEXT NOT NULL,
            ronda       INTEGER NOT NULL,
            tipo        TEXT NOT NULL,
            texto       TEXT NOT NULL,
            origen      TEXT NOT NULL,
            recibido_en TEXT NOT NULL
        )
    """)

    # --- Modelo conceptual consolidado del Expediente Maestro (Discovery) ---
    # Checkpoint de persistencia mínima aprobado. Dominio nuevo e
    # independiente de `expedientes`/`checklist` (PROJECT_STATE antiguo):
    # ninguna tabla de esta sección tiene FK hacia `expedientes` — mismo
    # criterio de vínculo flojo por `codigo` textual que ya usa `briefs`.
    # `relaciones` es la única tabla de aristas del grafo (Requisito-
    # >requiere->Capacidad, Capacidad->depende_de->Capacidad, Capacidad-
    # >opera_sobre->Dato, Funcionalidad->agrupa->Requisito): una sola tabla
    # genérica en vez de cuatro, aprobada como solución definitiva mientras
    # no haya necesidad real de integridad referencial específica por tipo.

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS respuestas_formulario (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo           TEXT NOT NULL,
            pregunta_id      TEXT NOT NULL,
            pregunta_texto   TEXT NOT NULL,
            tipo_pregunta    TEXT NOT NULL,
            respuesta        TEXT NOT NULL,
            respondido_en    TEXT NOT NULL,
            accion_id_origen INTEGER
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS perfiles (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo           TEXT NOT NULL,
            nombre           TEXT NOT NULL,
            descripcion      TEXT,
            naturaleza       TEXT NOT NULL,
            origen           TEXT NOT NULL,
            confianza        TEXT NOT NULL,
            accion_id_origen INTEGER,
            fuente_directa   TEXT,
            creado_en        TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS requisitos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo           TEXT NOT NULL,
            descripcion      TEXT NOT NULL,
            naturaleza       TEXT NOT NULL,
            origen           TEXT NOT NULL,
            confianza        TEXT NOT NULL,
            estado           TEXT NOT NULL,
            accion_id_origen INTEGER,
            fuente_directa   TEXT,
            creado_en        TEXT NOT NULL,
            actualizado_en   TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS capacidades (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo           TEXT NOT NULL,
            descripcion      TEXT NOT NULL,
            tipo             TEXT NOT NULL,
            naturaleza       TEXT NOT NULL,
            origen           TEXT NOT NULL,
            confianza        TEXT NOT NULL,
            accion_id_origen INTEGER,
            fuente_directa   TEXT,
            creado_en        TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS funcionalidades (
            id          INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo      TEXT NOT NULL,
            nombre      TEXT NOT NULL,
            descripcion TEXT,
            tier        TEXT,
            creado_en   TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS datos (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo           TEXT NOT NULL,
            descripcion      TEXT NOT NULL,
            temporalidad     TEXT,
            sensibilidad     TEXT,
            naturaleza       TEXT NOT NULL,
            origen           TEXT NOT NULL,
            confianza        TEXT NOT NULL,
            accion_id_origen INTEGER,
            fuente_directa   TEXT,
            creado_en        TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS restricciones (
            id               INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo           TEXT NOT NULL,
            tipo             TEXT NOT NULL,
            descripcion      TEXT NOT NULL,
            naturaleza       TEXT NOT NULL,
            origen           TEXT NOT NULL,
            accion_id_origen INTEGER,
            fuente_directa   TEXT,
            creado_en        TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS features_propuestas (
            id                     INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo                 TEXT NOT NULL,
            descripcion            TEXT NOT NULL,
            motivo                 TEXT NOT NULL,
            origen                 TEXT NOT NULL,
            confianza              TEXT NOT NULL,
            impacto                TEXT,
            estado                 TEXT NOT NULL,
            campo_relacionado_tipo TEXT,
            campo_relacionado_id   INTEGER,
            accion_id_origen       INTEGER,
            creado_en              TEXT NOT NULL,
            actualizado_en         TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS gaps (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo                TEXT NOT NULL,
            entidad_afectada_tipo TEXT NOT NULL,
            entidad_afectada_id   INTEGER,
            campo_o_concepto      TEXT NOT NULL,
            motivo                TEXT,
            bloquea               TEXT NOT NULL,
            criticidad            TEXT,
            estado                TEXT NOT NULL,
            creado_en             TEXT NOT NULL,
            resuelto_en           TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS contradicciones (
            id                    INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo                TEXT NOT NULL,
            entidad_tipo          TEXT NOT NULL,
            concepto              TEXT NOT NULL,
            afirmaciones          TEXT NOT NULL,
            estado                TEXT NOT NULL,
            resolucion_valor      TEXT,
            resolucion_accion_id  INTEGER,
            creado_en             TEXT NOT NULL,
            resuelto_en           TEXT
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS relaciones (
            id           INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo       TEXT NOT NULL,
            tipo         TEXT NOT NULL,
            origen_tipo  TEXT NOT NULL,
            origen_id    INTEGER NOT NULL,
            destino_tipo TEXT NOT NULL,
            destino_id   INTEGER NOT NULL,
            creado_en    TEXT NOT NULL
        )
    """)

    cursor.execute("""
        CREATE TABLE IF NOT EXISTS estado_observado_versiones (
            id                          INTEGER PRIMARY KEY AUTOINCREMENT,
            codigo                      TEXT NOT NULL,
            version                     INTEGER NOT NULL,
            capturado_en                TEXT NOT NULL,
            tecnologias_detectadas      TEXT,
            funcionalidades_detectadas  TEXT,
            aparenta_funcionar          TEXT,
            accion_id_origen            INTEGER
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

    def eliminar_tarea(self, tarea_id):
        """Elimina una tarea por id (TF-0016).

        Devuelve True si borró una fila, False si el id no existe. Borrar una
        tarea (hijo de la FK `tareas.proyecto_id`) no afecta a `proyectos`.
        """
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute("DELETE FROM tareas WHERE id = ?", (tarea_id,))
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
