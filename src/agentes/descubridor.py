"""TF-0028 — Agente Descubridor: primer agente de descubrimiento real.

Analiza el contexto disponible en `EntradaAgente` (hoy, vía el Orquestador,
la lista de preguntas pendientes de la raíz de `ExpedienteProyecto`) y
produce hallazgos estructurados en el formato que `src.orquestador.fusion`
(TF-0027) ya sabe interpretar: `{"hallazgos": [...]}`.

`parsear()` es un *passthrough* deliberado: no valida ni interpreta el JSON
de hallazgos aquí (eso ya lo hace `fusion.parsear_hallazgos()`, con manejo de
errores por elemento ya probado en TF-0027). Duplicarlo aquí violaría la
regla de no repetir manejo de errores ya existente.

Este agente no tiene capacidad de inspección real (sin Tools todavía —
TF-0029): solo interpreta lo que ya venga en `entrada.contexto`/
`entrada.archivos_relevantes`. La ausencia de evidencia real en el contexto
actual es una limitación conocida y aceptada para este ticket (ver
`docs/tickets/TF-0028.md`), no algo que este módulo intente compensar.

No importa Flask, `src.database`, `src.app`, `src.orquestador`,
`src.proyectos`, `src.repositorios` ni ningún proveedor de IA concreto
(`ClienteIA` se recibe siempre inyectado por el runner).
"""
from __future__ import annotations

from src.agentes.contrato import EntradaAgente, SalidaAgente
from src.ai.cliente import RespuestaIA
from src.ai.prompts import cargar_prompt

__all__ = ["Descubridor"]


def _lista(titulo, items):
    if not items:
        return [f"## {titulo}", "(ninguno)"]
    return [f"## {titulo}", *(f"- {x}" for x in items)]


class Descubridor:
    """Agente que produce hallazgos de descubrimiento (`{"hallazgos": [...]}`)."""

    nombre = "descubridor"
    tipo_accion = "descubrimiento_proyecto"

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
        """Passthrough puro: `resultado` es el texto crudo del modelo.

        La interpretación del contrato `{"hallazgos": [...]}` (JSON inválido,
        forma inesperada, hallazgos individuales inválidos) es responsabilidad
        exclusiva de `src.orquestador.fusion.parsear_hallazgos()`, que ya la
        implementa y ya la prueba (TF-0027). Este método no la duplica.
        """
        return SalidaAgente(resultado=respuesta.texto)
