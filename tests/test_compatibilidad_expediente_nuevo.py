"""Compatibilidad entre el modelo conceptual nuevo (`src.expediente`) y la
persistencia existente.

Verifica el requisito explícito del checkpoint: el checklist raíz antiguo
(`EstadoDato`, `campos_esperados()`, `ExpedienteProyecto.descubrimiento`)
sigue funcionando exactamente igual, sin que las tablas nuevas lo toquen, y
sin ningún mecanismo de sincronización entre ambos modelos.
"""
import sqlite3

import pytest

from src.expediente.modelo import NaturalezaInformacion
from src.proyectos.estado import (
    AplicabilidadDisciplina, Dato as DatoAntiguo, EstadoDato, NivelConfianza, OrigenDato,
)
from src.repositorios.expedientes import RepositorioExpedientes
from src.repositorios.requisitos import RepositorioRequisitos

_TABLAS_NUEVAS = (
    "respuestas_formulario", "perfiles", "requisitos", "capacidades",
    "funcionalidades", "datos", "restricciones", "features_propuestas",
    "gaps", "contradicciones", "relaciones", "estado_observado_versiones",
)

_TABLAS_ANTIGUAS = ("proyectos", "tareas", "acciones", "expedientes", "briefs")


class TestTodasLasTablasCoexisten:
    def test_crear_tablas_crea_las_12_tablas_nuevas(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        existentes = {
            fila[0] for fila in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        for tabla in _TABLAS_NUEVAS:
            assert tabla in existentes, f"falta la tabla nueva {tabla!r}"

    def test_las_tablas_antiguas_siguen_existiendo(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        existentes = {
            fila[0] for fila in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table'"
            ).fetchall()
        }
        conn.close()
        for tabla in _TABLAS_ANTIGUAS:
            assert tabla in existentes, f"la tabla antigua {tabla!r} desapareció"

    def test_crear_tablas_es_idempotente_con_el_esquema_ampliado(self, db):
        """Ejecutar `crear_tablas()` de nuevo (mismo patrón `CREATE TABLE IF
        NOT EXISTS`) no debe lanzar ni duplicar nada."""
        import src.database as database
        database.crear_tablas()
        database.crear_tablas()  # segunda vez, no debe fallar


class TestExpedienteAntiguoSinTocar:
    """El checklist raíz (`ExpedienteProyecto.descubrimiento`) sigue
    funcionando exactamente igual — el modelo nuevo no lo alimenta ni lo
    duplica."""

    def test_repositorio_expedientes_sigue_funcionando_igual(self, db):
        repo = RepositorioExpedientes()
        codigo = repo.crear("Demo")
        e = repo.obtener(codigo)
        e.descubrimiento["identidad"] = DatoAntiguo(
            valor="Demo", estado=EstadoDato.CONFIRMED, origen=OrigenDato.USER,
            confianza=NivelConfianza.ALTA, actualizado_en="2026-09-10 10:00:00",
        )
        repo.guardar(e)

        recargado = repo.obtener(codigo)
        assert recargado.descubrimiento["identidad"].estado == EstadoDato.CONFIRMED
        for r in recargado.disciplinas.values():
            assert r.aplicabilidad == AplicabilidadDisciplina.UNKNOWN

    def test_ambos_modelos_conviven_bajo_el_mismo_codigo_sin_mezclarse(self, db):
        """Un mismo `codigo` de expediente puede tener fila en `expedientes`
        (modelo antiguo) Y filas en `requisitos` (modelo nuevo) — sin FK
        entre ambos, sin que uno lea al otro."""
        repo_exp = RepositorioExpedientes()
        repo_req = RepositorioRequisitos()

        codigo = repo_exp.crear("Demo")
        repo_req.crear(
            codigo, "el usuario puede sumar dos numeros",
            NaturalezaInformacion.DECLARADO, OrigenDato.USER, NivelConfianza.ALTA,
        )

        expediente = repo_exp.obtener(codigo)
        requisitos = repo_req.listar(codigo)
        assert expediente is not None
        assert len(requisitos) == 1
        # el expediente antiguo no sabe nada de los requisitos nuevos
        assert "requisitos" not in expediente.to_dict()
        assert expediente.descubrimiento == {}


class TestSinSincronizacionBidireccional:
    """Verificación estructural: los módulos nuevos no importan `EstadoDato`
    ni `campos_esperados()` en su propio namespace (solo reutilizan el
    vocabulario puro `OrigenDato`/`NivelConfianza`) — se comprueba contra los
    símbolos realmente importados, no contra texto de docstrings que
    documentan la decisión (esos sí nombran "EstadoDato" en prosa)."""

    def test_repositorio_requisitos_no_importa_checklist_ni_estado_dato(self):
        import src.repositorios.requisitos as modulo
        assert not hasattr(modulo, "EstadoDato")
        assert not hasattr(modulo, "campos_esperados")
        assert not hasattr(modulo, "ExpedienteProyecto")

    def test_modelo_expediente_no_importa_checklist_ni_estado_dato(self):
        import src.expediente.modelo as modulo
        assert not hasattr(modulo, "EstadoDato")
        assert not hasattr(modulo, "campos_esperados")
        assert not hasattr(modulo, "ExpedienteProyecto")
