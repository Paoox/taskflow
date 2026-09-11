"""Pruebas de la tabla `funcionalidades` y de `RepositorioFuncionalidades`.

Sin `naturaleza`/`origen`/`confianza`: una Funcionalidad es puramente
organizativa (checkpoint de consolidación).
"""
import sqlite3

import pytest

from src.expediente.modelo import Funcionalidad
from src.repositorios.funcionalidades import RepositorioFuncionalidades


@pytest.fixture
def repo(db):
    return RepositorioFuncionalidades()


class TestCrearTablaFuncionalidades:
    def test_crear_tablas_crea_funcionalidades(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='funcionalidades'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestCrearYListar:
    def test_crear_sin_tier(self, repo):
        f = repo.crear("PROY-001", "Calculadora basica", "suma/resta/mult/div")
        assert isinstance(f, Funcionalidad)
        assert f.tier is None

    def test_crear_con_tier(self, repo):
        f = repo.crear("PROY-001", "Operaciones avanzadas", "raiz/matrices", tier="premium")
        assert f.tier == "premium"

    def test_no_tiene_campo_naturaleza(self):
        """Verificación estructural: `Funcionalidad` nunca duplica la
        clasificación epistémica de sus Requisitos."""
        import dataclasses
        campos = {c.name for c in dataclasses.fields(Funcionalidad)}
        assert "naturaleza" not in campos
        assert "origen" not in campos
        assert "confianza" not in campos

    def test_listar_filtra_por_codigo(self, repo):
        repo.crear("PROY-001", "a")
        repo.crear("PROY-002", "b")
        assert len(repo.listar("PROY-001")) == 1

    def test_obtener_inexistente_devuelve_none(self, repo):
        assert repo.obtener(999) is None
