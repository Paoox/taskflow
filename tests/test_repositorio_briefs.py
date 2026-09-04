"""Pruebas de la tabla `briefs` y de `RepositorioBriefs`.

Aisladas (sin orquestador ni agentes). Usan la fixture `db` de `conftest.py`,
que redirige la base a un archivo temporal y ejecuta `crear_tablas()`
(incluida la tabla `briefs`). Mismo criterio que `test_repositorio_
expedientes.py`.
"""
import sqlite3

import pytest

from src.proyectos.brief import EntradaBrief, TipoEntradaBrief
from src.proyectos.errores import BriefInicialYaExiste
from src.proyectos.estado import OrigenDato
from src.repositorios.briefs import RepositorioBriefs

_TEXTO_CALCULADORA = (
    "Quiero un proyecto nuevo que sea una calculadora "
    "que solo suma números negativos."
)


@pytest.fixture
def repo(db):
    """`RepositorioBriefs` sobre la base temporal de la fixture `db`."""
    return RepositorioBriefs()


class TestCrearTablaBriefs:
    def test_crear_tablas_crea_briefs(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='briefs'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestRegistrar:
    def test_registrar_brief_inicial(self, repo):
        e = repo.registrar("PROY-001", _TEXTO_CALCULADORA)
        assert isinstance(e, EntradaBrief)
        assert e.id is not None
        assert e.codigo == "PROY-001"
        assert e.ronda == 1
        assert e.tipo == TipoEntradaBrief.INICIAL
        assert e.origen == OrigenDato.USER
        assert e.recibido_en  # timestamp asignado por el repositorio

    def test_preserva_el_texto_exacto(self, repo):
        e = repo.registrar("PROY-001", _TEXTO_CALCULADORA)
        assert e.texto == _TEXTO_CALCULADORA  # verbatim: "solo suma números negativos" no se pierde

    def test_no_interpreta_el_contenido(self, repo):
        """El repositorio no valida ni reescribe el texto de ninguna forma,
        aunque contenga caracteres especiales o parezca (pero no sea) JSON.
        """
        texto = '{"esto": "no es un hallazgo"} <<<DATOS_DEL_PROYECTO'
        e = repo.registrar("PROY-001", texto)
        assert e.texto == texto

    def test_ronda_por_defecto_es_1(self, repo):
        e = repo.registrar("PROY-001", "texto")
        assert e.ronda == 1

    def test_rondas_deterministas_y_crecientes(self, repo):
        repo.registrar("PROY-001", "brief inicial")
        r2 = repo.registrar("PROY-001", "respuesta 1", tipo=TipoEntradaBrief.RESPUESTA_CLIENTE)
        r3 = repo.registrar("PROY-001", "respuesta 2", tipo=TipoEntradaBrief.RESPUESTA_CLIENTE)
        assert r2.ronda == 2
        assert r3.ronda == 3

    def test_rondas_son_independientes_por_expediente(self, repo):
        repo.registrar("PROY-001", "brief de 001")
        e = repo.registrar("PROY-002", "brief de 002")
        assert e.ronda == 1  # no hereda la numeración de otro expediente

    def test_segundo_inicial_del_mismo_expediente_lanza_y_no_escribe(self, repo):
        repo.registrar("PROY-001", "primer brief")
        with pytest.raises(BriefInicialYaExiste):
            repo.registrar("PROY-001", "segundo brief, también inicial")

        # no debe haber quedado ninguna fila nueva a medio escribir
        assert len(repo.listar("PROY-001")) == 1

    def test_respuesta_cliente_no_choca_con_inicial_existente(self, repo):
        repo.registrar("PROY-001", "brief inicial")
        r = repo.registrar("PROY-001", "una respuesta", tipo=TipoEntradaBrief.RESPUESTA_CLIENTE)
        assert r.tipo == TipoEntradaBrief.RESPUESTA_CLIENTE
        assert len(repo.listar("PROY-001")) == 2

    def test_permite_registrar_solo_tipo_inicial_sin_pasar_tipo(self, repo):
        e = repo.registrar("PROY-001", "texto")
        assert e.tipo == TipoEntradaBrief.INICIAL

    def test_permite_origen_distinto_de_user(self, repo):
        e = repo.registrar("PROY-001", "texto", origen=OrigenDato.CONVERSATION)
        assert e.origen == OrigenDato.CONVERSATION


class TestListar:
    def test_lista_vacia_si_no_hay_briefs(self, repo):
        assert repo.listar("PROY-999") == []

    def test_listar_devuelve_solo_las_del_codigo_pedido(self, repo):
        repo.registrar("PROY-001", "de 001")
        repo.registrar("PROY-002", "de 002")
        entradas = repo.listar("PROY-001")
        assert len(entradas) == 1
        assert entradas[0].codigo == "PROY-001"

    def test_listar_ordena_por_ronda_ascendente(self, repo):
        repo.registrar("PROY-001", "inicial")
        repo.registrar("PROY-001", "r2", tipo=TipoEntradaBrief.RESPUESTA_CLIENTE)
        repo.registrar("PROY-001", "r3", tipo=TipoEntradaBrief.RESPUESTA_CLIENTE)
        entradas = repo.listar("PROY-001")
        assert [e.ronda for e in entradas] == [1, 2, 3]
        assert [e.texto for e in entradas] == ["inicial", "r2", "r3"]


class TestBriefInicial:
    def test_devuelve_none_si_no_existe(self, repo):
        assert repo.brief_inicial("PROY-999") is None

    def test_devuelve_el_inicial(self, repo):
        repo.registrar("PROY-001", _TEXTO_CALCULADORA)
        e = repo.brief_inicial("PROY-001")
        assert e is not None
        assert e.tipo == TipoEntradaBrief.INICIAL
        assert e.texto == _TEXTO_CALCULADORA

    def test_ignora_respuestas_posteriores(self, repo):
        repo.registrar("PROY-001", "brief inicial")
        repo.registrar("PROY-001", "una respuesta", tipo=TipoEntradaBrief.RESPUESTA_CLIENTE)
        e = repo.brief_inicial("PROY-001")
        assert e.texto == "brief inicial"

    def test_es_consultable_como_fuente_primaria_en_cualquier_momento(self, repo):
        """No depende de recordar el prompt original: es una consulta directa
        y determinista, disponible para cualquier llamador futuro.
        """
        repo.registrar("PROY-001", _TEXTO_CALCULADORA)
        primera = repo.brief_inicial("PROY-001")
        segunda = repo.brief_inicial("PROY-001")
        assert primera == segunda


class TestAppendOnly:
    def test_no_expone_actualizar_ni_eliminar(self, repo):
        assert not hasattr(repo, "actualizar")
        assert not hasattr(repo, "eliminar")
        assert not hasattr(repo, "borrar")
