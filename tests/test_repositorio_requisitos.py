"""Pruebas de la tabla `requisitos` y de `RepositorioRequisitos`.

Aisladas. Fuente de verdad del modelo conceptual nuevo (checkpoint de
consolidación): no depende de `src.proyectos.estado.EstadoDato` ni del
checklist antiguo.
"""
import sqlite3

import pytest

from src.expediente.modelo import (
    EstadoRequisito, FuenteDirecta, NaturalezaInformacion, Requisito,
)
from src.proyectos.estado import NivelConfianza, OrigenDato
from src.repositorios.requisitos import RepositorioRequisitos


@pytest.fixture
def repo(db):
    return RepositorioRequisitos()


class TestCrearTablaRequisitos:
    def test_crear_tablas_crea_requisitos(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='requisitos'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestCrear:
    def test_crear_devuelve_requisito_activo(self, repo):
        r = repo.crear(
            "PROY-001", "el usuario puede sumar dos numeros",
            NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA,
        )
        assert isinstance(r, Requisito)
        assert r.id is not None
        assert r.estado == EstadoRequisito.ACTIVO
        assert r.actualizado_en == r.creado_en

    def test_naturaleza_deducido_permitida(self, repo):
        r = repo.crear(
            "PROY-001", "manejar division por cero de forma controlada",
            NaturalezaInformacion.DEDUCIDO, OrigenDato.INFERENCE, NivelConfianza.MEDIA,
        )
        assert r.naturaleza == NaturalezaInformacion.DEDUCIDO

    def test_conserva_accion_id_origen_y_fuente_directa(self, repo):
        r = repo.crear(
            "PROY-001", "x", NaturalezaInformacion.DECLARADO, OrigenDato.USER,
            NivelConfianza.ALTA, accion_id_origen=42,
            fuente_directa=FuenteDirecta(tipo="brief", referencia="1"),
        )
        recargado = repo.obtener(r.id)
        assert recargado.accion_id_origen == 42
        assert recargado.fuente_directa.tipo == "brief"


class TestListarYObtener:
    def test_listar_ordena_por_id_ascendente(self, repo):
        repo.crear("PROY-001", "r1", NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA)
        repo.crear("PROY-001", "r2", NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA)
        assert [r.descripcion for r in repo.listar("PROY-001")] == ["r1", "r2"]

    def test_listar_filtra_por_codigo(self, repo):
        repo.crear("PROY-001", "de 001", NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA)
        repo.crear("PROY-002", "de 002", NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA)
        assert len(repo.listar("PROY-001")) == 1

    def test_obtener_inexistente_devuelve_none(self, repo):
        assert repo.obtener(999) is None


class TestDescartar:
    def test_descartar_marca_estado_sin_borrar_la_fila(self, repo):
        r = repo.crear("PROY-001", "x", NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA)
        assert repo.descartar(r.id) is True
        recargado = repo.obtener(r.id)
        assert recargado is not None
        assert recargado.estado == EstadoRequisito.DESCARTADO

    def test_descartar_inexistente_devuelve_false(self, repo):
        assert repo.descartar(999) is False
