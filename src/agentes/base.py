"""TF-0023 — Interfaz de un agente ejecutable por el runner.

`DefinicionAgente` es un `typing.Protocol` *methods-only* (tipado estructural): un
agente lo satisface sin heredar de él. Además de estos métodos, el runner espera
dos atributos en el agente (no forman parte del `Protocol`; se verifican en los
tests):

  * ``nombre: str`` — identifica el agente y su archivo de prompt
    (``cargar_prompt(nombre)``); el runner deriva ``actor = f"agente:{nombre}"``;
  * ``tipo_accion: str`` — valor de la columna ``tipo`` de ``acciones``.

Sin dependencias nuevas. No importa Flask, `src.database`, `src.app` ni red.
"""
from __future__ import annotations

from typing import Protocol, runtime_checkable

from src.agentes.contrato import EntradaAgente, SalidaAgente
from src.ai.cliente import RespuestaIA

__all__ = ["DefinicionAgente"]


@runtime_checkable
class DefinicionAgente(Protocol):
    """Contrato estructural de un agente ejecutable (`CLAUDE.md` §27)."""

    def construir_prompt(self, entrada: EntradaAgente) -> str: ...

    def parsear(self, respuesta: RespuestaIA, entrada: EntradaAgente) -> SalidaAgente: ...
