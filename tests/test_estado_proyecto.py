"""TF-0026 — Pruebas del contrato PROJECT_STATE (`src.proyectos.estado`).

Cubre: valores exactos de los enums aprobados (guardarraíl de vocabulario),
round-trip `to_dict`/`from_dict`, JSON-serializabilidad sin `default=`,
campos exactos de cada dataclass y la matriz de `transicion_valida`.
"""
import ast
import dataclasses
import json
from pathlib import Path

from src.proyectos.checklist import DISCIPLINAS
from src.proyectos.estado import (
    AplicabilidadDisciplina,
    Dato,
    EstadoAprobacionMockup,
    EstadoDato,
    ExpedienteProyecto,
    Mockup,
    NivelConfianza,
    OrigenDato,
    Readiness,
    ResumenDisciplina,
    TRANSICIONES_RESTRINGIDAS,
    transicion_valida,
)


def _nombres(clase):
    return [f.name for f in dataclasses.fields(clase)]


# --- CA-1: vocabulario aprobado de los enums --------------------------------

class TestVocabularioEnums:
    def test_estado_dato(self):
        assert {e.value for e in EstadoDato} == {
            "confirmed", "discovered", "inferred", "unknown", "not_found",
            "not_applicable", "pending_decision", "incomplete",
        }

    def test_origen_dato(self):
        assert {e.value for e in OrigenDato} == {
            "user", "conversation", "file", "code", "documentation",
            "repository", "tool", "external", "inference", "agent",
            "configuration",
        }

    def test_nivel_confianza_se_mantiene_en_espanol(self):
        # Decisión final del checkpoint TF-0026: NO se traduce a inglés.
        assert {e.value for e in NivelConfianza} == {"ALTA", "MEDIA", "BAJA"}

    def test_aplicabilidad_disciplina(self):
        assert {e.value for e in AplicabilidadDisciplina} == {
            "required", "conditional", "not_applicable", "unknown",
        }

    def test_readiness(self):
        assert {e.value for e in Readiness} == {
            "READY", "READY_WITH_WARNINGS", "INCOMPLETE", "BLOCKED",
        }

    def test_estado_aprobacion_mockup(self):
        assert {e.value for e in EstadoAprobacionMockup} == {
            "draft", "in_review", "approved", "rejected",
        }


# --- CA-2: campos exactos de cada dataclass ---------------------------------

class TestCamposDeLosContratos:
    def test_dato(self):
        assert _nombres(Dato) == ["valor", "estado", "origen", "confianza", "actualizado_en", "notas"]

    def test_mockup(self):
        assert _nombres(Mockup) == [
            "id", "nombre", "tipo", "ruta", "version",
            "estado_aprobacion", "creado_en", "actualizado_en",
        ]

    def test_resumen_disciplina(self):
        # `Mockup` es un contrato independiente (no cuelga de aquí): ver
        # TestRoundTrip.test_mockup. PROJECT_STATE se mantiene acotado al
        # checklist de coordinación, sin campos añadidos sin decisión explícita.
        assert _nombres(ResumenDisciplina) == [
            "aplicabilidad", "datos", "notas", "referencia_estado",
        ]

    def test_expediente_proyecto(self):
        assert _nombres(ExpedienteProyecto) == [
            "codigo", "nombre", "descripcion", "checklist_version",
            "descubrimiento", "disciplinas", "creado_en", "actualizado_en",
            "last_analyzed_at",
        ]


# --- CA-3: valores por defecto -----------------------------------------

class TestValoresPorDefecto:
    def test_expediente_disciplinas_por_defecto_unknown(self):
        e = ExpedienteProyecto()
        assert set(e.disciplinas) == set(DISCIPLINAS)
        for resumen in e.disciplinas.values():
            assert resumen.aplicabilidad == AplicabilidadDisciplina.UNKNOWN
            assert resumen.datos == {}
            assert resumen.referencia_estado is None

    def test_instancias_por_defecto_no_comparten_estado_mutable(self):
        a, b = ExpedienteProyecto(), ExpedienteProyecto()
        a.disciplinas["ux"].datos["x"] = "marca"
        assert b.disciplinas["ux"].datos == {}


# --- CA-4: round-trip to_dict/from_dict + JSON sin default= -----------------

def _dato(valor="v", estado=EstadoDato.CONFIRMED, origen=OrigenDato.CODE,
          confianza=NivelConfianza.ALTA):
    return Dato(valor=valor, estado=estado, origen=origen, confianza=confianza,
                actualizado_en="2026-09-02 10:00:00", notas="nota")


class TestRoundTrip:
    def test_dato(self):
        d = _dato()
        assert Dato.from_dict(d.to_dict()) == d
        json.dumps(d.to_dict())  # no debe requerir default=

    def test_mockup(self):
        m = Mockup(id="MOCK-01", nombre="Home", tipo="wireframe", ruta="docs/x.png",
                    version=1, estado_aprobacion=EstadoAprobacionMockup.DRAFT,
                    creado_en="2026-09-02 10:00:00", actualizado_en="2026-09-02 10:00:00")
        assert Mockup.from_dict(m.to_dict()) == m
        json.dumps(m.to_dict())

    def test_resumen_disciplina_con_datos(self):
        r = ResumenDisciplina(
            aplicabilidad=AplicabilidadDisciplina.REQUIRED,
            datos={"usuarios_objetivo": _dato()},
            notas="nota",
            referencia_estado="ux_states/1",
        )
        assert ResumenDisciplina.from_dict(r.to_dict()) == r
        json.dumps(r.to_dict())

    def test_expediente_completo(self):
        e = ExpedienteProyecto(
            codigo="PROY-001", nombre="Demo", descripcion="desc",
            descubrimiento={"identidad": _dato(valor="Taskflow")},
            creado_en="2026-09-02 10:00:00", actualizado_en="2026-09-02 10:00:00",
            last_analyzed_at="2026-09-02 10:00:00",
        )
        e.disciplinas["ux"].aplicabilidad = AplicabilidadDisciplina.NOT_APPLICABLE
        e.disciplinas["analisis"].datos["restricciones"] = _dato(estado=EstadoDato.PENDING_DECISION)

        reconstruido = ExpedienteProyecto.from_dict(e.to_dict())
        assert reconstruido == e
        json.dumps(e.to_dict())

    def test_expediente_vacio_por_defecto(self):
        e = ExpedienteProyecto()
        assert ExpedienteProyecto.from_dict(e.to_dict()) == e


# --- CA-5: transicion_valida -------------------------------------------

class TestTransicionValida:
    def test_transiciones_restringidas_exactas(self):
        assert TRANSICIONES_RESTRINGIDAS == frozenset({
            (EstadoDato.INFERRED, EstadoDato.CONFIRMED),
            (EstadoDato.NOT_FOUND, EstadoDato.NOT_APPLICABLE),
            (EstadoDato.UNKNOWN, EstadoDato.NOT_APPLICABLE),
        })

    def test_restringidas_requieren_origen_usuario(self):
        for desde, hacia in TRANSICIONES_RESTRINGIDAS:
            assert transicion_valida(desde, hacia, OrigenDato.USER) is True

    def test_restringidas_rechazadas_sin_origen_usuario(self):
        otros_origenes = [o for o in OrigenDato if o != OrigenDato.USER]
        for desde, hacia in TRANSICIONES_RESTRINGIDAS:
            for origen in otros_origenes:
                assert transicion_valida(desde, hacia, origen) is False

    def test_transicion_no_restringida_siempre_valida(self):
        assert transicion_valida(EstadoDato.UNKNOWN, EstadoDato.DISCOVERED, OrigenDato.AGENT) is True
        assert transicion_valida(EstadoDato.CONFIRMED, EstadoDato.CONFIRMED, OrigenDato.CODE) is True

    def test_not_found_a_confirmed_no_esta_restringida(self):
        # not_found -> confirmed no es una de las 3 transiciones vetadas: un
        # descubrimiento posterior puede resolverlo sin pasar por un humano.
        assert transicion_valida(EstadoDato.NOT_FOUND, EstadoDato.CONFIRMED, OrigenDato.AGENT) is True


# --- CA-6: aislamiento (mismo criterio que TF-0024/TF-0025) -----------------

_RAIZ = Path(__file__).resolve().parents[1]
_MODULOS_PROYECTOS = [
    "src/proyectos/__init__.py",
    "src/proyectos/errores.py",
    "src/proyectos/checklist.py",
    "src/proyectos/estado.py",
    "src/proyectos/salud.py",
    "src/proyectos/workflow.py",
]


def _imports(rel):
    arbol = ast.parse((_RAIZ / rel).read_text(encoding="utf-8"), filename=rel)
    mods = set()
    for n in ast.walk(arbol):
        if isinstance(n, ast.Import):
            mods.update(a.name for a in n.names)
        elif isinstance(n, ast.ImportFrom):
            mods.add(n.module or "")
    return mods


class TestSinAcoplamiento:
    def test_modulos_no_importan_flask_app_agentes_ai_ni_red(self):
        prohibidos = {"flask", "app", "src.app", "httpx", "requests",
                      "urllib", "urllib.request", "http", "http.client", "socket",
                      "sqlite3", "src.database"}
        prefijos = ("flask.", "src.agentes.", "src.app.", "src.ai.")
        for rel in _MODULOS_PROYECTOS:
            mods = _imports(rel)
            for m in mods:
                assert m not in prohibidos, f"{rel} importa {m!r}"
                assert not m.startswith(prefijos), f"{rel} importa {m!r}"

    def test_salud_no_importa_ciclo_workflow_no_importa_salud_en_tiempo_de_carga(self):
        # salud.py sí debe importar workflow (para delegar next_agent)...
        mods_salud = _imports("src/proyectos/salud.py")
        assert "src.proyectos.workflow" in mods_salud or "src.proyectos" in mods_salud
        # ...pero workflow.py NUNCA debe importar salud.py a nivel de módulo
        # (cerraría el ciclo); solo puede aparecer bajo TYPE_CHECKING, que
        # `_imports` (basado en AST, no en ejecución) igual detectaría como
        # ImportFrom -- por eso se verifica leyendo el texto crudo del import.
        texto_workflow = (_RAIZ / "src/proyectos/workflow.py").read_text(encoding="utf-8")
        assert "from src.proyectos.salud import" in texto_workflow  # solo bajo TYPE_CHECKING
        assert "if TYPE_CHECKING:" in texto_workflow
        assert "src.proyectos.salud" not in _imports_top_level("src/proyectos/workflow.py")


def _imports_top_level(rel):
    """Como `_imports`, pero ignora los `import`/`from` anidados dentro de un
    bloque `if TYPE_CHECKING:` (no se ejecutan en tiempo de carga real).
    """
    arbol = ast.parse((_RAIZ / rel).read_text(encoding="utf-8"), filename=rel)
    mods = set()
    for nodo in arbol.body:
        if isinstance(nodo, ast.If):
            test = nodo.test
            if isinstance(test, ast.Name) and test.id == "TYPE_CHECKING":
                continue
        for n in ast.walk(nodo):
            if isinstance(n, ast.Import):
                mods.update(a.name for a in n.names)
            elif isinstance(n, ast.ImportFrom):
                mods.add(n.module or "")
    return mods
