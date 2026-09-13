"""TF-0032 — Motor de reglas de consecuencia sobre el estado acumulado de
un `codigo` (A3).

Cada regla es una función independiente `(codigo, respuestas) ->
Optional[HallazgoConsecuencia]` — ninguna conoce a las demás, ninguna
reacciona al resultado de otra (esa disciplina, y el límite de profundidad
de cadena entre RONDAS sucesivas, viven en `src.discovery.discovery`:
`evaluar_reglas()` aquí solo corre todas las reglas una vez sobre el
estado dado). Agregar una regla nueva no exige tocar ninguna otra, solo
sumarla a `_REGLAS`.

Regla de oro (A2, corrección explícita): una regla solo puede producir un
hecho determinista directo — `tipo="contradiccion"` sobre 2+ respuestas
CERRADAS ya en conflicto lógico necesario, o `tipo="gap"` que solo restate
literalmente una respuesta CERRADA ya dada (TF-0033,
`_regla_sintesis_rechazada`) — nunca una inferencia de negocio que "suena
razonable" pero no es lógicamente forzosa (ej. "el administrador puede
aprobar/rechazar" NO implica "existe aprobación previa a publicar").
Ninguna regla de este módulo hace ese tipo de salto.

Funciones puras: no abren conexión a BD, no llaman a ningún proveedor de
IA — mismo criterio que `interpretacion_directa.py`/`interpretacion_llm.py`.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from src.discovery.catalogo_dominios import CATALOGO_DOMINIOS
from src.formulario.preguntas import OPCION_MONETIZACION_SI, OPCION_NO, OPCION_SI

__all__ = ["HallazgoConsecuencia", "evaluar_reglas", "LIMITE_PROFUNDIDAD_CADENA"]

# Límite duro de saltos de cadena entre rondas sucesivas (ejecutar_discovery
# -> procesar_reapertura -> procesar_reapertura -> ...). Se hace cumplir en
# discovery.py contando Gap/Contradiccion ya existentes para el `codigo` —
# nunca degrada el estado real de un hallazgo al alcanzarse, solo detiene el
# encadenamiento automático (ver discovery.py).
LIMITE_PROFUNDIDAD_CADENA = 3


@dataclass
class HallazgoConsecuencia:
    """Un hallazgo propuesto por una regla determinista, todavía sin
    persistir. `tipo` es `"gap"` o `"contradiccion"` — nunca `"reapertura"`
    (eso es lo que hace `app.py` al ver un hallazgo ya persistido con
    `pregunta_id` resoluble, no un tipo de hallazgo en sí). Para
    `"contradiccion"`, `afirmaciones` ya viene lista para
    `RepositorioContradicciones.crear()`."""

    tipo: str
    dominio: str
    etiqueta: str
    respuestas_relacionadas: list
    motivo: str
    afirmaciones: list = field(default_factory=list)


def _ultima_fila(respuestas: list, pregunta_id: str):
    de_esta = [r for r in respuestas if r.pregunta_id == pregunta_id]
    return de_esta[-1] if de_esta else None


def _regla_suscripcion_sin_dato(codigo: str, respuestas: list):
    """Caso real ya auditado (`DISC-5eb5f65b`/`DISC-e7688072`): declarar
    cobro y, a la vez, decir que no hay nada que recordar entre visitas —
    un cobro implica, como mínimo, conocer el estado de esa cuenta. Ambos
    hechos son respuestas CERRADAS (`monetizacion`, `dato_recordar`): esto
    es exactamente lo que le corresponde al código, no a Qwen (A2/A4)."""
    fila_monetizacion = _ultima_fila(respuestas, "monetizacion")
    fila_datos = _ultima_fila(respuestas, "dato_recordar")
    if fila_monetizacion is None or fila_datos is None:
        return None
    if fila_monetizacion.respuesta != OPCION_MONETIZACION_SI:
        return None
    if fila_datos.respuesta == OPCION_SI:
        return None  # ya reconoce que sí hay que guardar algo: sin conflicto

    dominio, etiqueta = CATALOGO_DOMINIOS["dato_recordar"]
    return HallazgoConsecuencia(
        tipo="contradiccion", dominio=dominio, etiqueta=etiqueta,
        respuestas_relacionadas=[fila_monetizacion.id, fila_datos.id],
        motivo=(
            "El proyecto cobra de alguna forma, pero se declaró que no hay "
            "nada que recordar entre visitas — un cobro normalmente implica "
            "conocer, como mínimo, el estado de esa cuenta."
        ),
        afirmaciones=[
            {"valor": fila_monetizacion.respuesta, "origen": f"respuesta_formulario#{fila_monetizacion.id}"},
            {"valor": fila_datos.respuesta, "origen": f"respuesta_formulario#{fila_datos.id}"},
        ],
    )


def _regla_sintesis_rechazada(codigo: str, respuestas: list):
    """TF-0033, dominio 14 §3.4: la persona rechazó la síntesis del flujo
    (`sintesis_confirmacion="No"`). Deliberadamente **no** se infiere qué
    dominio específico causó el error — eso sería la inferencia semántica
    que la especificación prohíbe explícitamente. Se registra un `Gap` con
    `dominio="sintesis"`/`etiqueta="flujo_rechazado"`, una combinación sin
    entrada en `CATALOGO_DOMINIOS` a propósito: `resolver_pregunta()` nunca
    la resuelve a un `pregunta_id` (mismo criterio de A1 — "un hallazgo sin
    pregunta catalogada queda registrado tal cual, visible para revisión
    humana, nunca con una pregunta inventada"). El Gap sí aparece en
    `/resultado` y sí mueve el estado de la corrida a `REQUIERE_ACLARACION`
    — la respuesta "No" nunca se ignora, solo no se auto-resuelve."""
    fila = _ultima_fila(respuestas, "sintesis_confirmacion")
    if fila is None or fila.respuesta != OPCION_NO:
        return None

    return HallazgoConsecuencia(
        tipo="gap", dominio="sintesis", etiqueta="flujo_rechazado",
        respuestas_relacionadas=[fila.id],
        motivo=(
            "La persona indicó que la síntesis del flujo (dominio 14) no es "
            "correcta. No se infiere automáticamente qué dominio específico "
            "generó el error: requiere revisión humana directa del "
            "Expediente — ninguna reapertura puntual se activa sola."
        ),
    )


# Registro de reglas deterministas. Cada una, sin excepción, solo compara
# respuestas CERRADAS ya en conflicto lógico necesario (A2) — nunca una
# inferencia de negocio no forzosa.
_REGLAS = (
    _regla_suscripcion_sin_dato,
    _regla_sintesis_rechazada,
)


def evaluar_reglas(codigo: str, respuestas: list) -> list:
    """Corre todas las reglas registradas sobre `respuestas` una vez.
    Nunca lanza: una regla que no aplica devuelve `None` y se ignora."""
    hallazgos = []
    for regla in _REGLAS:
        hallazgo = regla(codigo, respuestas)
        if hallazgo is not None:
            hallazgos.append(hallazgo)
    return hallazgos
