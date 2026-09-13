"""Pruebas de `procesar_reapertura()` (TF-0032) contra SQLite real (fixture
`db`). No reprocesa nunca el formulario completo — solo resuelve UN
hallazgo puntual a partir de una respuesta ya registrada.
"""
import json

import pytest

from src.ai.cliente import RespuestaIA
from src.discovery.discovery import procesar_reapertura
from src.expediente.modelo import EstadoContradiccion, EstadoGap
from src.formulario.preguntas import PREGUNTAS
from src.formulario.respuestas import serializar_respuesta
from src.repositorios.acciones import COMPLETADA, RepositorioAcciones
from src.repositorios.contradicciones import RepositorioContradicciones
from src.repositorios.gaps import RepositorioGaps
from src.repositorios.requisitos import RepositorioRequisitos
from src.repositorios.respuestas_formulario import RepositorioRespuestasFormulario


class _ClienteFalso:
    def __init__(self, texto=""):
        self._texto = texto
        self.llamadas = 0

    def completar(self, prompt, opciones):
        self.llamadas += 1
        return RespuestaIA(texto=self._texto, tokens_entrada=1, tokens_salida=1, modelo="fake")


def _registrar(codigo, pregunta_id, valor):
    pregunta = PREGUNTAS[pregunta_id]
    texto = serializar_respuesta(pregunta, valor)
    return RepositorioRespuestasFormulario().registrar(codigo, pregunta_id, pregunta.texto, pregunta.tipo_pregunta, texto)


def _linea(**kw) -> str:
    return json.dumps(kw, ensure_ascii=False)


class TestGapResoluble:
    def test_respuesta_cerrada_no_incierta_resuelve(self, db):
        codigo = "PROY-R01"
        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.existencia_de_dato", motivo="x")
        _registrar(codigo, "dato_recordar", "Sí")

        resultado = procesar_reapertura(codigo, "gap", gap.id, _ClienteFalso())

        assert resultado.resuelto is True
        assert resultado.ya_procesado is False
        assert RepositorioGaps().obtener(gap.id).estado == EstadoGap.RESUELTO

    def test_respuesta_incierta_no_resuelve_ni_degrada(self, db):
        codigo = "PROY-R02"
        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.existencia_de_dato", motivo="x")
        _registrar(codigo, "dato_recordar", "No estoy seguro")

        resultado = procesar_reapertura(codigo, "gap", gap.id, _ClienteFalso())

        assert resultado.resuelto is False
        assert RepositorioGaps().obtener(gap.id).estado == EstadoGap.ABIERTO

    def test_respuesta_libre_suficiente_resuelve(self, db):
        codigo = "PROY-R03"
        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.retencion", motivo="x")
        _registrar(codigo, "dato_retencion", "Se borra automáticamente después de un año.")

        resultado = procesar_reapertura(codigo, "gap", gap.id, _ClienteFalso(""))  # Qwen no vuelve a señalar nada

        assert resultado.resuelto is True
        assert RepositorioGaps().obtener(gap.id).estado == EstadoGap.RESUELTO

    def test_respuesta_libre_que_qwen_sigue_senalando_no_resuelve(self, db):
        codigo = "PROY-R04"
        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.retencion", motivo="x")
        fila = _registrar(codigo, "dato_retencion", "Algo, no sé bien cuánto tiempo.")
        cliente = _ClienteFalso(_linea(
            tipo="hallazgo", respuesta_id=fila.id, dominio="datos", etiqueta="retencion",
            motivo="Sigue sin especificar cuánto tiempo se conserva.",
        ))

        resultado = procesar_reapertura(codigo, "gap", gap.id, cliente)

        assert resultado.resuelto is False
        assert RepositorioGaps().obtener(gap.id).estado == EstadoGap.ABIERTO


class TestContradiccionResoluble:
    def test_respuesta_cerrada_resuelve_y_conserva_afirmaciones(self, db):
        codigo = "PROY-R05"
        afirmaciones = [
            {"valor": "Sí, de alguna forma", "origen": "respuesta_formulario#1"},
            {"valor": "No", "origen": "respuesta_formulario#2"},
        ]
        contradiccion = RepositorioContradicciones().crear(
            codigo, "respuesta_formulario", "datos.existencia_de_dato", afirmaciones,
        )
        fila = _registrar(codigo, "dato_recordar", "Sí")

        resultado = procesar_reapertura(codigo, "contradiccion", contradiccion.id, _ClienteFalso())

        assert resultado.resuelto is True
        recargada = RepositorioContradicciones().obtener(contradiccion.id)
        assert recargada.estado == EstadoContradiccion.RESUELTA
        assert recargada.resolucion_valor == "Sí"
        assert len(recargada.afirmaciones) == 3
        assert recargada.afirmaciones[:2] == afirmaciones  # las originales, intactas
        assert recargada.afirmaciones[2]["origen"] == f"respuesta_formulario#{fila.id}"

    def test_no_resuelve_pero_agrega_evidencia_igual(self, db):
        codigo = "PROY-R06"
        afirmaciones = [
            {"valor": "Sí, de alguna forma", "origen": "respuesta_formulario#1"},
            {"valor": "No", "origen": "respuesta_formulario#2"},
        ]
        contradiccion = RepositorioContradicciones().crear(
            codigo, "respuesta_formulario", "datos.existencia_de_dato", afirmaciones,
        )
        _registrar(codigo, "dato_recordar", "No estoy seguro")

        resultado = procesar_reapertura(codigo, "contradiccion", contradiccion.id, _ClienteFalso())

        assert resultado.resuelto is False
        recargada = RepositorioContradicciones().obtener(contradiccion.id)
        assert recargada.estado == EstadoContradiccion.ABIERTA
        assert len(recargada.afirmaciones) == 3  # la nueva SÍ se conserva como evidencia


class TestIdempotencia:
    def test_hallazgo_ya_resuelto_es_no_op(self, db):
        codigo = "PROY-R07"
        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.existencia_de_dato", motivo="x")
        RepositorioGaps().marcar_estado(gap.id, EstadoGap.RESUELTO)
        _registrar(codigo, "dato_recordar", "Sí")

        resultado = procesar_reapertura(codigo, "gap", gap.id, _ClienteFalso())

        assert resultado.ya_procesado is True
        assert resultado.resuelto is False

    def test_terna_exacta_repetida_es_no_op_total(self, db):
        """(tipo_hallazgo, hallazgo_id, respuesta_nueva.id) repetida no crea
        otra acción, otro lote, otra entidad, ni una segunda resolución."""
        codigo = "PROY-R08"
        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.existencia_de_dato", motivo="x")
        _registrar(codigo, "dato_recordar", "Sí")
        cliente = _ClienteFalso()

        primero = procesar_reapertura(codigo, "gap", gap.id, cliente)
        assert primero.resuelto is True
        assert primero.ya_procesado is False

        # El Gap ya quedó RESUELTO, así que la guardia de estado (capa 1) ya
        # basta — pero además no debe haber una segunda acción registrada.
        repo_acc = RepositorioAcciones()
        acciones_resolver = [
            a for a in repo_acc.listar(ticket=codigo) if a["tipo"] == "resolver_hallazgo_discovery"
        ]
        assert len(acciones_resolver) == 1
        assert acciones_resolver[0]["estado"] == COMPLETADA

        segundo = procesar_reapertura(codigo, "gap", gap.id, cliente)
        assert segundo.ya_procesado is True
        acciones_resolver_despues = [
            a for a in repo_acc.listar(ticket=codigo) if a["tipo"] == "resolver_hallazgo_discovery"
        ]
        assert len(acciones_resolver_despues) == 1  # sin una segunda acción

    def test_capa_2_detecta_la_terna_aunque_el_estado_ya_cambiara(self, db, monkeypatch):
        """Simula la carrera: el hallazgo sigue ABIERTO (no lo detecta la
        capa 1), pero ya existe una acción registrada con la misma terna —
        la capa 2 debe interceptarla igual."""
        codigo = "PROY-R09"
        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.existencia_de_dato", motivo="x")
        fila = _registrar(codigo, "dato_recordar", "Sí")

        terna = {"tipo_hallazgo": "gap", "hallazgo_id": gap.id, "respuesta_id": fila.id}
        RepositorioAcciones().registrar(
            ticket=codigo, actor="discovery_reapertura", tipo="resolver_hallazgo_discovery", entrada=terna,
        )
        # El Gap sigue ABIERTO (no se tocó), pero la terna ya está registrada.
        resultado = procesar_reapertura(codigo, "gap", gap.id, _ClienteFalso())
        assert resultado.ya_procesado is True
        assert RepositorioGaps().obtener(gap.id).estado == EstadoGap.ABIERTO  # sin tocar


class TestSinPreguntaCatalogada:
    def test_devuelve_problema_sin_lanzar(self, db):
        codigo = "PROY-R10"
        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "marca.etiqueta_inventada", motivo="x")
        resultado = procesar_reapertura(codigo, "gap", gap.id, _ClienteFalso())
        assert resultado.ya_procesado is False
        assert resultado.resuelto is False
        assert any("sin pregunta catalogada" in p for p in resultado.problemas)


class TestSinRespuestaTodavia:
    def test_devuelve_problema_si_la_pregunta_no_se_ha_respondido(self, db):
        codigo = "PROY-R11"
        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.existencia_de_dato", motivo="x")
        resultado = procesar_reapertura(codigo, "gap", gap.id, _ClienteFalso())
        assert resultado.ya_procesado is False
        assert resultado.resuelto is False
        assert any("todavía no tiene respuesta" in p for p in resultado.problemas)


class TestTipoHallazgoInvalido:
    def test_lanza_value_error(self, db):
        with pytest.raises(ValueError):
            procesar_reapertura("PROY-R12", "algo_desconocido", 1, _ClienteFalso())


class TestEncadenamiento:
    def test_un_hallazgo_distinto_se_persiste_como_nuevo_gap(self, db):
        codigo = "PROY-R14"
        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.retencion", motivo="x")
        fila = _registrar(codigo, "dato_retencion", "El historial de pedidos se conserva un año")
        # Qwen resuelve ESTE gap (no vuelve a señalar datos.retencion) pero
        # además encuentra uno nuevo, distinto — una cadena legítima.
        cliente = _ClienteFalso(_linea(
            tipo="hallazgo", respuesta_id=fila.id, dominio="funcionalidad",
            etiqueta="funcionalidad_faltante", motivo="No se aclaró el flujo completo.",
        ))

        resultado = procesar_reapertura(codigo, "gap", gap.id, cliente)

        assert resultado.resuelto is True
        nuevos = RepositorioGaps().listar(codigo)
        assert any(g.campo_o_concepto == "funcionalidad.funcionalidad_faltante" for g in nuevos)

    def test_encadenamiento_respeta_el_limite_de_profundidad(self, db):
        from src.discovery.reglas_consecuencia import LIMITE_PROFUNDIDAD_CADENA

        codigo = "PROY-R15"
        # Ya hay LIMITE_PROFUNDIDAD_CADENA hallazgos previos para este codigo.
        for i in range(LIMITE_PROFUNDIDAD_CADENA):
            RepositorioGaps().crear(codigo, "respuesta_formulario", f"restricciones.otro{i}", motivo="x")

        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.retencion", motivo="x")
        fila = _registrar(codigo, "dato_retencion", "El historial de pedidos se conserva un año")
        cliente = _ClienteFalso(_linea(
            tipo="hallazgo", respuesta_id=fila.id, dominio="funcionalidad",
            etiqueta="funcionalidad_faltante", motivo="x",
        ))

        resultado = procesar_reapertura(codigo, "gap", gap.id, cliente)

        assert resultado.resuelto is True  # el hallazgo ORIGINAL sí se resuelve
        assert not any(
            g.campo_o_concepto == "funcionalidad.funcionalidad_faltante"
            for g in RepositorioGaps().listar(codigo)
        )
        assert any("límite de profundidad" in p for p in resultado.problemas)


class TestFalloDuranteResolucion:
    def test_marca_fallida_y_relanza(self, db, monkeypatch):
        codigo = "PROY-R16"
        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.existencia_de_dato", motivo="x")
        _registrar(codigo, "dato_recordar", "Sí")

        def _falla(self, *a, **kw):
            raise RuntimeError("fallo simulado al marcar resuelto")

        monkeypatch.setattr(RepositorioGaps, "marcar_estado", _falla)

        with pytest.raises(RuntimeError, match="fallo simulado"):
            procesar_reapertura(codigo, "gap", gap.id, _ClienteFalso())

        acciones = [
            a for a in RepositorioAcciones().listar(ticket=codigo)
            if a["tipo"] == "resolver_hallazgo_discovery"
        ]
        assert len(acciones) == 1
        assert acciones[0]["estado"] == "FALLIDA"


class TestNuncaReprocesaElFormularioCompleto:
    def test_entidades_de_la_corrida_original_no_se_duplican(self, db):
        """`procesar_reapertura()` nunca vuelve a llamar `interpretar_directo`
        ni a crear las entidades de una corrida completa — solo existe la vía
        de `ejecutar_discovery` para eso."""
        codigo = "PROY-R13"
        gap = RepositorioGaps().crear(codigo, "respuesta_formulario", "datos.existencia_de_dato", motivo="x")
        _registrar(codigo, "dato_recordar", "Sí")
        antes = len(RepositorioRequisitos().listar(codigo))
        procesar_reapertura(codigo, "gap", gap.id, _ClienteFalso())
        despues = len(RepositorioRequisitos().listar(codigo))
        assert antes == despues == 0  # nunca corrió ejecutar_discovery aquí
