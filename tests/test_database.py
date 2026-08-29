"""Pruebas de persistencia sobre SQLite temporal.

TF-0005 — CRUD básico.  TF-0009 — fecha_creacion.  TF-0013/0014 — completar/editar.
TF-0015 — enforcement de claves foráneas (PRAGMA foreign_keys = ON).
"""
import sqlite3

import pytest

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


class TestFechaCreacion:
    """TF-0009 — obtener_tareas() debe devolver el fecha_creacion almacenado."""

    def test_preserva_el_valor_almacenado(self, db):
        db.crear_tarea(Tarea(
            titulo="Con fecha", fecha_limite="2026-05-05", prioridad="Alta",
            proyecto_id=0, fecha_creacion="2020-01-02 03:04:05"))
        (t,) = db.obtener_tareas()
        assert t._fecha_creacion == "2020-01-02 03:04:05"

    def test_to_dict_refleja_el_valor_almacenado(self, db):
        db.crear_tarea(Tarea(
            titulo="Con fecha", fecha_limite="2026-05-05", prioridad="Alta",
            proyecto_id=0, fecha_creacion="2020-01-02 03:04:05"))
        (t,) = db.obtener_tareas()
        assert t.to_dict()["fecha_creacion"] == "2020-01-02 03:04:05"

    def test_estable_entre_lecturas_consecutivas(self, db):
        # Tarea creada sin fecha_creacion explícito: el valor lo genera el
        # constructor una vez y crear_tarea() lo persiste; dos lecturas deben
        # devolver el mismo valor (antes de TF-0009 cambiaba en cada lectura).
        db.crear_tarea(_tarea("Sin fecha explícita", "2026-05-05"))
        primera = db.obtener_tareas()[0]._fecha_creacion
        segunda = db.obtener_tareas()[0]._fecha_creacion
        assert primera == segunda

    def test_coincide_con_lo_que_persistio_crear_tarea(self, db):
        creada = db.crear_tarea(_tarea("X", "2026-05-05"))
        conn = database.get_connection()
        almacenado = conn.execute(
            "SELECT fecha_creacion FROM tareas WHERE id = ?",
            (creada.id,)).fetchone()["fecha_creacion"]
        conn.close()
        (leida,) = db.obtener_tareas()
        assert leida._fecha_creacion == almacenado


class TestMarcarTareaCompletada:
    """TF-0013 — DBManager.marcar_tarea_completada(id)."""

    def test_actualiza_el_estado_y_devuelve_true(self, db):
        creada = db.crear_tarea(_tarea("Cerrar", "2026-07-07"))
        assert db.marcar_tarea_completada(creada.id) is True

        (t,) = db.obtener_tareas(estado="Completada")
        assert t._titulo == "Cerrar"
        assert db.obtener_tareas(estado="Pendiente") == []

    def test_id_inexistente_devuelve_false(self, db):
        db.crear_tarea(_tarea("Otra", "2026-07-07"))
        assert db.marcar_tarea_completada(999999) is False
        # No debe alterar nada.
        assert len(db.obtener_tareas(estado="Pendiente")) == 1

    def test_idempotente_sobre_tarea_ya_completada(self, db):
        creada = db.crear_tarea(_tarea("Ya hecha", "2026-07-07", estado="Completada"))
        # La fila existe -> rowcount 1 aunque el valor no cambie.
        assert db.marcar_tarea_completada(creada.id) is True
        (t,) = db.obtener_tareas(estado="Completada")
        assert t._estado == "Completada"


def _datos_edicion(**cambios):
    base = {"titulo": "Editado", "descripcion": "nueva desc",
            "fecha_limite": "2026-11-11", "prioridad": "Baja", "proyecto_id": 0}
    base.update(cambios)
    return base


class TestObtenerTarea:
    """TF-0014 — DBManager.obtener_tarea(id)."""

    def test_devuelve_la_tarea_con_sus_campos(self, db):
        creada = db.crear_tarea(Tarea(
            titulo="Buscar", fecha_limite="2026-05-05", prioridad="Alta",
            proyecto_id=0, descripcion="d", fecha_creacion="2020-02-02 02:02:02"))
        t = db.obtener_tarea(creada.id)
        assert isinstance(t, Tarea)
        assert (t._titulo, t._prioridad, t._proyecto_id, t._fecha_limite) == (
            "Buscar", "Alta", 0, "2026-05-05")
        # Preserva fecha_creacion y estado (TF-0009).
        assert t._fecha_creacion == "2020-02-02 02:02:02"
        assert t._estado == "Pendiente"

    def test_id_inexistente_devuelve_none(self, db):
        assert db.obtener_tarea(999999) is None


class TestActualizarTarea:
    """TF-0014 — DBManager.actualizar_tarea(id, datos)."""

    def test_actualiza_los_campos_editables_y_devuelve_true(self, db):
        creada = db.crear_tarea(_tarea("Original", "2026-01-01", prioridad="Alta"))
        assert db.actualizar_tarea(creada.id, _datos_edicion()) is True
        t = db.obtener_tarea(creada.id)
        assert (t._titulo, t._descripcion, t._fecha_limite, t._prioridad,
                t._proyecto_id) == ("Editado", "nueva desc", "2026-11-11", "Baja", 0)

    def test_no_modifica_estado_ni_fecha_creacion(self, db):
        creada = db.crear_tarea(Tarea(
            titulo="Hecha", fecha_limite="2026-01-01", prioridad="Alta",
            proyecto_id=0, estado="Completada",
            fecha_creacion="2019-09-09 09:09:09"))
        db.actualizar_tarea(creada.id, _datos_edicion(titulo="Retocada"))
        t = db.obtener_tarea(creada.id)
        assert t._titulo == "Retocada"
        assert t._estado == "Completada"
        assert t._fecha_creacion == "2019-09-09 09:09:09"

    def test_id_inexistente_devuelve_false_y_no_altera_nada(self, db):
        db.crear_tarea(_tarea("Intacta", "2026-01-01"))
        assert db.actualizar_tarea(999999, _datos_edicion()) is False
        (t,) = db.obtener_tareas()
        assert t._titulo == "Intacta"


class TestForeignKeys:
    """TF-0015 — PRAGMA foreign_keys = ON en get_connection()."""

    def test_pragma_activo_en_toda_conexion(self, db):
        conn = database.get_connection()
        assert conn.execute("PRAGMA foreign_keys").fetchone()[0] == 1
        conn.close()

    def test_insert_raw_con_proyecto_inexistente_lanza_integrityerror(self, db):
        conn = database.get_connection()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO tareas(titulo, proyecto_id) VALUES ('x', 999)")
        conn.close()

    def test_update_raw_a_proyecto_inexistente_lanza_integrityerror(self, db):
        creada = db.crear_tarea(_tarea("ok", "2026-01-01"))
        conn = database.get_connection()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "UPDATE tareas SET proyecto_id = 999 WHERE id = ?", (creada.id,))
        conn.close()

    def test_crear_tarea_con_proyecto_inexistente_lanza_integrityerror(self, db):
        with pytest.raises(sqlite3.IntegrityError):
            db.crear_tarea(Tarea(titulo="Huerfana", fecha_limite="2026-01-01",
                                 prioridad="Alta", proyecto_id=999))
        assert db.obtener_tareas() == []

    def test_actualizar_tarea_con_proyecto_inexistente_lanza_y_no_altera(self, db):
        creada = db.crear_tarea(_tarea("Antes", "2026-01-01"))
        with pytest.raises(sqlite3.IntegrityError):
            db.actualizar_tarea(creada.id, _datos_edicion(proyecto_id=999))
        assert db.obtener_tarea(creada.id)._titulo == "Antes"
        assert db.obtener_tarea(creada.id)._proyecto_id == 0

    def test_delete_de_proyecto_referenciado_lanza_integrityerror(self, db):
        db.crear_tarea(_tarea("Referencia a 0", "2026-01-01"))
        conn = database.get_connection()
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute("DELETE FROM proyectos WHERE id = 0")
        conn.close()

    # --- positivos / no-regresión ---

    def test_operaciones_con_proyecto_existente_siguen_ok(self, db):
        creada = db.crear_tarea(_tarea("Valida", "2026-01-01", proyecto_id=0))
        assert db.actualizar_tarea(creada.id, _datos_edicion(proyecto_id=0)) is True
        assert db.marcar_tarea_completada(creada.id) is True

    def test_proyecto_id_null_sigue_permitido(self, db):
        conn = database.get_connection()
        conn.execute("INSERT INTO tareas(titulo, proyecto_id) VALUES ('sin proyecto', NULL)")
        conn.commit()
        n = conn.execute(
            "SELECT COUNT(*) FROM tareas WHERE proyecto_id IS NULL").fetchone()[0]
        conn.close()
        assert n == 1

    def test_seed_id_0_se_crea_con_fk_activa(self, db):
        proyectos = db.obtener_proyectos()
        assert any(p.id == 0 for p in proyectos)


class TestEliminarTarea:
    """TF-0016 — DBManager.eliminar_tarea(id) (borrado permanente)."""

    def test_borra_la_tarea_y_devuelve_true(self, db):
        creada = db.crear_tarea(_tarea("A borrar", "2026-01-01"))
        assert db.eliminar_tarea(creada.id) is True
        assert db.obtener_tarea(creada.id) is None
        assert db.obtener_tareas() == []

    def test_id_inexistente_devuelve_false_y_no_altera_nada(self, db):
        db.crear_tarea(_tarea("Intacta", "2026-01-01"))
        assert db.eliminar_tarea(999999) is False
        assert len(db.obtener_tareas()) == 1

    def test_solo_borra_la_indicada(self, db):
        a = db.crear_tarea(_tarea("A", "2026-01-01"))
        db.crear_tarea(_tarea("B", "2026-01-02"))
        db.eliminar_tarea(a.id)
        assert [t._titulo for t in db.obtener_tareas()] == ["B"]

    def test_borra_tarea_completada(self, db):
        creada = db.crear_tarea(_tarea("Hecha", "2026-01-01", estado="Completada"))
        assert db.eliminar_tarea(creada.id) is True
        assert db.obtener_tarea(creada.id) is None

    def test_borra_tarea_con_proyecto_id_null(self, db):
        conn = database.get_connection()
        conn.execute("INSERT INTO tareas(titulo, proyecto_id) VALUES ('sp', NULL)")
        conn.commit()
        tid = conn.execute(
            "SELECT id FROM tareas ORDER BY id DESC LIMIT 1").fetchone()[0]
        conn.close()
        assert db.eliminar_tarea(tid) is True

    def test_borrar_tarea_no_afecta_al_proyecto_ni_a_la_integridad(self, db):
        creada = db.crear_tarea(_tarea("Ref a 0", "2026-01-01", proyecto_id=0))
        db.eliminar_tarea(creada.id)
        assert any(p.id == 0 for p in db.obtener_proyectos())
        conn = database.get_connection()
        assert list(conn.execute("PRAGMA foreign_key_check")) == []
        conn.close()
