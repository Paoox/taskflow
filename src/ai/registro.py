"""TF-0024 — Registro de proveedores/runtimes de IA.

Mapa ``nombre -> fábrica`` de clientes que implementan `ClienteIA`. La factoría
(`src.ai.factory.crear_cliente`) despacha por este registro según
``TASKFLOW_AI_PROVIDER``.

``"eco"`` (el `ClienteEco` determinista de TF-0021) queda registrado al importar
este módulo. Un adaptador nuevo —p. ej. ``ClienteOllama`` en TF-0025— se añade
con ``registrar("ollama", lambda: ClienteOllama(...))`` desde su propio módulo,
**sin tocar este archivo**.

Una fábrica no recibe argumentos (DA-12): el ``lambda`` registrado lee de
`src.config` los ``TASKFLOW_AI_*`` que su adaptador necesite, en tiempo de
llamada. El adaptador recibe esos valores como parámetros explícitos en su
``__init__`` y no importa `src.config`.

Sin dependencias externas. No importa Flask, `src.agentes` ni red.
"""
from __future__ import annotations

from typing import Callable

from src.ai.cliente import ClienteEco, ClienteIA
from src.ai.errores import ErrorConfiguracionIA

__all__ = ["FabricaCliente", "registrar", "obtener", "nombres", "quitar"]

FabricaCliente = Callable[[], ClienteIA]

_REGISTRO: dict[str, FabricaCliente] = {}


def registrar(nombre: str, fabrica: FabricaCliente) -> None:
    """Registra ``fabrica`` bajo ``nombre`` (normalizado con ``strip`` +
    minúsculas). Un ``nombre`` ya registrado lanza `ErrorConfiguracionIA`.
    """
    clave = nombre.strip().lower()
    if clave in _REGISTRO:
        raise ErrorConfiguracionIA(f"proveedor de IA ya registrado: {clave!r}")
    _REGISTRO[clave] = fabrica


def obtener(nombre: str) -> FabricaCliente:
    """Devuelve la fábrica registrada bajo ``nombre``. Ausente lanza
    `ErrorConfiguracionIA` (el mensaje lista los proveedores disponibles).
    """
    clave = nombre.strip().lower()
    try:
        return _REGISTRO[clave]
    except KeyError:
        raise ErrorConfiguracionIA(
            f"proveedor de IA no registrado: {clave!r}; "
            f"disponibles: {list(_REGISTRO)}"
        ) from None


def nombres() -> "tuple[str, ...]":
    """Nombres de proveedor registrados, en orden de alta."""
    return tuple(_REGISTRO)


def quitar(nombre: str) -> None:
    """Elimina un proveedor del registro. No-op si no existe (útil para tests)."""
    _REGISTRO.pop(nombre.strip().lower(), None)


# Proveedor por defecto: el doble determinista de TF-0021.
registrar("eco", lambda: ClienteEco())
