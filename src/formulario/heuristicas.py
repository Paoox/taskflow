"""TF-0033 — Heurísticas sintácticas baratas sobre texto libre del formulario.

Regla de profundidad 3 de la especificación de "Discovery Inteligente":
señales verificables en código, sin ningún juicio semántico ni llamada a un
proveedor de IA — el filtro de calidad barato que antecede a Discovery/Qwen,
nunca lo reemplaza (D3: Qwen nunca decide el flujo del formulario).

Funciones puras: no importan `src.repositorios`, no abren conexión a BD, no
llaman a ningún `ClienteIA`.
"""
from __future__ import annotations

import re

__all__ = ["es_respuesta_vaga", "sugiere_enumeracion"]

# Verbos genéricos de una lista cerrada — vocabulario cerrado a propósito
# (ampliarlo es una revisión consciente, no un efecto colateral silencioso).
_VERBOS_GENERICOS = (
    "administrar", "gestionar", "manejar", "dar mantenimiento",
    "mantener", "controlar", "organizar",
)

# Umbral de longitud para considerar una respuesta "corta" (en palabras).
_LIMITE_PALABRAS_CORTA = 6

_CONECTORES_ENUMERACION = ("también", "además", " y también", " y además")


def es_respuesta_vaga(texto: str) -> bool:
    """True si `texto` es corta y usa solo un verbo genérico de la lista
    cerrada, sin objeto claro — dispara una aclaración obligatoria con
    ejemplo concreto (nunca decide por sí sola que algo está mal, solo pide
    más información)."""
    texto_normalizado = texto.strip().lower()
    if not texto_normalizado:
        return False
    palabras = texto_normalizado.split()
    if len(palabras) > _LIMITE_PALABRAS_CORTA:
        return False
    return any(verbo in texto_normalizado for verbo in _VERBOS_GENERICOS)


def sugiere_enumeracion(texto: str) -> bool:
    """True si `texto` parece mezclar varias ideas distintas — comas,
    conectores de enumeración, o más de un verbo de acción detectado por
    puntuación simple. Dispara una pregunta de desglose, nunca separa el
    texto por sí sola (nunca interpreta significado)."""
    texto_normalizado = texto.strip().lower()
    if not texto_normalizado:
        return False
    if "," in texto_normalizado:
        return True
    if any(conector in texto_normalizado for conector in _CONECTORES_ENUMERACION):
        return True
    # más de una coma decimal en una sola oración sugiere enumeración de
    # cláusulas separadas por " y " (no la conjunción simple de dos palabras)
    return bool(re.search(r"\by\b.*\by\b", texto_normalizado))
