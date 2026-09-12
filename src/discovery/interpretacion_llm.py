"""Interpretación por LLM de las respuestas de texto libre del formulario.

Primer bloque de Discovery nuevo (ver `src.discovery`). Complementa
`src.discovery.interpretacion_directa`: las respuestas `TEXTO_LIBRE` (y la
única cerrada que solo tiene sentido junto a una de ellas,
`administrador_tipo_acciones`) requieren juicio semántico para convertirse
en `Perfil` / `Requisito` / `Restriccion` / `Dato` — se delegan al agente
`InterpreteFormulario` (`src.agentes.interprete_formulario`).

Este módulo es puro: construye el texto de contexto que recibirá el agente
y parsea+valida su salida. No abre conexión a la base de datos, no llama a
ningún proveedor de IA directamente (eso lo hace `ejecutar_agente`, inyectado
por el llamador) y no importa `src.repositorios` ni `src.discovery.discovery`.

Formato de salida esperado del LLM — mismo criterio ya validado por
`src.orquestador.fusion` para el agente Descubridor (decisión de diseño del
2026-09-02: JSON Lines, nunca un único documento JSON, para que una sola
línea rota no invalide las demás): un objeto JSON por línea,

    {"tipo": "requisito", "respuesta_id": 12, "descripcion": "..."}
    {"tipo": "perfil", "respuesta_id": 15, "nombre": "...", "descripcion": "..."}
    {"tipo": "restriccion", "respuesta_id": 20, "tipo_restriccion": "...", "descripcion": "..."}
    {"tipo": "dato", "respuesta_id": 22, "descripcion": "...", "temporalidad": null, "sensibilidad": null}

`respuesta_id` debe ser exactamente el `id` de una de las filas mostradas en
el contexto (ver `construir_contexto`); cualquier línea cuyo `respuesta_id`
no aparezca en ese conjunto se descarta como información no fundamentada en
lo que la persona declaró (regla 18 del ticket TF-0030: "no inventar") —
nunca se persiste.

TF-0032 (A1/A4) añade un 5º tipo de línea, `"hallazgo"` — Qwen señala un
posible gap/ambigüedad en un `dominio`+`etiqueta` (el vocabulario cerrado de
`src.discovery.catalogo_dominios`, nunca el catálogo de preguntas en sí):

    {"tipo": "hallazgo", "respuesta_id": 23, "dominio": "datos", "etiqueta": "sensibilidad", "motivo": "..."}

El contexto que ve Qwen ahora también incluye, al final, los dominios y
etiquetas activos de esta corrida (`catalogo_dominios.dominios_activos`) —
Qwen nunca ve el catálogo completo de preguntas, solo esos nombres.
"""
from __future__ import annotations

import json
from dataclasses import dataclass

from src.discovery.catalogo_dominios import dominios_activos
from src.discovery.interpretacion_directa import EntidadPropuesta
from src.expediente.modelo import RespuestaFormulario, TipoPregunta
from src.formulario.preguntas import PREGUNTAS
from src.formulario.respuestas import deserializar_respuesta
from src.proyectos.estado import NivelConfianza

__all__ = ["HallazgoLLM", "construir_contexto", "parsear_entidades"]


@dataclass
class HallazgoLLM:
    """Un hallazgo (gap/ambigüedad) que Qwen señaló sobre una respuesta de
    texto libre — nunca una contradicción (comparar dos respuestas ya
    conocidas es trabajo determinista, ver `src.discovery.reglas_consecuencia`).
    Todavía sin resolver a `pregunta_id`: eso lo hace
    `src.discovery.catalogo_dominios.resolver_pregunta`, código puro, nunca
    Qwen."""

    dominio: str
    etiqueta: str
    motivo: str
    respuesta_id: int

# Preguntas que `interpretacion_directa.py` ya consume de forma determinista:
# no deben duplicarse aquí como contexto para el LLM.
_YA_DETERMINISTAS = frozenset({
    "plataforma", "plataforma_detalle", "plataforma_offline",
    "monetizacion", "monetizacion_forma",
})
# Controles de bucle: nunca aportan contenido propio (regla 16 del ticket).
_CONTROL_DE_FLUJO = frozenset({
    "perfil_usuario_continuar", "funcionalidad_declarada_continuar",
    "administrador_tipo_continuar", "dato_recordar_detalle_continuar",
})
# Compuertas del árbol sin contenido propio: solo deciden si se abre un
# bloque; lo declarado vive en las preguntas que desbloquean, no aquí.
_SOLO_COMPUERTA = frozenset({
    "nuevo_o_existente", "administracion_cantidad", "administracion_diferencias",
    "dato_recordar",
})
# `nombre_proyecto` se usa directamente, sin pasar por el LLM (regla 17).
_DIRECTA_SIN_LLM = frozenset({"nombre_proyecto"})

_EXCLUIDAS_DEL_CONTEXTO = _YA_DETERMINISTAS | _CONTROL_DE_FLUJO | _SOLO_COMPUERTA | _DIRECTA_SIN_LLM

_TIPOS_VALIDOS = frozenset({"perfil", "requisito", "restriccion", "dato", "hallazgo"})
# Claves de texto obligatorias por tipo, además de "tipo" y "respuesta_id".
_CAMPOS_REQUERIDOS = {
    "perfil": ("nombre", "descripcion"),
    "requisito": ("descripcion",),
    "restriccion": ("tipo_restriccion", "descripcion"),
    "dato": ("descripcion",),
    "hallazgo": ("dominio", "etiqueta", "motivo"),
}


def _texto_respuesta(fila: RespuestaFormulario) -> str:
    """Texto legible de `fila.respuesta` para mostrar en el contexto.

    Las cerradas (hoy, únicamente `administrador_tipo_acciones` llega hasta
    aquí sin haber sido excluida) se deserializan a su lista de opciones
    elegidas; las de texto libre se usan tal cual.
    """
    pregunta = PREGUNTAS.get(fila.pregunta_id)
    if pregunta is not None and pregunta.tipo_pregunta == TipoPregunta.OPCION_CERRADA:
        valor = deserializar_respuesta(pregunta, fila.respuesta)
        return ", ".join(valor) if isinstance(valor, list) else valor
    return fila.respuesta


def construir_contexto(respuestas: list) -> tuple:
    """Texto de contexto para `InterpreteFormulario` + el conjunto de `id`
    de `respuestas_formulario` efectivamente incluidos (usado por
    `parsear_entidades` para rechazar cualquier `respuesta_id` inventado).

    Solo incluye lo que de verdad requiere interpretación semántica: todo
    `TEXTO_LIBRE` salvo `nombre_proyecto`, más las cerradas sin significado
    autocontenido (hoy, únicamente `administrador_tipo_acciones`) — ver
    docstring del módulo. Devuelve `("", set())` si no hay nada que
    interpretar (el corto-circuito ocurre ANTES de mirar los dominios
    activos: sin texto libre que interpretar, tampoco vale la pena gastar
    una llamada a Qwen solo para reportar hallazgos).

    Cuando sí hay algo que interpretar, se añade al final una sección con
    los dominios+etiquetas activos de esta corrida (TF-0032, A1) — el único
    vocabulario que Qwen ve para el 5º tipo de salida, `"hallazgo"`; nunca
    el catálogo de preguntas en sí.
    """
    relevantes = [r for r in respuestas if r.pregunta_id not in _EXCLUIDAS_DEL_CONTEXTO]
    if not relevantes:
        return "", set()

    bloques = [f"(id={r.id}) {r.pregunta_texto}\n{_texto_respuesta(r)}" for r in relevantes]
    texto = "\n\n".join(bloques)

    activos = dominios_activos(respuestas)
    if activos:
        lineas_dominios = [
            f"- {dominio}: {', '.join(etiquetas)}" for dominio, etiquetas in sorted(activos.items())
        ]
        seccion_dominios = "## Dominios y etiquetas activos para esta corrida\n" + "\n".join(lineas_dominios)
        texto = f"{texto}\n\n{seccion_dominios}"

    return texto, {r.id for r in relevantes}


def _texto_opcional(valor):
    return valor.strip() if isinstance(valor, str) and valor.strip() else None


def _parsear_linea(linea: str, numero: int, ids_validos: set):
    """Parsea una única línea como una entidad propuesta o un hallazgo.
    Devuelve `(entidad_o_None, hallazgo_o_None, problema_o_None)` — nunca
    lanza. Exactamente uno de los dos primeros elementos es distinto de
    `None` cuando no hay problema."""
    try:
        item = json.loads(linea)
    except (ValueError, TypeError):
        return None, None, f"línea {numero}: no es JSON válido, descartada"
    if not isinstance(item, dict):
        return None, None, f"línea {numero}: el JSON no es un objeto, descartada"

    tipo = item.get("tipo")
    if tipo not in _TIPOS_VALIDOS:
        return None, None, f"línea {numero}: tipo {tipo!r} no reconocido, descartada"

    respuesta_id = item.get("respuesta_id")
    if isinstance(respuesta_id, bool) or not isinstance(respuesta_id, int) or respuesta_id not in ids_validos:
        return None, None, (
            f"línea {numero}: respuesta_id {respuesta_id!r} no corresponde a "
            "ninguna respuesta mostrada — posible información inventada, descartada"
        )

    valores = {}
    for clave in _CAMPOS_REQUERIDOS[tipo]:
        valor = item.get(clave)
        if not isinstance(valor, str) or not valor.strip():
            return None, None, f"línea {numero}: falta {clave!r} (o está vacío) para tipo {tipo!r}, descartada"
        valores[clave] = valor.strip()

    if tipo == "hallazgo":
        hallazgo = HallazgoLLM(
            dominio=valores["dominio"], etiqueta=valores["etiqueta"],
            motivo=valores["motivo"], respuesta_id=respuesta_id,
        )
        return None, hallazgo, None

    if tipo == "restriccion":
        campos = {"tipo": valores["tipo_restriccion"], "descripcion": valores["descripcion"]}
    elif tipo == "dato":
        campos = {
            "descripcion": valores["descripcion"],
            "temporalidad": _texto_opcional(item.get("temporalidad")),
            "sensibilidad": _texto_opcional(item.get("sensibilidad")),
        }
    else:
        campos = valores

    entidad = EntidadPropuesta(
        tipo=tipo, campos=campos, confianza=NivelConfianza.MEDIA, respuesta_id=respuesta_id,
    )
    return entidad, None, None


def _desenvolver_bloque_markdown(texto: str) -> str:
    """Igual criterio que `src.orquestador.fusion`: si `texto` es, de
    principio a fin, un único bloque de código Markdown, devuelve su
    contenido; si no, lo devuelve sin tocar."""
    lineas = texto.splitlines()
    if len(lineas) < 3:
        return texto
    if not lineas[0].startswith("```") or lineas[-1].strip() != "```":
        return texto
    return "\n".join(lineas[1:-1])


def parsear_entidades(texto: str, ids_validos: set) -> tuple:
    """Parsea la salida de `InterpreteFormulario` como JSON Lines.

    Tolerante línea por línea (mismo criterio que
    `src.orquestador.fusion.parsear_hallazgos`): una línea con JSON
    inválido, forma inesperada, tipo no reconocido, campos incompletos, o un
    `respuesta_id` que no aparece en `ids_validos`, se descarta y se reporta
    en `problemas` — nunca aborta el resto. Nunca lanza. `texto=""` devuelve
    `([], [], [])`.

    Devuelve `(entidades, hallazgos, problemas)` — TF-0032 separa las
    `EntidadPropuesta` (perfil/requisito/restriccion/dato, ya persistibles
    tal cual) de los `HallazgoLLM` (tipo `"hallazgo"`, que discovery.py debe
    resolver a `pregunta_id` antes de persistir nada).
    """
    texto_efectivo = _desenvolver_bloque_markdown(texto.strip())
    entidades = []
    hallazgos = []
    problemas = []
    for numero, linea_cruda in enumerate(texto_efectivo.splitlines(), start=1):
        linea = linea_cruda.strip()
        if not linea:
            continue
        entidad, hallazgo, problema = _parsear_linea(linea, numero, ids_validos)
        if entidad is not None:
            entidades.append(entidad)
        elif hallazgo is not None:
            hallazgos.append(hallazgo)
        else:
            problemas.append(problema)
    return entidades, hallazgos, problemas
