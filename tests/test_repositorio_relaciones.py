"""Pruebas de la tabla `relaciones` y de `RepositorioRelaciones`.

Una sola tabla genérica de aristas tipadas (aprobada como solución
definitiva), en vez de una tabla por tipo de relación
(`requisito_requiere_capacidad`, `capacidad_depende_de`, ...).
"""
import sqlite3

import pytest

from src.expediente.modelo import Relacion, TipoRelacion
from src.repositorios.relaciones import RepositorioRelaciones


@pytest.fixture
def repo(db):
    return RepositorioRelaciones()


class TestCrearTablaRelaciones:
    def test_crear_tablas_crea_relaciones(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='relaciones'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestCrear:
    def test_crear_requiere(self, repo):
        r = repo.crear("PROY-001", TipoRelacion.REQUIERE, "requisito", 1, "capacidad", 2)
        assert isinstance(r, Relacion)
        assert r.tipo == TipoRelacion.REQUIERE

    def test_los_cuatro_tipos_de_relacion_conviven_en_la_misma_tabla(self, repo):
        repo.crear("PROY-001", TipoRelacion.REQUIERE, "requisito", 1, "capacidad", 2)
        repo.crear("PROY-001", TipoRelacion.DEPENDE_DE, "capacidad", 2, "capacidad", 3)
        repo.crear("PROY-001", TipoRelacion.OPERA_SOBRE, "capacidad", 2, "dato", 4)
        repo.crear("PROY-001", TipoRelacion.AGRUPA, "funcionalidad", 5, "requisito", 1)
        tipos = {r.tipo for r in repo.listar("PROY-001")}
        assert tipos == {
            TipoRelacion.REQUIERE, TipoRelacion.DEPENDE_DE,
            TipoRelacion.OPERA_SOBRE, TipoRelacion.AGRUPA,
        }


class TestListarConFiltros:
    def test_listar_filtra_por_tipo(self, repo):
        repo.crear("PROY-001", TipoRelacion.REQUIERE, "requisito", 1, "capacidad", 2)
        repo.crear("PROY-001", TipoRelacion.DEPENDE_DE, "capacidad", 2, "capacidad", 3)
        solo_requiere = repo.listar("PROY-001", tipo=TipoRelacion.REQUIERE)
        assert len(solo_requiere) == 1
        assert solo_requiere[0].tipo == TipoRelacion.REQUIERE

    def test_listar_filtra_por_origen(self, repo):
        repo.crear("PROY-001", TipoRelacion.REQUIERE, "requisito", 1, "capacidad", 10)
        repo.crear("PROY-001", TipoRelacion.REQUIERE, "requisito", 2, "capacidad", 11)
        desde_r1 = repo.listar("PROY-001", origen_tipo="requisito", origen_id=1)
        assert len(desde_r1) == 1
        assert desde_r1[0].destino_id == 10

    def test_listar_filtra_por_codigo(self, repo):
        repo.crear("PROY-001", TipoRelacion.REQUIERE, "requisito", 1, "capacidad", 2)
        repo.crear("PROY-002", TipoRelacion.REQUIERE, "requisito", 1, "capacidad", 2)
        assert len(repo.listar("PROY-001")) == 1
