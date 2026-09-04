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

Corrección post-smoke-test (frontera metadata TaskFlow / evidencia del
proyecto): `entrada.ticket` y `entrada.objetivo` son metadata de
coordinación interna (el `codigo` del expediente y el objetivo del ciclo del
Orquestador) y ya NO se insertan dentro de `DATOS_DEL_PROYECTO` —
`construir_prompt()` solo llena esa zona con `entrada.contexto` (que ya trae,
separados por el Orquestador, la comunicación del cliente, las preguntas a
investigar y la evidencia real de Tools) y las listas de restricciones/
criterios/archivos.

No importa Flask, `src.database`, `src.app`, `src.orquestador`,
`src.proyectos`, `src.repositorios` ni ningún proveedor de IA concreto
(`ClienteIA` se recibe siempre inyectado por el runner).
"""
from __future__ import annotations

from src.agentes.contrato import EntradaAgente, SalidaAgente
from src.ai.cliente import RespuestaIA
from src.ai.prompts import cargar_prompt

__all__ = ["Descubridor"]

# Marcas del hueco de datos en `descubridor.md` (sección 2). El prompt base las
# trae vacías (dos líneas seguidas) y `construir_prompt` inserta la evidencia
# de la entrada entre ambas, de modo que las INSTRUCCIONES rodean a los DATOS
# y la sección 8 ("AHORA GENERA") queda siempre como lo último del prompt.
_MARCA_DATOS_INI = "<<<DATOS_DEL_PROYECTO"
_MARCA_DATOS_FIN = "DATOS_DEL_PROYECTO>>>"


def _lista(titulo, items):
    if not items:
        return [f"## {titulo}", "(ninguno)"]
    return [f"## {titulo}", *(f"- {x}" for x in items)]


class Descubridor:
    """Agente que produce hallazgos de descubrimiento (JSON Lines, ver prompt)."""

    nombre = "descubridor"
    tipo_accion = "descubrimiento_proyecto"

    def construir_prompt(self, entrada: EntradaAgente) -> str:
        # `entrada.ticket`/`entrada.objetivo` son metadata de coordinación de
        # TaskFlow (el `codigo` del expediente, p. ej. "PROY-001", y el
        # objetivo interno del ciclo del Orquestador) — NUNCA evidencia del
        # proyecto. Corrección post-smoke-test: a diferencia de versiones
        # anteriores, deliberadamente NO se insertan dentro de
        # DATOS_DEL_PROYECTO (ni en ningún otro lugar del prompt), para que
        # el modelo no pueda interpretarlos como `identidad`/`objetivo` del
        # proyecto del cliente. Todo lo que sí entra en DATOS_DEL_PROYECTO
        # viene exclusivamente de `entrada.contexto` (comunicación del
        # cliente + preguntas a investigar + evidencia real de Tools, ya
        # separadas entre sí por el Orquestador) y de las listas de abajo.
        base = cargar_prompt(self.nombre).rstrip()
        datos = "\n".join([
            "## Evidencia del proyecto",
            entrada.contexto.strip() or "(sin contexto)",
            "",
            *_lista("Restricciones", entrada.restricciones),
            "",
            *_lista("Criterios de aceptación", entrada.criterios_aceptacion),
            "",
            *_lista("Archivos relevantes", entrada.archivos_relevantes),
        ])
        hueco = f"{_MARCA_DATOS_INI}\n{_MARCA_DATOS_FIN}"
        relleno = f"{_MARCA_DATOS_INI}\n{datos}\n{_MARCA_DATOS_FIN}"
        return base.replace(hueco, relleno, 1)

    def parsear(self, respuesta: RespuestaIA, entrada: EntradaAgente) -> SalidaAgente:
        """Passthrough puro: `resultado` es el texto crudo del modelo.

        La interpretación del contrato `{"hallazgos": [...]}` (JSON inválido,
        forma inesperada, hallazgos individuales inválidos) es responsabilidad
        exclusiva de `src.orquestador.fusion.parsear_hallazgos()`, que ya la
        implementa y ya la prueba (TF-0027). Este método no la duplica.
        """
        return SalidaAgente(resultado=respuesta.texto)
