"""TF-0026 — Pruebas de PROJECT_HEALTH (`src.proyectos.salud`).

Cubre las fórmulas de cobertura/completitud/avance, la corrección de pesos
(`not_found` != resuelto, `not_applicable` excluido), blockers/warnings,
readiness y su delegación a `workflow.determinar_siguiente_agente`.
"""
import pytest

from src.proyectos.checklist import DISCIPLINAS
from src.proyectos.estado import (
    AplicabilidadDisciplina,
    Dato,
    EstadoDato,
    ExpedienteProyecto,
    NivelConfianza,
    OrigenDato,
    Readiness,
)
from src.proyectos.salud import (
    PESO_APLICABILIDAD_CONDITIONAL,
    UMBRAL_AVANCE_LISTO,
    Hallazgo,
    MetricaDimension,
    _determinar_readiness,
    _metrica,
    calcular_salud,
)

_TS = "2026-09-02 10:00:00"


def _dato(estado, confianza=NivelConfianza.ALTA, origen=OrigenDato.CODE, valor="v"):
    return Dato(valor=valor, estado=estado, origen=origen, confianza=confianza, actualizado_en=_TS)


# --- Fórmula de cobertura / completitud / avance (aisladas, sin SQLite) -----

class TestMetrica:
    def test_nada_investigado(self):
        m = _metrica(("a", "b"), {})
        assert m == MetricaDimension(cobertura=0.0, completitud=0.0, avance=0.0,
                                      campos_investigados=0, campos_esperados_total=2)

    def test_todo_not_applicable_completitud_100(self):
        datos = {
            "a": _dato(EstadoDato.NOT_APPLICABLE),
            "b": _dato(EstadoDato.NOT_APPLICABLE),
        }
        m = _metrica(("a", "b"), datos)
        assert m.cobertura == pytest.approx(1.0)
        assert m.completitud == pytest.approx(1.0)
        assert m.avance == pytest.approx(1.0)

    def test_mezcla_realista(self):
        # 5 campos esperados; 4 investigados (uno queda sin tocar).
        datos = {
            "a": _dato(EstadoDato.CONFIRMED),
            "b": _dato(EstadoDato.INFERRED),
            "c": _dato(EstadoDato.UNKNOWN),
            "d": _dato(EstadoDato.NOT_FOUND),
        }
        m = _metrica(("a", "b", "c", "d", "e"), datos)
        assert m.campos_investigados == 4
        assert m.campos_esperados_total == 5
        assert m.cobertura == pytest.approx(4 / 5)
        assert m.completitud == pytest.approx((1.0 + 0.5 + 0.0 + 0.0) / 4)
        assert m.avance == pytest.approx((4 / 5) * 0.375)

    def test_not_applicable_se_excluye_solo_de_completitud_no_de_cobertura(self):
        # 3 esperados; a=confirmed, b=not_applicable, c sin investigar.
        datos = {"a": _dato(EstadoDato.CONFIRMED), "b": _dato(EstadoDato.NOT_APPLICABLE)}
        m = _metrica(("a", "b", "c"), datos)
        assert m.cobertura == pytest.approx(2 / 3)      # b SÍ cuenta como investigado
        assert m.completitud == pytest.approx(1.0)      # pero b no entra en la calidad
        assert m.avance == pytest.approx(2 / 3)

    def test_not_found_pesa_0_no_como_resuelto(self):
        m = _metrica(("a",), {"a": _dato(EstadoDato.NOT_FOUND)})
        assert m.completitud == pytest.approx(0.0)   # NO 1.0: "no encontrado" != "resuelto"

    def test_checklist_vacio_no_divide_por_cero(self):
        m = _metrica((), {})
        assert m == MetricaDimension(0.0, 0.0, 0.0, 0, 0)


# --- Helpers para construir un ExpedienteProyecto controlado ---------------

def _expediente_vacio():
    return ExpedienteProyecto(nombre="Demo")


def _confirmar_todos(campos, confianza=NivelConfianza.ALTA):
    return {c: _dato(EstadoDato.CONFIRMED, confianza=confianza) for c in campos}


def _expediente_todo_resuelto():
    """Expediente con todas las dimensiones REQUIRED y 100% confirmadas."""
    from src.proyectos.checklist import campos_esperados
    esperados = campos_esperados("1.0")
    e = ExpedienteProyecto(nombre="Demo")
    e.descubrimiento = _confirmar_todos(esperados["_raiz"])
    for k in DISCIPLINAS:
        e.disciplinas[k].aplicabilidad = AplicabilidadDisciplina.REQUIRED
        e.disciplinas[k].datos = _confirmar_todos(esperados[k])
    return e


# --- Blockers / warnings / readiness ---------------------------------------

class TestBlockersYWarnings:
    def test_expediente_vacio_bloqueado_por_descubrimiento_y_disciplinas_unknown(self):
        salud = calcular_salud(_expediente_vacio())
        assert salud.readiness == Readiness.BLOCKED
        assert any("Descubrimiento" in b for b in salud.blockers)
        assert sum("sin determinar" in b for b in salud.blockers) == len(DISCIPLINAS)

    def test_pending_decision_bloquea(self):
        e = _expediente_todo_resuelto()
        e.disciplinas["analisis"].datos["restricciones"] = _dato(EstadoDato.PENDING_DECISION)
        salud = calcular_salud(e)
        assert salud.readiness == Readiness.BLOCKED
        assert any("Decisión pendiente en 'analisis.restricciones'" in b for b in salud.blockers)

    def test_not_found_genera_warning_no_blocker(self):
        e = _expediente_todo_resuelto()
        e.descubrimiento["contexto_negocio"] = _dato(EstadoDato.NOT_FOUND)
        salud = calcular_salud(e)
        assert salud.blockers == []
        assert any("no encontrado" in w for w in salud.warnings)
        assert salud.readiness == Readiness.READY_WITH_WARNINGS

    def test_confianza_baja_en_confirmado_genera_warning(self):
        e = _expediente_todo_resuelto()
        e.disciplinas["seguridad"].datos["autenticacion"] = _dato(
            EstadoDato.CONFIRMED, confianza=NivelConfianza.BAJA
        )
        salud = calcular_salud(e)
        assert salud.blockers == []
        assert any("confianza baja" in w for w in salud.warnings)

    def test_conditional_sin_investigar_genera_warning_no_blocker(self):
        e = _expediente_todo_resuelto()
        e.disciplinas["documentacion"].aplicabilidad = AplicabilidadDisciplina.CONDITIONAL
        e.disciplinas["documentacion"].datos = {}
        salud = calcular_salud(e)
        assert not any("documentacion" in b and "requerida" in b for b in salud.blockers)
        assert any("condicional de 'documentacion'" in w for w in salud.warnings)

    def test_required_con_avance_bajo_bloquea(self):
        e = _expediente_todo_resuelto()
        e.disciplinas["testing"].datos = {}  # nada investigado -> avance 0
        salud = calcular_salud(e)
        assert salud.readiness == Readiness.BLOCKED
        assert any("Disciplina 'testing' requerida" in b for b in salud.blockers)

    def test_todo_resuelto_es_ready_sin_warnings(self):
        salud = calcular_salud(_expediente_todo_resuelto())
        assert salud.blockers == []
        assert salud.warnings == []
        assert salud.readiness == Readiness.READY
        assert salud.estado_general == pytest.approx(1.0)
        assert salud.next_agent == "CIERRE"


# --- not_applicable: excluida de estado_general, pero no de la cobertura ---

class TestNotApplicableExcluidaDeEstadoGeneral:
    def test_unknown_pondera_not_applicable_no(self):
        """Compara estado_general dejando una disciplina en UNKNOWN vs
        NOT_APPLICABLE, con todo lo demás idéntico: UNKNOWN debe pesar en el
        denominador (más "castigo"); NOT_APPLICABLE debe quedar excluida.
        """
        base = _expediente_vacio()
        from src.proyectos.checklist import campos_esperados
        base.descubrimiento = _confirmar_todos(campos_esperados("1.0")["_raiz"])
        base.disciplinas["analisis"].aplicabilidad = AplicabilidadDisciplina.REQUIRED
        base.disciplinas["analisis"].datos = _confirmar_todos(campos_esperados("1.0")["analisis"])
        # Las otras 6 disciplinas quedan en UNKNOWN (default), avance=0.

        salud_unknown = calcular_salud(base)
        # numerador = 1 (raiz) + 1 (analisis) + 0*6 = 2 ; denominador = 1+1+6 = 8
        assert salud_unknown.estado_general == pytest.approx(2 / 8)

        base.disciplinas["ux"].aplicabilidad = AplicabilidadDisciplina.NOT_APPLICABLE
        salud_not_applicable = calcular_salud(base)
        # denominador baja a 7 (ux ya no pondera); numerador sigue en 2
        assert salud_not_applicable.estado_general == pytest.approx(2 / 7)
        assert salud_not_applicable.estado_general > salud_unknown.estado_general

    def test_conditional_pondera_la_mitad(self):
        assert PESO_APLICABILIDAD_CONDITIONAL == 0.5


# --- _determinar_readiness aislado: borde exacto del umbral -----------------

class TestDeterminarReadinessBorde:
    def test_igual_al_umbral_es_listo(self):
        assert _determinar_readiness(UMBRAL_AVANCE_LISTO, [], []) == Readiness.READY

    def test_justo_debajo_del_umbral_es_incompleto(self):
        assert _determinar_readiness(UMBRAL_AVANCE_LISTO - 0.01, [], []) == Readiness.INCOMPLETE

    def test_blocker_manda_sobre_todo(self):
        assert _determinar_readiness(1.0, [Hallazgo(None, "x")], []) == Readiness.BLOCKED

    def test_umbral_ok_con_warning_es_ready_with_warnings(self):
        assert _determinar_readiness(1.0, [], [Hallazgo(None, "x")]) == Readiness.READY_WITH_WARNINGS


# --- next_agent respeta el workflow oficial (delegado, no reimplementado) --

class TestNextAgentDelegaEnWorkflow:
    def test_disciplina_not_applicable_no_bloquea_el_recorrido(self):
        e = _expediente_todo_resuelto()
        e.disciplinas["ux"].aplicabilidad = AplicabilidadDisciplina.NOT_APPLICABLE
        e.disciplinas["ux"].datos = {}  # sin investigar: solo válido porque es NOT_APPLICABLE
        salud = calcular_salud(e)
        assert salud.next_agent == "CIERRE"

    def test_disciplina_required_sin_avance_detiene_en_su_etapa(self):
        e = _expediente_todo_resuelto()
        e.disciplinas["ux"].datos = {}
        salud = calcular_salud(e)
        assert salud.next_agent == "UX_UI"

    def test_checklist_version_queda_registrada_en_la_salud(self):
        salud = calcular_salud(_expediente_todo_resuelto())
        assert salud.checklist_version == "1.0"


# --- Round-trip / serialización de los tipos de salud -----------------------

class TestSerializacionSalud:
    def test_salud_round_trip(self):
        salud = calcular_salud(_expediente_todo_resuelto())
        from src.proyectos.salud import SaludProyecto
        assert SaludProyecto.from_dict(salud.to_dict()) == salud

    def test_salud_json_serializable_sin_default(self):
        import json
        salud = calcular_salud(_expediente_todo_resuelto())
        json.dumps(salud.to_dict())

    def test_metrica_dimension_to_dict_from_dict_directo(self):
        # Contrato explícito de MetricaDimension (checkpoint TF-0026): debe
        # tener to_dict/from_dict propios, cubiertos por una llamada directa
        # y no solo por la recursión de `dataclasses.asdict` en el padre.
        m = MetricaDimension(cobertura=0.5, completitud=0.8, avance=0.4,
                              campos_investigados=2, campos_esperados_total=4)
        d = m.to_dict()
        assert d == {
            "cobertura": 0.5, "completitud": 0.8, "avance": 0.4,
            "campos_investigados": 2, "campos_esperados_total": 4,
        }
        assert MetricaDimension.from_dict(d) == m
