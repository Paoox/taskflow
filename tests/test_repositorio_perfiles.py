"""Pruebas de la tabla `perfiles` y de `RepositorioPerfiles`.

Aisladas. Usan la fixture `db` de `conftest.py`, que redirige la base a un
archivo temporal y ejecuta `crear_tablas()` (incluida `perfiles`).
"""
import sqlite3

import pytest

from src.expediente.modelo import FuenteDirecta, NaturalezaInformacion, Perfil
from src.proyectos.estado import NivelConfianza, OrigenDato
from src.repositorios.perfiles import RepositorioPerfiles


@pytest.fixture
def repo(db):
    return RepositorioPerfiles()


class TestCrearTablaPerfiles:
    def test_crear_tablas_crea_perfiles(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='perfiles'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestCrearYListar:
    def test_crear_devuelve_perfil_con_id(self, repo):
        p = repo.crear(
            "PROY-001", "cliente", "persona que usa la calculadora",
            NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA,
        )
        assert isinstance(p, Perfil)
        assert p.id is not None
        assert p.nombre == "cliente"
        assert p.naturaleza == NaturalezaInformacion.DECLARADO

    def test_listar_filtra_por_codigo(self, repo):
        repo.crear("PROY-001", "a", "", NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA)
        repo.crear("PROY-002", "b", "", NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA)
        assert [p.nombre for p in repo.listar("PROY-001")] == ["a"]

    def test_obtener_inexistente_devuelve_none(self, repo):
        assert repo.obtener(999) is None

    def test_conserva_fuente_directa(self, repo):
        p = repo.crear(
            "PROY-001", "cliente", "", NaturalezaInformacion.DECLARADO, OrigenDato.USER,
            NivelConfianza.ALTA, fuente_directa=FuenteDirecta(tipo="brief", referencia="1"),
        )
        recargado = repo.obtener(p.id)
        assert recargado.fuente_directa == FuenteDirecta(tipo="brief", referencia="1")

    def test_fuente_directa_ausente_es_none(self, repo):
        p = repo.crear("PROY-001", "x", "", NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA)
        assert repo.obtener(p.id).fuente_directa is None
