"""Pruebas de la tabla `contradicciones` y de `RepositorioContradicciones`.

Genérico (D2): relación entre 2+ afirmaciones en conflicto, nunca un estado
de una entidad individual. `afirmaciones` se persiste como JSON (decisión
aprobada).
"""
import sqlite3

import pytest

from src.expediente.modelo import Contradiccion, EstadoContradiccion
from src.repositorios.contradicciones import RepositorioContradicciones

_AFIRMACIONES = [
    {"valor": "gratis", "origen": "brief", "naturaleza": "declarado"},
    {"valor": "suscripcion mensual", "origen": "formulario", "naturaleza": "declarado"},
]


@pytest.fixture
def repo(db):
    return RepositorioContradicciones()


class TestCrearTablaContradicciones:
    def test_crear_tablas_crea_contradicciones(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='contradicciones'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestCrear:
    def test_crear_devuelve_contradiccion_abierta(self, repo):
        c = repo.crear("PROY-001", "requisito", "modelo de negocio", _AFIRMACIONES)
        assert isinstance(c, Contradiccion)
        assert c.estado == EstadoContradiccion.ABIERTA
        assert len(c.afirmaciones) == 2

    def test_rechaza_menos_de_dos_afirmaciones(self, repo):
        with pytest.raises(ValueError):
            repo.crear("PROY-001", "requisito", "x", [_AFIRMACIONES[0]])
        assert repo.listar("PROY-001") == []

    def test_conserva_afirmaciones_exactas(self, repo):
        c = repo.crear("PROY-001", "requisito", "x", _AFIRMACIONES)
        recargado = repo.obtener(c.id)
        assert recargado.afirmaciones == _AFIRMACIONES


class TestResolver:
    def test_resolver_marca_resuelta_y_conserva_resolucion(self, repo):
        c = repo.crear("PROY-001", "requisito", "x", _AFIRMACIONES)
        assert repo.resolver(c.id, "suscripcion mensual", resolucion_accion_id=7) is True
        recargado = repo.obtener(c.id)
        assert recargado.estado == EstadoContradiccion.RESUELTA
        assert recargado.resolucion_valor == "suscripcion mensual"
        assert recargado.resolucion_accion_id == 7
        assert recargado.resuelto_en is not None

    def test_resolver_inexistente_devuelve_false(self, repo):
        assert repo.resolver(999, "x", resolucion_accion_id=1) is False


class TestListar:
    def test_listar_filtra_por_codigo(self, repo):
        repo.crear("PROY-001", "requisito", "a", _AFIRMACIONES)
        repo.crear("PROY-002", "requisito", "b", _AFIRMACIONES)
        assert len(repo.listar("PROY-001")) == 1
