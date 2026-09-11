"""Formulario / árbol de decisión determinista de entrada al Discovery.

Checkpoint de diseño aprobado (árbol adaptativo, agnóstico al tipo de
proyecto, sin tecnicismos, sin LLM). Responsabilidad única: capturar
pregunta+respuesta y decidir determinísticamente cuál es la siguiente
pregunta — nunca interpreta el contenido de una respuesta ni escribe
ninguna entidad del modelo nuevo (`Requisito`/`Capacidad`/...).

    Formulario -> respuestas_formulario -> Discovery -> Expediente

Este paquete no importa `src.orquestador`, `src.proyectos` ni ningún
proveedor de IA. No conoce Flask ni ninguna ruta — es la lógica pura del
árbol; la superficie web queda para un ticket posterior.
"""
