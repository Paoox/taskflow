"""TF-0030 — Agente InterpreteFormulario: segundo agente de Discovery nuevo.

Convierte las respuestas de texto libre del formulario (recibidas ya
armadas en `entrada.contexto` por `src.discovery.discovery`, vía
`src.discovery.interpretacion_llm.construir_contexto`) en entidades
estructuradas del Expediente Maestro, en JSON Lines — mismo contrato de
salida (una línea, un objeto JSON, por entidad) ya validado para el agente
Descubridor.

`parsear()` es un *passthrough* deliberado — mismo criterio que
`src.agentes.descubridor.Descubridor.parsear()`: no valida ni interpreta el
JSON aquí, eso lo hace `src.discovery.interpretacion_llm.parsear_entidades()`
después de `ejecutar_agente()` (evita duplicar el manejo de errores ya
implementado y probado ahí).

No importa Flask, `src.database`, `src.app`, `src.orquestador`,
`src.proyectos`, `src.repositorios` ni `src.discovery` (el propio Discovery
nuevo) — ni ningún proveedor de IA concreto (`ClienteIA` se recibe siempre
inyectado por el runner, `src.agentes.runner.ejecutar_agente`).
"""
from __future__ import annotations

from src.agentes.contrato import EntradaAgente, SalidaAgente
from src.ai.cliente import RespuestaIA
from src.ai.prompts import cargar_prompt

__all__ = ["InterpreteFormulario"]

# Marcas del hueco de respuestas (sección 2 del prompt). El prompt base las
# trae vacías (dos líneas seguidas) y `construir_prompt` inserta el contexto
# de la entrada entre ambas.
_MARCA_RESPUESTAS_INI = "<<<RESPUESTAS_DEL_FORMULARIO"
_MARCA_RESPUESTAS_FIN = "RESPUESTAS_DEL_FORMULARIO>>>"


class InterpreteFormulario:
    """`DefinicionAgente`: interpreta respuestas de texto libre del formulario."""

    nombre = "interprete_formulario"
    tipo_accion = "interpretar_formulario"

    def construir_prompt(self, entrada: EntradaAgente) -> str:
        base = cargar_prompt(self.nombre).rstrip()
        hueco = f"{_MARCA_RESPUESTAS_INI}\n{_MARCA_RESPUESTAS_FIN}"
        relleno = f"{_MARCA_RESPUESTAS_INI}\n{entrada.contexto.strip()}\n{_MARCA_RESPUESTAS_FIN}"
        return base.replace(hueco, relleno, 1)

    def parsear(self, respuesta: RespuestaIA, entrada: EntradaAgente) -> SalidaAgente:
        """Passthrough puro: `resultado` es el texto crudo del modelo.

        La interpretación del contrato JSON Lines (JSON inválido, forma
        inesperada, entidades individuales inválidas) es responsabilidad
        exclusiva de `src.discovery.interpretacion_llm.parsear_entidades()`,
        que ya la implementa y ya la prueba. Este método no la duplica.
        """
        return SalidaAgente(resultado=respuesta.texto)
