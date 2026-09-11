"""Pruebas de la tabla `capacidades` y de `RepositorioCapacidades`.

Foco especial en la validación de `naturaleza`: una Capacidad nunca puede
ser `OBSERVADO` (checkpoint de consolidación) — es una habilidad deducida o,
rara vez, declarada directamente, nunca "evidencia observada" en sí misma.
"""
import sqlite3

import pytest

from src.expediente.errores import NaturalezaInvalida
from src.expediente.modelo import Capacidad, NaturalezaInformacion
from src.proyectos.estado import NivelConfianza, OrigenDato
from src.repositorios.capacidades import RepositorioCapacidades


@pytest.fixture
def repo(db):
    return RepositorioCapacidades()


class TestCrearTablaCapacidades:
    def test_crear_tablas_crea_capacidades(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='capacidades'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestCrear:
    def test_crear_deducida(self, repo):
        c = repo.crear(
            "PROY-001", "identificar usuario", "identidad",
            NaturalezaInformacion.DEDUCIDO, OrigenDato.INFERENCE, NivelConfianza.MEDIA,
        )
        assert isinstance(c, Capacidad)
        assert c.tipo == "identidad"

    def test_crear_declarada(self, repo):
        c = repo.crear(
            "PROY-001", "controlar acceso", "acceso",
            NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA,
        )
        assert c.naturaleza == NaturalezaInformacion.DECLARADO

    def test_naturaleza_observado_rechazada(self, repo):
        with pytest.raises(NaturalezaInvalida):
            repo.crear(
                "PROY-001", "algo", "x",
                NaturalezaInformacion.OBSERVADO, OrigenDato.REPOSITORY, NivelConfianza.BAJA,
            )
        # nada debió escribirse
        assert repo.listar("PROY-001") == []

    def test_tipo_es_vocabulario_abierto_sin_validar_contra_catalogo(self, repo):
        """D4: vocabulario extensible — este primer corte no valida `tipo`
        contra ningún catálogo (decisión pospuesta a propósito)."""
        c = repo.crear(
            "PROY-001", "algo muy especifico de este proyecto", "tipo_nunca_visto_antes",
            NaturalezaInformacion.DEDUCIDO, OrigenDato.INFERENCE, NivelConfianza.BAJA,
        )
        assert c.tipo == "tipo_nunca_visto_antes"


class TestListarYObtener:
    def test_listar_filtra_por_codigo(self, repo):
        repo.crear("PROY-001", "a", "x", NaturalezaInformacion.DEDUCIDO, OrigenDato.INFERENCE, NivelConfianza.MEDIA)
        repo.crear("PROY-002", "b", "x", NaturalezaInformacion.DEDUCIDO, OrigenDato.INFERENCE, NivelConfianza.MEDIA)
        assert len(repo.listar("PROY-001")) == 1

    def test_obtener_inexistente_devuelve_none(self, repo):
        assert repo.obtener(999) is None
