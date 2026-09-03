"""TF-0027 — Preguntas pendientes: derivadas de `ExpedienteProyecto`, sin
estado propio.

`preguntas_pendientes()` cubre exactamente los estados de `EstadoDato` que
`PESO_ESTADO_COMPLETITUD` (TF-0026) pondera por debajo de 1.0 en la raíz, más
el caso "ausente" — es lo que garantiza el invariante del checkpoint de
diseño revisado: si el avance de la raíz es menor a 1.0 y no hay ningún
`pending_decision`, esta función nunca devuelve una lista vacía.

`pending_decision` NO genera pregunta aquí a propósito: genera `BLOQUEADO`
en `orquestador.py` (requiere una decisión humana explícita, no una simple
respuesta factual).

Sin dependencias nuevas. No importa Flask, `src.database`, `src.app`, `src.ai`
ni `src.agentes`.
"""
from __future__ import annotations

from src.orquestador.contrato import PreguntaPendiente
from src.proyectos.checklist import campos_esperados
from src.proyectos.estado import EstadoDato, ExpedienteProyecto

__all__ = ["preguntas_pendientes"]

_MOTIVO_AUSENTE = "nunca_investigado"

# Un motivo por cada EstadoDato con peso < 1.0 en PESO_ESTADO_COMPLETITUD,
# salvo PENDING_DECISION (genera BLOQUEADO, no pregunta).
_MOTIVO_POR_ESTADO = {
    EstadoDato.UNKNOWN: "sigue_desconocido",
    EstadoDato.NOT_FOUND: "confirmar_no_encontrado",
    EstadoDato.INFERRED: "confirmar_inferencia",
    EstadoDato.INCOMPLETE: "completar_informacion",
}

# Plantillas deterministas por campo raíz (`checklist._CHECKLISTS["1.0"]["_raiz"]`).
# Un campo fuera de esta tabla (checklist futuro con más campos) recibe una
# pregunta genérica en vez de fallar.
_PLANTILLAS = {
    "identidad": "¿Cuál es el nombre o identidad del proyecto?",
    "tipo_proyecto": "¿Qué tipo de proyecto es (landing, API, CLI, app móvil, SaaS, etc.)?",
    "objetivo": "¿Cuál es el objetivo principal del proyecto?",
    "usuarios": "¿Quiénes son los usuarios de este proyecto?",
    "stack_declarado": "¿Qué stack tecnológico usa (o usará) el proyecto?",
    "contexto_negocio": "¿Cuál es el contexto de negocio del proyecto?",
}


def _pregunta_para(campo: str, motivo: str) -> PreguntaPendiente:
    texto = _PLANTILLAS.get(campo, f"¿Puedes aportar información sobre '{campo}'?")
    return PreguntaPendiente(campo=campo, pregunta=texto, motivo=motivo)


def preguntas_pendientes(expediente: ExpedienteProyecto) -> list[PreguntaPendiente]:
    """Preguntas derivadas de los campos raíz sin resolver, en orden de
    checklist. No muta `expediente`.
    """
    esperados = campos_esperados(expediente.checklist_version)["_raiz"]
    preguntas: list[PreguntaPendiente] = []
    for campo in esperados:
        dato = expediente.descubrimiento.get(campo)
        if dato is None:
            preguntas.append(_pregunta_para(campo, _MOTIVO_AUSENTE))
            continue
        motivo = _MOTIVO_POR_ESTADO.get(dato.estado)
        if motivo is not None:
            preguntas.append(_pregunta_para(campo, motivo))
    return preguntas
