"""TF-0027/TF-0029 — Fusión de hallazgos propuestos por un agente de
descubrimiento.

Contrato esperado en `SalidaAgente.resultado` de cualquier agente de
descubrimiento inyectado en `ejecutar_orquestador()`: **JSON Lines** — un
objeto JSON completo por línea, uno por hallazgo, sin envoltorio de array ni
clave `"hallazgos"`:

    {"campo": "tipo_proyecto", "valor": "CLI", "estado": "confirmed", "origen": "file", "confianza": "ALTA", "notas": "..."}
    {"campo": "identidad", "valor": "Gestor-CLI", "estado": "confirmed", "origen": "file", "confianza": "ALTA"}

Decisión de diseño (investigación del 2026-09-02, smoke test real contra
`qwen2.5:3b`): el formato anterior (`{"hallazgos": [...]}` en un único
documento) hacía que **una sola comilla sin escapar en un solo hallazgo
invalidara el documento entero** — JSON no es recuperable: un error de
sintaxis en cualquier punto rompe el parseo de todo lo demás, aunque el
resto fuera perfectamente válido. JSON Lines resuelve esto por diseño: cada
línea se parsea de forma **independiente**, así que una línea rota solo
pierde esa línea, nunca las demás. Es una solución agnóstica de proveedor
(depende únicamente de qué formato le pedimos al modelo en el prompt, no de
ninguna capacidad especial de Ollama ni de ningún otro proveedor) — no
requiere que el modelo "se comporte mejor": si igual produce una línea rota,
el daño queda contenido a esa línea.

`parsear_hallazgos()` es tolerante línea por línea: ignora líneas vacías;
una línea que no es JSON válido, o cuyo JSON no tiene la forma de un
hallazgo (campo/enum faltante o inválido), se descarta y se reporta en
`problemas` identificando el número de línea — **sin abortar el resto**.
Antes de dividir en líneas, se desenvuelve un único bloque de código
Markdown si envuelve la respuesta completa (con o sin etiqueta de lenguaje,
p. ej. ` ```json ` — comportamiento real observado con `qwen2.5:3b`),
reutilizando `_desenvolver_bloque_markdown`. El desenvolvimiento sigue siendo
**estricto**: nunca busca ni extrae JSON dentro de texto libre con
heurísticas o regex difusa, y nunca "repara" una línea sintácticamente
inválida (p. ej. comillas sin escapar) — esa línea simplemente se descarta.

`fusionar_hallazgos()` (sin cambios) pre-valida cada hallazgo (checklist raíz
vigente, `origen` nunca `user` viniendo de un agente, `transicion_valida()`
de TF-0026) **antes** de aplicarlo a una copia en memoria del expediente, de
modo que un hallazgo inválido nunca invalida el resto del lote ni dispara
`TransicionEstadoInvalida` en `RepositorioExpedientes.guardar()`.

Solo fusiona en `expediente.descubrimiento` (la raíz): un agente de
descubrimiento en TF-0027 no propone datos de disciplinas (fuera de alcance,
le pertenecen a agentes especializados que no existen todavía).

No persiste nada: devuelve el expediente actualizado en memoria, persistirlo
es responsabilidad del llamador (`orquestador.py`).

Sin dependencias nuevas. No importa Flask, `src.database`, `src.app`, `src.ai`
ni `src.agentes`.
"""
from __future__ import annotations

import copy
import json
from dataclasses import dataclass
from datetime import datetime
from typing import Any

from src.proyectos.checklist import campos_esperados
from src.proyectos.estado import (
    Dato,
    EstadoDato,
    ExpedienteProyecto,
    NivelConfianza,
    OrigenDato,
    transicion_valida,
)

__all__ = ["HallazgoPropuesto", "parsear_hallazgos", "fusionar_hallazgos"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


@dataclass
class HallazgoPropuesto:
    """Un hallazgo ya parseado, todavía sin pre-validar contra el expediente.

    Tipo puramente interno a la fusión: nunca se persiste tal cual (se
    convierte en `Dato` solo si sobrevive `fusionar_hallazgos()`); por eso no
    tiene `to_dict`/`from_dict` — no hay nada que lo (de)serialice fuera de
    este módulo.
    """

    campo: str
    valor: Any
    estado: EstadoDato
    origen: OrigenDato
    confianza: NivelConfianza
    notas: str = ""


def _desenvolver_bloque_markdown(texto: str) -> str:
    """Si `texto` es, de principio a fin, un único bloque de código Markdown
    (primera línea `` ``` `` u `` ```<etiqueta> ``, última línea exactamente
    `` ``` ``), devuelve el contenido entre ambas líneas. Si no, devuelve
    `texto` sin tocar.

    Estricto a propósito: no es una búsqueda de JSON dentro de texto libre —
    si hay cualquier prosa antes o después del bloque, la primera o la última
    línea no coinciden con el patrón y la función es un no-op.
    """
    lineas = texto.splitlines()
    if len(lineas) < 3:
        return texto
    if not lineas[0].startswith("```") or lineas[-1].strip() != "```":
        return texto
    return "\n".join(lineas[1:-1])


def _parsear_linea(linea: str, numero: int) -> tuple[HallazgoPropuesto | None, str | None]:
    """Parsea una única línea como un hallazgo. Devuelve `(hallazgo, None)`
    si es válida, o `(None, problema)` si no — nunca lanza.
    """
    try:
        item = json.loads(linea)
    except (ValueError, TypeError):
        return None, f"línea {numero}: no es JSON válido, descartada"

    if not isinstance(item, dict):
        return None, f"línea {numero}: el JSON no es un objeto, descartada"

    try:
        return HallazgoPropuesto(
            campo=item["campo"],
            valor=item["valor"],
            estado=EstadoDato(item["estado"]),
            origen=OrigenDato(item["origen"]),
            confianza=NivelConfianza(item["confianza"]),
            notas=item.get("notas", ""),
        ), None
    except (KeyError, ValueError) as exc:
        return None, f"línea {numero}: hallazgo inválido ({exc}), descartada"


def parsear_hallazgos(texto: str) -> tuple[list[HallazgoPropuesto], list[str]]:
    """Parsea `texto` (se espera `SalidaAgente.resultado`) como JSON Lines:
    un objeto JSON de hallazgo por línea. Nunca lanza: una línea con JSON
    inválido, con forma inesperada, o con un valor de enum no reconocido se
    reporta en `problemas` (identificando el número de línea) y **no
    detiene el parseo de las demás líneas** — es exactamente la propiedad
    que motivó este formato (una línea rota nunca invalida las demás).

    Tolera un único bloque de código Markdown envolviendo la respuesta
    completa (ver `_desenvolver_bloque_markdown`) antes de dividir en
    líneas. Las líneas vacías se ignoran sin generar ningún problema.
    """
    texto_efectivo = _desenvolver_bloque_markdown(texto.strip())

    hallazgos: list[HallazgoPropuesto] = []
    problemas: list[str] = []
    for numero, linea_cruda in enumerate(texto_efectivo.splitlines(), start=1):
        linea = linea_cruda.strip()
        if not linea:
            continue
        hallazgo, problema = _parsear_linea(linea, numero)
        if hallazgo is not None:
            hallazgos.append(hallazgo)
        else:
            problemas.append(problema)
    return hallazgos, problemas


def fusionar_hallazgos(
    expediente: ExpedienteProyecto, hallazgos: list[HallazgoPropuesto],
) -> tuple[ExpedienteProyecto, int, list[str]]:
    """Pre-valida cada hallazgo y los fusiona en una COPIA de `expediente`.

    Devuelve `(expediente_actualizado, cantidad_aplicada, problemas)`.
    `expediente` (el original) nunca se muta.
    """
    problemas: list[str] = []
    esperados = set(campos_esperados(expediente.checklist_version)["_raiz"])
    actualizado = copy.deepcopy(expediente)
    aplicados = 0

    for h in hallazgos:
        if h.campo not in esperados:
            problemas.append(f"campo '{h.campo}' no pertenece al checklist raíz: descartado")
            continue

        origen = h.origen
        if origen == OrigenDato.USER:
            problemas.append(
                f"hallazgo de agente para '{h.campo}' reclamaba origen=user: forzado a agent"
            )
            origen = OrigenDato.AGENT

        anterior = actualizado.descubrimiento.get(h.campo)
        if anterior is not None and not transicion_valida(anterior.estado, h.estado, origen):
            problemas.append(
                f"transición no permitida en '{h.campo}': "
                f"{anterior.estado.value} -> {h.estado.value} (origen={origen.value}): descartado"
            )
            continue

        actualizado.descubrimiento[h.campo] = Dato(
            valor=h.valor, estado=h.estado, origen=origen,
            confianza=h.confianza, actualizado_en=_ahora(), notas=h.notas,
        )
        aplicados += 1

    return actualizado, aplicados, problemas
