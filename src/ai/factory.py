"""TF-0024 — Factoría del runtime de IA: `crear_cliente()`.

Punto único donde TaskFlow decide qué implementación de `ClienteIA` usar, según
``TASKFLOW_AI_PROVIDER``. El runner y los agentes reciben el `ClienteIA` ya
construido y **no** llaman aquí (decisiones DA-1 / DA-4): detrás del `ClienteIA`
puede haber `ClienteEco`, Ollama, otro proveedor, otro modelo, un modelo
cuantizado o un modelo con LoRA sin que el runner lo sepa.

`crear_cliente()` solo lanza subclases de `ErrorIA`.

Sin dependencias externas. No importa Flask, `src.agentes` ni red.
"""
from __future__ import annotations

from src import config
from src.ai.cliente import ClienteIA
from src.ai.registro import obtener

__all__ = ["crear_cliente"]


def crear_cliente() -> ClienteIA:
    """Construye el `ClienteIA` del proveedor configurado en
    ``TASKFLOW_AI_PROVIDER`` (por defecto ``"eco"``).

    Proveedor no registrado -> `ErrorConfiguracionIA`. Late binding: lee la
    configuración en cada llamada.
    """
    nombre = config.proveedor_ia()
    fabrica = obtener(nombre)  # ErrorConfiguracionIA si no existe
    return fabrica()
