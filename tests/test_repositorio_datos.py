"""Pruebas de la tabla `datos` y de `RepositorioDatos`.

Sin restricción de `naturaleza` (a diferencia de `Capacidad`): un `Dato`
puede ser declarado, observado o deducido por igual.
"""
import sqlite3

import pytest

from src.expediente.modelo import Dato, NaturalezaInformacion
from src.proyectos.estado import NivelConfianza, OrigenDato
from src.repositorios.datos import RepositorioDatos


@pytest.fixture
def repo(db):
    return RepositorioDatos()


class TestCrearTablaDatos:
    def test_crear_tablas_crea_datos(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='datos'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestCrear:
    @pytest.mark.parametrize("naturaleza", [
        NaturalezaInformacion.DECLARADO,
        NaturalezaInformacion.OBSERVADO,
        NaturalezaInformacion.DEDUCIDO,
    ])
    def test_acepta_las_tres_naturalezas(self, repo, naturaleza):
        d = repo.crear(
            "PROY-001", "estado de suscripcion del usuario", naturaleza,
            OrigenDato.INFERENCE, NivelConfianza.MEDIA,
            temporalidad="persistente", sensibilidad="privada",
        )
        assert isinstance(d, Dato)
        assert d.naturaleza == naturaleza
        assert d.temporalidad == "persistente"
        assert d.sensibilidad == "privada"

    def test_temporalidad_y_sensibilidad_son_opcionales(self, repo):
        d = repo.crear(
            "PROY-001", "algo", NaturalezaInformacion.DEDUCIDO,
            OrigenDato.INFERENCE, NivelConfianza.BAJA,
        )
        assert d.temporalidad is None
        assert d.sensibilidad is None


class TestListarYObtener:
    def test_listar_filtra_por_codigo(self, repo):
        repo.crear("PROY-001", "a", NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA)
        repo.crear("PROY-002", "b", NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA)
        assert len(repo.listar("PROY-001")) == 1

    def test_obtener_inexistente_devuelve_none(self, repo):
        assert repo.obtener(999) is None
