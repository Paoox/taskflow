"""TF-0030/TF-0032 — `ejecutar_discovery()` / `procesar_reapertura()`: punto
de entrada de Discovery nuevo.

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

División de trabajo (TF-0030, ampliada por TF-0032 — ver
`docs/tickets/TF-0032.md`):

* `src.discovery.interpretacion_directa` interpreta, en Python puro, las
  respuestas cerradas cuyo significado es completo por sí solo — nunca
  llama al LLM.
* `src.discovery.interpretacion_llm` construye el contexto (incluidos los
  dominios+etiquetas activos, A1) y valida la salida JSON Lines de
  `InterpreteFormulario` — entidades y, desde TF-0032, hallazgos.
* `src.discovery.reglas_consecuencia` evalúa reglas deterministas
  cerrada-vs-cerrada sobre el estado acumulado (A3/A4).
* `src.discovery.catalogo_dominios` resuelve un hallazgo (dominio+etiqueta)
  a un `pregunta_id` reactivable — nunca lo hace Qwen (A1).
* Este módulo combina todo y persiste en un único `LoteDescubrimiento`
  (atómico), incluidos `Gap`/`Contradiccion` (A4, ya existentes en el
  modelo y sus repositorios — TF-0032 es el primer llamador real).

Alcance de entidades: `Perfil`, `Requisito`, `Restriccion`, `Dato`, más
(TF-0032) `Gap`/`Contradiccion` como registros de hallazgos — nunca como
entidades nuevas del modelo. `Capacidad`/`Funcionalidad`/`Relacion`/
`FeaturePropuesta`/`EstadoObservado` siguen fuera de alcance.

`nombre_proyecto` se usa directamente (regla 17, sin pasar por el LLM) pero
no se persiste como entidad — se devuelve como metadato informativo en
`ResultadoDiscovery`.
"""
from __future__ import annotations

import json
from dataclasses import dataclass, field
from enum import Enum
from typing import Optional

from src.agentes.contrato import EntradaAgente
from src.agentes.interprete_formulario import InterpreteFormulario
from src.agentes.runner import ejecutar_agente
from src.ai.cliente import ClienteIA
from src.discovery import reglas_consecuencia
from src.discovery.catalogo_dominios import resolver_pregunta
from src.discovery.interpretacion_directa import EntidadPropuesta, interpretar_directo
from src.discovery.interpretacion_llm import construir_contexto, parsear_entidades
from src.discovery.reglas_consecuencia import HallazgoConsecuencia, LIMITE_PROFUNDIDAD_CADENA
from src.expediente.modelo import (
    EstadoContradiccion, EstadoGap, FuenteDirecta, NaturalezaInformacion, TipoPregunta,
)
from src.formulario.arbol import siguiente_pregunta
from src.formulario.preguntas import PREGUNTAS
from src.proyectos.estado import OrigenDato
from src.repositorios.acciones import COMPLETADA, FALLIDA, RepositorioAcciones
from src.repositorios.contradicciones import RepositorioContradicciones
from src.repositorios.datos import RepositorioDatos
from src.repositorios.gaps import RepositorioGaps
from src.repositorios.lote_descubrimiento import LoteDescubrimiento
from src.repositorios.perfiles import RepositorioPerfiles
from src.repositorios.requisitos import RepositorioRequisitos
from src.repositorios.respuestas_formulario import RepositorioRespuestasFormulario
from src.repositorios.restricciones import RepositorioRestricciones

__all__ = [
    "EstadoDiscovery", "FormularioIncompleto", "ResultadoDiscovery", "ResultadoReapertura",
    "ejecutar_discovery", "procesar_reapertura",
]

# Tipo/actor fijos de la acción que envuelve una corrida completa de
# Discovery — distinta de la acción propia que registra `ejecutar_agente`
# para la llamada al InterpreteFormulario (mismo criterio que
# `TIPO_ACCION_ORQUESTAR` en `src.orquestador.orquestador`).
TIPO_ACCION_DISCOVERY = "discovery_formulario"
_ACTOR_DISCOVERY = "discovery"

# TF-0032 — acción que envuelve la resolución de UNA reapertura puntual.
TIPO_ACCION_RESOLVER_HALLAZGO = "resolver_hallazgo_discovery"
_ACTOR_REAPERTURA = "discovery_reapertura"

# Opciones cerradas de "incertidumbre" del catálogo actual — una respuesta
# reactivada con cualquiera de estas NUNCA resuelve un hallazgo por sí sola
# (regla 4 del checkpoint TF-0032: "no sé" no es lo mismo que "resuelto").
_OPCIONES_INCERTIDUMBRE = frozenset({
    "No sé", "No estoy seguro", "Todavía no lo sé", "Todavía no lo he decidido",
})


class FormularioIncompleto(Exception):
    """`ejecutar_discovery()` se llamó para un `codigo` cuyo formulario
    todavía tiene, al menos, una pregunta sin responder."""


class EstadoDiscovery(str, Enum):
    """TF-0032 (D8) — estado de UNA corrida de Discovery. Nunca se mezcla
    con la readiness de fases posteriores (ver ADR de política
    epistemológica): esto solo describe si Discovery mismo terminó, no si
    "está listo para construirse"."""

    EN_PROGRESO = "en_progreso"
    REQUIERE_ACLARACION = "requiere_aclaracion"
    COMPLETO_CON_PENDIENTES = "completo_con_pendientes"
    COMPLETO = "completo"


@dataclass
class ResultadoDiscovery:
    """Resultado de una corrida de `ejecutar_discovery()`."""

    codigo: str
    nombre_proyecto: Optional[str]
    entidades_creadas: int
    estado: EstadoDiscovery
    problemas: list = field(default_factory=list)


@dataclass
class ResultadoReapertura:
    """Resultado de una corrida de `procesar_reapertura()`."""

    codigo: str
    tipo_hallazgo: str
    hallazgo_id: int
    resuelto: bool
    ya_procesado: bool
    problemas: list = field(default_factory=list)


def _ultimo_texto(respuestas, pregunta_id: str) -> Optional[str]:
    de_esta = [r.respuesta for r in respuestas if r.pregunta_id == pregunta_id]
    return de_esta[-1] if de_esta else None


def _ultima_fila(respuestas, pregunta_id: str):
    de_esta = [r for r in respuestas if r.pregunta_id == pregunta_id]
    return de_esta[-1] if de_esta else None


def _campo_o_concepto(dominio: str, etiqueta: str) -> str:
    return f"{dominio}.{etiqueta}"


def _dominio_etiqueta_de(campo_o_concepto: str) -> tuple:
    dominio, _, etiqueta = campo_o_concepto.partition(".")
    return dominio, etiqueta


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


def _profundidad_alcanzada(codigo: str, repo_gaps: RepositorioGaps, repo_contradicciones: RepositorioContradicciones) -> bool:
    """TF-0032 (A3) — proxy simple y verificable del límite de profundidad
    de cadena: cuenta cuántos Gap/Contradiccion ya existen (en cualquier
    estado) para `codigo`. Alcanzado el límite, se detiene la creación de
    hallazgos NUEVOS — nunca se degrada el estado de uno ya existente."""
    total = len(repo_gaps.listar(codigo)) + len(repo_contradicciones.listar(codigo))
    return total >= LIMITE_PROFUNDIDAD_CADENA


def _persistir_hallazgo_determinista(
    hallazgo: HallazgoConsecuencia, *, codigo: str, conexion,
    repo_gaps: RepositorioGaps, repo_contradicciones: RepositorioContradicciones,
) -> None:
    """Persiste un `HallazgoConsecuencia` (motor de reglas). Idempotente:
    si ya existe un Gap/Contradiccion con el mismo `campo_o_concepto`/
    `concepto` para este `codigo` (en cualquier estado), no se duplica."""
    campo = _campo_o_concepto(hallazgo.dominio, hallazgo.etiqueta)

    if hallazgo.tipo == "contradiccion":
        if any(c.concepto == campo for c in repo_contradicciones.listar(codigo)):
            return
        repo_contradicciones.crear(
            codigo, "respuesta_formulario", campo, hallazgo.afirmaciones, conn=conexion,
        )
    elif hallazgo.tipo == "gap":
        if any(g.campo_o_concepto == campo for g in repo_gaps.listar(codigo)):
            return
        repo_gaps.crear(
            codigo, "respuesta_formulario", campo, motivo=hallazgo.motivo, conn=conexion,
        )
    else:  # pragma: no cover - HallazgoConsecuencia solo produce estos 2 tipos
        raise ValueError(f"tipo de hallazgo desconocido: {hallazgo.tipo!r}")


def _persistir_hallazgo_llm(hallazgo, *, codigo: str, conexion, repo_gaps: RepositorioGaps) -> None:
    """Persiste un `HallazgoLLM` (Qwen) siempre como `Gap` — comparar dos
    afirmaciones ya conocidas para producir una `Contradiccion` es trabajo
    determinista (`reglas_consecuencia`), nunca de Qwen (A2/A4). Idempotente
    igual que la variante determinista."""
    campo = _campo_o_concepto(hallazgo.dominio, hallazgo.etiqueta)
    if any(g.campo_o_concepto == campo for g in repo_gaps.listar(codigo)):
        return
    repo_gaps.crear(codigo, "respuesta_formulario", campo, motivo=hallazgo.motivo, conn=conexion)


def _calcular_estado(
    respuestas, codigo: str, repo_gaps: RepositorioGaps, repo_contradicciones: RepositorioContradicciones,
) -> EstadoDiscovery:
    if siguiente_pregunta(respuestas) is not None:
        return EstadoDiscovery.EN_PROGRESO
    gaps = repo_gaps.listar(codigo)
    contradicciones = repo_contradicciones.listar(codigo)
    if any(c.estado == EstadoContradiccion.ABIERTA for c in contradicciones):
        return EstadoDiscovery.REQUIERE_ACLARACION
    if any(g.estado == EstadoGap.ABIERTO for g in gaps):
        return EstadoDiscovery.REQUIERE_ACLARACION
    if any(g.estado == EstadoGap.DOCUMENTADO_NO_BLOQUEANTE for g in gaps):
        return EstadoDiscovery.COMPLETO_CON_PENDIENTES
    return EstadoDiscovery.COMPLETO


def ejecutar_discovery(
    codigo: str,
    cliente: ClienteIA,
    *,
    repo_respuestas: Optional[RepositorioRespuestasFormulario] = None,
    repo_acciones: Optional[RepositorioAcciones] = None,
    repo_gaps: Optional[RepositorioGaps] = None,
    repo_contradicciones: Optional[RepositorioContradicciones] = None,
) -> ResultadoDiscovery:
    """Interpreta el formulario completo de `codigo` y escribe el Expediente
    Maestro correspondiente.

    Lanza `FormularioIncompleto` si `siguiente_pregunta()` todavía devuelve
    una pregunta — Discovery nunca interpreta un formulario a medias.
    `RepositorioRespuestasFormulario` es la única fuente de respuestas.

    La escritura (deterministas + LLM + hallazgos de ambos orígenes) ocurre
    dentro de un único `LoteDescubrimiento`: si cualquier escritura falla,
    ninguna de las de esta corrida sobrevive. Un fallo ahí se propaga (no se
    silencia) después de marcar la acción envolvente como `FALLIDA`.
    """
    repo_resp = repo_respuestas if repo_respuestas is not None else RepositorioRespuestasFormulario()
    repo_acc = repo_acciones if repo_acciones is not None else RepositorioAcciones()
    repo_gap = repo_gaps if repo_gaps is not None else RepositorioGaps()
    repo_contra = repo_contradicciones if repo_contradicciones is not None else RepositorioContradicciones()

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
    hallazgos_llm: list = []
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
            propuestas_llm, hallazgos_llm, problemas_parseo = parsear_entidades(salida.resultado, ids_contexto)
            problemas.extend(problemas_parseo)
            propuestas.extend(propuestas_llm)

        hallazgos_deterministas = reglas_consecuencia.evaluar_reglas(codigo, respuestas)

        with LoteDescubrimiento() as lote:
            for propuesta in propuestas:
                _persistir(propuesta, codigo=codigo, accion_id=accion_id, conexion=lote.conexion)
            for hallazgo in hallazgos_deterministas:
                _persistir_hallazgo_determinista(
                    hallazgo, codigo=codigo, conexion=lote.conexion,
                    repo_gaps=repo_gap, repo_contradicciones=repo_contra,
                )
            for hallazgo_llm in hallazgos_llm:
                _persistir_hallazgo_llm(hallazgo_llm, codigo=codigo, conexion=lote.conexion, repo_gaps=repo_gap)
    except Exception as exc:
        repo_acc.marcar(
            accion_id, FALLIDA,
            resultado={"problemas": problemas, "error": f"{type(exc).__name__}: {exc}"},
        )
        raise

    estado = _calcular_estado(respuestas, codigo, repo_gap, repo_contra)
    repo_acc.marcar(
        accion_id, COMPLETADA,
        resultado={"entidades_creadas": len(propuestas), "problemas": problemas, "estado": estado.value},
    )

    return ResultadoDiscovery(
        codigo=codigo, nombre_proyecto=nombre_proyecto,
        entidades_creadas=len(propuestas), estado=estado, problemas=problemas,
    )


def _terna_reapertura(tipo_hallazgo: str, hallazgo_id: int, respuesta_id: int) -> dict:
    return {"tipo_hallazgo": tipo_hallazgo, "hallazgo_id": hallazgo_id, "respuesta_id": respuesta_id}


def procesar_reapertura(
    codigo: str,
    tipo_hallazgo: str,
    hallazgo_id: int,
    cliente: ClienteIA,
    *,
    repo_gaps: Optional[RepositorioGaps] = None,
    repo_contradicciones: Optional[RepositorioContradicciones] = None,
    repo_respuestas: Optional[RepositorioRespuestasFormulario] = None,
    repo_acciones: Optional[RepositorioAcciones] = None,
) -> ResultadoReapertura:
    """Resuelve UNA reapertura puntual — nunca vuelve a procesar el
    formulario completo (`ejecutar_discovery()` sigue siendo la única vía
    que crea las entidades de una corrida; esta función jamás las repite).

    Responder no resuelve automáticamente (TF-0032, corrección explícita):
    una respuesta cerrada distinta de la opción de incertidumbre resuelve;
    la opción de incertidumbre nunca degrada por sí sola a
    `DOCUMENTADO_NO_BLOQUEANTE`; una respuesta libre solo resuelve si la
    interpretación acotada de Qwen no vuelve a señalar el mismo
    `dominio.etiqueta` como hallazgo.

    Idempotencia exacta por `(tipo_hallazgo, hallazgo_id, respuesta_nueva.id)`,
    verificada en dos capas: estado del hallazgo, y existencia previa de una
    acción `resolver_hallazgo_discovery` con esa misma terna.
    """
    repo_gap = repo_gaps if repo_gaps is not None else RepositorioGaps()
    repo_contra = repo_contradicciones if repo_contradicciones is not None else RepositorioContradicciones()
    repo_resp = repo_respuestas if repo_respuestas is not None else RepositorioRespuestasFormulario()
    repo_acc = repo_acciones if repo_acciones is not None else RepositorioAcciones()

    if tipo_hallazgo == "gap":
        hallazgo = repo_gap.obtener(hallazgo_id)
        abierto = hallazgo is not None and hallazgo.estado == EstadoGap.ABIERTO
        campo_o_concepto = hallazgo.campo_o_concepto if hallazgo is not None else None
    elif tipo_hallazgo == "contradiccion":
        hallazgo = repo_contra.obtener(hallazgo_id)
        abierto = hallazgo is not None and hallazgo.estado == EstadoContradiccion.ABIERTA
        campo_o_concepto = hallazgo.concepto if hallazgo is not None else None
    else:
        raise ValueError(f"tipo_hallazgo desconocido: {tipo_hallazgo!r}")

    # --- guardia de idempotencia, capa 1: estado del hallazgo ---
    if hallazgo is None or not abierto:
        return ResultadoReapertura(
            codigo=codigo, tipo_hallazgo=tipo_hallazgo, hallazgo_id=hallazgo_id,
            resuelto=False, ya_procesado=True,
        )

    dominio, etiqueta = _dominio_etiqueta_de(campo_o_concepto)
    pregunta_id = resolver_pregunta(dominio, etiqueta)
    if pregunta_id is None:
        return ResultadoReapertura(
            codigo=codigo, tipo_hallazgo=tipo_hallazgo, hallazgo_id=hallazgo_id,
            resuelto=False, ya_procesado=False,
            problemas=[f"sin pregunta catalogada para {campo_o_concepto!r}"],
        )

    respuestas = repo_resp.listar(codigo)
    respuesta_nueva = _ultima_fila(respuestas, pregunta_id)
    if respuesta_nueva is None:
        return ResultadoReapertura(
            codigo=codigo, tipo_hallazgo=tipo_hallazgo, hallazgo_id=hallazgo_id,
            resuelto=False, ya_procesado=False,
            problemas=["la pregunta reactivada todavía no tiene respuesta"],
        )

    # --- guardia de idempotencia, capa 2: acción ya registrada para esta terna ---
    terna = _terna_reapertura(tipo_hallazgo, hallazgo_id, respuesta_nueva.id)
    for a in repo_acc.listar(ticket=codigo):
        if a["tipo"] == TIPO_ACCION_RESOLVER_HALLAZGO and a["entrada"] and json.loads(a["entrada"]) == terna:
            return ResultadoReapertura(
                codigo=codigo, tipo_hallazgo=tipo_hallazgo, hallazgo_id=hallazgo_id,
                resuelto=False, ya_procesado=True,
            )

    accion_id = repo_acc.registrar(
        ticket=codigo, actor=_ACTOR_REAPERTURA, tipo=TIPO_ACCION_RESOLVER_HALLAZGO, entrada=terna,
    )

    problemas: list = []
    resuelto = False
    resolucion_valor: Optional[str] = None
    hallazgos_encadenados: list = []
    pregunta = PREGUNTAS[pregunta_id]

    try:
        if pregunta.tipo_pregunta == TipoPregunta.OPCION_CERRADA:
            if respuesta_nueva.respuesta not in _OPCIONES_INCERTIDUMBRE:
                resuelto = True
                resolucion_valor = respuesta_nueva.respuesta
            # incierta: permanece ABIERTO/ABIERTA, nunca se degrada aquí.
        else:
            entrada_agente = EntradaAgente(
                ticket=codigo,
                objetivo="Evaluar si esta respuesta resuelve un hallazgo de Discovery",
                contexto=(
                    f"(id={respuesta_nueva.id}) {respuesta_nueva.pregunta_texto}\n"
                    f"{respuesta_nueva.respuesta}"
                ),
            )
            salida = ejecutar_agente(entrada_agente, cliente, InterpreteFormulario(), repositorio=repo_acc)
            problemas.extend(salida.problemas)
            _, hallazgos_llm, problemas_parseo = parsear_entidades(salida.resultado, {respuesta_nueva.id})
            problemas.extend(problemas_parseo)

            # El mismo dominio.etiqueta que seguía sin resolverse decide
            # "resuelto"; cualquier OTRO hallazgo que Qwen señale es una
            # cadena nueva, distinta de esta reapertura (se procesa abajo,
            # sujeta al límite de profundidad — nunca decide si ESTA se
            # resuelve o no).
            sigue_senalado = any(
                _campo_o_concepto(h.dominio, h.etiqueta) == campo_o_concepto for h in hallazgos_llm
            )
            if not sigue_senalado:
                resuelto = True
                resolucion_valor = respuesta_nueva.respuesta
            hallazgos_encadenados = [
                h for h in hallazgos_llm if _campo_o_concepto(h.dominio, h.etiqueta) != campo_o_concepto
            ]

        with LoteDescubrimiento() as lote:
            if tipo_hallazgo == "gap":
                if resuelto:
                    repo_gap.marcar_estado(hallazgo_id, EstadoGap.RESUELTO, conn=lote.conexion)
                # no resuelto: no-op, el Gap permanece ABIERTO tal cual.
            else:
                repo_contra.agregar_afirmacion(
                    hallazgo_id,
                    {"valor": respuesta_nueva.respuesta, "origen": f"respuesta_formulario#{respuesta_nueva.id}"},
                    conn=lote.conexion,
                )
                if resuelto:
                    repo_contra.resolver(
                        hallazgo_id, resolucion_valor=resolucion_valor,
                        resolucion_accion_id=accion_id, conn=lote.conexion,
                    )

            for h_encadenado in hallazgos_encadenados:
                if _profundidad_alcanzada(codigo, repo_gap, repo_contra):
                    problemas.append(
                        f"límite de profundidad de cadena alcanzado — "
                        f"{h_encadenado.dominio}.{h_encadenado.etiqueta} no se encadena en esta corrida"
                    )
                    continue
                _persistir_hallazgo_llm(h_encadenado, codigo=codigo, conexion=lote.conexion, repo_gaps=repo_gap)
    except Exception as exc:
        repo_acc.marcar(accion_id, FALLIDA, resultado={"problemas": problemas, "error": f"{type(exc).__name__}: {exc}"})
        raise

    repo_acc.marcar(accion_id, COMPLETADA, resultado={"resuelto": resuelto, "problemas": problemas})
    return ResultadoReapertura(
        codigo=codigo, tipo_hallazgo=tipo_hallazgo, hallazgo_id=hallazgo_id,
        resuelto=resuelto, ya_procesado=False, problemas=problemas,
    )
