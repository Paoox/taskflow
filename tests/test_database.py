"""TF-0005 — Pruebas de persistencia sobre SQLite temporal."""
from src import database
from src.modelos import Proyecto, Tarea


def _tarea(titulo, fecha_limite, estado="Pendiente", prioridad="Normal", proyecto_id=0):
    return Tarea(titulo=titulo, fecha_limite=fecha_limite, prioridad=prioridad,
                 proyecto_id=proyecto_id, estado=estado)


class TestCrearTablas:
    def test_crea_las_tablas_proyectos_y_tareas(self, db):
        conn = database.get_connection()
        nombres = {fila["name"] for fila in
                   conn.execute("SELECT name FROM sqlite_master WHERE type='table'")}
        conn.close()
        assert {"proyectos", "tareas"}.issubset(nombres)

    def test_proyecto_semilla_existe_una_sola_vez(self, db):
        conn = database.get_connection()
        filas = conn.execute(
            "SELECT id, nombre FROM proyectos WHERE id = 0").fetchall()
        conn.close()
        assert len(filas) == 1
        assert filas[0]["nombre"] == "Tareas Generales"

    def test_reinicializar_no_duplica_ni_falla(self, db):
        database.crear_tablas()
        database.DBManager()
        conn = database.get_connection()
        total = conn.execute("SELECT COUNT(*) FROM proyectos").fetchone()[0]
        conn.close()
        assert total == 1


class TestObtenerProyectos:
    def test_devuelve_objetos_proyecto_con_la_semilla(self, db):
        proyectos = db.obtener_proyectos()
        assert all(isinstance(p, Proyecto) for p in proyectos)
        assert any(p.id == 0 and p.to_dict()["nombre"] == "Tareas Generales"
                   for p in proyectos)


class TestCrearTarea:
    def test_asigna_id_y_persiste(self, db):
        creada = db.crear_tarea(_tarea("Escribir tests", "2026-03-01"))
        assert creada.id is not None

        conn = database.get_connection()
        fila = conn.execute(
            "SELECT titulo, estado, proyecto_id FROM tareas WHERE id = ?",
            (creada.id,)).fetchone()
        conn.close()
        assert fila["titulo"] == "Escribir tests"
        assert fila["estado"] == "Pendiente"
        assert fila["proyecto_id"] == 0

    def test_round_trip_de_campos(self, db):
        db.crear_tarea(_tarea("Con datos", "2026-04-02",
                              prioridad="Alta", proyecto_id=0))
        (t,) = db.obtener_tareas(estado="Pendiente")
        assert t._titulo == "Con datos"
        assert t._prioridad == "Alta"
        assert t._proyecto_id == 0
        assert t._estado == "Pendiente"
        assert t._fecha_limite == "2026-04-02"


class TestObtenerTareas:
    def test_sin_filtro_devuelve_todas(self, db):
        db.crear_tarea(_tarea("A", "2026-01-01"))
        db.crear_tarea(_tarea("B", "2026-01-02", estado="Completada"))
        assert len(db.obtener_tareas()) == 2

    def test_filtra_por_estado(self, db):
        db.crear_tarea(_tarea("Pend", "2026-01-01"))
        db.crear_tarea(_tarea("Hecha", "2026-01-02", estado="Completada"))
        pendientes = db.obtener_tareas(estado="Pendiente")
        assert [t._titulo for t in pendientes] == ["Pend"]

    def test_ordena_por_fecha_limite_ascendente(self, db):
        db.crear_tarea(_tarea("media", "2026-06-15"))
        db.crear_tarea(_tarea("lejana", "2026-12-31"))
        db.crear_tarea(_tarea("cercana", "2026-01-05"))
        titulos = [t._titulo for t in db.obtener_tareas()]
        assert titulos == ["cercana", "media", "lejana"]

    def test_estado_sin_coincidencias_devuelve_lista_vacia(self, db):
        db.crear_tarea(_tarea("A", "2026-01-01"))
        assert db.obtener_tareas(estado="Inexistente") == []
