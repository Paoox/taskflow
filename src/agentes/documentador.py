"""TF-0023 — Agente Documentador: primer agente ejecutable.

Dada la información de un ticket (`EntradaAgente`, que aporta el llamador),
produce el borrador de su `docs/tickets/<ticket>.md` como `Artefacto` **en
memoria**. No escribe nada en disco y no afirma haberlo hecho.

Parseo híbrido de `RespuestaIA.texto` (DA-5):

  1. si es un objeto JSON con la clave ``resultado`` -> `SalidaAgente.from_dict`;
  2. en cualquier otro caso -> se envuelve el texto crudo como ``resultado``.

En ambos casos la salida incluye el `Artefacto` `docs/tickets/<ticket>.md` (sin
duplicarlo si el modelo ya lo aportó). `parsear` **no** rellena `meta` (lo hace
el runner) y **no** añade texto propio: `resultado` proviene íntegramente de la
respuesta o de `SalidaAgente.from_dict`.

No importa Flask, `src.database`, `src.app` ni red.
"""
from __future__ import annotations

import json

from src.agentes.contrato import Artefacto, EntradaAgente, SalidaAgente
from src.ai.cliente import RespuestaIA
from src.ai.prompts import cargar_prompt

__all__ = ["Documentador"]

_TIPO_ARTEFACTO = "markdown"


def _ruta_doc(ticket: str) -> str:
    return f"docs/tickets/{ticket}.md"


def _lista(titulo, items):
    if not items:
        return [f"## {titulo}", "(ninguno)"]
    return [f"## {titulo}", *(f"- {x}" for x in items)]


class Documentador:
    """Agente que redacta el borrador de `docs/tickets/<ticket>.md` (en memoria)."""

    nombre = "documentador"
    tipo_accion = "generar_doc_ticket"

    def construir_prompt(self, entrada: EntradaAgente) -> str:
        base = cargar_prompt(self.nombre).rstrip()
        secciones = [
            base,
            "",
            "## Ticket",
            f"- ticket: {entrada.ticket}",
            f"- objetivo: {entrada.objetivo}",
            "",
            "## Contexto",
            entrada.contexto.strip() or "(sin contexto)",
            "",
            *_lista("Restricciones", entrada.restricciones),
            "",
            *_lista("Criterios de aceptación", entrada.criterios_aceptacion),
            "",
            *_lista("Archivos relevantes", entrada.archivos_relevantes),
        ]
        return "\n".join(secciones)

    def parsear(self, respuesta: RespuestaIA, entrada: EntradaAgente) -> SalidaAgente:
        salida = self._parsear_json(respuesta.texto)
        if salida is None:
            salida = SalidaAgente(resultado=respuesta.texto)
        self._asegurar_artefacto(salida, entrada)
        return salida

    @staticmethod
    def _parsear_json(texto):
        """`SalidaAgente` si `texto` es un objeto JSON con `resultado`; si no, `None`."""
        try:
            datos = json.loads(texto)
        except (ValueError, TypeError):
            return None
        if isinstance(datos, dict) and "resultado" in datos:
            return SalidaAgente.from_dict(datos)
        return None

    @staticmethod
    def _asegurar_artefacto(salida, entrada):
        """Añade el `Artefacto` `docs/tickets/<ticket>.md` si no está ya presente."""
        ruta = _ruta_doc(entrada.ticket)
        if any(a.ruta == ruta for a in salida.artefactos):
            return
        salida.artefactos.append(
            Artefacto(ruta=ruta, contenido=salida.resultado, tipo=_TIPO_ARTEFACTO)
        )
