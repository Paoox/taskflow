"""TF-0007 — Pruebas unitarias de validar_datos_tarea (sin Flask ni base de datos)."""
import pytest

from src.validaciones import (
    DESCRIPCION_MAX,
    TITULO_MAX,
    validar_datos_tarea,
)

IDS = {0, 1, 2}


def _form(**kw):
    base = {
        "titulo": "Tarea válida",
        "descripcion": "algo",
        "fecha_limite": "2026-09-01",
        "prioridad": "Alta",
        "proyecto_id": "0",
    }
    base.update(kw)
    # Simula campos ausentes: valor None -> se elimina la clave.
    return {k: v for k, v in base.items() if v is not None}


class TestCasoValido:
    def test_sin_errores_y_datos_saneados(self):
        datos, errores = validar_datos_tarea(_form(), IDS)
        assert errores == {}
        assert datos == {
            "titulo": "Tarea válida",
            "descripcion": "algo",
            "fecha_limite": "2026-09-01",
            "prioridad": "Alta",
            "proyecto_id": 0,
        }

    def test_titulo_y_descripcion_se_hacen_strip(self):
        datos, errores = validar_datos_tarea(
            _form(titulo="  hola  ", descripcion="  d  "), IDS)
        assert errores == {}
        assert datos["titulo"] == "hola"
        assert datos["descripcion"] == "d"

    def test_fecha_limite_ausente_queda_none(self):
        datos, errores = validar_datos_tarea(_form(fecha_limite=None), IDS)
        assert errores == {}
        assert datos["fecha_limite"] is None

    def test_fecha_limite_vacia_queda_none(self):
        datos, errores = validar_datos_tarea(_form(fecha_limite="   "), IDS)
        assert errores == {}
        assert datos["fecha_limite"] is None

    @pytest.mark.parametrize("prio", ["Alta", "Media", "Baja"])
    def test_prioridades_validas(self, prio):
        _, errores = validar_datos_tarea(_form(prioridad=prio), IDS)
        assert "prioridad" not in errores

    def test_proyecto_id_se_devuelve_como_int(self):
        datos, errores = validar_datos_tarea(_form(proyecto_id="2"), IDS)
        assert errores == {}
        assert datos["proyecto_id"] == 2


class TestTitulo:
    @pytest.mark.parametrize("valor", [None, "", "   "])
    def test_obligatorio(self, valor):
        _, errores = validar_datos_tarea(_form(titulo=valor), IDS)
        assert "titulo" in errores

    def test_longitud_maxima(self):
        _, errores = validar_datos_tarea(_form(titulo="x" * (TITULO_MAX + 1)), IDS)
        assert "titulo" in errores

    def test_longitud_en_el_limite_es_valida(self):
        _, errores = validar_datos_tarea(_form(titulo="x" * TITULO_MAX), IDS)
        assert "titulo" not in errores


class TestDescripcion:
    def test_longitud_maxima(self):
        _, errores = validar_datos_tarea(
            _form(descripcion="x" * (DESCRIPCION_MAX + 1)), IDS)
        assert "descripcion" in errores

    def test_ausente_es_valida(self):
        datos, errores = validar_datos_tarea(_form(descripcion=None), IDS)
        assert "descripcion" not in errores
        assert datos["descripcion"] == ""


class TestFechaLimite:
    @pytest.mark.parametrize("valor", ["ayer", "01/02/2026", "2026-13-40", "20260201", "2026-02"])
    def test_formato_invalido(self, valor):
        _, errores = validar_datos_tarea(_form(fecha_limite=valor), IDS)
        assert "fecha_limite" in errores

    def test_formato_valido(self):
        _, errores = validar_datos_tarea(_form(fecha_limite="2026-01-05"), IDS)
        assert "fecha_limite" not in errores


class TestPrioridad:
    @pytest.mark.parametrize("valor", [None, "", "Urgente", "alta", "MEDIA"])
    def test_fuera_de_catalogo(self, valor):
        _, errores = validar_datos_tarea(_form(prioridad=valor), IDS)
        assert "prioridad" in errores


class TestProyectoId:
    def test_ausente(self):
        _, errores = validar_datos_tarea(_form(proyecto_id=None), IDS)
        assert "proyecto_id" in errores

    @pytest.mark.parametrize("valor", ["abc", "", "  ", "1.5"])
    def test_no_entero(self, valor):
        _, errores = validar_datos_tarea(_form(proyecto_id=valor), IDS)
        assert "proyecto_id" in errores

    def test_entero_pero_inexistente(self):
        _, errores = validar_datos_tarea(_form(proyecto_id="999"), IDS)
        assert "proyecto_id" in errores

    def test_id_cero_valido_cuando_esta_en_el_conjunto(self):
        datos, errores = validar_datos_tarea(_form(proyecto_id="0"), {0})
        assert errores == {}
        assert datos["proyecto_id"] == 0


class TestMultiplesErrores:
    def test_se_acumulan_todos(self):
        _, errores = validar_datos_tarea(
            _form(titulo="", prioridad="X", proyecto_id="abc", fecha_limite="no"),
            IDS,
        )
        assert set(errores) == {"titulo", "prioridad", "proyecto_id", "fecha_limite"}
