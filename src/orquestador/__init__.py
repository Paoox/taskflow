"""TF-0027 — Orquestador: coordinador determinista del descubrimiento raíz.

Consume `ExpedienteProyecto` / `SaludProyecto` / `workflow` de `src.proyectos`
(TF-0026) sin reimplementar ninguna de sus reglas. Coordina; no razona
contenido ni ejecuta Tools directamente (ADR-0001, tabla conceptual): la
investigación real la hace un agente inyectado (`DefinicionAgente`) a través
del runner ya existente (`src.agentes.runner.ejecutar_agente`).

Alcance de TF-0027: solo la dimensión raíz (`descubrimiento`) del expediente
— es la única disciplina que `workflow.DEPENDENCIA_ETAPA["ORQUESTADOR"]`
asigna al Orquestador. No implementa ningún agente de descubrimiento real
(queda para TF-0028) ni invoca a Arquitecto/UX/Analista/etc. (no existen
todavía): solo reporta `next_agent`.
"""
