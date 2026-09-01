"""TF-0022 — `RepositorioAcciones`: registro persistente de ejecuciones.

Materializa la trazabilidad de `CLAUDE.md` §28: cada ejecución relevante (humana o
de agente) asociada a un `ticket` queda registrada y es consultable. Es
**infraestructura de trazabilidad, no parte del dominio de tareas/proyectos**.

Diseño (TF-0022, decisiones aprobadas D1–D17):

* una sola tabla `acciones`, creada por `crear_tablas()` en `src.database`
  (`CREATE TABLE IF NOT EXISTS`, sin ORM ni migraciones);
* patrón "una conexión por operación" vía `get_connection()` (respeta
  `PRAGMA foreign_keys = ON`); sin capa de sesión / unit-of-work;
* `entrada` / `resultado` se guardan como texto: un `dict` / `list` se serializa
  con `json.dumps`; un `str` se guarda **verbatim**; `None` es `NULL`. La lectura
  (`obtener` / `listar`) devuelve ese texto **crudo**: deserializar es del
  llamador;
* estados válidos `{EN_CURSO, COMPLETADA, FALLIDA}`, validados **solo en Python**
  (sin `CHECK` en el esquema);
* fechas en formato `%Y-%m-%d %H:%M:%S` con hora local naive (igual que
  `src.modelos`).

**No** importa las dataclasses de TF-0021 ni Flask ni `app`. `DBManager` no
importa este módulo (sin dependencia circular).
"""
import json
from datetime import datetime

from src.database import get_connection

# Estados válidos de una acción (validados en Python; sin CHECK en el esquema).
EN_CURSO = "EN_CURSO"
COMPLETADA = "COMPLETADA"
FALLIDA = "FALLIDA"
ESTADOS = frozenset({EN_CURSO, COMPLETADA, FALLIDA})

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"


def _ahora():
    """Marca de tiempo actual, hora local naive, `%Y-%m-%d %H:%M:%S`."""
    return datetime.now().strftime(_FORMATO_FECHA)


def _serializar(valor):
    """Prepara `entrada` / `resultado` para almacenarlos como texto.

    - `None` -> `None` (se guarda como `NULL`);
    - `str` -> se devuelve **verbatim** (se asume JSON ya serializado; no se valida);
    - `dict` / `list` -> `json.dumps(valor, ensure_ascii=False)`;
    - cualquier otro tipo -> `TypeError`.
    """
    if valor is None or isinstance(valor, str):
        return valor
    if isinstance(valor, (dict, list)):
        return json.dumps(valor, ensure_ascii=False)
    raise TypeError(
        "entrada/resultado debe ser dict, list, str o None; "
        f"recibido {type(valor).__name__}"
    )


class RepositorioAcciones:
    """Acceso a la tabla `acciones`. Una conexión por operación."""

    def registrar(self, ticket, actor, tipo, entrada=None):
        """Crea una acción en estado `EN_CURSO` y devuelve su `id` (int).

        `creado_en` = ahora; `actualizado_en` y `resultado` quedan a `NULL`.
        """
        entrada_txt = _serializar(entrada)
        creado_en = _ahora()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO acciones
                (ticket, actor, tipo, entrada, resultado, estado, creado_en, actualizado_en)
            VALUES (?, ?, ?, ?, NULL, ?, ?, NULL)
            """,
            (ticket, actor, tipo, entrada_txt, EN_CURSO, creado_en),
        )
        accion_id = cursor.lastrowid
        conn.commit()
        conn.close()
        return accion_id

    def marcar(self, accion_id, estado, resultado=None):
        """Actualiza `estado` (+ `actualizado_en`, + `resultado` si se pasa).

        - `estado` fuera de `ESTADOS` -> `ValueError` (**antes** de abrir la
          conexión; no escribe nada).
        - `resultado=None` -> **no** se toca la columna `resultado`.
        - Devuelve `True` si el `id` existía, `False` si no.
        """
        if estado not in ESTADOS:
            raise ValueError(
                f"estado no válido: {estado!r}; debe ser uno de {sorted(ESTADOS)}"
            )
        actualizado_en = _ahora()
        conn = get_connection()
        cursor = conn.cursor()
        if resultado is None:
            cursor.execute(
                "UPDATE acciones SET estado = ?, actualizado_en = ? WHERE id = ?",
                (estado, actualizado_en, accion_id),
            )
        else:
            cursor.execute(
                "UPDATE acciones SET estado = ?, resultado = ?, actualizado_en = ? "
                "WHERE id = ?",
                (estado, _serializar(resultado), actualizado_en, accion_id),
            )
        conn.commit()
        afectadas = cursor.rowcount
        conn.close()
        return afectadas > 0

    def obtener(self, accion_id):
        """Devuelve la acción como `dict` (9 claves = columnas) o `None`.

        `entrada` / `resultado` se devuelven **tal cual se almacenaron** (texto
        JSON o `None`); deserializar es responsabilidad del llamador.
        """
        conn = get_connection()
        cursor = conn.cursor()
        fila = cursor.execute(
            "SELECT * FROM acciones WHERE id = ?", (accion_id,)
        ).fetchone()
        conn.close()
        return dict(fila) if fila is not None else None

    def listar(self, ticket=None):
        """Lista de acciones como `dict`, ordenadas por `id` ascendente.

        `ticket=None` devuelve todas; un `ticket` concreto filtra por él.
        """
        conn = get_connection()
        cursor = conn.cursor()
        if ticket is None:
            filas = cursor.execute(
                "SELECT * FROM acciones ORDER BY id ASC"
            ).fetchall()
        else:
            filas = cursor.execute(
                "SELECT * FROM acciones WHERE ticket = ? ORDER BY id ASC", (ticket,)
            ).fetchall()
        conn.close()
        return [dict(fila) for fila in filas]
