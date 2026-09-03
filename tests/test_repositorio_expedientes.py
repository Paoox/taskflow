"""TF-0026 — Pruebas de la tabla `expedientes` y de `RepositorioExpedientes`.

Aisladas (sin runner ni agentes). Usan la fixture `db` de `conftest.py`, que
redirige la base a un archivo temporal y ejecuta `crear_tablas()` (incluida
la tabla `expedientes`).
"""
import sqlite3

import pytest

from src.proyectos.errores import ExpedienteNoEncontrado, TransicionEstadoInvalida
from src.proyectos.estado import AplicabilidadDisciplina, Dato, EstadoDato, ExpedienteProyecto, NivelConfianza, OrigenDato
from src.proyectos.salud import calcular_salud
from src.repositorios.expedientes import RepositorioExpedientes

_TS = "2026-09-02 10:00:00"


@pytest.fixture
def repo(db):
    """`RepositorioExpedientes` sobre la base temporal de la fixture `db`."""
    return RepositorioExpedientes()


def _dato(estado, origen=OrigenDato.CODE, confianza=NivelConfianza.ALTA):
    return Dato(valor="v", estado=estado, origen=origen, confianza=confianza, actualizado_en=_TS)


class TestCrearTablaExpedientes:
    def test_crear_tablas_crea_expedientes(self, db):
        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        filas = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name='expedientes'"
        ).fetchall()
        conn.close()
        assert len(filas) == 1


class TestCrearYObtener:
    def test_crear_asigna_codigos_correlativos(self, repo):
        assert repo.crear("Uno") == "PROY-001"
        assert repo.crear("Dos") == "PROY-002"

    def test_obtener_devuelve_expediente_recien_creado(self, repo):
        codigo = repo.crear("Demo", descripcion="una descripción")
        e = repo.obtener(codigo)
        assert e.codigo == codigo
        assert e.nombre == "Demo"
        assert e.descripcion == "una descripción"
        assert e.checklist_version == "1.0"
        assert set(e.disciplinas) == {
            "analisis", "ux", "arquitectura", "implementacion",
            "testing", "seguridad", "documentacion",
        }
        for r in e.disciplinas.values():
            assert r.aplicabilidad == AplicabilidadDisciplina.UNKNOWN

    def test_obtener_inexistente_devuelve_none(self, repo):
        assert repo.obtener("PROY-999") is None


class TestGuardar:
    def test_guardar_persiste_cambios(self, repo):
        codigo = repo.crear("Demo")
        e = repo.obtener(codigo)
        e.descubrimiento["identidad"] = _dato(EstadoDato.CONFIRMED)
        repo.guardar(e)

        recargado = repo.obtener(codigo)
        assert recargado.descubrimiento["identidad"].estado == EstadoDato.CONFIRMED

    def test_guardar_codigo_inexistente_lanza_y_no_escribe(self, repo):
        fantasma = ExpedienteProyecto(codigo="PROY-999", nombre="No existe")
        with pytest.raises(ExpedienteNoEncontrado):
            repo.guardar(fantasma)

        # nada debió escribirse: la tabla sigue vacía
        assert repo.listar() == []

    def test_guardar_transicion_restringida_sin_origen_usuario_falla_y_no_escribe(self, repo):
        codigo = repo.crear("Demo")
        e = repo.obtener(codigo)
        e.disciplinas["ux"].datos["usuarios_objetivo"] = _dato(EstadoDato.UNKNOWN)
        repo.guardar(e)

        e2 = repo.obtener(codigo)
        e2.disciplinas["ux"].datos["usuarios_objetivo"] = _dato(
            EstadoDato.NOT_APPLICABLE, origen=OrigenDato.AGENT
        )
        with pytest.raises(TransicionEstadoInvalida):
            repo.guardar(e2)

        # el registro previo debe quedar intacto (no se escribió nada)
        intacto = repo.obtener(codigo)
        assert intacto.disciplinas["ux"].datos["usuarios_objetivo"].estado == EstadoDato.UNKNOWN

    def test_guardar_transicion_restringida_en_descubrimiento_raiz_tambien_se_valida(self, repo):
        """`_validar_transiciones` revisa tanto `descubrimiento` (raíz) como
        cada disciplina con la misma función `_revisar` — sin duplicar la
        llamada por disciplina (una sola vez por `k` en `nuevo.disciplinas`).
        Este test cubre el camino de la raíz, que las otras pruebas de esta
        clase no ejercitan (esas usan la disciplina `ux`).
        """
        codigo = repo.crear("Demo")
        e = repo.obtener(codigo)
        e.descubrimiento["identidad"] = _dato(EstadoDato.UNKNOWN)
        repo.guardar(e)

        e2 = repo.obtener(codigo)
        e2.descubrimiento["identidad"] = _dato(EstadoDato.NOT_APPLICABLE, origen=OrigenDato.AGENT)
        with pytest.raises(TransicionEstadoInvalida):
            repo.guardar(e2)

        intacto = repo.obtener(codigo)
        assert intacto.descubrimiento["identidad"].estado == EstadoDato.UNKNOWN

    def test_guardar_transicion_restringida_inferred_a_confirmed_lanza_y_no_escribe(self, repo):
        """Integración: `inferred -> confirmed` con `origen=AGENT` (no USER)
        debe rechazarse a través de `guardar()`, no solo en `transicion_valida`
        aislada."""
        codigo = repo.crear("Demo")
        e = repo.obtener(codigo)
        e.disciplinas["ux"].datos["flujos_clave"] = _dato(EstadoDato.INFERRED, origen=OrigenDato.AGENT)
        repo.guardar(e)

        e2 = repo.obtener(codigo)
        e2.disciplinas["ux"].datos["flujos_clave"] = _dato(EstadoDato.CONFIRMED, origen=OrigenDato.AGENT)
        with pytest.raises(TransicionEstadoInvalida):
            repo.guardar(e2)

        intacto = repo.obtener(codigo)
        assert intacto.disciplinas["ux"].datos["flujos_clave"].estado == EstadoDato.INFERRED

    def test_guardar_transicion_restringida_not_found_a_not_applicable_lanza_y_no_escribe(self, repo):
        """Integración: `not_found -> not_applicable` con `origen=AGENT` (no
        USER) debe rechazarse a través de `guardar()` — "no lo encontré" no
        implica "no existe" salvo que lo confirme una persona."""
        codigo = repo.crear("Demo")
        e = repo.obtener(codigo)
        e.disciplinas["ux"].datos["referencias_visuales"] = _dato(EstadoDato.NOT_FOUND, origen=OrigenDato.AGENT)
        repo.guardar(e)

        e2 = repo.obtener(codigo)
        e2.disciplinas["ux"].datos["referencias_visuales"] = _dato(
            EstadoDato.NOT_APPLICABLE, origen=OrigenDato.AGENT
        )
        with pytest.raises(TransicionEstadoInvalida):
            repo.guardar(e2)

        intacto = repo.obtener(codigo)
        assert intacto.disciplinas["ux"].datos["referencias_visuales"].estado == EstadoDato.NOT_FOUND

    def test_guardar_transicion_restringida_con_origen_usuario_se_permite(self, repo):
        codigo = repo.crear("Demo")
        e = repo.obtener(codigo)
        e.disciplinas["ux"].datos["usuarios_objetivo"] = _dato(EstadoDato.UNKNOWN)
        repo.guardar(e)

        e2 = repo.obtener(codigo)
        e2.disciplinas["ux"].datos["usuarios_objetivo"] = _dato(
            EstadoDato.NOT_APPLICABLE, origen=OrigenDato.USER
        )
        repo.guardar(e2)  # no debe lanzar

        recargado = repo.obtener(codigo)
        assert recargado.disciplinas["ux"].datos["usuarios_objetivo"].estado == EstadoDato.NOT_APPLICABLE

    def test_guardar_transicion_no_restringida_no_requiere_validacion_previa(self, repo):
        codigo = repo.crear("Demo")
        e = repo.obtener(codigo)
        e.descubrimiento["identidad"] = _dato(EstadoDato.DISCOVERED, origen=OrigenDato.AGENT)
        repo.guardar(e)  # primera vez: no hay "actual" con ese campo, no valida nada

        e2 = repo.obtener(codigo)
        e2.descubrimiento["identidad"] = _dato(EstadoDato.CONFIRMED, origen=OrigenDato.AGENT)
        repo.guardar(e2)  # discovered -> confirmed no está restringida

        recargado = repo.obtener(codigo)
        assert recargado.descubrimiento["identidad"].estado == EstadoDato.CONFIRMED


class TestGuardarSalud:
    def test_guardar_salud_actualiza_columnas_promovidas(self, repo, db):
        codigo = repo.crear("Demo")
        e = repo.obtener(codigo)
        salud = calcular_salud(e)
        repo.guardar_salud(codigo, salud)

        import src.database as database
        conn = sqlite3.connect(database.DATABASE_NAME)
        conn.row_factory = sqlite3.Row
        fila = conn.execute(
            "SELECT readiness, estado_general, last_analyzed_at, salud FROM expedientes WHERE id = 1"
        ).fetchone()
        conn.close()
        assert fila["readiness"] == salud.readiness.value
        assert fila["estado_general"] == pytest.approx(salud.estado_general)
        assert fila["last_analyzed_at"] == salud.calculado_en
        assert fila["salud"] is not None

    def test_guardar_salud_codigo_inexistente_lanza_y_no_escribe(self, repo):
        fantasma = ExpedienteProyecto(codigo="PROY-999", nombre="No existe")
        salud = calcular_salud(fantasma)
        with pytest.raises(ExpedienteNoEncontrado):
            repo.guardar_salud("PROY-999", salud)

        # nada debió escribirse: la tabla sigue vacía
        assert repo.listar() == []


class TestListar:
    def test_listar_resumen_liviano(self, repo):
        repo.crear("Uno")
        repo.crear("Dos")
        resumen = repo.listar()
        assert [r["codigo"] for r in resumen] == ["PROY-001", "PROY-002"]
        assert [r["nombre"] for r in resumen] == ["Uno", "Dos"]

    def test_listar_vacio(self, repo):
        assert repo.listar() == []
