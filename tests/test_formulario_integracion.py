"""Prueba de integración: Formulario -> `respuestas_formulario` real.

Verifica que `arbol.py` + `respuestas.py` + `RepositorioRespuestasFormulario`
(ya existente, sin tocar) funcionan juntos contra una base real — no solo en
memoria. Usa la fixture `db` de `conftest.py`.
"""
import pytest

from src.formulario.arbol import siguiente_pregunta
from src.formulario.preguntas import PREGUNTAS
from src.formulario.respuestas import deserializar_respuesta, serializar_respuesta
from src.repositorios.respuestas_formulario import RepositorioRespuestasFormulario


@pytest.fixture
def repo(db):
    return RepositorioRespuestasFormulario()


def _responder_y_persistir(repo, codigo, pregunta_id, valor):
    pregunta = PREGUNTAS[pregunta_id]
    texto = serializar_respuesta(pregunta, valor)
    repo.registrar(codigo, pregunta.pregunta_id, pregunta.texto, pregunta.tipo_pregunta, texto)


class TestCicloCompletoContraLaBaseReal:
    def test_arbol_avanza_leyendo_directamente_del_repositorio(self, repo):
        codigo = "PROY-001"

        primera = siguiente_pregunta(repo.listar(codigo))
        assert primera.pregunta_id == "nuevo_o_existente"

        _responder_y_persistir(repo, codigo, "nuevo_o_existente", "Es un proyecto nuevo")
        segunda = siguiente_pregunta(repo.listar(codigo))
        assert segunda.pregunta_id == "nombre_proyecto"

    def test_seleccion_multiple_persistida_como_json_se_lee_de_vuelta_correctamente(self, repo):
        codigo = "PROY-002"
        pregunta = PREGUNTAS["administrador_tipo_acciones"]
        valor_original = ["Ver información", "Eliminar cosas", "Otra cosa"]

        _responder_y_persistir(repo, codigo, "administrador_tipo_acciones", valor_original)

        fila = repo.listar(codigo)[0]
        import json
        assert json.loads(fila.respuesta) == valor_original  # JSON válido, no CSV
        assert deserializar_respuesta(pregunta, fila.respuesta) == valor_original

    def test_respuestas_conservan_codigo_por_expediente(self, repo):
        _responder_y_persistir(repo, "PROY-A", "nuevo_o_existente", "Es un proyecto nuevo")
        _responder_y_persistir(repo, "PROY-B", "nuevo_o_existente", "Ya tengo algo construido")

        assert len(repo.listar("PROY-A")) == 1
        assert len(repo.listar("PROY-B")) == 1
        assert repo.listar("PROY-A")[0].respuesta == "Es un proyecto nuevo"
        assert repo.listar("PROY-B")[0].respuesta == "Ya tengo algo construido"

    def test_bucle_perfil_usuario_persistido_produce_multiples_filas(self, repo):
        codigo = "PROY-003"
        r = repo.listar(codigo)
        assert siguiente_pregunta(r).pregunta_id != "perfil_usuario"  # todavía no llegamos ahí

        _responder_y_persistir(repo, codigo, "nuevo_o_existente", "Es un proyecto nuevo")
        _responder_y_persistir(repo, codigo, "nombre_proyecto", "")
        _responder_y_persistir(repo, codigo, "problema_objetivo", "algo")
        _responder_y_persistir(repo, codigo, "plataforma", "No estoy seguro todavía")

        assert siguiente_pregunta(repo.listar(codigo)).pregunta_id == "perfil_usuario"
        _responder_y_persistir(repo, codigo, "perfil_usuario", "clientes")
        _responder_y_persistir(repo, codigo, "perfil_usuario_continuar", "Sí")
        _responder_y_persistir(repo, codigo, "perfil_usuario", "empleados")
        _responder_y_persistir(repo, codigo, "perfil_usuario_continuar", "No")

        filas_perfil = [f for f in repo.listar(codigo) if f.pregunta_id == "perfil_usuario"]
        assert [f.respuesta for f in filas_perfil] == ["clientes", "empleados"]
        assert siguiente_pregunta(repo.listar(codigo)).pregunta_id == "administracion_cantidad"

    def test_formulario_nunca_escribe_en_tablas_de_entidades_interpretadas(self, repo, db):
        """Frontera formulario -> respuestas_formulario -> Discovery ->
        Expediente (decisión 5): tras un ciclo completo, ninguna tabla de
        entidades interpretadas tiene filas."""
        import sqlite3

        import src.database as database

        codigo = "PROY-004"
        _responder_y_persistir(repo, codigo, "nuevo_o_existente", "Es un proyecto nuevo")
        _responder_y_persistir(repo, codigo, "problema_objetivo", "una calculadora")

        conn = sqlite3.connect(database.DATABASE_NAME)
        for tabla in ("requisitos", "capacidades", "funcionalidades", "datos", "restricciones", "features_propuestas"):
            n = conn.execute(f"SELECT COUNT(*) FROM {tabla}").fetchone()[0]
            assert n == 0, f"{tabla} no debería tener filas — el formulario nunca las escribe"
        conn.close()
