"""TF-0030 — Discovery nuevo: primer bloque del flujo

    respuestas_formulario -> Discovery -> Expediente Maestro

Paquete nuevo e independiente del Orquestador viejo (`src.orquestador`, que
sigue alimentando PROJECT_STATE sin cambios) y de `src.proyectos`. No
importa ninguno de los dos, ni `src.repositorios.expedientes`
(`RepositorioExpedientes`, exclusivo de PROJECT_STATE). Tampoco modifica
`src.formulario`: solo reutiliza su función pública `siguiente_pregunta()`.

Contenido:

* `discovery.py` — punto de entrada `ejecutar_discovery(codigo, cliente)`.
* `interpretacion_directa.py` — mapeo determinista (sin LLM) de las
  respuestas cerradas con significado completo por sí solas.
* `interpretacion_llm.py` — construcción del contexto y validación de la
  salida JSON Lines del agente `InterpreteFormulario`
  (`src.agentes.interprete_formulario`).

Ver `docs/tickets/TF-0030.md` para el alcance aprobado (qué tipos de
entidad produce este primer bloque y cuáles quedan fuera).
"""
