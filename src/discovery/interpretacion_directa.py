"""Interpretación determinista de respuestas cerradas del formulario.

Primer bloque de Discovery nuevo (`respuestas_formulario -> Discovery ->
Expediente Maestro`, ver `src.discovery`): convierte en propuestas de
entidades del modelo nuevo (`src.expediente.modelo`) las respuestas
`OPCION_CERRADA` del árbol cuyo significado es completo por sí solo — el
texto de la opción elegida ya es, literalmente, la afirmación que se
persiste, sin que haga falta ningún juicio semántico.

Regla de alcance (aprobada, ticket TF-0030, sin cambios en TF-0033): solo se
interpretan aquí `plataforma` (+ `plataforma_detalle`), `plataforma_offline`,
`monetizacion` y `monetizacion_forma` — los mismos 5 `pregunta_id`,
conservados verbatim por el catálogo nuevo de 16 dominios
(`docs/tickets/TF-0033.md`) precisamente para no tener que tocar este
módulo. Las demás preguntas cerradas quedan fuera por diseño: los controles
de bucle (`*_continuar`) nunca aportan contenido propio; las "compuertas"
del árbol (`nuevo_o_existente`, `personas_gate`, `contenido_gate`,
`dato_recordar`, y el resto de gates del catálogo nuevo) solo deciden si se
abre un bloque, no declaran nada por sí mismas. TF-0033 retiró el único caso
de "cerrada sin significado autocontenido" que existía en TF-0030
(`administrador_tipo_acciones`, emparejada con `administrador_tipo_nombre`)
junto con todo el bloque `administrador_tipo_*`/`administracion_*`: el
dominio 06 nuevo no tiene un caso equivalente.

No convertir automáticamente cualquier respuesta cerrada en una entidad es
una regla explícita del checkpoint aprobado, no un descuido.

Funciones puras: no abren conexión a la base de datos, no llaman a ningún
proveedor de IA, no importan `src.repositorios` ni `src.discovery.discovery`.
No modifican `src.formulario` — solo reutilizan su catálogo y su
(de)serialización públicos.
"""
from __future__ import annotations

from dataclasses import dataclass
from typing import Optional

from src.expediente.modelo import RespuestaFormulario
from src.formulario.preguntas import (
    OPCION_DETALLE_CELULAR,
    OPCION_MONETIZACION_SI,
    OPCION_PLATAFORMA_CELULAR,
    OPCION_PLATAFORMA_COMPUTADORA,
    OPCION_PLATAFORMA_NAVEGADOR,
    OPCION_PLATAFORMA_VARIAS,
    OPCION_SI,
    PREGUNTAS,
)
from src.formulario.respuestas import deserializar_respuesta
from src.proyectos.estado import NivelConfianza

__all__ = ["EntidadPropuesta", "interpretar_directo"]


@dataclass
class EntidadPropuesta:
    """Una entidad del Expediente Maestro todavía sin persistir.

    `tipo` es uno de `"perfil"`, `"requisito"`, `"restriccion"`, `"dato"` —
    los únicos que produce este primer bloque de Discovery (`Capacidad` /
    `Funcionalidad` / `Relacion` / `Gap` / `Contradiccion` /
    `FeaturePropuesta` / `EstadoObservado` quedan fuera, ver
    `docs/tickets/TF-0030.md`). `campos` son los argumentos propios de
    `Repositorio<Tipo>.crear()` (sin `codigo`/`naturaleza`/`origen`/
    `confianza`/`accion_id_origen`/`fuente_directa`/`conn`, que decide
    `src.discovery.discovery` de forma uniforme para toda propuesta).
    `respuesta_id` es el `id` de la fila `respuestas_formulario` de la que
    sale, usado para construir su `FuenteDirecta`.
    """

    tipo: str
    campos: dict
    confianza: NivelConfianza
    respuesta_id: int


def _fila(respuestas: list, pregunta_id: str) -> Optional[RespuestaFormulario]:
    """Última fila de `pregunta_id` en `respuestas`, o `None` si no está."""
    de_esta = [r for r in respuestas if r.pregunta_id == pregunta_id]
    return de_esta[-1] if de_esta else None


def _requisito(fila: RespuestaFormulario, descripcion: str) -> EntidadPropuesta:
    return EntidadPropuesta(
        tipo="requisito", campos={"descripcion": descripcion},
        confianza=NivelConfianza.ALTA, respuesta_id=fila.id,
    )


# Texto fijo por opción de `plataforma` (pregunta de elección única).
_TEXTO_PLATAFORMA = {
    OPCION_PLATAFORMA_NAVEGADOR: "El sistema debe poder usarse desde un navegador web.",
    OPCION_PLATAFORMA_CELULAR: "El sistema debe poder usarse desde un celular.",
    OPCION_PLATAFORMA_COMPUTADORA: (
        "El sistema debe poder usarse desde una computadora (programa instalado)."
    ),
}
# `plataforma_detalle` reutiliza el mismo significado con su propio texto de
# opción (p. ej. "Celular" en vez de "Desde el celular" — ver
# `src.formulario.preguntas`).
_TEXTO_PLATAFORMA_DETALLE = {
    OPCION_PLATAFORMA_NAVEGADOR: _TEXTO_PLATAFORMA[OPCION_PLATAFORMA_NAVEGADOR],
    OPCION_DETALLE_CELULAR: _TEXTO_PLATAFORMA[OPCION_PLATAFORMA_CELULAR],
    OPCION_PLATAFORMA_COMPUTADORA: _TEXTO_PLATAFORMA[OPCION_PLATAFORMA_COMPUTADORA],
}

# TF-0033: `monetizacion_forma` amplió sus opciones de 4 a 7 (dominio 05 de
# "Discovery Inteligente"). Mismo criterio: texto fijo por opción, sin
# interpretación.
_TEXTO_MONETIZACION_FORMA = {
    "Pago único": "El cobro debe hacerse como un pago único.",
    "Suscripción": "El cobro debe hacerse como una suscripción con pago recurrente.",
    "Según uso": "El cobro debe depender del uso que la persona le dé al proyecto.",
    "Comisión": "El cobro debe hacerse como una comisión sobre alguna transacción.",
    "Anuncios": "El proyecto debe generar ingresos mostrando anuncios.",
    "Donaciones": "El proyecto debe permitir recibir donaciones.",
    "Combinación": "El cobro debe combinar más de una de estas formas.",
}


def _requisitos_plataforma(respuestas: list) -> list:
    fila_plataforma = _fila(respuestas, "plataforma")
    if fila_plataforma is None:
        return []

    if fila_plataforma.respuesta in _TEXTO_PLATAFORMA:
        return [_requisito(fila_plataforma, _TEXTO_PLATAFORMA[fila_plataforma.respuesta])]

    if fila_plataforma.respuesta != OPCION_PLATAFORMA_VARIAS:
        return []  # "No estoy seguro todavía": nada que declarar (regla 18/19).

    fila_detalle = _fila(respuestas, "plataforma_detalle")
    if fila_detalle is None:
        return []
    seleccionadas = deserializar_respuesta(PREGUNTAS["plataforma_detalle"], fila_detalle.respuesta)
    return [
        _requisito(fila_detalle, _TEXTO_PLATAFORMA_DETALLE[opcion])
        for opcion in seleccionadas
        if opcion in _TEXTO_PLATAFORMA_DETALLE
    ]


def _requisito_offline(respuestas: list) -> list:
    fila = _fila(respuestas, "plataforma_offline")
    if fila is None or fila.respuesta != OPCION_SI:
        return []
    return [_requisito(fila, "El sistema debe poder usarse sin conexión a internet (modo offline).")]


def _requisitos_monetizacion(respuestas: list) -> list:
    fila_monetiza = _fila(respuestas, "monetizacion")
    if fila_monetiza is None or fila_monetiza.respuesta != OPCION_MONETIZACION_SI:
        return []
    propuestas = [_requisito(fila_monetiza, "El proyecto debe permitir cobrar de alguna forma.")]

    fila_forma = _fila(respuestas, "monetizacion_forma")
    if fila_forma is not None and fila_forma.respuesta in _TEXTO_MONETIZACION_FORMA:
        propuestas.append(_requisito(fila_forma, _TEXTO_MONETIZACION_FORMA[fila_forma.respuesta]))
    return propuestas


def interpretar_directo(respuestas: list) -> list:
    """Entidades deterministas derivadas de respuestas cerradas autocontenidas.

    Nunca llama a ningún proveedor de IA — esta función ni siquiera recibe
    un `ClienteIA`. `confianza` siempre `NivelConfianza.ALTA` (regla 15 del
    ticket TF-0030): una opción cerrada elegida por la persona no admite
    grados de interpretación.
    """
    return [
        *_requisitos_plataforma(respuestas),
        *_requisito_offline(respuestas),
        *_requisitos_monetizacion(respuestas),
    ]
