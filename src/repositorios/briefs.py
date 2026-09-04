"""`RepositorioBriefs`: persistencia append-only del brief del cliente.

Materializa `EntradaBrief` (`src.proyectos.brief`) sobre la tabla `briefs`.
Mismo patrón que `RepositorioAcciones`/`RepositorioExpedientes`: una conexión
por operación vía `get_connection()`, sin ORM ni migraciones, vínculo flojo a
`codigo` (string "PROY-XXX", sin FK — igual criterio que `acciones.ticket`).

Append-only por contrato: esta clase **no** expone ninguna operación de
actualización ni borrado sobre una `EntradaBrief` ya registrada — la
inmutabilidad se garantiza por ausencia de esas operaciones, mismo criterio
que ya usa el resto del repositorio (las transiciones de `EstadoDato` se
validan en Python, no con `CHECK`/triggers de SQLite).

`registrar()` asigna `ronda` de forma determinista (siguiente entero libre
para ese `codigo`) y rechaza un segundo `INICIAL` para el mismo `codigo`
(`BriefInicialYaExiste`) **antes** de escribir nada.

No valida que `codigo` corresponda a un expediente existente en
`RepositorioExpedientes`: mismo desacoplamiento entre dominios que ya existe
entre `acciones` y `expedientes` (tablas de dominios distintos, sin FK entre
ellas).
"""
from __future__ import annotations

from datetime import datetime

from src.database import get_connection
from src.proyectos.brief import EntradaBrief, TipoEntradaBrief
from src.proyectos.errores import BriefInicialYaExiste
from src.proyectos.estado import OrigenDato

__all__ = ["RepositorioBriefs"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _fila_a_entrada(fila) -> EntradaBrief:
    return EntradaBrief(
        id=fila["id"],
        codigo=fila["codigo"],
        ronda=fila["ronda"],
        tipo=TipoEntradaBrief(fila["tipo"]),
        texto=fila["texto"],
        origen=OrigenDato(fila["origen"]),
        recibido_en=fila["recibido_en"],
    )


class RepositorioBriefs:
    """Acceso a la tabla `briefs`. Una conexión por operación. Append-only."""

    def registrar(
        self,
        codigo: str,
        texto: str,
        *,
        tipo: TipoEntradaBrief = TipoEntradaBrief.INICIAL,
        origen: OrigenDato = OrigenDato.USER,
    ) -> EntradaBrief:
        """Registra una nueva entrada de brief para `codigo` y la devuelve.

        `texto` se guarda **verbatim**, sin normalizar ni recortar. `ronda`
        la asigna este método (siguiente entero libre para `codigo`; nunca
        el llamador). Lanza `BriefInicialYaExiste` —antes de escribir nada—
        si `tipo=INICIAL` y ya existe un `INICIAL` registrado para `codigo`.
        """
        conn = get_connection()
        cursor = conn.cursor()
        filas = cursor.execute(
            "SELECT tipo, ronda FROM briefs WHERE codigo = ? ORDER BY ronda ASC",
            (codigo,),
        ).fetchall()

        if tipo == TipoEntradaBrief.INICIAL and any(
            f["tipo"] == TipoEntradaBrief.INICIAL.value for f in filas
        ):
            conn.close()
            raise BriefInicialYaExiste(
                f"ya existe un brief inicial registrado para el expediente {codigo!r}"
            )

        ronda = (filas[-1]["ronda"] if filas else 0) + 1
        recibido_en = _ahora()
        cursor.execute(
            """
            INSERT INTO briefs (codigo, ronda, tipo, texto, origen, recibido_en)
            VALUES (?, ?, ?, ?, ?, ?)
            """,
            (codigo, ronda, tipo.value, texto, origen.value, recibido_en),
        )
        id_ = cursor.lastrowid
        conn.commit()
        conn.close()
        return EntradaBrief(
            id=id_, codigo=codigo, ronda=ronda, tipo=tipo,
            texto=texto, origen=origen, recibido_en=recibido_en,
        )

    def listar(self, codigo: str) -> list[EntradaBrief]:
        """Todas las entradas de brief de `codigo`, ordenadas por ronda ascendente."""
        conn = get_connection()
        cursor = conn.cursor()
        filas = cursor.execute(
            "SELECT * FROM briefs WHERE codigo = ? ORDER BY ronda ASC",
            (codigo,),
        ).fetchall()
        conn.close()
        return [_fila_a_entrada(f) for f in filas]

    def brief_inicial(self, codigo: str) -> EntradaBrief | None:
        """El `EntradaBrief` con `tipo=INICIAL` de `codigo`, o `None` si no existe."""
        conn = get_connection()
        cursor = conn.cursor()
        fila = cursor.execute(
            "SELECT * FROM briefs WHERE codigo = ? AND tipo = ? ORDER BY ronda ASC LIMIT 1",
            (codigo, TipoEntradaBrief.INICIAL.value),
        ).fetchone()
        conn.close()
        return _fila_a_entrada(fila) if fila is not None else None
