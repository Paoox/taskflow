"""TF-0021 — Interfaz de proveedor de IA + implementación *eco*.

`ClienteIA` es un `typing.Protocol` (tipado estructural): un proveedor real o un
adaptador sobre un SDK lo satisface sin heredar de él. `ClienteEco` es un doble
de test determinista, sin red y sin coste, para validar contrato, integración y
flujo.

Sin dependencias nuevas. No importa Flask, `src.database`, `src.app` ni red.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Protocol, runtime_checkable

__all__ = ["OpcionesIA", "RespuestaIA", "ClienteIA", "ClienteEco"]


@dataclass
class OpcionesIA:
    """Parámetros de una llamada al proveedor."""

    modelo: str = "eco"
    max_tokens: int = 1024
    temperatura: float = 0.0
    timeout: float = 30.0


@dataclass
class RespuestaIA:
    """Resultado de una llamada al proveedor.

    `coste_estimado` en la unidad monetaria que fije el proveedor real; para
    `ClienteEco` es siempre `0.0`.
    """

    texto: str
    tokens_entrada: int
    tokens_salida: int
    modelo: str
    coste_estimado: float = 0.0


@runtime_checkable
class ClienteIA(Protocol):
    """Contrato mínimo de un proveedor de IA (`CLAUDE.md` §26)."""

    def completar(self, prompt: str, opciones: "OpcionesIA") -> "RespuestaIA": ...


# Longitud máxima del eco (recorte determinista del prompt).
_LIMITE_ECO = 500


class ClienteEco:
    """Implementación *eco* de `ClienteIA`: determinista, sin red, sin coste.

    Devuelve el prompt saneado y recortado con un prefijo, más metadatos
    mecánicos. **No** simula inteligencia ni genera lógica de negocio: su único
    propósito es validar el contrato y el flujo.
    """

    def __init__(self, logger=None):
        # Logger opcional (TF-0020): si se pasa, se deja una traza `debug` de la
        # llamada. Por defecto el cliente no depende de logging.
        self._logger = logger

    def completar(self, prompt: str, opciones: OpcionesIA) -> RespuestaIA:
        texto = f"[eco] {prompt.strip()[:_LIMITE_ECO]}"
        if self._logger is not None:
            self._logger.debug(
                "ClienteEco.completar modelo=%s prompt_chars=%d",
                opciones.modelo, len(prompt),
            )
        return RespuestaIA(
            texto=texto,
            tokens_entrada=len(prompt.split()),
            tokens_salida=len(texto.split()),
            modelo=opciones.modelo,
            coste_estimado=0.0,
        )
