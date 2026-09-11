"""Pruebas de la tabla `respuestas_formulario` y de
`RepositorioRespuestasFormulario`.

Captura la pregunta+respuesta cruda, antes de interpretarse en cualquier
entidad del modelo. `pregunta_id` es texto libre mantenido por el código
del árbol (sin catálogo — decisión aprobada del checkpoint de persistencia
mínima).
"""
import sqlite3

import pytest

from src.expediente.modelo import RespuestaFormulario, TipoPregunta
from src.repositorios.respuestas_formulario import RepositorioRespuestasFormulario


@pytest.fixture
def repo(db):
    return RepositorioRespuestasFormulario()


class TestCrearTablaRespuestasFormulario:
    def test_crear_tablas_crea_respuestas_formulario(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='respuestas_formulario'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestRegistrar:
    def test_registrar_opcion_cerrada(self, repo):
        r = repo.registrar(
            "PROY-001", "plataforma_principal", "¿Donde quieres usar tu app?",
            TipoPregunta.OPCION_CERRADA, "navegador",
        )
        assert isinstance(r, RespuestaFormulario)
        assert r.tipo_pregunta == TipoPregunta.OPCION_CERRADA
        assert r.respondido_en

    def test_registrar_texto_libre(self, repo):
        r = repo.registrar(
            "PROY-001", "descripcion_problema", "Describe el problema que quieres resolver",
            TipoPregunta.TEXTO_LIBRE, "quiero controlar mis gastos personales",
        )
        assert r.tipo_pregunta == TipoPregunta.TEXTO_LIBRE

    def test_conserva_accion_id_origen_opcional(self, repo):
        r = repo.registrar(
            "PROY-001", "x", "¿x?", TipoPregunta.TEXTO_LIBRE, "y", accion_id_origen=5,
        )
        assert repo.obtener(r.id).accion_id_origen == 5

    def test_accion_id_origen_por_defecto_es_none(self, repo):
        r = repo.registrar("PROY-001", "x", "¿x?", TipoPregunta.OPCION_CERRADA, "y")
        assert r.accion_id_origen is None

    def test_conserva_snapshot_del_texto_de_la_pregunta(self, repo):
        """El texto exacto que se mostró queda fijo, aunque el árbol de
        decisión en código cambie después de wording."""
        r = repo.registrar("PROY-001", "x", "texto original", TipoPregunta.OPCION_CERRADA, "y")
        assert repo.obtener(r.id).pregunta_texto == "texto original"


class TestListarYObtener:
    def test_listar_conserva_orden_de_respuesta(self, repo):
        repo.registrar("PROY-001", "p1", "¿1?", TipoPregunta.OPCION_CERRADA, "r1")
        repo.registrar("PROY-001", "p2", "¿2?", TipoPregunta.OPCION_CERRADA, "r2")
        assert [r.pregunta_id for r in repo.listar("PROY-001")] == ["p1", "p2"]

    def test_listar_filtra_por_codigo(self, repo):
        repo.registrar("PROY-001", "p", "¿?", TipoPregunta.OPCION_CERRADA, "r")
        repo.registrar("PROY-002", "p", "¿?", TipoPregunta.OPCION_CERRADA, "r")
        assert len(repo.listar("PROY-001")) == 1

    def test_obtener_inexistente_devuelve_none(self, repo):
        assert repo.obtener(999) is None
