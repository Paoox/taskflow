"""TF-0026 — Constantes deterministas compartidas por `salud.py` y
`workflow.py`.

Viven en su propio módulo (en vez de en `salud.py`) porque `workflow.py`
también las necesita y `salud.py` importa `workflow.py` para delegar
`next_agent`: si las constantes vivieran en `salud.py`, `workflow.py`
tendría que importarlo de vuelta y se cerraría un ciclo. Ninguno de los dos
módulos importa al otro a través de esta pieza.

Sin dependencias externas.
"""

# Una etapa/disciplina se considera "lista" cuando su `avance >= UMBRAL_AVANCE_LISTO`.
UMBRAL_AVANCE_LISTO = 0.8

# Peso de una disciplina `conditional` en el promedio ponderado de `estado_general`.
PESO_APLICABILIDAD_CONDITIONAL = 0.5
