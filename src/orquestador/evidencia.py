"""TF-0029 — Recolector determinista de evidencia para el descubrimiento raíz.

Puente entre `src.tools` (capacidades ejecutables) y `ejecutar_orquestador()`
(TF-0027): decide **qué** Tools invocar y en qué orden — código puro, sin que
el modelo elija nada (ADR-0001: "determinista -> Tool/código; razonamiento ->
LLM"). El resultado se incorpora a `EntradaAgente.contexto`/
`archivos_relevantes` por el llamador; este módulo no conoce `EntradaAgente`
ni ningún agente.

La lista de archivos conocidos es fija y determinista (no hay bucle de
decisión del modelo sobre qué leer): se intenta leer cada uno y se ignora en
silencio el que no exista (una ausencia esperable no es un problema a
reportar). Solo se reportan en `problemas` los truncados y los fallos reales
de la Tool de listado.

Sin dependencias externas más allá de `src.tools` y los tipos de
`src.orquestador.contrato`/`src.proyectos.estado`. No importa Flask,
`src.database`, `src.app`, `src.agentes` ni `src.ai`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Callable, List

from src.orquestador.contrato import PreguntaPendiente
from src.proyectos.estado import ExpedienteProyecto
from src.tools.archivos import LeerArchivoTool, ListarArchivosTool
from src.tools.contrato import EntradaListarArchivos, EntradaLeerArchivo

__all__ = ["EvidenciaRecolectada", "RecolectorEvidencia", "recolector_evidencia_archivos_conocidos"]

# Lista fija de archivos que suelen declarar identidad/tipo/stack de un
# proyecto. El código decide qué mirar; el modelo no elige ninguno.
_ARCHIVOS_CONOCIDOS = (
    "README.md", "package.json", "pyproject.toml", "requirements.txt",
    "Dockerfile", "CLAUDE.md", "go.mod", "Cargo.toml", "composer.json",
)


@dataclass
class EvidenciaRecolectada:
    """Evidencia ya lista para anexar a un `EntradaAgente`."""

    contexto_adicional: str = ""
    archivos_relevantes: List[str] = field(default_factory=list)
    problemas: List[str] = field(default_factory=list)


RecolectorEvidencia = Callable[[ExpedienteProyecto, List[PreguntaPendiente]], EvidenciaRecolectada]


def recolector_evidencia_archivos_conocidos(raiz_permitida: str) -> RecolectorEvidencia:
    """Fábrica: devuelve un recolector determinista sandboxed a `raiz_permitida`.

    El recolector resultante: lista superficialmente `raiz_permitida` y lee
    los archivos de `_ARCHIVOS_CONOCIDOS` que existan dentro de ella.
    """
    leer = LeerArchivoTool(raiz_permitida)
    listar = ListarArchivosTool(raiz_permitida)

    def _recolectar(
        expediente: ExpedienteProyecto, preguntas: List[PreguntaPendiente],
    ) -> EvidenciaRecolectada:
        secciones: List[str] = []
        archivos_relevantes: List[str] = []
        problemas: List[str] = []

        listado = listar.ejecutar(EntradaListarArchivos())
        if listado.exito:
            secciones.append(
                "## Estructura del proyecto (superficial)\n" + (listado.contenido or "(vacío)")
            )
        else:
            problemas.append(f"listado de estructura no disponible: {listado.error}")

        for nombre in _ARCHIVOS_CONOCIDOS:
            resultado = leer.ejecutar(EntradaLeerArchivo(nombre))
            if not resultado.exito:
                continue  # ausencia esperable: no todo proyecto tiene todos estos archivos
            secciones.append(f"## Contenido de {nombre}\n{resultado.contenido}")
            archivos_relevantes.append(nombre)
            if resultado.truncado:
                problemas.append(f"contenido de '{nombre}' truncado (límite determinista alcanzado)")

        return EvidenciaRecolectada(
            contexto_adicional="\n\n".join(secciones),
            archivos_relevantes=archivos_relevantes,
            problemas=problemas,
        )

    return _recolectar
