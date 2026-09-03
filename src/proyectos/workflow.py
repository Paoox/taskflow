"""TF-0026 — Workflow oficial de Taskflow: orden de etapas + siguiente agente.

Pieza independiente y reutilizable a propósito: `src.proyectos.salud` NO
implementa su propio orden de etapas, delega aquí con una sola llamada
(`determinar_siguiente_agente`). El futuro Orquestador podrá usar esta misma
función directamente, sin pasar por `calcular_salud()`.

Este módulo NO importa `src.proyectos.salud` (evita el ciclo: es `salud.py`
quien importa `workflow.py`). Los tipos de `salud.py` usados solo para las
anotaciones se importan bajo `TYPE_CHECKING`.

Sin dependencias nuevas. No importa Flask, `src.database`, `src.agentes` ni
`src.ai`.
"""
from __future__ import annotations

from typing import TYPE_CHECKING

from src.proyectos.constantes import UMBRAL_AVANCE_LISTO
from src.proyectos.estado import AplicabilidadDisciplina, ResumenDisciplina

if TYPE_CHECKING:  # pragma: no cover - solo para tipado estático
    from src.proyectos.salud import Hallazgo, MetricaDimension

__all__ = ["ETAPAS_WORKFLOW", "DEPENDENCIA_ETAPA", "determinar_siguiente_agente"]

# Flujo oficial aprobado (checkpoint TF-0026). Orden fijo: no se deriva de
# nada más, y `calcular_salud()` no puede reordenarlo.
ETAPAS_WORKFLOW: tuple[str, ...] = (
    "ORQUESTADOR", "ARQUITECTO", "UX_UI", "ANALISTA",
    "DEVELOPER", "TESTER", "SECURITY", "DOCUMENTACION", "CIERRE",
)

# Etapa -> clave de disciplina de la que depende. "_raiz" = descubrimiento
# (campos raíz del expediente); None = CIERRE, etapa terminal sin dependencia.
DEPENDENCIA_ETAPA: dict[str, str | None] = {
    "ORQUESTADOR": "_raiz",
    "ARQUITECTO": "arquitectura",
    "UX_UI": "ux",
    "ANALISTA": "analisis",
    "DEVELOPER": "implementacion",
    "TESTER": "testing",
    "SECURITY": "seguridad",
    "DOCUMENTACION": "documentacion",
    "CIERRE": None,
}


def _etapa_lista(
    dep: str,
    disciplinas: dict[str, ResumenDisciplina],
    metrica: "MetricaDimension",
    bloqueada: bool,
) -> bool:
    """True si la etapa que depende de `dep` puede darse por superada.

    * `dep == "_raiz"` (ORQUESTADOR): siempre exige `avance >= umbral` y
      ausencia de blockers propios.
    * disciplina `NOT_APPLICABLE`: lista, **independientemente de su
      avance** — una disciplina correctamente excluida del proyecto no debe
      bloquear el recorrido solo porque no tiene campos investigados.
    * disciplina `UNKNOWN`: nunca lista (ya genera blocker en
      `salud._blockers_y_warnings`; se deja explícito aquí para que el
      comportamiento no dependa implícitamente de esa otra regla).
    * `REQUIRED` / `CONDITIONAL`: lista solo si `avance >= umbral` y sin
      blockers propios (no se convierte automáticamente en `NOT_APPLICABLE`).
    """
    if dep == "_raiz":
        return not bloqueada and metrica.avance >= UMBRAL_AVANCE_LISTO

    aplicabilidad = disciplinas[dep].aplicabilidad
    if aplicabilidad == AplicabilidadDisciplina.NOT_APPLICABLE:
        return True
    if aplicabilidad == AplicabilidadDisciplina.UNKNOWN:
        return False
    return not bloqueada and metrica.avance >= UMBRAL_AVANCE_LISTO


def determinar_siguiente_agente(
    disciplinas: dict[str, ResumenDisciplina],
    descubrimiento: "MetricaDimension",
    por_disciplina: dict[str, "MetricaDimension"],
    blockers: list["Hallazgo"],
) -> str:
    """Primera etapa de `ETAPAS_WORKFLOW` (en orden) que no está superada.

    Devuelve `"CIERRE"` si todas las etapas previas están listas.
    """
    bloqueadas = {h.disciplina for h in blockers if h.disciplina}
    raiz_bloqueada = any(h.disciplina is None for h in blockers)

    # CIERRE (última etapa, DEPENDENCIA_ETAPA=None) se excluye del recorrido a
    # propósito: es el valor de retorno cuando ninguna etapa anterior detiene
    # el recorrido, no una etapa con dependencia propia que evaluar.
    for etapa in ETAPAS_WORKFLOW[:-1]:
        dep = DEPENDENCIA_ETAPA[etapa]
        metrica = descubrimiento if dep == "_raiz" else por_disciplina[dep]
        bloqueada = raiz_bloqueada if dep == "_raiz" else dep in bloqueadas
        if not _etapa_lista(dep, disciplinas, metrica, bloqueada):
            return etapa
    return ETAPAS_WORKFLOW[-1]
