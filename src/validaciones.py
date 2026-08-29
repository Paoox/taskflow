"""TF-0007 — Validación de los datos del formulario de creación de tareas.

Función pura, sin dependencias de Flask ni de la base de datos: recibe un mapping
tipo ``request.form`` y el conjunto de ids de proyecto válidos, y devuelve los
datos saneados junto con un diccionario de errores por campo.
"""
from datetime import datetime

PRIORIDADES_VALIDAS = ("Alta", "Media", "Baja")
TITULO_MAX = 200
DESCRIPCION_MAX = 2000
FORMATO_FECHA = "%Y-%m-%d"


def validar_datos_tarea(form, proyecto_ids_validos):
    """Valida y sanea los campos de una tarea nueva.

    Args:
        form: mapping con ``.get(clave)`` (p. ej. ``request.form`` o un ``dict``).
        proyecto_ids_validos: iterable de ids de proyecto existentes.

    Returns:
        (datos, errores) donde ``datos`` es un dict con las claves del
        constructor de ``Tarea`` (``titulo``, ``descripcion``, ``fecha_limite``,
        ``prioridad``, ``proyecto_id``) y ``errores`` es un dict
        ``{campo: mensaje}``. Si ``errores`` está vacío, ``datos`` es apto para
        crear la tarea.
    """
    ids_validos = set(proyecto_ids_validos)
    errores = {}

    titulo = (form.get("titulo") or "").strip()
    if not titulo:
        errores["titulo"] = "El título es obligatorio."
    elif len(titulo) > TITULO_MAX:
        errores["titulo"] = f"El título no puede superar los {TITULO_MAX} caracteres."

    descripcion = (form.get("descripcion") or "").strip()
    if len(descripcion) > DESCRIPCION_MAX:
        errores["descripcion"] = (
            f"La descripción no puede superar los {DESCRIPCION_MAX} caracteres."
        )

    fecha_limite = (form.get("fecha_limite") or "").strip()
    if fecha_limite:
        try:
            datetime.strptime(fecha_limite, FORMATO_FECHA)
        except ValueError:
            errores["fecha_limite"] = "La fecha límite debe tener el formato AAAA-MM-DD."

    prioridad = (form.get("prioridad") or "").strip()
    if prioridad not in PRIORIDADES_VALIDAS:
        errores["prioridad"] = "Selecciona una prioridad válida (Alta, Media o Baja)."

    raw_proyecto_id = (form.get("proyecto_id") or "").strip()
    proyecto_id = None
    if not raw_proyecto_id:
        errores["proyecto_id"] = "Selecciona un proyecto."
    else:
        try:
            proyecto_id = int(raw_proyecto_id)
        except ValueError:
            errores["proyecto_id"] = "El proyecto seleccionado no es válido."
        else:
            if proyecto_id not in ids_validos:
                errores["proyecto_id"] = "El proyecto seleccionado no existe."

    datos = {
        "titulo": titulo,
        "descripcion": descripcion,
        "fecha_limite": fecha_limite or None,
        "prioridad": prioridad,
        "proyecto_id": proyecto_id,
    }
    return datos, errores
