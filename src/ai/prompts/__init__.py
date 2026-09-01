"""TF-0021 — Prompts de agentes: ubicación separada de la lógica (`CLAUDE.md` §26).

Convención (ver `README.md`): un archivo `<nombre>.md` por agente, texto plano /
Markdown, sin lógica. `cargar_prompt` solo los lee.
"""
import re
from pathlib import Path

__all__ = ["cargar_prompt", "PromptNoEncontrado"]

_DIR_PROMPTS = Path(__file__).parent
# `nombre` debe ser un identificador simple: sin separadores de ruta ni `..`.
_NOMBRE_VALIDO = re.compile(r"[a-z0-9_-]+")


class PromptNoEncontrado(FileNotFoundError):
    """No existe un prompt con el nombre pedido en `src/ai/prompts/`."""


def cargar_prompt(nombre: str) -> str:
    """Devuelve el contenido de `src/ai/prompts/<nombre>.md`.

    Lanza `PromptNoEncontrado` si `nombre` no es un identificador simple
    (`[a-z0-9_-]+`) o si el archivo no existe.
    """
    if not isinstance(nombre, str) or not _NOMBRE_VALIDO.fullmatch(nombre):
        raise PromptNoEncontrado(f"nombre de prompt inválido: {nombre!r}")
    ruta = _DIR_PROMPTS / f"{nombre}.md"
    if not ruta.is_file():
        raise PromptNoEncontrado(f"no existe el prompt {nombre!r} ({ruta})")
    return ruta.read_text(encoding="utf-8")
