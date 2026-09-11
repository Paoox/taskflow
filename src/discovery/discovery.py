"""TF-0030 — `ejecutar_discovery()`: punto de entrada de Discovery nuevo.

Cierra el primer tramo del flujo aprobado:

    respuestas_formulario -> Discovery -> Expediente Maestro

Paquete nuevo e independiente de `src.orquestador` (el Orquestador viejo,
que sigue alimentando PROJECT_STATE sin cambios) y de `src.proyectos`. No
importa ninguno de los dos, ni `src.repositorios.expedientes`
(`RepositorioExpedientes`) — nunca escribe en la tabla `expedientes`
(PROJECT_STATE). No modifica `src.formulario`: solo reutiliza su función
pública `siguiente_pregunta()` para comprobar que el árbol ya terminó.

A diferencia de `ejecutar_orquestador()` (un ciclo incremental, repetible),
`ejecutar_discovery()` corre **una sola vez, completo**, cuando
`siguiente_pregunta(respuestas)` ya devuelve `None` — el árbol captura todas
las respuestas antes de que Discovery empiece a interpretar, así que no
hace falta un modelo de ciclos. Llamarlo con un formulario incompleto lanza
`FormularioIncompleto` sin tocar nada.

División de trabajo (checkpoint aprobado, ver `docs/tickets/TF-0030.md`):

* `src.discovery.interpretacion_directa` interpreta, en Python puro, las
  respuestas cerradas cuyo significado es completo por sí solo — nunca
  llama al LLM.
* `src.discovery.interpretacion_llm` construye el contexto y valida la
  salida JSON Lines de `src.agentes.interprete_formulario.InterpreteFormulario`
  — un agente más, ejecutado con el `ejecutar_agente()` ya existente (mismo
  runner, mismo `ClienteIA`, misma tabla `acciones`; ningún mecanismo nuevo
  de ejecución).
* Este módulo combina ambas listas de `EntidadPropuesta` y las persiste en
  un único `LoteDescubrimiento` (atómico: o se escribe el Expediente
  completo de esta corrida, o no se escribe nada).

Alcance de entidades de este primer bloque: `Perfil`, `Requisito`,
`Restriccion`, `Dato`. `Capacidad` / `Funcionalidad` / `Relacion` / `Gap` /
`Contradiccion` / `FeaturePropuesta` / `EstadoObservado` quedan fuera de
este ticket — requieren relacionar entidades entre sí o deducir más allá de
lo declarado, ver `docs/tickets/TF-0030.md`.

`nombre_proyecto` se usa directamente (regla 17 del ticket, sin pasar por el
LLM) pero no se persiste como entidad — el modelo nuevo no tiene hoy una
entidad "Expediente" con nombre propio (`src.expediente.modelo` no la
define, y este ticket no introduce ninguna, regla 20); se devuelve como
metadato informativo en `ResultadoDiscovery`.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Optional

from src.agentes.contrato import EntradaAgente
from src.agentes.interprete_formulario import InterpreteFormulario
from src.agentes.runner import ejecutar_agente
from src.ai.cliente import ClienteIA
from src.discovery.interpretacion_directa import EntidadPropuesta, interpretar_directo
from src.discovery.interpretacion_llm import construir_contexto, parsear_entidades
from src.expediente.modelo import FuenteDirecta, NaturalezaInformacion
from src.formulario.arbol import siguiente_pregunta
from src.proyectos.estado import OrigenDato
from src.repositorios.acciones import COMPLETADA, FALLIDA, RepositorioAcciones
from src.repositorios.datos import RepositorioDatos
from src.repositorios.lote_descubrimiento import LoteDescubrimiento
from src.repositorios.perfiles import RepositorioPerfiles
from src.repositorios.requisitos import RepositorioRequisitos
from src.repositorios.respuestas_formulario import RepositorioRespuestasFormulario
from src.repositorios.restricciones import RepositorioRestricciones

__all__ = ["FormularioIncompleto", "ResultadoDiscovery", "ejecutar_discovery"]

# Tipo/actor fijos de la acción que envuelve una corrida completa de
# Discovery — distinta de la acción propia que registra `ejecutar_agente`
# para la llamada al InterpreteFormulario (mismo criterio que
# `TIPO_ACCION_ORQUESTAR` en `src.orquestador.orquestador`).
TIPO_ACCION_DISCOVERY = "discovery_formulario"
_ACTOR_DISCOVERY = "discovery"


class FormularioIncompleto(Exception):
    """`ejecutar_discovery()` se llamó para un `codigo` cuyo formulario
    todavía tiene, al menos, una pregunta sin responder."""


@dataclass
class ResultadoDiscovery:
    """Resultado de una corrida de `ejecutar_discovery()`."""

    codigo: str
    nombre_proyecto: Optional[str]
    entidades_creadas: int
    problemas: list = field(default_factory=list)


def _ultimo_texto(respuestas, pregunta_id: str) -> Optional[str]:
    de_esta = [r.respuesta for r in respuestas if r.pregunta_id == pregunta_id]
    return de_esta[-1] if de_esta else None


def _persistir(propuesta: EntidadPropuesta, *, codigo: str, accion_id: int, conexion) -> None:
    """Llama al `Repositorio<Tipo>.crear()` correcto para `propuesta`,
    dentro de la conexión de un `LoteDescubrimiento` (nunca comitea ni
    cierra nada — eso lo decide el lote)."""
    fuente = FuenteDirecta(tipo="formulario", referencia=str(propuesta.respuesta_id))

    if propuesta.tipo == "perfil":
        RepositorioPerfiles().crear(
            codigo, propuesta.campos["nombre"], propuesta.campos["descripcion"],
            NaturalezaInformacion.DECLARADO, OrigenDato.USER, propuesta.confianza,
            accion_id_origen=accion_id, fuente_directa=fuente, conn=conexion,
        )
    elif propuesta.tipo == "requisito":
        RepositorioRequisitos().crear(
            codigo, propuesta.campos["descripcion"],
            NaturalezaInformacion.DECLARADO, OrigenDato.USER, propuesta.confianza,
            accion_id_origen=accion_id, fuente_directa=fuente, conn=conexion,
        )
    elif propuesta.tipo == "restriccion":
        RepositorioRestricciones().crear(
            codigo, propuesta.campos["tipo"], propuesta.campos["descripcion"], OrigenDato.USER,
            naturaleza=NaturalezaInformacion.DECLARADO,
            accion_id_origen=accion_id, fuente_directa=fuente, conn=conexion,
        )
    elif propuesta.tipo == "dato":
        RepositorioDatos().crear(
            codigo, propuesta.campos["descripcion"],
            NaturalezaInformacion.DECLARADO, OrigenDato.USER, propuesta.confianza,
            temporalidad=propuesta.campos.get("temporalidad"),
            sensibilidad=propuesta.campos.get("sensibilidad"),
            accion_id_origen=accion_id, fuente_directa=fuente, conn=conexion,
        )
    else:  # pragma: no cover - cerrado por los dos intérpretes, nunca produce otro valor
        raise ValueError(f"tipo de entidad desconocido: {propuesta.tipo!r}")


def ejecutar_discovery(
    codigo: str,
    cliente: ClienteIA,
    *,
    repo_respuestas: Optional[RepositorioRespuestasFormulario] = None,
    repo_acciones: Optional[RepositorioAcciones] = None,
) -> ResultadoDiscovery:
    """Interpreta el formulario completo de `codigo` y escribe el Expediente
    Maestro correspondiente.

    Lanza `FormularioIncompleto` si `siguiente_pregunta()` todavía devuelve
    una pregunta — Discovery nunca interpreta un formulario a medias.
    `RepositorioRespuestasFormulario` es la única fuente de respuestas.

    La escritura (deterministas + las que sobreviven el parseo de la salida
    del LLM) ocurre dentro de un único `LoteDescubrimiento`: si cualquier
    escritura falla, ninguna de las de esta corrida sobrevive. Un fallo ahí
    se propaga (no se silencia) después de marcar la acción envolvente como
    `FALLIDA` para trazabilidad.
    """
    repo_resp = repo_respuestas if repo_respuestas is not None else RepositorioRespuestasFormulario()
    repo_acc = repo_acciones if repo_acciones is not None else RepositorioAcciones()

    respuestas = repo_resp.listar(codigo)
    if siguiente_pregunta(respuestas) is not None:
        raise FormularioIncompleto(
            f"el formulario de {codigo!r} todavía no está completo: "
            "siguiente_pregunta() devuelve una pregunta pendiente"
        )

    nombre_proyecto = _ultimo_texto(respuestas, "nombre_proyecto")
    propuestas = list(interpretar_directo(respuestas))
    contexto, ids_contexto = construir_contexto(respuestas)

    problemas: list = []
    accion_id = repo_acc.registrar(
        ticket=codigo, actor=_ACTOR_DISCOVERY, tipo=TIPO_ACCION_DISCOVERY,
        entrada={"respuestas": len(respuestas)},
    )

    try:
        if contexto:
            entrada_agente = EntradaAgente(
                ticket=codigo,
                objetivo="Interpretar las respuestas de texto libre del formulario de Discovery",
                contexto=contexto,
            )
            salida = ejecutar_agente(entrada_agente, cliente, InterpreteFormulario(), repositorio=repo_acc)
            problemas.extend(salida.problemas)
            propuestas_llm, problemas_parseo = parsear_entidades(salida.resultado, ids_contexto)
            problemas.extend(problemas_parseo)
            propuestas.extend(propuestas_llm)

        with LoteDescubrimiento() as lote:
            for propuesta in propuestas:
                _persistir(propuesta, codigo=codigo, accion_id=accion_id, conexion=lote.conexion)
    except Exception as exc:
        repo_acc.marcar(
            accion_id, FALLIDA,
            resultado={"problemas": problemas, "error": f"{type(exc).__name__}: {exc}"},
        )
        raise

    repo_acc.marcar(
        accion_id, COMPLETADA,
        resultado={"entidades_creadas": len(propuestas), "problemas": problemas},
    )

    return ResultadoDiscovery(
        codigo=codigo, nombre_proyecto=nombre_proyecto,
        entidades_creadas=len(propuestas), problemas=problemas,
    )
