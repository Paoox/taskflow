"""Pruebas de integración de `ejecutar_discovery()` (TF-0030) contra
`RepositorioRespuestasFormulario` y los repositorios del Expediente Maestro
reales (SQLite temporal, fixture `db` de `conftest.py`).

Usa un `ClienteIA` de prueba (sin red, sin proveedor real): Discovery no
debe conocer Ollama ni ningún proveedor concreto — mismo criterio que
`tests/test_orquestador.py` para el Orquestador viejo.
"""
import json

import pytest

from src import database
from src.discovery.discovery import (
    EstadoDiscovery,
    FormularioIncompleto,
    ResultadoDiscovery,
    ejecutar_discovery,
)
from src.ai.cliente import RespuestaIA
from src.expediente.modelo import (
    EstadoContradiccion, EstadoGap, FuenteDirecta, NaturalezaInformacion,
)
from src.formulario.preguntas import PREGUNTAS
from src.formulario.respuestas import serializar_respuesta
from src.proyectos.estado import NivelConfianza, OrigenDato
from src.repositorios.acciones import FALLIDA, RepositorioAcciones
from src.repositorios.contradicciones import RepositorioContradicciones
from src.repositorios.datos import RepositorioDatos
from src.repositorios.gaps import RepositorioGaps
from src.repositorios.perfiles import RepositorioPerfiles
from src.repositorios.requisitos import RepositorioRequisitos
from src.repositorios.respuestas_formulario import RepositorioRespuestasFormulario
from src.repositorios.restricciones import RepositorioRestricciones


class _ClienteFalso:
    """`ClienteIA` de prueba: devuelve un texto fijo, sin red. Cuenta
    cuántas veces se le llamó `completar`."""

    def __init__(self, texto=""):
        self._texto = texto
        self.llamadas = 0

    def completar(self, prompt, opciones):
        self.llamadas += 1
        return RespuestaIA(texto=self._texto, tokens_entrada=1, tokens_salida=1, modelo="fake")


def _registrar(codigo, pregunta_id, valor, repo):
    pregunta = PREGUNTAS[pregunta_id]
    texto = serializar_respuesta(pregunta, valor)
    return repo.registrar(codigo, pregunta_id, pregunta.texto, pregunta.tipo_pregunta, texto)


# Recorrido lineal completo del árbol (proyecto nuevo, un solo perfil, un
# solo administrador implícito, sin datos a recordar) — exercita al menos
# una pregunta de cada categoría: deterministas (plataforma*, monetizacion*),
# de texto libre (LLM), controles de bucle y compuertas.
_PASOS = [
    ("nuevo_o_existente", "Es un proyecto nuevo"),
    ("nombre_proyecto", "Cafecito"),
    ("problema_objetivo", "Quiero llevar el control de pedidos de mi cafetería."),
    ("plataforma", "Desde el celular"),
    ("plataforma_offline", "Sí"),
    ("perfil_usuario", "Meseros del café"),
    ("perfil_usuario_continuar", "No"),
    ("administracion_cantidad", "Una sola persona"),
    ("funcionalidad_declarada", "Registrar pedidos nuevos"),
    ("funcionalidad_declarada_continuar", "No"),
    ("monetizacion", "Sí, de alguna forma"),
    ("monetizacion_forma", "Suscripción (pago recurrente)"),
    ("dato_recordar", "No"),
    ("restriccion_tecnica", "Ya usamos Google Sheets, si se puede reutilizar mejor."),
    ("restriccion_tiempo_presupuesto", "Presupuesto limitado, no hay fecha límite estricta."),
    ("restriccion_negocio", "No debe compartir los datos de los clientes con terceros."),
    ("cierre_libre", "Nada más por ahora."),
]


def _completar_formulario(codigo: str) -> dict:
    """Registra `_PASOS` completo vía `RepositorioRespuestasFormulario` real
    y devuelve `{pregunta_id: RespuestaFormulario}` (con `id` real de BD)."""
    repo = RepositorioRespuestasFormulario()
    filas = {}
    for pregunta_id, valor in _PASOS:
        filas[pregunta_id] = _registrar(codigo, pregunta_id, valor, repo)
    return filas


def _linea(**kw) -> str:
    return json.dumps(kw, ensure_ascii=False)


class TestPrecondicionArbolCompleto:
    def test_el_recorrido_de_prueba_completa_el_arbol(self, db):
        from src.formulario.arbol import siguiente_pregunta
        _completar_formulario("PROY-VERIF")
        respuestas = RepositorioRespuestasFormulario().listar("PROY-VERIF")
        assert siguiente_pregunta(respuestas) is None


class TestFormularioIncompleto:
    def test_sin_ninguna_respuesta_lanza(self, db):
        with pytest.raises(FormularioIncompleto):
            ejecutar_discovery("PROY-VACIO", _ClienteFalso())

    def test_formulario_a_medias_lanza(self, db):
        repo = RepositorioRespuestasFormulario()
        _registrar("PROY-MEDIO", "nuevo_o_existente", "Es un proyecto nuevo", repo)
        _registrar("PROY-MEDIO", "nombre_proyecto", "X", repo)
        with pytest.raises(FormularioIncompleto):
            ejecutar_discovery("PROY-MEDIO", _ClienteFalso())

    def test_formulario_incompleto_no_registra_ninguna_accion(self, db):
        repo_acc = RepositorioAcciones()
        with pytest.raises(FormularioIncompleto):
            ejecutar_discovery("PROY-MEDIO2", _ClienteFalso(), repo_acciones=repo_acc)
        assert repo_acc.listar(ticket="PROY-MEDIO2") == []


class TestFormularioCompletoEjecutable:
    def test_ejecuta_y_devuelve_resultado(self, db):
        filas = _completar_formulario("PROY-001")
        cliente = _ClienteFalso(_linea(
            tipo="requisito", respuesta_id=filas["problema_objetivo"].id,
            descripcion="Poder registrar pedidos nuevos de clientes",
        ))
        resultado = ejecutar_discovery("PROY-001", cliente)
        assert isinstance(resultado, ResultadoDiscovery)
        assert resultado.codigo == "PROY-001"
        assert resultado.nombre_proyecto == "Cafecito"
        assert resultado.entidades_creadas > 0

    def test_llama_al_llm_exactamente_una_vez(self, db):
        _completar_formulario("PROY-002")
        cliente = _ClienteFalso("")
        ejecutar_discovery("PROY-002", cliente)
        assert cliente.llamadas == 1

    def test_no_llama_al_llm_si_no_hay_contexto_que_interpretar(self, db, monkeypatch):
        """Guarda de cortocircuito: si `construir_contexto` no encuentra
        nada que interpretar, Discovery no gasta una llamada al proveedor."""
        _completar_formulario("PROY-003")
        import src.discovery.discovery as discovery_mod
        monkeypatch.setattr(discovery_mod, "construir_contexto", lambda respuestas: ("", set()))
        cliente = _ClienteFalso("")
        ejecutar_discovery("PROY-003", cliente)
        assert cliente.llamadas == 0


class TestRespuestasDeterministasNoLlamanAlLLM:
    def test_entidades_deterministas_no_dependen_de_la_salida_del_llm(self, db):
        """Aunque el LLM no devuelva nada útil, las entidades deterministas
        (plataforma, plataforma_offline, monetizacion*) se crean igual: no
        dependen de lo que responda el proveedor."""
        _completar_formulario("PROY-004")
        ejecutar_discovery("PROY-004", _ClienteFalso(""))

        requisitos = RepositorioRequisitos().listar("PROY-004")
        descripciones = " ".join(r.descripcion for r in requisitos)
        assert "celular" in descripciones
        assert "conexión" in descripciones
        assert "cobrar" in descripciones
        assert "suscripción" in descripciones.lower()
        assert all(r.confianza == NivelConfianza.ALTA for r in requisitos)


class TestControlesDeBucleNoGeneranEntidades:
    def test_ningun_requisito_menciona_contenido_de_un_continuar(self, db):
        """Los controles `*_continuar` ("Sí"/"No") no tienen contenido
        propio interpretable; esta prueba confirma que Discovery completo
        no produce ninguna entidad para ellos (ni determinista ni vía LLM,
        porque ni siquiera llegan al contexto del agente)."""
        filas = _completar_formulario("PROY-005")
        ejecutar_discovery("PROY-005", _ClienteFalso(""))
        for pregunta_id in (
            "perfil_usuario_continuar", "funcionalidad_declarada_continuar",
        ):
            referencia = str(filas[pregunta_id].id)
            for repo in (RepositorioRequisitos(), RepositorioPerfiles(), RepositorioDatos()):
                entidades = repo.listar("PROY-005")
                assert all(
                    e.fuente_directa is None or e.fuente_directa.referencia != referencia
                    for e in entidades
                )


class TestTextoLibreLlegaAlIntprete:
    def test_texto_libre_aparece_en_el_prompt_recibido_por_el_cliente(self, db):
        class _ClienteQueGuardaPrompt:
            def __init__(self):
                self.ultimo_prompt = None

            def completar(self, prompt, opciones):
                self.ultimo_prompt = prompt
                return RespuestaIA(texto="", tokens_entrada=1, tokens_salida=1, modelo="fake")

        _completar_formulario("PROY-006")
        cliente = _ClienteQueGuardaPrompt()
        ejecutar_discovery("PROY-006", cliente)
        assert "Quiero llevar el control de pedidos de mi cafetería." in cliente.ultimo_prompt
        assert "Meseros del café" in cliente.ultimo_prompt
        assert "Ya usamos Google Sheets" in cliente.ultimo_prompt


class TestJsonValidoDelLlmSeInterpreta:
    def test_entidad_valida_del_llm_se_persiste(self, db):
        filas = _completar_formulario("PROY-007")
        cliente = _ClienteFalso(_linea(
            tipo="perfil", respuesta_id=filas["perfil_usuario"].id,
            nombre="Meseros", descripcion="Atienden a los clientes y registran pedidos",
        ))
        ejecutar_discovery("PROY-007", cliente)
        perfiles = RepositorioPerfiles().listar("PROY-007")
        assert len(perfiles) == 1
        assert perfiles[0].nombre == "Meseros"
        assert perfiles[0].confianza == NivelConfianza.MEDIA


class TestRestriccionDelLlm:
    def test_restriccion_valida_se_persiste(self, db):
        filas = _completar_formulario("PROY-007B")
        cliente = _ClienteFalso(_linea(
            tipo="restriccion", respuesta_id=filas["restriccion_tecnica"].id,
            tipo_restriccion="tecnica", descripcion="Ya usan Google Sheets y prefieren reutilizarlo",
        ))
        ejecutar_discovery("PROY-007B", cliente)
        restricciones = RepositorioRestricciones().listar("PROY-007B")
        assert len(restricciones) == 1
        assert restricciones[0].tipo == "tecnica"
        assert restricciones[0].naturaleza == NaturalezaInformacion.DECLARADO
        assert restricciones[0].origen == OrigenDato.USER


class TestJsonInvalidoDelLlmNoRompeDiscovery:
    def test_texto_ininterpretable_no_lanza_y_reporta_problema(self, db):
        _completar_formulario("PROY-008")
        cliente = _ClienteFalso("esto no es json en absoluto")
        resultado = ejecutar_discovery("PROY-008", cliente)
        assert resultado.problemas  # reportado, no silenciado
        # las deterministas igual se crearon:
        assert RepositorioRequisitos().listar("PROY-008") != []
        # nada del LLM se persistió:
        assert RepositorioPerfiles().listar("PROY-008") == []


class TestInformacionInventadaNoSePersiste:
    def test_respuesta_id_inventado_se_descarta(self, db):
        _completar_formulario("PROY-009")
        cliente = _ClienteFalso(_linea(
            tipo="perfil", respuesta_id=999999, nombre="Fantasma", descripcion="No existe",
        ))
        resultado = ejecutar_discovery("PROY-009", cliente)
        assert RepositorioPerfiles().listar("PROY-009") == []
        assert any("inventada" in p for p in resultado.problemas)


class TestTrazabilidadFuenteDirecta:
    def test_entidad_determinista_referencia_su_fila(self, db):
        filas = _completar_formulario("PROY-010")
        ejecutar_discovery("PROY-010", _ClienteFalso(""))
        requisitos = RepositorioRequisitos().listar("PROY-010")
        offline = next(r for r in requisitos if "conexión" in r.descripcion)
        assert offline.fuente_directa == FuenteDirecta(
            tipo="formulario", referencia=str(filas["plataforma_offline"].id),
        )

    def test_entidad_del_llm_referencia_la_fila_de_texto_libre_correcta(self, db):
        filas = _completar_formulario("PROY-011")
        cliente = _ClienteFalso(_linea(
            tipo="requisito", respuesta_id=filas["funcionalidad_declarada"].id,
            descripcion="Poder registrar un pedido nuevo",
        ))
        ejecutar_discovery("PROY-011", cliente)
        requisitos = RepositorioRequisitos().listar("PROY-011")
        del_llm = next(r for r in requisitos if r.confianza == NivelConfianza.MEDIA)
        assert del_llm.fuente_directa == FuenteDirecta(
            tipo="formulario", referencia=str(filas["funcionalidad_declarada"].id),
        )


class TestConfianza:
    def test_deterministas_alta_llm_media(self, db):
        filas = _completar_formulario("PROY-012")
        cliente = _ClienteFalso(_linea(
            tipo="requisito", respuesta_id=filas["problema_objetivo"].id, descripcion="Algo",
        ))
        ejecutar_discovery("PROY-012", cliente)
        requisitos = RepositorioRequisitos().listar("PROY-012")
        deterministas = [r for r in requisitos if r.fuente_directa.referencia == str(filas["plataforma"].id)]
        del_llm = [r for r in requisitos if r.fuente_directa.referencia == str(filas["problema_objetivo"].id)]
        assert deterministas and all(r.confianza == NivelConfianza.ALTA for r in deterministas)
        assert del_llm and all(r.confianza == NivelConfianza.MEDIA for r in del_llm)


def _falla_persistencia(self, *a, **kw):
    raise RuntimeError("fallo simulado en persistencia de Dato")


class TestAtomicidad:
    def test_fallo_en_una_escritura_no_deja_nada_de_esa_corrida(self, db, monkeypatch):
        """Si la persistencia de una de las entidades del lote falla (aquí,
        la que viene del LLM), NINGUNA entidad de esa corrida debe
        sobrevivir — ni siquiera las deterministas que ya se habían escrito
        antes, dentro del mismo `LoteDescubrimiento`."""
        filas = _completar_formulario("PROY-013")
        cliente = _ClienteFalso(_linea(
            tipo="dato", respuesta_id=filas["problema_objetivo"].id,
            descripcion="Historial de pedidos", temporalidad=None, sensibilidad=None,
        ))

        monkeypatch.setattr(RepositorioDatos, "crear", _falla_persistencia)

        with pytest.raises(RuntimeError, match="fallo simulado"):
            ejecutar_discovery("PROY-013", cliente)

        # Las deterministas (plataforma*, monetizacion*) se intentaron ANTES
        # que el Dato roto, dentro del mismo lote — deben haberse revertido.
        assert RepositorioRequisitos().listar("PROY-013") == []
        assert RepositorioDatos().listar("PROY-013") == []

    def test_accion_envolvente_queda_fallida(self, db, monkeypatch):
        filas = _completar_formulario("PROY-014")
        cliente = _ClienteFalso(_linea(
            tipo="dato", respuesta_id=filas["problema_objetivo"].id,
            descripcion="x", temporalidad=None, sensibilidad=None,
        ))
        monkeypatch.setattr(RepositorioDatos, "crear", _falla_persistencia)
        repo_acc = RepositorioAcciones()
        with pytest.raises(RuntimeError):
            ejecutar_discovery("PROY-014", cliente, repo_acciones=repo_acc)

        acciones = [a for a in repo_acc.listar(ticket="PROY-014") if a["tipo"] == "discovery_formulario"]
        assert len(acciones) == 1
        assert acciones[0]["estado"] == FALLIDA


class TestNuncaEscribeProjectState:
    def test_expedientes_permanece_vacia(self, db):
        _completar_formulario("PROY-015")
        cliente = _ClienteFalso(_linea(
            tipo="perfil", respuesta_id=0, nombre="x", descripcion="y",
        ))
        # `respuesta_id=0` no es válido (se descarta) — igual sirve para
        # comprobar que, pase lo que pase, `expedientes` nunca se toca.
        ejecutar_discovery("PROY-015", cliente)

        conn = database.get_connection()
        fila = conn.execute("SELECT COUNT(*) AS n FROM expedientes").fetchone()
        conn.close()
        assert fila["n"] == 0

    def test_no_importa_repositorio_expedientes_ni_el_orquestador_viejo(self):
        """Revisa las líneas `import`/`from` reales del módulo (no la prosa
        del docstring, que sí nombra `RepositorioExpedientes` para explicar
        por qué NO se importa)."""
        import ast
        import src.discovery.discovery as discovery_mod

        arbol = ast.parse(open(discovery_mod.__file__, encoding="utf-8").read())
        modulos_importados = set()
        for nodo in ast.walk(arbol):
            if isinstance(nodo, ast.ImportFrom) and nodo.module:
                modulos_importados.add(nodo.module)
                modulos_importados.update(f"{nodo.module}.{alias.name}" for alias in nodo.names)
            elif isinstance(nodo, ast.Import):
                modulos_importados.update(alias.name for alias in nodo.names)

        assert not any(m.startswith("src.orquestador") for m in modulos_importados)
        assert not any(m.startswith("src.app") for m in modulos_importados)
        assert "src.repositorios.expedientes" not in modulos_importados
        assert "src.repositorios.expedientes.RepositorioExpedientes" not in modulos_importados


# --- TF-0032: reglas de consecuencia + Gap/Contradiccion + EstadoDiscovery --

# _PASOS ya contiene el caso real auditado (monetizacion=Sí + dato_recordar=No):
# toda corrida con _completar_formulario() dispara la contradicción real.
_PASOS_SIN_CONTRADICCION = []
for _pid, _val in _PASOS:
    if _pid == "dato_recordar":
        _PASOS_SIN_CONTRADICCION.append((_pid, "Sí"))
        _PASOS_SIN_CONTRADICCION.append(("dato_recordar_detalle", "El historial de pedidos de cada cliente"))
        _PASOS_SIN_CONTRADICCION.append(("dato_recordar_detalle_continuar", "No"))
    else:
        _PASOS_SIN_CONTRADICCION.append((_pid, _val))


def _completar_formulario_sin_contradiccion(codigo: str) -> dict:
    repo = RepositorioRespuestasFormulario()
    filas = {}
    for pregunta_id, valor in _PASOS_SIN_CONTRADICCION:
        filas[pregunta_id] = _registrar(codigo, pregunta_id, valor, repo)
    return filas


class TestReglasConsecuenciaWiring:
    def test_contradiccion_real_queda_registrada(self, db):
        _completar_formulario("PROY-016")
        ejecutar_discovery("PROY-016", _ClienteFalso(""))
        contradicciones = RepositorioContradicciones().listar("PROY-016")
        assert len(contradicciones) == 1
        assert contradicciones[0].estado == EstadoContradiccion.ABIERTA
        assert contradicciones[0].concepto == "datos.existencia_de_dato"
        assert len(contradicciones[0].afirmaciones) == 2

    def test_no_se_duplica_si_ya_existe_para_el_mismo_concepto(self, db):
        """Idempotencia (A3): `_persistir_hallazgo_determinista` no crea un
        segundo registro para el mismo `codigo` + `concepto`."""
        from src.discovery import reglas_consecuencia
        from src.discovery.discovery import _persistir_hallazgo_determinista
        from src.repositorios.lote_descubrimiento import LoteDescubrimiento

        _completar_formulario("PROY-016B")
        respuestas = RepositorioRespuestasFormulario().listar("PROY-016B")
        hallazgo = reglas_consecuencia.evaluar_reglas("PROY-016B", respuestas)[0]
        repo_gap, repo_contra = RepositorioGaps(), RepositorioContradicciones()

        for _ in range(2):
            with LoteDescubrimiento() as lote:
                _persistir_hallazgo_determinista(
                    hallazgo, codigo="PROY-016B", conexion=lote.conexion,
                    repo_gaps=repo_gap, repo_contradicciones=repo_contra,
                )
        assert len(repo_contra.listar("PROY-016B")) == 1


class TestEstadoDiscovery:
    def test_requiere_aclaracion_si_hay_contradiccion_abierta(self, db):
        _completar_formulario("PROY-017")
        resultado = ejecutar_discovery("PROY-017", _ClienteFalso(""))
        assert resultado.estado == EstadoDiscovery.REQUIERE_ACLARACION

    def test_completo_sin_contradiccion_ni_gap(self, db):
        _completar_formulario_sin_contradiccion("PROY-018")
        resultado = ejecutar_discovery("PROY-018", _ClienteFalso(""))
        assert resultado.estado == EstadoDiscovery.COMPLETO
        assert RepositorioContradicciones().listar("PROY-018") == []

    def test_estado_se_guarda_en_el_resultado_de_la_accion(self, db):
        _completar_formulario("PROY-018B")
        repo_acc = RepositorioAcciones()
        ejecutar_discovery("PROY-018B", _ClienteFalso(""), repo_acciones=repo_acc)
        accion = next(a for a in repo_acc.listar(ticket="PROY-018B") if a["tipo"] == "discovery_formulario")
        assert json.loads(accion["resultado"])["estado"] == "requiere_aclaracion"


class TestHallazgoLLMSePersisteComoGap:
    def test_hallazgo_valido_crea_un_gap(self, db):
        filas = _completar_formulario("PROY-019")
        cliente = _ClienteFalso(_linea(
            tipo="hallazgo", respuesta_id=filas["problema_objetivo"].id,
            dominio="datos", etiqueta="sensibilidad",
            motivo="No queda claro si el historial incluye datos de pago.",
        ))
        ejecutar_discovery("PROY-019", cliente)
        gaps = RepositorioGaps().listar("PROY-019")
        assert any(g.campo_o_concepto == "datos.sensibilidad" for g in gaps)
        assert all(g.estado == EstadoGap.ABIERTO for g in gaps)

    def test_hallazgo_del_llm_nunca_se_persiste_como_contradiccion(self, db):
        filas = _completar_formulario("PROY-020")
        cliente = _ClienteFalso(_linea(
            tipo="hallazgo", respuesta_id=filas["problema_objetivo"].id,
            dominio="funcionalidad", etiqueta="funcionalidad_faltante", motivo="x",
        ))
        ejecutar_discovery("PROY-020", cliente)
        contradicciones = RepositorioContradicciones().listar("PROY-020")
        assert all(c.concepto != "funcionalidad.funcionalidad_faltante" for c in contradicciones)


class TestHelpersInternos:
    """Cobertura directa de las funciones privadas que no se alcanzan con
    un escenario real completo (solo 1 regla implementada hoy)."""

    def test_calcular_estado_en_progreso_si_falta_una_pregunta(self, db):
        from src.discovery.discovery import _calcular_estado
        respuestas = RepositorioRespuestasFormulario().listar("PROY-VACIO-ESTADO")
        estado = _calcular_estado(respuestas, "PROY-VACIO-ESTADO", RepositorioGaps(), RepositorioContradicciones())
        assert estado == EstadoDiscovery.EN_PROGRESO

    def test_calcular_estado_requiere_aclaracion_por_gap_abierto(self, db):
        from src.discovery.discovery import _calcular_estado
        _completar_formulario_sin_contradiccion("PROY-ESTADO-GAP")
        RepositorioGaps().crear("PROY-ESTADO-GAP", "respuesta_formulario", "datos.sensibilidad", motivo="x")
        respuestas = RepositorioRespuestasFormulario().listar("PROY-ESTADO-GAP")
        estado = _calcular_estado(respuestas, "PROY-ESTADO-GAP", RepositorioGaps(), RepositorioContradicciones())
        assert estado == EstadoDiscovery.REQUIERE_ACLARACION

    def test_calcular_estado_completo_con_pendientes_por_gap_documentado(self, db):
        from src.discovery.discovery import _calcular_estado
        _completar_formulario_sin_contradiccion("PROY-ESTADO-PEND")
        gap = RepositorioGaps().crear("PROY-ESTADO-PEND", "respuesta_formulario", "datos.sensibilidad", motivo="x")
        RepositorioGaps().marcar_estado(gap.id, EstadoGap.DOCUMENTADO_NO_BLOQUEANTE)
        respuestas = RepositorioRespuestasFormulario().listar("PROY-ESTADO-PEND")
        estado = _calcular_estado(respuestas, "PROY-ESTADO-PEND", RepositorioGaps(), RepositorioContradicciones())
        assert estado == EstadoDiscovery.COMPLETO_CON_PENDIENTES

    def test_persistir_hallazgo_determinista_tipo_gap(self, db):
        from src.discovery.discovery import _persistir_hallazgo_determinista
        from src.discovery.reglas_consecuencia import HallazgoConsecuencia
        from src.repositorios.lote_descubrimiento import LoteDescubrimiento

        hallazgo = HallazgoConsecuencia(
            tipo="gap", dominio="datos", etiqueta="sensibilidad",
            respuestas_relacionadas=[1], motivo="x",
        )
        with LoteDescubrimiento() as lote:
            _persistir_hallazgo_determinista(
                hallazgo, codigo="PROY-GAP-DET", conexion=lote.conexion,
                repo_gaps=RepositorioGaps(), repo_contradicciones=RepositorioContradicciones(),
            )
        gaps = RepositorioGaps().listar("PROY-GAP-DET")
        assert len(gaps) == 1 and gaps[0].campo_o_concepto == "datos.sensibilidad"

    def test_persistir_hallazgo_determinista_tipo_gap_es_idempotente(self, db):
        from src.discovery.discovery import _persistir_hallazgo_determinista
        from src.discovery.reglas_consecuencia import HallazgoConsecuencia
        from src.repositorios.lote_descubrimiento import LoteDescubrimiento

        hallazgo = HallazgoConsecuencia(
            tipo="gap", dominio="datos", etiqueta="sensibilidad",
            respuestas_relacionadas=[1], motivo="x",
        )
        for _ in range(2):
            with LoteDescubrimiento() as lote:
                _persistir_hallazgo_determinista(
                    hallazgo, codigo="PROY-GAP-DET-IDEMP", conexion=lote.conexion,
                    repo_gaps=RepositorioGaps(), repo_contradicciones=RepositorioContradicciones(),
                )
        assert len(RepositorioGaps().listar("PROY-GAP-DET-IDEMP")) == 1

    def test_persistir_hallazgo_llm_es_idempotente(self, db):
        from src.discovery.discovery import _persistir_hallazgo_llm
        from src.discovery.interpretacion_llm import HallazgoLLM
        from src.repositorios.lote_descubrimiento import LoteDescubrimiento

        hallazgo = HallazgoLLM(dominio="datos", etiqueta="sensibilidad", motivo="x", respuesta_id=1)
        for _ in range(2):
            with LoteDescubrimiento() as lote:
                _persistir_hallazgo_llm(hallazgo, codigo="PROY-GAP-LLM", conexion=lote.conexion, repo_gaps=RepositorioGaps())
        assert len(RepositorioGaps().listar("PROY-GAP-LLM")) == 1

    def test_profundidad_alcanzada(self, db):
        from src.discovery.discovery import _profundidad_alcanzada
        from src.discovery.reglas_consecuencia import LIMITE_PROFUNDIDAD_CADENA
        repo_gaps = RepositorioGaps()
        for i in range(LIMITE_PROFUNDIDAD_CADENA):
            repo_gaps.crear("PROY-PROFUNDIDAD", "respuesta_formulario", f"datos.etiqueta{i}", motivo="x")
        assert _profundidad_alcanzada("PROY-PROFUNDIDAD", repo_gaps, RepositorioContradicciones()) is True
        assert _profundidad_alcanzada("PROY-OTRO", repo_gaps, RepositorioContradicciones()) is False


class TestAtomicidadIncluyeHallazgos:
    def test_fallo_en_la_escritura_tambien_revierte_los_hallazgos(self, db, monkeypatch):
        filas = _completar_formulario("PROY-021")
        cliente = _ClienteFalso(_linea(
            tipo="dato", respuesta_id=filas["problema_objetivo"].id,
            descripcion="x", temporalidad=None, sensibilidad=None,
        ))
        monkeypatch.setattr(RepositorioDatos, "crear", _falla_persistencia)

        with pytest.raises(RuntimeError):
            ejecutar_discovery("PROY-021", cliente)

        # La contradicción real (monetizacion/datos) se intenta ANTES que el
        # Dato roto (los hallazgos se persisten después de las entidades,
        # en el mismo lote) — debe revertirse igual que las entidades.
        assert RepositorioContradicciones().listar("PROY-021") == []
        assert RepositorioRequisitos().listar("PROY-021") == []
