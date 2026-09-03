"""TF-0026 — Pruebas de `src.proyectos.workflow` (orden de etapas + next_agent).

`determinar_siguiente_agente` se testea aislado, sin pasar por `calcular_salud`.
"""
from src.proyectos.estado import AplicabilidadDisciplina, ResumenDisciplina
from src.proyectos.salud import Hallazgo, MetricaDimension
from src.proyectos.workflow import DEPENDENCIA_ETAPA, ETAPAS_WORKFLOW, determinar_siguiente_agente

_LISTO = MetricaDimension(cobertura=1.0, completitud=1.0, avance=1.0,
                           campos_investigados=1, campos_esperados_total=1)
_NO_LISTO = MetricaDimension(cobertura=0.0, completitud=0.0, avance=0.0,
                              campos_investigados=0, campos_esperados_total=1)


def test_orden_exacto_de_las_etapas():
    assert ETAPAS_WORKFLOW == (
        "ORQUESTADOR", "ARQUITECTO", "UX_UI", "ANALISTA",
        "DEVELOPER", "TESTER", "SECURITY", "DOCUMENTACION", "CIERRE",
    )


def test_dependencia_etapa_cubre_todas_las_etapas():
    assert set(DEPENDENCIA_ETAPA) == set(ETAPAS_WORKFLOW)
    assert DEPENDENCIA_ETAPA["CIERRE"] is None


def _disciplinas_required(*, excepto_not_applicable=()):
    disciplinas = {}
    for k in ("arquitectura", "ux", "analisis", "implementacion", "testing", "seguridad", "documentacion"):
        ap = AplicabilidadDisciplina.NOT_APPLICABLE if k in excepto_not_applicable else AplicabilidadDisciplina.REQUIRED
        disciplinas[k] = ResumenDisciplina(aplicabilidad=ap)
    return disciplinas


def _metricas_todas_listas():
    return {
        "arquitectura": _LISTO, "ux": _LISTO, "analisis": _LISTO,
        "implementacion": _LISTO, "testing": _LISTO, "seguridad": _LISTO,
        "documentacion": _LISTO,
    }


def test_todo_listo_devuelve_cierre():
    disciplinas = _disciplinas_required()
    resultado = determinar_siguiente_agente(disciplinas, _LISTO, _metricas_todas_listas(), [])
    assert resultado == "CIERRE"


def test_una_etapa_bloqueada_a_la_vez():
    """Por cada etapa (salvo CIERRE), dejarla como la única no lista debe
    devolver exactamente esa etapa, sin importar el estado de las demás.
    """
    disciplinas = _disciplinas_required()
    for etapa in ETAPAS_WORKFLOW[:-1]:
        dep = DEPENDENCIA_ETAPA[etapa]
        metricas = _metricas_todas_listas()
        descubrimiento = _LISTO
        if dep == "_raiz":
            descubrimiento = _NO_LISTO
        else:
            metricas[dep] = _NO_LISTO
        resultado = determinar_siguiente_agente(disciplinas, descubrimiento, metricas, [])
        assert resultado == etapa, f"esperaba {etapa}, obtuve {resultado}"


def test_blocker_en_disciplina_intermedia_detiene_ahi_aunque_avance_alcance():
    """Aunque la métrica numérica de 'ux' esté en el umbral, un blocker propio
    debe seguir deteniendo el recorrido en esa etapa.
    """
    disciplinas = _disciplinas_required()
    metricas = _metricas_todas_listas()
    blockers = [Hallazgo("ux", "algo pendiente en ux")]
    resultado = determinar_siguiente_agente(disciplinas, _LISTO, metricas, blockers)
    assert resultado == "UX_UI"


def test_disciplina_not_applicable_se_considera_lista_pese_a_avance_cero():
    disciplinas = _disciplinas_required(excepto_not_applicable=("ux",))
    metricas = _metricas_todas_listas()
    metricas["ux"] = _NO_LISTO  # avance 0, pero la disciplina es NOT_APPLICABLE
    resultado = determinar_siguiente_agente(disciplinas, _LISTO, metricas, [])
    assert resultado == "CIERRE"


def test_disciplina_unknown_nunca_se_considera_lista():
    disciplinas = _disciplinas_required()
    disciplinas["arquitectura"] = ResumenDisciplina(aplicabilidad=AplicabilidadDisciplina.UNKNOWN)
    metricas = _metricas_todas_listas()  # avance "listo", pero aplicabilidad sin resolver
    resultado = determinar_siguiente_agente(disciplinas, _LISTO, metricas, [])
    assert resultado == "ARQUITECTO"


def test_raiz_bloqueada_detiene_en_orquestador_sin_mirar_el_resto():
    disciplinas = _disciplinas_required()
    metricas = _metricas_todas_listas()
    resultado = determinar_siguiente_agente(disciplinas, _NO_LISTO, metricas, [])
    assert resultado == "ORQUESTADOR"
