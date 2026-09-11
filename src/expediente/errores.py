"""Errores del modelo conceptual nuevo (Requisito/Capacidad/Funcionalidad/...).

Jerarquía propia, sin relación con `src.proyectos.errores` (dominio distinto,
mismo criterio de independencia que el resto de este paquete). Ambas
subclases heredan también de `ValueError` — mismo criterio de tolerancia que
`src.proyectos.errores`.
"""

__all__ = ["ErrorExpediente", "NaturalezaInvalida", "OrigenInvalido"]


class ErrorExpediente(Exception):
    """Base de los errores del modelo conceptual nuevo."""


class NaturalezaInvalida(ErrorExpediente, ValueError):
    """Una entidad recibió una `naturaleza` que su tipo no permite.

    Ejemplos: una `Restriccion` con `naturaleza` distinta de `DECLARADO` (por
    definición, una restricción solo existe si alguien la declaró — nunca se
    deduce ni se propone); una `Capacidad` con `naturaleza=OBSERVADO` (una
    capacidad se deduce o, rara vez, se declara directamente — nunca es en sí
    misma "evidencia observada", eso es un `Dato` o un `Requisito`).
    """


class OrigenInvalido(ErrorExpediente, ValueError):
    """Una entidad recibió un `origen` que su tipo no permite.

    Ejemplo: una `FeaturePropuesta` con `origen` distinto de `AGENT` — por
    definición, una propuesta es iniciativa del sistema; si el usuario la
    pidió directamente, es un `Requisito`, no una propuesta.
    """
