"""TF-0026 — Checklist de coordinación de PROJECT_STATE (versionado).

`campos_esperados(version)` es el conjunto CERRADO y deliberadamente pequeño
de campos que el Orquestador necesita para calcular cobertura/completitud/
avance por dimensión (`src.proyectos.salud`). No intenta modelar el trabajo
completo de ninguna disciplina — eso vive en su futuro `*_STATE` — por eso es
agnóstico al tipo de proyecto: sirve igual para "una calculadora" que para un
SaaS (la mayoría de los campos simplemente se marcarán `not_applicable`).

Versionado (decisión cerrada del checkpoint TF-0026): cada versión publicada
en `_CHECKLISTS` queda CONGELADA para siempre. Evolucionar el checklist es
agregar una clave nueva (p. ej. `"1.1"`), nunca editar `"1.0"`.
`ExpedienteProyecto.checklist_version` fija con qué versión fue creado un
expediente, y `calcular_salud()` siempre resuelve contra ESA versión — nunca
contra `CHECKLIST_VERSION_ACTUAL` directamente. Así, publicar un checklist
nuevo no cambia silenciosamente el porcentaje histórico de un proyecto ya
creado. Migrar un expediente de una versión a otra (recalcular qué campos
nuevos quedan pendientes) es una operación explícita que TF-0026 no
implementa: el seam es esta estructura versionada.

Sin dependencias externas. No importa Flask, `src.agentes`, `src.ai` ni red.
"""
from __future__ import annotations

from src.proyectos.errores import VersionChecklistNoEncontrada

__all__ = ["CHECKLIST_VERSION_ACTUAL", "DISCIPLINAS", "campos_esperados"]

CHECKLIST_VERSION_ACTUAL = "1.0"

# Orden estable de las 7 disciplinas de PROJECT_STATE (mapea 1:1 a
# ARCHITECTURE_STATE, UX_STATE, ANALYSIS_STATE, IMPLEMENTATION_STATE,
# TEST_STATE, SECURITY_STATE, DOCUMENTATION_STATE del diagrama aprobado).
DISCIPLINAS: tuple[str, ...] = (
    "analisis", "ux", "arquitectura", "implementacion",
    "testing", "seguridad", "documentacion",
)

_CHECKLISTS: dict[str, dict[str, tuple[str, ...]]] = {
    "1.0": {
        "_raiz": (
            "identidad", "tipo_proyecto", "objetivo", "usuarios",
            "stack_declarado", "contexto_negocio",
        ),
        "analisis": (
            "requisitos_funcionales", "requisitos_no_funcionales",
            "restricciones", "criterios_aceptacion",
        ),
        "ux": (
            "usuarios_objetivo", "flujos_clave",
            "referencias_visuales", "accesibilidad",
        ),
        "arquitectura": (
            "componentes_principales", "decision_stack",
            "integraciones_externas", "modelo_datos_alto_nivel",
        ),
        "implementacion": (
            "estructura_codigo", "convenciones", "dependencias_clave",
        ),
        "testing": (
            "estrategia_pruebas", "cobertura_actual", "entornos_prueba",
        ),
        "seguridad": (
            "autenticacion", "datos_sensibles", "superficie_expuesta",
        ),
        "documentacion": (
            "readme", "adrs", "guia_arranque",
        ),
    },
}


def campos_esperados(version: str) -> dict[str, tuple[str, ...]]:
    """Checklist de coordinación (`{dimension: (campo, ...)}`) para `version`.

    Lanza `VersionChecklistNoEncontrada` si `version` no está registrada.

    Devuelve una **copia nueva** del diccionario (los valores siguen siendo
    `tuple`, ya inmutables): modificar el `dict` retornado no debe poder
    tocar `_CHECKLISTS`, que es el estado congelado real.
    """
    try:
        checklist = _CHECKLISTS[version]
    except KeyError:
        raise VersionChecklistNoEncontrada(
            f"versión de checklist no registrada: {version!r}; "
            f"disponibles: {list(_CHECKLISTS)}"
        ) from None
    return {dimension: tuple(campos) for dimension, campos in checklist.items()}
