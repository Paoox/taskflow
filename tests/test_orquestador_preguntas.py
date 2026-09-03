"""TF-0027 — Pruebas de `src.orquestador.preguntas` (derivadas, sin estado propio)."""
from src.orquestador.preguntas import preguntas_pendientes
from src.proyectos.checklist import campos_esperados
from src.proyectos.estado import Dato, EstadoDato, ExpedienteProyecto, NivelConfianza, OrigenDato

_TS = "2026-09-02 10:00:00"
_RAIZ = campos_esperados("1.0")["_raiz"]


def _dato(estado):
    return Dato(valor="v", estado=estado, origen=OrigenDato.AGENT,
                confianza=NivelConfianza.ALTA, actualizado_en=_TS)


def test_expediente_vacio_genera_una_pregunta_por_campo_raiz():
    e = ExpedienteProyecto()
    preguntas = preguntas_pendientes(e)
    assert [p.campo for p in preguntas] == list(_RAIZ)
    assert all(p.motivo == "nunca_investigado" for p in preguntas)
    assert all(p.pregunta for p in preguntas)  # ninguna plantilla vacía


def test_confirmed_discovered_not_applicable_no_generan_pregunta():
    e = ExpedienteProyecto()
    e.descubrimiento = {
        _RAIZ[0]: _dato(EstadoDato.CONFIRMED),
        _RAIZ[1]: _dato(EstadoDato.DISCOVERED),
        _RAIZ[2]: _dato(EstadoDato.NOT_APPLICABLE),
    }
    preguntas = preguntas_pendientes(e)
    campos_con_pregunta = {p.campo for p in preguntas}
    assert _RAIZ[0] not in campos_con_pregunta
    assert _RAIZ[1] not in campos_con_pregunta
    assert _RAIZ[2] not in campos_con_pregunta


def test_unknown_genera_pregunta_sigue_desconocido():
    e = ExpedienteProyecto()
    e.descubrimiento = {_RAIZ[0]: _dato(EstadoDato.UNKNOWN)}
    preguntas = {p.campo: p.motivo for p in preguntas_pendientes(e)}
    assert preguntas[_RAIZ[0]] == "sigue_desconocido"


def test_not_found_genera_pregunta_confirmar_no_encontrado():
    e = ExpedienteProyecto()
    e.descubrimiento = {_RAIZ[0]: _dato(EstadoDato.NOT_FOUND)}
    preguntas = {p.campo: p.motivo for p in preguntas_pendientes(e)}
    assert preguntas[_RAIZ[0]] == "confirmar_no_encontrado"


def test_inferred_genera_pregunta_confirmar_inferencia():
    e = ExpedienteProyecto()
    e.descubrimiento = {_RAIZ[0]: _dato(EstadoDato.INFERRED)}
    preguntas = {p.campo: p.motivo for p in preguntas_pendientes(e)}
    assert preguntas[_RAIZ[0]] == "confirmar_inferencia"


def test_incomplete_genera_pregunta_completar_informacion():
    e = ExpedienteProyecto()
    e.descubrimiento = {_RAIZ[0]: _dato(EstadoDato.INCOMPLETE)}
    preguntas = {p.campo: p.motivo for p in preguntas_pendientes(e)}
    assert preguntas[_RAIZ[0]] == "completar_informacion"


def test_pending_decision_no_genera_pregunta():
    e = ExpedienteProyecto()
    e.descubrimiento = {_RAIZ[0]: _dato(EstadoDato.PENDING_DECISION)}
    campos_con_pregunta = {p.campo for p in preguntas_pendientes(e)}
    assert _RAIZ[0] not in campos_con_pregunta


def test_mezcla_completa_una_de_cada_categoria():
    """Los 6 campos raíz, uno con cada estado relevante: exactamente 4
    generan pregunta (unknown, not_found, inferred, incomplete), 1 no genera
    nada (confirmed) y 1 no genera pregunta pero tampoco cuenta aquí
    (pending_decision, se prueba aparte en test_orquestador.py que produce
    BLOQUEADO)."""
    e = ExpedienteProyecto()
    e.descubrimiento = {
        _RAIZ[0]: _dato(EstadoDato.CONFIRMED),
        _RAIZ[1]: _dato(EstadoDato.UNKNOWN),
        _RAIZ[2]: _dato(EstadoDato.NOT_FOUND),
        _RAIZ[3]: _dato(EstadoDato.INFERRED),
        _RAIZ[4]: _dato(EstadoDato.INCOMPLETE),
        _RAIZ[5]: _dato(EstadoDato.PENDING_DECISION),
    }
    motivos = {p.campo: p.motivo for p in preguntas_pendientes(e)}
    assert set(motivos) == {_RAIZ[1], _RAIZ[2], _RAIZ[3], _RAIZ[4]}
    assert motivos[_RAIZ[1]] == "sigue_desconocido"
    assert motivos[_RAIZ[2]] == "confirmar_no_encontrado"
    assert motivos[_RAIZ[3]] == "confirmar_inferencia"
    assert motivos[_RAIZ[4]] == "completar_informacion"


def test_no_muta_el_expediente():
    e = ExpedienteProyecto()
    antes = dict(e.descubrimiento)
    preguntas_pendientes(e)
    assert e.descubrimiento == antes
