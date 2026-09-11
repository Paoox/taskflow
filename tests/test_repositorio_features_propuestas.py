"""Pruebas de la tabla `features_propuestas` y de
`RepositorioFeaturesPropuestas`.

Foco especial en la garantía estructural contra la contaminación: una
propuesta nunca puede tener `origen=USER`, y este repositorio no expone
ningún camino de escritura que mueva una fila a `requisitos`.
"""
import sqlite3

import pytest

from src.expediente.errores import OrigenInvalido
from src.expediente.modelo import EstadoFeaturePropuesta, FeaturePropuesta
from src.proyectos.estado import NivelConfianza, OrigenDato
from src.repositorios.features_propuestas import RepositorioFeaturesPropuestas


@pytest.fixture
def repo(db):
    return RepositorioFeaturesPropuestas()


class TestCrearTablaFeaturesPropuestas:
    def test_crear_tablas_crea_features_propuestas(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='features_propuestas'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestCrear:
    def test_origen_agent_por_defecto(self, repo):
        f = repo.crear("PROY-001", "historial de operaciones", "podria aportar valor", NivelConfianza.MEDIA)
        assert isinstance(f, FeaturePropuesta)
        assert f.origen == OrigenDato.AGENT
        assert f.estado == EstadoFeaturePropuesta.PROPUESTA

    def test_origen_user_rechazado(self, repo):
        with pytest.raises(OrigenInvalido):
            repo.crear(
                "PROY-001", "algo que el usuario si pidio", "motivo",
                NivelConfianza.ALTA, origen=OrigenDato.USER,
            )
        assert repo.listar("PROY-001") == []

    def test_origen_file_rechazado(self, repo):
        with pytest.raises(OrigenInvalido):
            repo.crear("PROY-001", "x", "y", NivelConfianza.BAJA, origen=OrigenDato.FILE)


class TestMarcarEstado:
    def test_marcar_aceptada(self, repo):
        f = repo.crear("PROY-001", "x", "y", NivelConfianza.MEDIA)
        assert repo.marcar_estado(f.id, EstadoFeaturePropuesta.ACEPTADA) is True
        assert repo.obtener(f.id).estado == EstadoFeaturePropuesta.ACEPTADA

    def test_marcar_inexistente_devuelve_false(self, repo):
        assert repo.marcar_estado(999, EstadoFeaturePropuesta.RECHAZADA) is False

    def test_no_expone_ninguna_operacion_de_promocion_a_requisito(self, repo):
        """Garantía estructural: no existe ningún método que mueva una fila
        de aquí a `requisitos` automáticamente — promoverla es una operación
        explícita de `RepositorioRequisitos`, fuera de este repositorio."""
        assert not hasattr(repo, "promover")
        assert not hasattr(repo, "convertir_en_requisito")
        assert not hasattr(repo, "aceptar_como_requisito")


class TestListarYObtener:
    def test_listar_filtra_por_codigo(self, repo):
        repo.crear("PROY-001", "a", "m", NivelConfianza.BAJA)
        repo.crear("PROY-002", "b", "m", NivelConfianza.BAJA)
        assert len(repo.listar("PROY-001")) == 1

    def test_obtener_inexistente_devuelve_none(self, repo):
        assert repo.obtener(999) is None
