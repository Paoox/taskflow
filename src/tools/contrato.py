"""TF-0029 — Contrato mínimo de una Tool: entrada tipada + `ResultadoTool`.

Dataclasses puras. `ResultadoTool.to_dict()` existe para trazabilidad (se
persiste dentro del `resultado` de una `acción` de `RepositorioAcciones`,
que ya acepta `dict`/`list`/`str`/`None`); no lleva `from_dict()` porque nada
en TF-0029 reconstruye un `ResultadoTool` a partir de JSON persistido — solo
se serializa hacia adelante.

Sin dependencias externas. No importa Flask, `src.database`, `src.app`,
`src.agentes`, `src.ai`, `src.orquestador` ni `src.repositorios`.
"""
from __future__ import annotations

import dataclasses
from dataclasses import dataclass
from typing import Optional

__all__ = ["ResultadoTool", "EntradaLeerArchivo", "EntradaListarArchivos"]


@dataclass
class ResultadoTool:
    """Resultado de ejecutar una Tool. Nunca se lanza una excepción por un
    error esperable (archivo ausente, fuera de sandbox, binario, etc.):
    siempre se devuelve como `exito=False` + `error`.
    """

    exito: bool
    contenido: str = ""
    ruta: Optional[str] = None
    error: Optional[str] = None
    truncado: bool = False

    def to_dict(self) -> dict:
        return dataclasses.asdict(self)


@dataclass
class EntradaLeerArchivo:
    """Entrada tipada de `LeerArchivoTool`. `ruta` es relativa a la
    `raiz_permitida` configurada en la Tool.
    """

    ruta: str


@dataclass
class EntradaListarArchivos:
    """Entrada tipada de `ListarArchivosTool`.

    `directorio` es relativo a la `raiz_permitida` ("" = la propia raíz).
    `profundidad_maxima` limita cuántos niveles de subdirectorios se recorren
    (1 = solo el contenido directo de `directorio`).
    """

    directorio: str = ""
    profundidad_maxima: int = 2
