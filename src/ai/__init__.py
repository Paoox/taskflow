"""Capa de IA de Taskflow — superficie pública del runtime.

TF-0021 fijó el contrato: `ClienteIA` (interfaz de proveedor), `OpcionesIA`,
`RespuestaIA` y el doble determinista `ClienteEco`.

TF-0024 añadió la **capa de abstracción / runtime**: la factoría desacoplada
`crear_cliente()`, el registro de proveedores (`registrar` / `nombres`) y la
taxonomía de errores del límite (`ErrorIA` y subclases). **No hay proveedor de
red todavía.**

Este paquete es el **único** punto consciente del proveedor: cambiar de
runtime/modelo (p. ej. a Ollama en TF-0025, o a un modelo cuantizado o con LoRA)
consiste en registrar un adaptador y ajustar `TASKFLOW_AI_*`, sin tocar el
runner, los agentes ni los contratos de negocio.
"""
from src.ai.cliente import ClienteEco, ClienteIA, OpcionesIA, RespuestaIA
from src.ai.errores import (
    ErrorConfiguracionIA,
    ErrorIA,
    ErrorProveedorNoDisponible,
    ErrorRespuestaIA,
)
from src.ai.factory import crear_cliente
from src.ai.registro import nombres, registrar

__all__ = [
    "ClienteIA",
    "OpcionesIA",
    "RespuestaIA",
    "ClienteEco",
    "crear_cliente",
    "registrar",
    "nombres",
    "ErrorIA",
    "ErrorConfiguracionIA",
    "ErrorProveedorNoDisponible",
    "ErrorRespuestaIA",
]
