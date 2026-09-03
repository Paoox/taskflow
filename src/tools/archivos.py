"""TF-0029 — Tools de filesystem: `LeerArchivoTool` y `ListarArchivosTool`.

Solo lectura, deterministas, sandboxed a una `raiz_permitida` configurable
(no hardcodeada al propio repo de Taskflow: Taskflow orquestará proyectos de
terceros, no solo a sí mismo). Ninguna excepción esperable escapa de
`ejecutar()`: toda condición de error (ruta fuera del sandbox, archivo
ausente, binario, excluido por política) se devuelve como
`ResultadoTool(exito=False, ...)`.

Sandbox: `raiz_permitida` se resuelve una sola vez en el constructor
(`Path.resolve()`); cada ruta pedida se resuelve contra ella y se verifica
que el resultado siga dentro de la raíz **después** de resolver symlinks
(`Path.relative_to()` sobre las dos rutas ya resueltas) — así una ruta con
`..`, una ruta absoluta, o un symlink que apunte fuera del sandbox se
rechazan de la misma forma.

Sin dependencias externas. No importa Flask, `src.database`, `src.app`,
`src.agentes`, `src.ai`, `src.orquestador` ni `src.repositorios`.
"""
from __future__ import annotations

from pathlib import Path, PurePath
from typing import Optional

from src.tools.contrato import EntradaListarArchivos, EntradaLeerArchivo, ResultadoTool

__all__ = ["LeerArchivoTool", "ListarArchivosTool", "LIMITE_CARACTERES_LECTURA"]

# Límite determinista de caracteres devueltos por una lectura (no un recorte
# aleatorio): evita volcar un archivo gigante entero al contexto de un agente.
LIMITE_CARACTERES_LECTURA = 8000

# Directorios de infraestructura que ListarArchivosTool nunca recorre.
_DIRECTORIOS_IGNORADOS = frozenset({".git", "__pycache__", "venv", ".venv", "node_modules"})

# Archivos que LeerArchivoTool nunca lee, sin importar si son legibles
# (CLAUDE.md §21/§25.3: nunca exponer secretos, ni siquiera hacia un LLM).
_NOMBRES_SENSIBLES = frozenset({"id_rsa", "id_dsa", "id_ecdsa", "id_ed25519"})
_PREFIJOS_SENSIBLES = (".env",)
_SUFIJOS_SENSIBLES = (".pem", ".key", ".pfx", ".p12")


def _es_nombre_sensible(nombre: str) -> bool:
    return (
        nombre in _NOMBRES_SENSIBLES
        or nombre.startswith(_PREFIJOS_SENSIBLES)
        or nombre.endswith(_SUFIJOS_SENSIBLES)
    )


def _resolver_dentro_de_raiz(raiz: Path, ruta_relativa: str) -> Optional[Path]:
    """Resuelve `ruta_relativa` contra `raiz`. Devuelve `None` si la ruta es
    absoluta o si el resultado (ya resuelto, symlinks incluidos) queda fuera
    de `raiz`. `ruta_relativa=""` resuelve a la propia `raiz`.
    """
    if PurePath(ruta_relativa).is_absolute():
        return None
    candidato = (raiz / ruta_relativa).resolve()
    try:
        candidato.relative_to(raiz)
    except ValueError:
        return None
    return candidato


class LeerArchivoTool:
    """Lee un archivo de texto dentro de `raiz_permitida`. Solo lectura."""

    nombre = "leer_archivo"

    def __init__(self, raiz_permitida: str, limite_caracteres: int = LIMITE_CARACTERES_LECTURA):
        self._raiz = Path(raiz_permitida).resolve()
        self._limite = limite_caracteres

    def ejecutar(self, entrada: EntradaLeerArchivo) -> ResultadoTool:
        candidato = _resolver_dentro_de_raiz(self._raiz, entrada.ruta)
        if candidato is None:
            return ResultadoTool(exito=False, ruta=entrada.ruta,
                                  error="ruta fuera del alcance permitido")
        if _es_nombre_sensible(candidato.name):
            return ResultadoTool(exito=False, ruta=entrada.ruta,
                                  error="archivo excluido por política de seguridad")
        if not candidato.is_file():
            return ResultadoTool(exito=False, ruta=entrada.ruta, error="archivo no encontrado")

        try:
            crudo = candidato.read_bytes()
        except OSError as exc:
            return ResultadoTool(exito=False, ruta=entrada.ruta, error=f"error de lectura: {exc}")

        try:
            texto = crudo.decode("utf-8")
        except UnicodeDecodeError:
            return ResultadoTool(exito=False, ruta=entrada.ruta, error="archivo no es texto plano")

        truncado = len(texto) > self._limite
        contenido = texto[: self._limite] if truncado else texto
        return ResultadoTool(exito=True, contenido=contenido, ruta=entrada.ruta, truncado=truncado)


class ListarArchivosTool:
    """Lista el árbol de un directorio dentro de `raiz_permitida`, con
    profundidad limitada, ignorando directorios de infraestructura. Solo
    lectura.
    """

    nombre = "listar_archivos"

    def __init__(self, raiz_permitida: str):
        self._raiz = Path(raiz_permitida).resolve()

    def ejecutar(self, entrada: EntradaListarArchivos) -> ResultadoTool:
        base = _resolver_dentro_de_raiz(self._raiz, entrada.directorio)
        if base is None:
            return ResultadoTool(exito=False, ruta=entrada.directorio,
                                  error="ruta fuera del alcance permitido")
        if not base.is_dir():
            return ResultadoTool(exito=False, ruta=entrada.directorio,
                                  error="directorio no encontrado")

        lineas: list[str] = []
        self._recorrer(base, 1, "", entrada.profundidad_maxima, lineas)
        return ResultadoTool(exito=True, contenido="\n".join(lineas), ruta=entrada.directorio or ".")

    @staticmethod
    def _recorrer(actual: Path, nivel: int, prefijo: str, profundidad_maxima: int,
                  lineas: list[str]) -> None:
        if nivel > profundidad_maxima:
            return
        try:
            hijos = sorted(actual.iterdir(), key=lambda p: p.name)
        except OSError:
            return
        for hijo in hijos:
            if hijo.name in _DIRECTORIOS_IGNORADOS:
                continue
            relativo = f"{prefijo}{hijo.name}"
            if hijo.is_dir():
                lineas.append(f"{relativo}/")
                ListarArchivosTool._recorrer(hijo, nivel + 1, relativo + "/", profundidad_maxima, lineas)
            else:
                lineas.append(relativo)
