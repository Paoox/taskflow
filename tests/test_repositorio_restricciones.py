"""Pruebas de la tabla `restricciones` y de `RepositorioRestricciones`.

Foco especial en la garantía "siempre declarado": ninguna preferencia
tecnológica del Orquestador puede colarse aquí como si el usuario la
hubiera pedido (reemplaza a `stack_declarado` del modelo antiguo).
"""
import sqlite3

import pytest

from src.expediente.errores import NaturalezaInvalida
from src.expediente.modelo import NaturalezaInformacion, Restriccion
from src.proyectos.estado import OrigenDato
from src.repositorios.restricciones import RepositorioRestricciones


@pytest.fixture
def repo(db):
    return RepositorioRestricciones()


class TestCrearTablaRestricciones:
    def test_crear_tablas_crea_restricciones(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='restricciones'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestCrear:
    def test_naturaleza_declarado_por_defecto(self, repo):
        r = repo.crear("PROY-001", "tecnica_declarada", "el equipo ya sabe Python", OrigenDato.USER)
        assert isinstance(r, Restriccion)
        assert r.naturaleza == NaturalezaInformacion.DECLARADO

    def test_naturaleza_deducido_rechazada(self, repo):
        with pytest.raises(NaturalezaInvalida):
            repo.crear(
                "PROY-001", "tecnica_declarada", "usar Java",
                OrigenDato.INFERENCE, naturaleza=NaturalezaInformacion.DEDUCIDO,
            )
        assert repo.listar("PROY-001") == []

    def test_naturaleza_observado_rechazada(self, repo):
        with pytest.raises(NaturalezaInvalida):
            repo.crear(
                "PROY-001", "tecnica_declarada", "usa Django",
                OrigenDato.REPOSITORY, naturaleza=NaturalezaInformacion.OBSERVADO,
            )


class TestListarYObtener:
    def test_listar_filtra_por_codigo(self, repo):
        repo.crear("PROY-001", "presupuesto", "limitado", OrigenDato.USER)
        repo.crear("PROY-002", "tiempo", "6 semanas", OrigenDato.USER)
        assert len(repo.listar("PROY-001")) == 1

    def test_obtener_inexistente_devuelve_none(self, repo):
        assert repo.obtener(999) is None
