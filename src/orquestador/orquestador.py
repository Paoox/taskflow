"""TF-0027 — `ejecutar_orquestador()`: un ciclo de coordinación determinista.

Matriz de decisión (checkpoint de diseño revisado, aprobado):

    1. ¿hay `pending_decision` en la raíz?              -> BLOQUEADO
    2. ¿`salud.next_agent != "ORQUESTADOR"`?             -> HANDOFF
    3. ¿ya existe una investigación previa (COMPLETADA o
       FALLIDA) de este Orquestador para este `codigo`?
         NO  -> INVESTIGAR
         SÍ  -> PREGUNTAR

Por el invariante de `src.orquestador.preguntas` (si el avance de la raíz es
menor a 1.0 y no hay `pending_decision`, `preguntas_pendientes()` nunca está
vacía), esta matriz es total: no hay ningún estado de expediente sin una
acción determinista.

`ejecutar_orquestador()` hace UN ciclo (como `ejecutar_agente()`); repetirlo
es responsabilidad del llamador. `cliente` (`ClienteIA`) y
`agente_descubrimiento` (`DefinicionAgente`) se reciben inyectados: este
módulo no conoce ningún proveedor de IA ni agente concreto (ADR-0001 / punto
15 del checkpoint).

Solo cuando la acción es `INVESTIGAR` se registra una `acción` propia del
Orquestador (vía `RepositorioAcciones`, con `tipo=TIPO_ACCION_ORQUESTAR` y
`actor="orquestador"` — nunca el `tipo`/`actor` del agente inyectado, para no
acoplar la detección de "¿ya investigamos?" a qué agente concreto se usó).
Las demás acciones (HANDOFF/PREGUNTAR/BLOQUEADO) son decisiones puras sin
efecto propio más allá de persistir el snapshot de salud, ya visible en
`expedientes.salud`/`readiness`.

TF-0029 añade `recolector_evidencia` (opcional, default `None`): si se
inyecta, se invoca justo antes de construir `EntradaAgente` para enriquecer
`contexto`/`archivos_relevantes` con evidencia real (`src.tools`, vía
`src.orquestador.evidencia`). Con `recolector_evidencia=None` el
comportamiento es idéntico al de TF-0027. El propio `ejecutar_orquestador`
no ejecuta ninguna Tool directamente: solo invoca la función que le inyectan,
igual que ya hace con `cliente`/`agente_descubrimiento`.

Sin dependencias nuevas. No importa Flask ni `src.app`.
"""
from __future__ import annotations

from datetime import datetime
from typing import Optional

from src.agentes.base import DefinicionAgente
from src.agentes.contrato import EntradaAgente
from src.agentes.runner import ejecutar_agente
from src.ai.cliente import ClienteIA
from src.orquestador.contrato import AccionOrquestador, ResultadoOrquestador
from src.orquestador.evidencia import RecolectorEvidencia
from src.orquestador.fusion import fusionar_hallazgos, parsear_hallazgos
from src.orquestador.preguntas import preguntas_pendientes
from src.proyectos.errores import ExpedienteNoEncontrado, TransicionEstadoInvalida
from src.proyectos.estado import Dato, EstadoDato, NivelConfianza, OrigenDato
from src.proyectos.salud import calcular_salud
from src.repositorios.acciones import COMPLETADA, FALLIDA, RepositorioAcciones
from src.repositorios.expedientes import RepositorioExpedientes

__all__ = [
    "TIPO_ACCION_ORQUESTAR", "TIPO_ACCION_RECOLECTAR_EVIDENCIA",
    "ejecutar_orquestador", "responder_pregunta",
]

# Tipo/actor fijos y propios del Orquestador (no del agente inyectado).
TIPO_ACCION_ORQUESTAR = "orquestar_descubrimiento"
TIPO_ACCION_RECOLECTAR_EVIDENCIA = "recolectar_evidencia"
_ACTOR_ORQUESTADOR = "orquestador"
_ETAPA_ORQUESTADOR = "ORQUESTADOR"

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _ya_investigado(repo_acciones: RepositorioAcciones, codigo: str) -> bool:
    """True si ya existe una ejecución terminal (COMPLETADA o FALLIDA) del
    propio Orquestador para este `codigo`. `EN_CURSO` no cuenta: pudo no
    haber terminado nunca (p. ej. un crash a medio camino) y debe poder
    reintentarse.
    """
    return any(
        a["tipo"] == TIPO_ACCION_ORQUESTAR and a["estado"] in (COMPLETADA, FALLIDA)
        for a in repo_acciones.listar(ticket=codigo)
    )


def _tiene_pending_decision_raiz(expediente) -> bool:
    return any(
        d.estado == EstadoDato.PENDING_DECISION
        for d in expediente.descubrimiento.values()
    )


def ejecutar_orquestador(
    codigo: str,
    cliente: ClienteIA,
    agente_descubrimiento: DefinicionAgente,
    *,
    repo_expedientes: Optional[RepositorioExpedientes] = None,
    repo_acciones: Optional[RepositorioAcciones] = None,
    recolector_evidencia: Optional[RecolectorEvidencia] = None,
) -> ResultadoOrquestador:
    """Ejecuta un ciclo de coordinación sobre el expediente `codigo`.

    Lanza `ExpedienteNoEncontrado` si `codigo` no existe. No reintenta ni
    hace bucle interno.

    `recolector_evidencia` (TF-0029) es opcional; con `None` (default) el
    comportamiento es idéntico al de TF-0027. Si se inyecta, se invoca antes
    de construir `EntradaAgente` para enriquecer `contexto`/
    `archivos_relevantes` con evidencia real (ver `src.orquestador.evidencia`).
    """
    repo_exp = repo_expedientes if repo_expedientes is not None else RepositorioExpedientes()
    repo_acc = repo_acciones if repo_acciones is not None else RepositorioAcciones()

    expediente = repo_exp.obtener(codigo)
    if expediente is None:
        raise ExpedienteNoEncontrado(f"no existe ningún expediente con codigo {codigo!r}")

    salud = calcular_salud(expediente)
    preguntas = preguntas_pendientes(expediente)
    problemas: list[str] = []
    hallazgos_aplicados = 0

    if _tiene_pending_decision_raiz(expediente):
        accion = AccionOrquestador.BLOQUEADO
    elif salud.next_agent != _ETAPA_ORQUESTADOR:
        accion = AccionOrquestador.HANDOFF
    elif _ya_investigado(repo_acc, codigo):
        accion = AccionOrquestador.PREGUNTAR
    else:
        accion = AccionOrquestador.INVESTIGAR

    if accion == AccionOrquestador.INVESTIGAR:
        contexto = "\n".join(f"- {p.campo}: {p.pregunta}" for p in preguntas)
        archivos_relevantes: list[str] = []

        if recolector_evidencia is not None:
            evidencia_id = repo_acc.registrar(
                ticket=codigo, actor=_ACTOR_ORQUESTADOR, tipo=TIPO_ACCION_RECOLECTAR_EVIDENCIA,
            )
            evidencia = recolector_evidencia(expediente, preguntas)
            if evidencia.contexto_adicional:
                contexto = f"{contexto}\n\n{evidencia.contexto_adicional}".strip()
            archivos_relevantes = evidencia.archivos_relevantes
            problemas.extend(evidencia.problemas)
            repo_acc.marcar(
                evidencia_id, COMPLETADA,
                resultado={"archivos_relevantes": archivos_relevantes, "problemas": evidencia.problemas},
            )

        accion_id = repo_acc.registrar(
            ticket=codigo, actor=_ACTOR_ORQUESTADOR, tipo=TIPO_ACCION_ORQUESTAR,
            entrada={"preguntas": [p.to_dict() for p in preguntas]},
        )
        entrada_agente = EntradaAgente(
            ticket=codigo,
            objetivo="Descubrimiento de los campos raíz de PROJECT_STATE",
            contexto=contexto,
            archivos_relevantes=archivos_relevantes,
        )
        salida = ejecutar_agente(entrada_agente, cliente, agente_descubrimiento, repositorio=repo_acc)
        hallazgos, problemas_parseo = parsear_hallazgos(salida.resultado)
        problemas.extend(problemas_parseo)
        problemas.extend(salida.problemas)

        expediente_actualizado, hallazgos_aplicados, problemas_fusion = fusionar_hallazgos(
            expediente, hallazgos
        )
        problemas.extend(problemas_fusion)

        if hallazgos_aplicados > 0:
            try:
                repo_exp.guardar(expediente_actualizado)
            except TransicionEstadoInvalida as exc:
                # Red de seguridad ante una carrera real (BL-19): el
                # expediente cambió en la base entre el `obtener()` de este
                # ciclo y este `guardar()` (p. ej. un humano respondió una
                # pregunta al mismo tiempo). La pre-validación de
                # `fusionar_hallazgos` no puede verla porque valida contra el
                # snapshot leído al inicio del ciclo, no contra la base en
                # el instante del `guardar()`.
                problemas.append(
                    f"fusión descartada por una transición inválida detectada al guardar: {exc}"
                )
                hallazgos_aplicados = 0
            else:
                expediente = expediente_actualizado
                salud = calcular_salud(expediente)
                preguntas = preguntas_pendientes(expediente)

        repo_acc.marcar(
            accion_id, COMPLETADA,
            resultado={"hallazgos_aplicados": hallazgos_aplicados, "problemas": problemas},
        )

    repo_exp.guardar_salud(codigo, salud)

    return ResultadoOrquestador(
        codigo=codigo, accion=accion, salud=salud, preguntas=preguntas,
        problemas=problemas, hallazgos_aplicados=hallazgos_aplicados,
    )


def responder_pregunta(
    repo_expedientes: RepositorioExpedientes,
    codigo: str,
    campo: str,
    valor,
    estado: EstadoDato = EstadoDato.CONFIRMED,
) -> None:
    """Registra la respuesta de una persona a una pregunta pendiente.

    Único punto del sistema donde un `Dato` se construye con
    `origen=OrigenDato.USER`. `estado` por defecto es `CONFIRMED`; el
    llamador puede pasar `EstadoDato.UNKNOWN` (el usuario respondió "no sé":
    debe registrarse como tal, nunca como `NOT_APPLICABLE`) o `NOT_APPLICABLE`
    (el usuario confirma explícitamente que el campo no aplica).
    """
    expediente = repo_expedientes.obtener(codigo)
    if expediente is None:
        raise ExpedienteNoEncontrado(f"no existe ningún expediente con codigo {codigo!r}")

    expediente.descubrimiento[campo] = Dato(
        valor=valor, estado=estado, origen=OrigenDato.USER,
        confianza=NivelConfianza.ALTA, actualizado_en=_ahora(),
    )
    repo_expedientes.guardar(expediente)
