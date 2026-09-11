"""Pruebas de la tabla `gaps` y de `RepositorioGaps`.

Genérico (D2): sin tabla `GapRequisito`/`GapCapacidad` por separado.
`bloquea` se persiste como JSON (decisión aprobada). `criticidad` es un
campo de lectura cacheada: este repositorio no la calcula, solo la
almacena.
"""
import sqlite3

import pytest

from src.expediente.modelo import EstadoGap, Gap
from src.repositorios.gaps import RepositorioGaps


@pytest.fixture
def repo(db):
    return RepositorioGaps()


class TestCrearTablaGaps:
    def test_crear_tablas_crea_gaps(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='gaps'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestCrear:
    def test_crear_sin_bloquea_devuelve_lista_vacia(self, repo):
        g = repo.crear("PROY-001", "monetizacion", "medio de cobro preferido")
        assert isinstance(g, Gap)
        assert g.bloquea == []
        assert g.estado == EstadoGap.ABIERTO
        assert g.criticidad is None

    def test_crear_con_bloquea_generico(self, repo):
        """Un mismo Gap puede bloquear entidades de tipos distintos —
        exactamente lo que D2 exige de una estructura genérica."""
        g = repo.crear(
            "PROY-001", "requisito", "evaluacion de cuestionarios",
            bloquea=[{"tipo": "requisito", "id": 4}, {"tipo": "capacidad", "id": 7}],
        )
        recargado = repo.obtener(g.id)
        assert recargado.bloquea == [{"tipo": "requisito", "id": 4}, {"tipo": "capacidad", "id": 7}]

    def test_entidad_afectada_id_puede_ser_none(self, repo):
        """Un gap puede referirse a algo que todavía no existe (p. ej. "no
        sabemos el modelo de monetización") — no tiene fila que referenciar."""
        g = repo.crear("PROY-001", "monetizacion", "modelo de negocio")
        assert g.entidad_afectada_id is None


class TestActualizarCriticidad:
    def test_actualizar_criticidad(self, repo):
        g = repo.crear("PROY-001", "requisito", "x", bloquea=[{"tipo": "requisito", "id": 1}])
        assert repo.actualizar_criticidad(g.id, "critico") is True
        assert repo.obtener(g.id).criticidad == "critico"

    def test_actualizar_criticidad_inexistente_devuelve_false(self, repo):
        assert repo.actualizar_criticidad(999, "critico") is False


class TestMarcarEstado:
    def test_marcar_resuelto_asigna_resuelto_en(self, repo):
        g = repo.crear("PROY-001", "requisito", "x")
        assert repo.marcar_estado(g.id, EstadoGap.RESUELTO) is True
        recargado = repo.obtener(g.id)
        assert recargado.estado == EstadoGap.RESUELTO
        assert recargado.resuelto_en is not None

    def test_documentado_no_bloqueante_tambien_asigna_resuelto_en(self, repo):
        g = repo.crear("PROY-001", "requisito", "x")
        repo.marcar_estado(g.id, EstadoGap.DOCUMENTADO_NO_BLOQUEANTE)
        assert repo.obtener(g.id).resuelto_en is not None


class TestListar:
    def test_listar_filtra_por_codigo(self, repo):
        repo.crear("PROY-001", "requisito", "a")
        repo.crear("PROY-002", "requisito", "b")
        assert len(repo.listar("PROY-001")) == 1
