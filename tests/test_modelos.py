"""TF-0005 — Pruebas de los modelos de dominio (sin base de datos)."""
import re

from src.modelos import Proyecto, Tarea

_TIMESTAMP_RE = re.compile(r"^\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2}$")


class TestProyecto:
    def test_to_dict_devuelve_los_valores_dados(self):
        p = Proyecto(nombre="Web", descripcion="Sitio", id=3, estado="Activo")
        d = p.to_dict()
        assert d["id"] == 3
        assert d["nombre"] == "Web"
        assert d["descripcion"] == "Sitio"
        assert d["estado"] == "Activo"
        assert _TIMESTAMP_RE.match(d["fecha_inicio"])

    def test_valores_por_defecto(self):
        p = Proyecto(nombre="Solo nombre")
        assert p.id is None
        assert p.to_dict()["descripcion"] == ""
        assert p.to_dict()["estado"] == "Activo"

    def test_id_setter(self):
        p = Proyecto(nombre="X")
        p.id = 42
        assert p.id == 42
        assert p.to_dict()["id"] == 42


class TestTarea:
    def _tarea(self, **kw):
        base = dict(titulo="T", fecha_limite="2026-01-01", prioridad="Alta", proyecto_id=0)
        base.update(kw)
        return Tarea(**base)

    def test_estado_por_defecto_es_pendiente(self):
        assert self._tarea()._estado == "Pendiente"

    def test_fecha_creacion_se_autogenera_si_no_se_pasa(self):
        t = self._tarea()
        assert _TIMESTAMP_RE.match(t._fecha_creacion)

    def test_fecha_creacion_se_respeta_si_se_pasa(self):
        t = self._tarea(fecha_creacion="2020-05-05 10:00:00")
        assert t._fecha_creacion == "2020-05-05 10:00:00"

    def test_marcar_como_completada_primera_vez(self):
        t = self._tarea()
        assert t.marcar_como_completada() is True
        assert t._estado == "Completada"

    def test_marcar_como_completada_cuando_ya_lo_esta(self):
        t = self._tarea(estado="Completada")
        assert t.marcar_como_completada() is False
        assert t._estado == "Completada"

    def test_to_dict_incluye_todas_las_claves(self):
        t = self._tarea(descripcion="desc", id=7, estado="Pendiente")
        d = t.to_dict()
        assert d == {
            "id": 7,
            "titulo": "T",
            "descripcion": "desc",
            "fecha_creacion": t._fecha_creacion,
            "fecha_limite": "2026-01-01",
            "prioridad": "Alta",
            "estado": "Pendiente",
            "proyecto_id": 0,
        }

    def test_id_setter(self):
        t = self._tarea()
        t.id = 99
        assert t.id == 99
