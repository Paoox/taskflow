"""TF-0022 — Pruebas de la tabla `acciones` y de `RepositorioAcciones`.

Se prueban de forma aislada (sin runner ni agentes). Usan la fixture `db` de
`conftest.py`, que redirige la base a un archivo temporal y ejecuta
`crear_tablas()` (incluida la tabla `acciones`). `tests/test_database.py` no se
toca: la aserción de que `crear_tablas()` crea `acciones` vive aquí.
"""
import ast
import json
import os
import re
import sqlite3
import subprocess
import sys
from pathlib import Path

import pytest

from src import database
from src.repositorios.acciones import (
    COMPLETADA,
    EN_CURSO,
    ESTADOS,
    FALLIDA,
    RepositorioAcciones,
    _serializar,
)

_RAIZ = Path(__file__).resolve().parents[1]
_FECHA_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")
_COLUMNAS = [
    "id", "ticket", "actor", "tipo", "entrada", "resultado", "estado",
    "creado_en", "actualizado_en",
]


@pytest.fixture
def repo(db):
    """`RepositorioAcciones` sobre la base temporal de la fixture `db`."""
    return RepositorioAcciones()


def _importaciones(ruta_rel):
    arbol = ast.parse((_RAIZ / ruta_rel).read_text(encoding="utf-8"), filename=ruta_rel)
    mods = set()
    for nodo in ast.walk(arbol):
        if isinstance(nodo, ast.Import):
            mods.update(a.name for a in nodo.names)
        elif isinstance(nodo, ast.ImportFrom):
            mods.add(nodo.module or "")
    return mods


# --- CA-1: esquema de la tabla -------------------------------------

class TestEsquema:
    def test_columnas_esperadas(self, db):
        conn = database.get_connection()
        cols = [f["name"] for f in conn.execute("PRAGMA table_info(acciones)")]
        conn.close()
        assert cols == _COLUMNAS

    def test_id_es_autoincrement(self, db):
        conn = database.get_connection()
        sql = conn.execute(
            "SELECT sql FROM sqlite_master WHERE type='table' AND name='acciones'"
        ).fetchone()[0]
        conn.close()
        assert "AUTOINCREMENT" in sql.upper()

    def test_sin_foreign_keys(self, db):
        conn = database.get_connection()
        fks = list(conn.execute("PRAGMA foreign_key_list(acciones)"))
        conn.close()
        assert fks == []

    def test_sin_indices_adicionales(self, db):
        conn = database.get_connection()
        idx = list(conn.execute("PRAGMA index_list(acciones)"))
        conn.close()
        assert idx == []

    def test_reinicializar_no_falla_ni_duplica(self, db):
        database.crear_tablas()
        database.DBManager()
        conn = database.get_connection()
        cols = [f["name"] for f in conn.execute("PRAGMA table_info(acciones)")]
        conn.close()
        assert cols == _COLUMNAS


# --- CA-2: registrar ---------------------------------------------

class TestRegistrar:
    def test_devuelve_id_int_y_fila_en_curso(self, repo):
        aid = repo.registrar("TF-0022", "humano:pao", "checkpoint", {"n": 1})
        assert isinstance(aid, int)
        fila = repo.obtener(aid)
        assert fila["estado"] == EN_CURSO
        assert fila["actualizado_en"] is None
        assert _FECHA_RE.match(fila["creado_en"])
        assert (fila["ticket"], fila["actor"], fila["tipo"]) == (
            "TF-0022", "humano:pao", "checkpoint")

    def test_ids_incrementales(self, repo):
        a = repo.registrar("T", "a", "t")
        b = repo.registrar("T", "a", "t")
        assert b > a

    def test_entrada_none_se_guarda_como_null(self, repo):
        aid = repo.registrar("T", "a", "t", entrada=None)
        assert repo.obtener(aid)["entrada"] is None

    def test_actor_none_viola_not_null(self, repo):
        with pytest.raises(sqlite3.IntegrityError):
            repo.registrar("T", None, "t")


# --- CA-3: marcar (éxito e id inexistente) --------------------

class TestMarcarExito:
    def test_completa_con_resultado(self, repo):
        aid = repo.registrar("TF-0022", "agente:eco", "completar", {"in": 1})
        assert repo.marcar(aid, COMPLETADA, resultado={"out": 2, "ok": True}) is True
        fila = repo.obtener(aid)
        assert fila["estado"] == COMPLETADA
        assert json.loads(fila["resultado"]) == {"out": 2, "ok": True}
        assert _FECHA_RE.match(fila["actualizado_en"])

    def test_no_altera_creado_en(self, repo):
        aid = repo.registrar("T", "a", "t")
        creado = repo.obtener(aid)["creado_en"]
        repo.marcar(aid, FALLIDA, resultado={"error": "x"})
        assert repo.obtener(aid)["creado_en"] == creado

    def test_id_inexistente_devuelve_false_sin_tocar_nada(self, repo):
        repo.registrar("T", "a", "t")
        antes = repo.listar()
        assert repo.marcar(999999, COMPLETADA, resultado={"x": 1}) is False
        assert repo.listar() == antes


# --- CA-4: marcar con estado inválido ------------------------

class TestMarcarEstadoInvalido:
    def test_lanza_valueerror_y_no_escribe(self, repo):
        aid = repo.registrar("T", "a", "t")
        with pytest.raises(ValueError):
            repo.marcar(aid, "ESTADO_RARO", resultado={"x": 1})
        fila = repo.obtener(aid)
        assert fila["estado"] == EN_CURSO
        assert fila["actualizado_en"] is None
        assert fila["resultado"] is None

    def test_valida_antes_de_abrir_la_bd(self, repo, monkeypatch):
        import src.repositorios.acciones as mod

        def _no_deberia():
            raise AssertionError("marcar() no debe abrir conexión con estado inválido")

        monkeypatch.setattr(mod, "get_connection", _no_deberia)
        with pytest.raises(ValueError):
            repo.marcar(1, "NOPE")

    def test_conjunto_de_estados(self):
        assert ESTADOS == frozenset({"EN_CURSO", "COMPLETADA", "FALLIDA"})


# --- D11: marcar(resultado=None) no toca `resultado` --------

class TestMarcarSinResultado:
    def test_no_modifica_resultado_existente(self, repo):
        aid = repo.registrar("T", "a", "t")
        repo.marcar(aid, COMPLETADA, resultado={"v": 1})
        assert repo.marcar(aid, FALLIDA) is True
        fila = repo.obtener(aid)
        assert fila["estado"] == FALLIDA
        assert json.loads(fila["resultado"]) == {"v": 1}
        assert _FECHA_RE.match(fila["actualizado_en"])

    def test_resultado_sigue_null_si_nunca_se_paso(self, repo):
        aid = repo.registrar("T", "a", "t")
        repo.marcar(aid, COMPLETADA)
        assert repo.obtener(aid)["resultado"] is None


# --- CA-5: obtener ------------------------------------------

class TestObtener:
    def test_devuelve_dict_con_las_9_claves(self, repo):
        aid = repo.registrar("TF-1", "a", "t", {"k": "v"})
        fila = repo.obtener(aid)
        assert set(fila) == set(_COLUMNAS)
        assert json.loads(fila["entrada"]) == {"k": "v"}

    def test_id_inexistente_devuelve_none(self, repo):
        assert repo.obtener(123456) is None


# --- CA-6: listar -----------------------------------------

class TestListar:
    def test_todas_ordenadas_por_id(self, repo):
        ids = [repo.registrar(f"TF-{i}", "a", "t") for i in range(3)]
        assert [f["id"] for f in repo.listar()] == ids

    def test_filtra_por_ticket(self, repo):
        repo.registrar("TF-0021", "a", "t")
        repo.registrar("TF-0022", "a", "t")
        repo.registrar("TF-0022", "a", "t")
        assert [f["ticket"] for f in repo.listar(ticket="TF-0022")] == [
            "TF-0022", "TF-0022"]

    def test_ticket_sin_coincidencias_devuelve_vacio(self, repo):
        repo.registrar("TF-0022", "a", "t")
        assert repo.listar(ticket="TF-9999") == []

    def test_sin_filas_devuelve_vacio(self, repo):
        assert repo.listar() == []


# --- CA-7: entrada/resultado dict y str; round-trip ----

class TestSerializacion:
    def test_dict_se_guarda_como_json_y_round_trip(self, repo):
        original = {"a": 1, "b": ["x", "y"], "c": None, "ñ": "áé"}
        aid = repo.registrar("T", "a", "t", entrada=original)
        crudo = repo.obtener(aid)["entrada"]
        assert isinstance(crudo, str)
        assert json.loads(crudo) == original

    def test_str_se_guarda_verbatim(self, repo):
        aid = repo.registrar("T", "a", "t", entrada='{"ya":"json"}')
        assert repo.obtener(aid)["entrada"] == '{"ya":"json"}'

    def test_list_se_guarda_como_json(self, repo):
        aid = repo.registrar("T", "a", "t", entrada=[1, 2, 3])
        assert json.loads(repo.obtener(aid)["entrada"]) == [1, 2, 3]

    def test_resultado_acepta_dict_y_str(self, repo):
        aid = repo.registrar("T", "a", "t")
        repo.marcar(aid, COMPLETADA, resultado={"d": 1})
        assert json.loads(repo.obtener(aid)["resultado"]) == {"d": 1}
        repo.marcar(aid, COMPLETADA, resultado='"cadena-json"')
        assert repo.obtener(aid)["resultado"] == '"cadena-json"'

    def test_tipo_no_soportado_lanza_typeerror(self, repo):
        with pytest.raises(TypeError):
            repo.registrar("T", "a", "t", entrada=123)

    def test_serializar_directo(self):
        assert _serializar(None) is None
        assert _serializar("x") == "x"
        assert _serializar({"k": 1}) == '{"k": 1}'
        assert json.loads(_serializar([1, 2])) == [1, 2]
        with pytest.raises(TypeError):
            _serializar(3.14)


# --- CA-8: `ticket` textual sin FK -----------------------

class TestTicketSinFK:
    def test_ticket_arbitrario_no_requiere_tareas_ni_proyectos(self, repo):
        aid = repo.registrar("TF-9999", "agente:x", "t", {"k": 1})
        assert repo.obtener(aid)["ticket"] == "TF-9999"

    def test_no_hay_violaciones_de_fk(self, repo):
        repo.registrar("TF-9999", "a", "t")
        conn = database.get_connection()
        assert list(conn.execute("PRAGMA foreign_key_check")) == []
        conn.close()

    def test_ticket_none_permitido_y_listar_none_devuelve_todas(self, repo):
        aid = repo.registrar(None, "a", "t")
        assert repo.obtener(aid)["ticket"] is None
        assert [f["id"] for f in repo.listar(ticket=None)] == [aid]


# --- CA-9: sin acoplamiento ni ciclo --------------------

class TestSinAcoplamiento:
    def test_acciones_no_importa_flask_ni_app(self):
        mods = _importaciones("src/repositorios/acciones.py")
        for prohibido in ("flask", "app", "src.app"):
            assert prohibido not in mods, f"acciones.py importa {prohibido!r}"
        assert not any(m.startswith(("flask.", "src.app.")) for m in mods)

    def test_database_no_importa_repositorios(self):
        mods = _importaciones("src/database.py")
        assert not any("repositorio" in m for m in mods)

    def test_import_aislado_sin_efectos(self):
        codigo = (
            "import sys\n"
            "import src.repositorios.acciones, src.database\n"
            "malo = [m for m in sys.modules if m == 'flask' or m.startswith('flask.') "
            "or m == 'app']\n"
            "assert not malo, malo\n"
            "print('ok')\n"
        )
        r = subprocess.run(
            [sys.executable, "-c", codigo],
            cwd=str(_RAIZ), capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(_RAIZ)},
        )
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip().endswith("ok")
