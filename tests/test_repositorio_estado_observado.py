"""Pruebas de la tabla `estado_observado_versiones` y de
`RepositorioEstadoObservado`.

D3: versionado, append-only, separado de lo deseado (`requisitos`).
`version` se asigna de forma determinista, mismo patrón que `ronda` en
`RepositorioBriefs`.
"""
import sqlite3

import pytest

from src.expediente.modelo import EstadoObservado
from src.repositorios.estado_observado import RepositorioEstadoObservado


@pytest.fixture
def repo(db):
    return RepositorioEstadoObservado()


class TestCrearTablaEstadoObservado:
    def test_crear_tablas_crea_estado_observado_versiones(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='estado_observado_versiones'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestRegistrar:
    def test_primera_version_es_1(self, repo):
        v = repo.registrar("PROY-001", tecnologias_detectadas=["js"], funcionalidades_detectadas=["tablero"])
        assert isinstance(v, EstadoObservado)
        assert v.version == 1

    def test_versiones_crecientes_y_deterministas(self, repo):
        repo.registrar("PROY-001")
        v2 = repo.registrar("PROY-001")
        v3 = repo.registrar("PROY-001")
        assert v2.version == 2
        assert v3.version == 3

    def test_versiones_independientes_por_codigo(self, repo):
        repo.registrar("PROY-001")
        v = repo.registrar("PROY-002")
        assert v.version == 1  # no hereda la numeración de otro expediente

    def test_conserva_listas_detectadas(self, repo):
        v = repo.registrar(
            "PROY-001",
            tecnologias_detectadas=["javascript", "html", "css"],
            funcionalidades_detectadas=["tablero 3x3", "turnos alternados"],
            aparenta_funcionar="si",
        )
        assert v.tecnologias_detectadas == ["javascript", "html", "css"]
        assert v.funcionalidades_detectadas == ["tablero 3x3", "turnos alternados"]
        assert v.aparenta_funcionar == "si"

    def test_sin_evidencia_devuelve_listas_vacias(self, repo):
        v = repo.registrar("PROY-001")
        assert v.tecnologias_detectadas == []
        assert v.funcionalidades_detectadas == []


class TestListarYUltimaVersion:
    def test_listar_ordena_por_version_ascendente(self, repo):
        repo.registrar("PROY-001", tecnologias_detectadas=["v1"])
        repo.registrar("PROY-001", tecnologias_detectadas=["v2"])
        versiones = repo.listar("PROY-001")
        assert [v.version for v in versiones] == [1, 2]
        assert [v.tecnologias_detectadas for v in versiones] == [["v1"], ["v2"]]

    def test_ultima_version_devuelve_la_mas_reciente(self, repo):
        repo.registrar("PROY-001", tecnologias_detectadas=["v1"])
        repo.registrar("PROY-001", tecnologias_detectadas=["v2"])
        ultima = repo.ultima_version("PROY-001")
        assert ultima.version == 2
        assert ultima.tecnologias_detectadas == ["v2"]

    def test_ultima_version_none_si_no_hay_ninguna(self, repo):
        assert repo.ultima_version("PROY-999") is None

    def test_no_expone_actualizar_ni_eliminar(self, repo):
        """Append-only: mismo criterio que `RepositorioBriefs`."""
        assert not hasattr(repo, "actualizar")
        assert not hasattr(repo, "eliminar")
        assert not hasattr(repo, "borrar")
