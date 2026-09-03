"""TF-0026 — `RepositorioExpedientes`: persistencia de PROJECT_STATE.

Materializa `ExpedienteProyecto` sobre la tabla `expedientes`. Mismo patrón
que `RepositorioAcciones` (TF-0022): una conexión por operación vía
`get_connection()`, sin ORM ni migraciones; `contenido`/`salud` se guardan
como JSON (mismo criterio que `acciones.entrada`/`resultado`).

`codigo` ("PROY-001", …) se deriva del `id` autoincremental de SQLite: único,
permanente, no depende del nombre y no lo genera el usuario ni este módulo a
mano (`CLAUDE.md` — decisiones aprobadas del checkpoint PROJECT_STATE).

No confundir la tabla `expedientes` con `proyectos` (agrupador de tareas del
CRUD original): son dominios distintos, sin FK entre ellas.

`guardar()` valida las transiciones de `EstadoDato` restringidas
(`src.proyectos.estado.transicion_valida`) comparando contra el registro ya
persistido, **antes** de escribir nada: ante una transición inválida levanta
`TransicionEstadoInvalida` y no toca la fila.
"""
from __future__ import annotations

import json
from datetime import datetime

from src.database import get_connection
from src.proyectos.errores import ExpedienteNoEncontrado, TransicionEstadoInvalida
from src.proyectos.estado import ExpedienteProyecto, transicion_valida

__all__ = ["RepositorioExpedientes"]

_FORMATO_FECHA = "%Y-%m-%d %H:%M:%S"
_PREFIJO_CODIGO = "PROY-"


def _ahora() -> str:
    return datetime.now().strftime(_FORMATO_FECHA)


def _codigo_desde_id(id_: int) -> str:
    return f"{_PREFIJO_CODIGO}{id_:03d}"


def _id_desde_codigo(codigo: str) -> int:
    # Evita `str.removeprefix` (Python 3.9+): el entorno de desarrollo local
    # de Taskflow todavía corre sobre Python 3.8 (ver docs/tickets/TF-0011.md).
    return int(codigo[len(_PREFIJO_CODIGO):])


class RepositorioExpedientes:
    """Acceso a la tabla `expedientes`. Una conexión por operación."""

    def crear(self, nombre: str, descripcion: str = "") -> str:
        """Crea un expediente vacío (disciplinas `UNKNOWN`, checklist
        vigente) y devuelve su `codigo` (p. ej. `"PROY-001"`).
        """
        ahora = _ahora()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            INSERT INTO expedientes
                (nombre, checklist_version, contenido, salud, readiness,
                 estado_general, creado_en, actualizado_en, last_analyzed_at)
            VALUES (?, ?, '{}', NULL, NULL, NULL, ?, ?, NULL)
            """,
            (nombre, ExpedienteProyecto().checklist_version, ahora, ahora),
        )
        id_ = cursor.lastrowid
        codigo = _codigo_desde_id(id_)
        expediente = ExpedienteProyecto(
            codigo=codigo, nombre=nombre, descripcion=descripcion,
            creado_en=ahora, actualizado_en=ahora,
        )
        cursor.execute(
            "UPDATE expedientes SET contenido = ? WHERE id = ?",
            (json.dumps(expediente.to_dict(), ensure_ascii=False), id_),
        )
        conn.commit()
        conn.close()
        return codigo

    def obtener(self, codigo: str) -> ExpedienteProyecto | None:
        """Devuelve el `ExpedienteProyecto` con ese `codigo`, o `None`."""
        conn = get_connection()
        cursor = conn.cursor()
        fila = cursor.execute(
            "SELECT contenido FROM expedientes WHERE id = ?",
            (_id_desde_codigo(codigo),),
        ).fetchone()
        conn.close()
        if fila is None:
            return None
        return ExpedienteProyecto.from_dict(json.loads(fila["contenido"]))

    def guardar(self, expediente: ExpedienteProyecto) -> None:
        """Persiste `expediente` completo.

        Lanza `ExpedienteNoEncontrado` si `expediente.codigo` no corresponde
        a ningún expediente existente — antes de escribir nada. Si existe,
        valida toda transición de `EstadoDato` restringida contra lo ya
        guardado (raíz y cada disciplina); si alguna es inválida, levanta
        `TransicionEstadoInvalida` y tampoco escribe nada.
        """
        actual = self.obtener(expediente.codigo)
        if actual is None:
            raise ExpedienteNoEncontrado(f"no existe ningún expediente con codigo {expediente.codigo!r}")
        self._validar_transiciones(actual, expediente)

        expediente.actualizado_en = _ahora()
        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            "UPDATE expedientes SET contenido = ?, actualizado_en = ? WHERE id = ?",
            (
                json.dumps(expediente.to_dict(), ensure_ascii=False),
                expediente.actualizado_en,
                _id_desde_codigo(expediente.codigo),
            ),
        )
        conn.commit()
        conn.close()

    def guardar_salud(self, codigo: str, salud) -> None:
        """Actualiza las columnas promovidas (`salud`, `readiness`,
        `estado_general`, `last_analyzed_at`) a partir de un `SaludProyecto`
        ya calculado (`src.proyectos.salud.calcular_salud`).

        Lanza `ExpedienteNoEncontrado` si `codigo` no corresponde a ningún
        expediente existente — antes de escribir nada.
        """
        if self.obtener(codigo) is None:
            raise ExpedienteNoEncontrado(f"no existe ningún expediente con codigo {codigo!r}")

        conn = get_connection()
        cursor = conn.cursor()
        cursor.execute(
            """
            UPDATE expedientes
               SET salud = ?, readiness = ?, estado_general = ?, last_analyzed_at = ?
             WHERE id = ?
            """,
            (
                json.dumps(salud.to_dict(), ensure_ascii=False),
                salud.readiness.value,
                salud.estado_general,
                salud.calculado_en,
                _id_desde_codigo(codigo),
            ),
        )
        conn.commit()
        conn.close()

    def listar(self) -> list[dict]:
        """Resumen liviano de todos los expedientes (sin deserializar
        `contenido`), ordenados por `id` ascendente.
        """
        conn = get_connection()
        cursor = conn.cursor()
        filas = cursor.execute(
            "SELECT id, nombre, readiness, estado_general FROM expedientes ORDER BY id ASC"
        ).fetchall()
        conn.close()
        return [
            {
                "codigo": _codigo_desde_id(f["id"]),
                "nombre": f["nombre"],
                "readiness": f["readiness"],
                "estado_general": f["estado_general"],
            }
            for f in filas
        ]

    @staticmethod
    def _validar_transiciones(actual: ExpedienteProyecto, nuevo: ExpedienteProyecto) -> None:
        def _revisar(anteriores, nuevos, etiqueta):
            for campo, dato_nuevo in nuevos.items():
                dato_anterior = anteriores.get(campo)
                if dato_anterior is None:
                    continue
                if not transicion_valida(dato_anterior.estado, dato_nuevo.estado, dato_nuevo.origen):
                    raise TransicionEstadoInvalida(
                        f"transición no permitida en '{etiqueta}.{campo}': "
                        f"{dato_anterior.estado.value} -> {dato_nuevo.estado.value} "
                        f"(origen={dato_nuevo.origen.value})"
                    )

        # El conjunto de claves de `disciplinas` es fijo (`checklist.DISCIPLINAS`)
        # y no varía por `checklist_version` (solo varían los campos esperados
        # DENTRO de cada disciplina): `actual.disciplinas` y `nuevo.disciplinas`
        # siempre comparten las mismas 7 claves.
        _revisar(actual.descubrimiento, nuevo.descubrimiento, "descubrimiento")
        for k, disciplina_nueva in nuevo.disciplinas.items():
            _revisar(actual.disciplinas[k].datos, disciplina_nueva.datos, k)
