"""TF-0032 — Metadata de dominio+etiqueta sobre el catálogo de preguntas ya
existente (`src.formulario.preguntas`), y su resolución hacia un
`pregunta_id` concreto (A1).

Qwen nunca ve el catálogo completo de 27 preguntas: solo ve nombres de
dominio y, por dominio activo en la corrida, su vocabulario cerrado de
etiquetas (`dominios_activos()`). El mapeo etiqueta→`pregunta_id` concreto
lo hace únicamente este módulo (`resolver_pregunta()`), código puro — nunca
Qwen. Una combinación (dominio, etiqueta) sin match no produce ningún
`pregunta_id` (nunca se inventa uno): queda como hallazgo sin pregunta
catalogada, visible para revisión humana del catálogo.

No agrega preguntas nuevas ni modifica `src.formulario`: es una capa de
metadata externa sobre el mismo catálogo de 27 preguntas, agrupada según
los bloques ya existentes en `preguntas.py`. Los controles de bucle puros
(`*_continuar`) quedan deliberadamente fuera — nunca tiene sentido
reactivar "¿hay otro?" como resolución de un hallazgo, solo la pregunta de
contenido real del bloque.

Funciones puras: no abren conexión a BD, no llaman a ningún proveedor de IA.
"""
from __future__ import annotations

from typing import Optional

__all__ = ["CATALOGO_DOMINIOS", "dominios_activos", "resolver_pregunta"]

# pregunta_id -> (dominio, etiqueta). Un dominio puede repetirse en varias
# preguntas; una etiqueta puede repetirse si varias preguntas del mismo
# dominio describen la misma faceta (ej. problema_objetivo /
# objetivo_proyecto_existente comparten "proposito" — solo una de las dos
# aplica según nuevo_o_existente, nunca ambas a la vez).
CATALOGO_DOMINIOS: dict = {
    "nuevo_o_existente": ("identidad", "tipo_proyecto"),
    "referencia_proyecto_existente": ("identidad", "referencia_existente"),
    "nombre_proyecto": ("identidad", "nombre"),
    "problema_objetivo": ("identidad", "proposito"),
    "objetivo_proyecto_existente": ("identidad", "proposito"),

    "plataforma": ("plataforma", "alcance_plataforma"),
    "plataforma_detalle": ("plataforma", "alcance_plataforma"),
    "plataforma_offline": ("plataforma", "modo_offline"),

    "perfil_usuario": ("personas", "tipo_usuario"),

    "administracion_cantidad": ("administracion", "cantidad_admins"),
    "administracion_diferencias": ("administracion", "diferenciacion_roles"),
    "administrador_tipo_nombre": ("administracion", "permisos_admin"),
    "administrador_tipo_acciones": ("administracion", "permisos_admin"),
    "administrador_tipo_otra": ("administracion", "permisos_admin"),

    "funcionalidad_declarada": ("funcionalidad", "funcionalidad_faltante"),

    "monetizacion": ("monetizacion", "modelo_cobro"),
    "monetizacion_forma": ("monetizacion", "modelo_cobro"),

    "dato_recordar": ("datos", "existencia_de_dato"),
    "dato_recordar_detalle": ("datos", "sensibilidad"),

    "restriccion_tecnica": ("restricciones", "restriccion_tecnica"),
    "restriccion_tiempo_presupuesto": ("restricciones", "restriccion_tiempo"),
    "restriccion_negocio": ("restricciones", "restriccion_negocio"),

    "cierre_libre": ("cierre", "informacion_adicional"),
}

# (dominio, etiqueta) -> pregunta_id "canónico" a reactivar. Se construye a
# partir de CATALOGO_DOMINIOS en su orden de declaración: la primera
# pregunta_id de cada combinación es la que se reactiva (ej.
# ("identidad", "proposito") -> "problema_objetivo", la pregunta universal;
# "objetivo_proyecto_existente" solo aplica al caso "ya tengo algo
# construido" y no es el destino canónico de una reapertura genérica).
_MAPA_ETIQUETA_A_PREGUNTA: dict = {}
for _pregunta_id, _clave in CATALOGO_DOMINIOS.items():
    _MAPA_ETIQUETA_A_PREGUNTA.setdefault(_clave, _pregunta_id)


def dominios_activos(respuestas: list) -> dict:
    """Dominios presentes en `respuestas` (ya respondidas) -> tupla
    ordenada de sus etiquetas — el único vocabulario que ve Qwen, nunca el
    catálogo de preguntas en sí."""
    por_dominio: dict = {}
    ids_presentes = {r.pregunta_id for r in respuestas}
    for pregunta_id, (dominio, etiqueta) in CATALOGO_DOMINIOS.items():
        if pregunta_id in ids_presentes:
            por_dominio.setdefault(dominio, set()).add(etiqueta)
    return {dominio: tuple(sorted(etiquetas)) for dominio, etiquetas in por_dominio.items()}


def resolver_pregunta(dominio: str, etiqueta: str) -> Optional[str]:
    """`pregunta_id` a reactivar para `(dominio, etiqueta)`, o `None` si no
    hay ninguna registrada — nunca se inventa una."""
    return _MAPA_ETIQUETA_A_PREGUNTA.get((dominio, etiqueta))
