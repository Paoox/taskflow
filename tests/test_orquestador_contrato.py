"""TF-0027 — Pruebas de contrato de `src.orquestador.contrato`.

Round-trip `to_dict`/`from_dict` + JSON-serializabilidad, mismo criterio que
`tests/test_estado_proyecto.py` / `tests/test_salud_proyecto.py`.
"""
import dataclasses
import json

from src.orquestador.contrato import AccionOrquestador, PreguntaPendiente, ResultadoOrquestador
from src.proyectos.estado import Readiness
from src.proyectos.salud import MetricaDimension, SaludProyecto

_TS = "2026-09-02 10:00:00"


def _nombres(clase):
    return [f.name for f in dataclasses.fields(clase)]


def _metrica():
    return MetricaDimension(cobertura=0.5, completitud=0.8, avance=0.4,
                             campos_investigados=3, campos_esperados_total=6)


def _salud():
    return SaludProyecto(
        descubrimiento=_metrica(),
        por_disciplina={"analisis": _metrica()},
        estado_general=0.42,
        blockers=["algo"],
        warnings=["otra cosa"],
        readiness=Readiness.INCOMPLETE,
        next_agent="ORQUESTADOR",
        checklist_version="1.0",
        calculado_en=_TS,
    )


class TestAccionOrquestador:
    def test_valores_exactos(self):
        assert {a.value for a in AccionOrquestador} == {
            "investigar", "preguntar", "handoff", "bloqueado",
        }


class TestCamposDeLosContratos:
    def test_pregunta_pendiente(self):
        assert _nombres(PreguntaPendiente) == ["campo", "pregunta", "motivo"]

    def test_resultado_orquestador(self):
        assert _nombres(ResultadoOrquestador) == [
            "codigo", "accion", "salud", "preguntas", "problemas", "hallazgos_aplicados",
        ]


class TestRoundTrip:
    def test_pregunta_pendiente(self):
        p = PreguntaPendiente(campo="objetivo", pregunta="¿Cuál es el objetivo?",
                               motivo="nunca_investigado")
        assert PreguntaPendiente.from_dict(p.to_dict()) == p
        json.dumps(p.to_dict())

    def test_resultado_orquestador_completo(self):
        r = ResultadoOrquestador(
            codigo="PROY-001",
            accion=AccionOrquestador.PREGUNTAR,
            salud=_salud(),
            preguntas=[PreguntaPendiente(campo="objetivo", pregunta="¿Cuál es el objetivo?",
                                          motivo="nunca_investigado")],
            problemas=["algo salió mal"],
            hallazgos_aplicados=2,
        )
        reconstruido = ResultadoOrquestador.from_dict(r.to_dict())
        assert reconstruido == r
        json.dumps(r.to_dict())

    def test_resultado_orquestador_valores_por_defecto(self):
        r = ResultadoOrquestador(codigo="PROY-001", accion=AccionOrquestador.HANDOFF, salud=_salud())
        assert ResultadoOrquestador.from_dict(r.to_dict()) == r
