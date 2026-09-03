"""TF-0026 — PROJECT_STATE: expediente maestro de un proyecto de software.

Modelo de datos + PROJECT_HEALTH determinista que servirán de fuente de
verdad al futuro Orquestador (`CLAUDE.md` visión de agentes; ADR-0001).

`ExpedienteProyecto` (aquí, en `estado.py`) es distinto y sin relación con
`src.modelos.Proyecto` (el agrupador de tareas del CRUD original): son
dominios independientes que comparten motor de persistencia (SQLite) pero no
esquema ni significado.

Este paquete no contiene Orquestador ni agentes: solo las estructuras de
PROJECT_STATE, el cálculo de PROJECT_HEALTH y el workflow oficial de etapas.
"""
