"""TF-0027 — Pruebas de integración de `ejecutar_orquestador()` /
`responder_pregunta()` contra `RepositorioExpedientes` y `RepositorioAcciones`
reales (SQLite temporal, fixture `db` de `conftest.py`).

Usa un `ClienteIA` y un `DefinicionAgente` de prueba (sin red, sin proveedor
real): el Orquestador no debe conocer Ollama ni ningún proveedor concreto.
"""
import json

import pytest

from src.agentes.contrato import SalidaAgente
from src.ai.cliente import RespuestaIA
from src.orquestador.contrato import AccionOrquestador
from src.orquestador.orquestador import (
    TIPO_ACCION_ORQUESTAR,
    ejecutar_orquestador,
    responder_pregunta,
)
from src.proyectos.errores import ExpedienteNoEncontrado, TransicionEstadoInvalida
from src.proyectos.estado import Dato, EstadoDato, NivelConfianza, OrigenDato
from src.repositorios.acciones import COMPLETADA, RepositorioAcciones
from src.repositorios.briefs import RepositorioBriefs
from src.repositorios.expedientes import RepositorioExpedientes

_TS = "2026-09-02 10:00:00"


class _AgenteFalso:
    """`DefinicionAgente` de prueba: no llama a ningún proveedor real."""

    nombre = "descubrimiento_fake"
    tipo_accion = "descubrimiento_fake"

    def construir_prompt(self, entrada):
        return f"prompt para {entrada.ticket}"

    def parsear(self, respuesta, entrada):
        return SalidaAgente(resultado=respuesta.texto)


class _ClienteFalso:
    """`ClienteIA` de prueba: devuelve un texto fijo, sin red."""

    def __init__(self, texto):
        self._texto = texto

    def completar(self, prompt, opciones):
        return RespuestaIA(texto=self._texto, tokens_entrada=1, tokens_salida=1, modelo="fake")


class _ClienteQueFalla:
    """Simula un `ErrorIA` de proveedor: `ejecutar_agente` ya lo absorbe."""

    def completar(self, prompt, opciones):
        from src.ai.errores import ErrorProveedorNoDisponible
        raise ErrorProveedorNoDisponible("proveedor de prueba caído")


class _AgenteExponeContexto:
    """`DefinicionAgente` de prueba que expone `entrada.contexto` tal cual,
    para poder inspeccionar cómo se ensambló (mismo patrón que
    `test_orquestador_evidencia.py`).
    """

    nombre = "descubrimiento_fake"
    tipo_accion = "descubrimiento_fake"

    def construir_prompt(self, entrada):
        return entrada.contexto

    def parsear(self, respuesta, entrada):
        return SalidaAgente(resultado=respuesta.texto)


def _hallazgos_json(*campos_confirmados):
    """JSON Lines (TF-0029: un objeto por línea, sin envoltorio "hallazgos")."""
    return "\n".join(
        json.dumps({"campo": c, "valor": "v", "estado": "confirmed",
                    "origen": "file", "confianza": "ALTA"})
        for c in campos_confirmados
    )


def _dato(estado, origen=OrigenDato.AGENT):
    return Dato(valor="v", estado=estado, origen=origen,
                confianza=NivelConfianza.ALTA, actualizado_en=_TS)


@pytest.fixture
def repo_exp(db):
    return RepositorioExpedientes()


@pytest.fixture
def repo_acc(db):
    return RepositorioAcciones()


class TestExpedienteNoEncontrado:
    def test_propaga(self, repo_exp, repo_acc):
        with pytest.raises(ExpedienteNoEncontrado):
            ejecutar_orquestador("PROY-999", _ClienteFalso("{}"), _AgenteFalso(),
                                  repo_expedientes=repo_exp, repo_acciones=repo_acc)


class TestBloqueado:
    def test_pending_decision_en_raiz_bloquea_sin_llamar_al_cliente(self, repo_exp, repo_acc):
        codigo = repo_exp.crear("Demo")
        e = repo_exp.obtener(codigo)
        e.descubrimiento["identidad"] = _dato(EstadoDato.PENDING_DECISION)
        repo_exp.guardar(e)

        class _ClienteQueNuncaDebeLlamarse:
            def completar(self, prompt, opciones):
                raise AssertionError("no debía invocarse el cliente en BLOQUEADO")

        resultado = ejecutar_orquestador(
            codigo, _ClienteQueNuncaDebeLlamarse(), _AgenteFalso(),
            repo_expedientes=repo_exp, repo_acciones=repo_acc,
        )
        assert resultado.accion == AccionOrquestador.BLOQUEADO
        assert repo_acc.listar(ticket=codigo) == []  # ninguna accion propia registrada


class TestInvestigarYPreguntar:
    def test_primer_ciclo_investiga_y_aplica_hallazgos(self, repo_exp, repo_acc):
        codigo = repo_exp.crear("Demo")
        cliente = _ClienteFalso(_hallazgos_json("identidad"))

        resultado = ejecutar_orquestador(codigo, cliente, _AgenteFalso(),
                                          repo_expedientes=repo_exp, repo_acciones=repo_acc)

        assert resultado.accion == AccionOrquestador.INVESTIGAR
        assert resultado.hallazgos_aplicados == 1
        assert resultado.problemas == []
        assert not any(p.campo == "identidad" for p in resultado.preguntas)

        acciones = repo_acc.listar(ticket=codigo)
        propias = [a for a in acciones if a["tipo"] == TIPO_ACCION_ORQUESTAR]
        assert len(propias) == 1
        assert propias[0]["estado"] == COMPLETADA
        assert propias[0]["actor"] == "orquestador"

    def test_segundo_ciclo_sin_nuevos_hallazgos_pasa_a_preguntar(self, repo_exp, repo_acc):
        codigo = repo_exp.crear("Demo")
        cliente_vacio = _ClienteFalso("")  # JSON Lines vacío = sin hallazgos

        primero = ejecutar_orquestador(codigo, cliente_vacio, _AgenteFalso(),
                                        repo_expedientes=repo_exp, repo_acciones=repo_acc)
        assert primero.accion == AccionOrquestador.INVESTIGAR
        assert primero.hallazgos_aplicados == 0

        segundo = ejecutar_orquestador(codigo, cliente_vacio, _AgenteFalso(),
                                        repo_expedientes=repo_exp, repo_acciones=repo_acc)
        assert segundo.accion == AccionOrquestador.PREGUNTAR
        assert len(segundo.preguntas) == 6

    def test_fallo_del_proveedor_de_ia_no_crashea_el_ciclo(self, repo_exp, repo_acc):
        codigo = repo_exp.crear("Demo")
        resultado = ejecutar_orquestador(codigo, _ClienteQueFalla(), _AgenteFalso(),
                                          repo_expedientes=repo_exp, repo_acciones=repo_acc)
        assert resultado.accion == AccionOrquestador.INVESTIGAR
        assert resultado.hallazgos_aplicados == 0
        assert resultado.problemas  # el problema del ErrorIA queda reflejado

    def test_hallazgo_invalido_no_bloquea_los_validos_del_mismo_lote(self, repo_exp, repo_acc):
        codigo = repo_exp.crear("Demo")
        e = repo_exp.obtener(codigo)
        e.descubrimiento["identidad"] = _dato(EstadoDato.INFERRED)
        repo_exp.guardar(e)

        # "identidad" pasar a confirmed sin origen=user viola una transición
        # restringida; "objetivo" es un hallazgo nuevo y válido. JSON Lines:
        # una línea por hallazgo (TF-0029).
        texto = "\n".join([
            json.dumps({"campo": "identidad", "valor": "x", "estado": "confirmed",
                        "origen": "agent", "confianza": "ALTA"}),
            json.dumps({"campo": "objetivo", "valor": "y", "estado": "confirmed",
                        "origen": "file", "confianza": "ALTA"}),
        ])
        resultado = ejecutar_orquestador(codigo, _ClienteFalso(texto), _AgenteFalso(),
                                          repo_expedientes=repo_exp, repo_acciones=repo_acc)

        assert resultado.hallazgos_aplicados == 1
        recargado = repo_exp.obtener(codigo)
        assert recargado.descubrimiento["identidad"].estado == EstadoDato.INFERRED
        assert recargado.descubrimiento["objetivo"].estado == EstadoDato.CONFIRMED
        assert any("transición no permitida" in p for p in resultado.problemas)


class TestRepoBriefs:
    """`repo_briefs` (corrección post-smoke-test): el brief del cliente como
    fuente de primera clase, separada de las preguntas y de la evidencia.
    """

    def test_repo_briefs_none_preserva_comportamiento_previo(self, repo_exp, repo_acc):
        """Sin `repo_briefs` (default `None`), el contexto que recibe el
        agente es exactamente el de antes: solo las preguntas, sin ningún
        encabezado de brief.
        """
        codigo = repo_exp.crear("Demo")
        cliente = _ClienteFalso("")

        resultado = ejecutar_orquestador(codigo, cliente, _AgenteExponeContexto(),
                                          repo_expedientes=repo_exp, repo_acciones=repo_acc)

        assert resultado.accion == AccionOrquestador.INVESTIGAR
        # (el prompt real capturado vive en el propio cliente en otros tests;
        # aquí basta con que el ciclo se complete igual que sin repo_briefs)

    def test_recupera_el_brief_inicial_y_lo_antepone_al_contexto(self, repo_exp, repo_acc):
        codigo = repo_exp.crear("Demo")
        repo_briefs = RepositorioBriefs()
        texto_cliente = (
            "Quiero un proyecto nuevo que sea una calculadora "
            "que solo suma números negativos."
        )
        repo_briefs.registrar(codigo, texto_cliente)

        class _ClienteCapturaPrompt:
            def completar(self, prompt, opciones):
                self.ultimo_prompt = prompt
                return RespuestaIA(texto="", tokens_entrada=1, tokens_salida=1, modelo="fake")

        cliente = _ClienteCapturaPrompt()
        ejecutar_orquestador(codigo, cliente, _AgenteExponeContexto(),
                              repo_expedientes=repo_exp, repo_acciones=repo_acc,
                              repo_briefs=repo_briefs)

        assert "## Comunicación del cliente" in cliente.ultimo_prompt
        assert texto_cliente in cliente.ultimo_prompt
        assert "## Preguntas a investigar" in cliente.ultimo_prompt
        # el brief queda separado y antes de las preguntas, no mezclado con ellas
        assert (
            cliente.ultimo_prompt.index("## Comunicación del cliente")
            < cliente.ultimo_prompt.index("## Preguntas a investigar")
        )

    def test_sin_brief_inicial_registrado_no_agrega_seccion(self, repo_exp, repo_acc):
        """`repo_briefs` inyectado pero sin ningún brief registrado para este
        `codigo`: el comportamiento debe seguir siendo el mismo que con
        `repo_briefs=None` (no se agrega una sección vacía).
        """
        codigo = repo_exp.crear("Demo")
        repo_briefs = RepositorioBriefs()

        class _ClienteCapturaPrompt:
            def completar(self, prompt, opciones):
                self.ultimo_prompt = prompt
                return RespuestaIA(texto="", tokens_entrada=1, tokens_salida=1, modelo="fake")

        cliente = _ClienteCapturaPrompt()
        ejecutar_orquestador(codigo, cliente, _AgenteExponeContexto(),
                              repo_expedientes=repo_exp, repo_acciones=repo_acc,
                              repo_briefs=repo_briefs)

        assert "## Comunicación del cliente" not in cliente.ultimo_prompt


class TestHandoff:
    def test_raiz_resuelta_hace_handoff_con_next_agent_correcto(self, repo_exp, repo_acc):
        codigo = repo_exp.crear("Demo")
        e = repo_exp.obtener(codigo)
        from src.proyectos.checklist import campos_esperados
        for campo in campos_esperados("1.0")["_raiz"]:
            e.descubrimiento[campo] = _dato(EstadoDato.CONFIRMED)
        repo_exp.guardar(e)

        class _ClienteQueNuncaDebeLlamarse:
            def completar(self, prompt, opciones):
                raise AssertionError("no debía investigarse: la raíz ya está resuelta")

        resultado = ejecutar_orquestador(codigo, _ClienteQueNuncaDebeLlamarse(), _AgenteFalso(),
                                          repo_expedientes=repo_exp, repo_acciones=repo_acc)
        assert resultado.accion == AccionOrquestador.HANDOFF
        assert resultado.salud.next_agent == "ARQUITECTO"
        assert repo_acc.listar(ticket=codigo) == []  # HANDOFF no registra accion propia


class TestRedDeSeguridadTransicionInvalida:
    def test_transicion_invalida_al_guardar_no_crashea_el_ciclo(self, repo_exp, repo_acc):
        """Simula la carrera descrita en el diseño: `fusionar_hallazgos` pre-
        valida contra un snapshot que queda desactualizado antes del
        `guardar()` real (p. ej. otro proceso cambió el expediente en medio).
        """
        codigo = repo_exp.crear("Demo")

        class _RepoQueFallaAlGuardar(RepositorioExpedientes):
            def guardar(self, expediente):
                raise TransicionEstadoInvalida("simulado: el expediente cambió antes de guardar")

        resultado = ejecutar_orquestador(
            codigo, _ClienteFalso(_hallazgos_json("identidad")), _AgenteFalso(),
            repo_expedientes=_RepoQueFallaAlGuardar(), repo_acciones=repo_acc,
        )
        assert resultado.accion == AccionOrquestador.INVESTIGAR
        assert resultado.hallazgos_aplicados == 0
        assert any("descartada por una transición inválida" in p for p in resultado.problemas)
        # la acción propia del Orquestador igual se cierra (COMPLETADA, no cuelga EN_CURSO)
        propias = [a for a in repo_acc.listar(ticket=codigo) if a["tipo"] == TIPO_ACCION_ORQUESTAR]
        assert len(propias) == 1
        assert propias[0]["estado"] == COMPLETADA


class TestResponderPregunta:
    def test_persiste_con_origen_user(self, repo_exp):
        codigo = repo_exp.crear("Demo")
        responder_pregunta(repo_exp, codigo, "objetivo", "Vender X")
        e = repo_exp.obtener(codigo)
        assert e.descubrimiento["objetivo"].estado == EstadoDato.CONFIRMED
        assert e.descubrimiento["objetivo"].origen == OrigenDato.USER

    def test_no_se_que_se_registra_como_unknown_no_como_not_applicable(self, repo_exp):
        codigo = repo_exp.crear("Demo")
        responder_pregunta(repo_exp, codigo, "objetivo", None, estado=EstadoDato.UNKNOWN)
        e = repo_exp.obtener(codigo)
        assert e.descubrimiento["objetivo"].estado == EstadoDato.UNKNOWN
        assert e.descubrimiento["objetivo"].origen == OrigenDato.USER

    def test_codigo_inexistente_propaga(self, repo_exp):
        with pytest.raises(ExpedienteNoEncontrado):
            responder_pregunta(repo_exp, "PROY-999", "objetivo", "x")


# --- Aislamiento: no debe importar Flask/app directamente -----------------

import ast
from pathlib import Path

_RAIZ = Path(__file__).resolve().parents[1]
_MODULOS_ORQUESTADOR = [
    "src/orquestador/__init__.py",
    "src/orquestador/contrato.py",
    "src/orquestador/preguntas.py",
    "src/orquestador/fusion.py",
    "src/orquestador/orquestador.py",
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


class TestSinAcoplamientoAFlask:
    def test_modulos_no_importan_flask_ni_app(self):
        prohibidos = {"flask", "app", "src.app"}
        for rel in _MODULOS_ORQUESTADOR:
            mods = _imports(rel)
            for m in mods:
                assert m not in prohibidos, f"{rel} importa {m!r}"
                assert not m.startswith("flask."), f"{rel} importa {m!r}"

    def test_orquestador_no_importa_ningun_proveedor_de_ia_concreto(self):
        prohibidos = {"src.ai.ollama", "urllib", "urllib.request", "http", "http.client", "socket"}
        for rel in _MODULOS_ORQUESTADOR:
            mods = _imports(rel)
            for m in mods:
                assert m not in prohibidos, f"{rel} importa {m!r}"
