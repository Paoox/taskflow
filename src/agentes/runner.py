"""TF-0023 — Runner de agentes: `ejecutar_agente`.

Ejecuta *un* agente sobre una `EntradaAgente` con un `ClienteIA` dado, produce una
`SalidaAgente` y registra la ejecución en `acciones` (`registrar` en `EN_CURSO` →
`marcar` en `COMPLETADA` / `FALLIDA`), sellando `Meta`.

Alcance TF-0023: sin proveedor LLM real (el llamador pasa `ClienteEco`), sin CLI,
sin HTTP, sin concurrencia. No modifica ningún contrato existente.

Consume por sus **APIs públicas**: `src.repositorios.acciones` (que usa
`src.database`), `src.agentes.contrato`, `src.ai.cliente` y `src.observabilidad`.
No importa Flask ni `src.app`.
"""
from __future__ import annotations

import time

from src import observabilidad as obs
from src.agentes.base import DefinicionAgente
from src.agentes.contrato import EntradaAgente, Meta, SalidaAgente
from src.ai.cliente import ClienteIA, OpcionesIA
from src.repositorios.acciones import COMPLETADA, FALLIDA, RepositorioAcciones

__all__ = ["ejecutar_agente"]

# Valor con el que `observabilidad.get_correlation_id()` indica "no hay ninguno"
# (== observabilidad._FALLBACK_CID; contrato documentado y estable, pinneado por
# un test de guardarraíl en tests/test_runner.py).
_CID_AUSENTE = "-"


def _entrar_en_correlacion():
    """Devuelve ``(cid_activo, token)``.

    Si no hay ``correlation_id`` activo, fija uno nuevo (``uuid4().hex``) y
    devuelve su ``Token``; si ya hay uno, lo reutiliza y ``token`` es ``None``
    (no se toca el contexto del llamador).
    """
    if obs.get_correlation_id() in ("", _CID_AUSENTE):
        token = obs.set_correlation_id()
        return obs.get_correlation_id(), token
    return obs.get_correlation_id(), None


def _salir_de_correlacion(token):
    """Restaura el contexto de correlación si el runner lo fijó."""
    if token is not None:
        obs.reset_correlation_id(token)


def _construir_meta(cid, duracion_s, *, respuesta, opciones):
    """`Meta` de la ejecución.

    En éxito los valores vienen de `RespuestaIA`; en fallo (`respuesta is None`)
    se usan el `modelo` de `opciones` y ceros. `tokens` es exactamente
    `tokens_entrada + tokens_salida`.
    """
    if respuesta is not None:
        modelo = respuesta.modelo
        tokens = respuesta.tokens_entrada + respuesta.tokens_salida
        coste = respuesta.coste_estimado
    else:
        modelo = opciones.modelo
        tokens = 0
        coste = 0.0
    return Meta(
        modelo=modelo,
        tokens=tokens,
        coste_estimado=coste,
        duracion_s=duracion_s,
        correlation_id=cid,
    )


def ejecutar_agente(
    entrada: EntradaAgente,
    cliente: ClienteIA,
    definicion: DefinicionAgente,
    *,
    opciones: OpcionesIA | None = None,
    repositorio: RepositorioAcciones | None = None,
) -> SalidaAgente:
    """Ejecuta ``definicion`` sobre ``entrada`` con ``cliente`` y registra la
    ejecución en ``acciones``.

    Devuelve la ``SalidaAgente`` producida (``COMPLETADA``) o una ``SalidaAgente``
    de error (``resultado=""``, ``problemas`` no vacío; ``FALLIDA``). No propaga
    excepciones de ``construir_prompt`` / ``completar`` / ``parsear`` / sellado de
    ``Meta`` (D8). Los errores de ``RepositorioAcciones`` (BD) **sí** se propagan.
    """
    opts = opciones or OpcionesIA()
    repo = repositorio if repositorio is not None else RepositorioAcciones()
    logger = obs.obtener_logger()

    cid, token = _entrar_en_correlacion()
    try:
        logger.info(
            "agente inicio agente=%s ticket=%s", definicion.nombre, entrada.ticket
        )
        accion_id = repo.registrar(
            ticket=entrada.ticket,
            actor=f"agente:{definicion.nombre}",
            tipo=definicion.tipo_accion,
            entrada=entrada.to_dict(),
        )

        inicio = time.monotonic()
        try:
            prompt = definicion.construir_prompt(entrada)
            respuesta = cliente.completar(prompt, opts)
            salida = definicion.parsear(respuesta, entrada)
            salida.meta = _construir_meta(
                cid, time.monotonic() - inicio, respuesta=respuesta, opciones=opts
            )
            repo.marcar(accion_id, COMPLETADA, resultado=salida.to_dict())
            logger.info(
                "agente completado agente=%s ticket=%s accion_id=%s",
                definicion.nombre, entrada.ticket, accion_id,
            )
            return salida
        except Exception as exc:  # D8: registrar FALLIDA y devolver salida de error; no relanzar.
            salida = SalidaAgente(
                resultado="",
                problemas=[f"{type(exc).__name__}: {exc}"],
                meta=_construir_meta(
                    cid, time.monotonic() - inicio, respuesta=None, opciones=opts
                ),
            )
            repo.marcar(accion_id, FALLIDA, resultado=salida.to_dict())
            logger.error(
                "agente fallo agente=%s ticket=%s accion_id=%s error=%s",
                definicion.nombre, entrada.ticket, accion_id, exc,
            )
            return salida
    finally:
        _salir_de_correlacion(token)
