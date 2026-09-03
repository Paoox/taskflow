"""TF-0027 — Pruebas de `src.orquestador.fusion` (parseo + pre-validación +
fusión de hallazgos)."""
import json

from src.orquestador.fusion import HallazgoPropuesto, fusionar_hallazgos, parsear_hallazgos
from src.proyectos.estado import Dato, EstadoDato, ExpedienteProyecto, NivelConfianza, OrigenDato

_TS = "2026-09-02 10:00:00"


def _dato(estado, origen=OrigenDato.AGENT):
    return Dato(valor="v", estado=estado, origen=origen,
                confianza=NivelConfianza.ALTA, actualizado_en=_TS)


def _hallazgo(campo="identidad", valor="Taskflow", estado=EstadoDato.CONFIRMED,
              origen=OrigenDato.FILE, confianza=NivelConfianza.ALTA, notas=""):
    return {"campo": campo, "valor": valor, "estado": estado.value,
            "origen": origen.value, "confianza": confianza.value, "notas": notas}


# --- parsear_hallazgos --------------------------------------------------

class TestParsearHallazgos:
    def test_json_valido_dos_hallazgos(self):
        texto = json.dumps({"hallazgos": [_hallazgo(campo="identidad"), _hallazgo(campo="objetivo")]})
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 2
        assert problemas == []
        assert isinstance(hallazgos[0], HallazgoPropuesto)
        assert hallazgos[0].estado == EstadoDato.CONFIRMED
        assert hallazgos[0].origen == OrigenDato.FILE
        assert hallazgos[0].confianza == NivelConfianza.ALTA

    def test_texto_no_es_json(self):
        hallazgos, problemas = parsear_hallazgos("esto no es json {")
        assert hallazgos == []
        assert len(problemas) == 1

    def test_json_sin_clave_hallazgos(self):
        hallazgos, problemas = parsear_hallazgos(json.dumps({"otracosa": []}))
        assert hallazgos == []
        assert len(problemas) == 1

    def test_hallazgos_no_es_lista(self):
        hallazgos, problemas = parsear_hallazgos(json.dumps({"hallazgos": "no-es-lista"}))
        assert hallazgos == []
        assert len(problemas) == 1

    def test_entrada_no_es_objeto_se_descarta_sin_abortar(self):
        texto = json.dumps({"hallazgos": ["no-es-un-dict", _hallazgo()]})
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 1
        assert len(problemas) == 1

    def test_estado_invalido_se_descarta_sin_abortar_el_resto(self):
        malo = _hallazgo(campo="identidad")
        malo["estado"] = "no-es-un-estado-valido"
        texto = json.dumps({"hallazgos": [malo, _hallazgo(campo="objetivo")]})
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 1
        assert hallazgos[0].campo == "objetivo"
        assert len(problemas) == 1

    def test_campo_faltante_se_descarta(self):
        malo = _hallazgo()
        del malo["campo"]
        hallazgos, problemas = parsear_hallazgos(json.dumps({"hallazgos": [malo]}))
        assert hallazgos == []
        assert len(problemas) == 1


# --- fusionar_hallazgos --------------------------------------------------

class TestFusionarHallazgos:
    def test_hallazgo_valido_para_campo_nuevo_se_aplica(self):
        e = ExpedienteProyecto()
        h = [HallazgoPropuesto(campo="identidad", valor="Taskflow",
                                estado=EstadoDato.CONFIRMED, origen=OrigenDato.FILE,
                                confianza=NivelConfianza.ALTA)]
        actualizado, aplicados, problemas = fusionar_hallazgos(e, h)
        assert aplicados == 1
        assert problemas == []
        assert actualizado.descubrimiento["identidad"].estado == EstadoDato.CONFIRMED
        assert actualizado.descubrimiento["identidad"].origen == OrigenDato.FILE

    def test_no_muta_el_expediente_original(self):
        e = ExpedienteProyecto()
        h = [HallazgoPropuesto(campo="identidad", valor="Taskflow",
                                estado=EstadoDato.CONFIRMED, origen=OrigenDato.FILE,
                                confianza=NivelConfianza.ALTA)]
        fusionar_hallazgos(e, h)
        assert "identidad" not in e.descubrimiento

    def test_campo_fuera_del_checklist_raiz_se_descarta(self):
        e = ExpedienteProyecto()
        h = [HallazgoPropuesto(campo="campo_inventado", valor="x",
                                estado=EstadoDato.CONFIRMED, origen=OrigenDato.FILE,
                                confianza=NivelConfianza.ALTA)]
        actualizado, aplicados, problemas = fusionar_hallazgos(e, h)
        assert aplicados == 0
        assert "campo_inventado" not in actualizado.descubrimiento
        assert len(problemas) == 1

    def test_origen_user_de_un_agente_se_fuerza_a_agent(self):
        e = ExpedienteProyecto()
        h = [HallazgoPropuesto(campo="identidad", valor="Taskflow",
                                estado=EstadoDato.CONFIRMED, origen=OrigenDato.USER,
                                confianza=NivelConfianza.ALTA)]
        actualizado, aplicados, problemas = fusionar_hallazgos(e, h)
        assert aplicados == 1
        assert actualizado.descubrimiento["identidad"].origen == OrigenDato.AGENT
        assert any("forzado a agent" in p for p in problemas)

    def test_transicion_restringida_se_descarta_sin_abortar_el_resto_del_lote(self):
        e = ExpedienteProyecto()
        e.descubrimiento["identidad"] = _dato(EstadoDato.INFERRED)
        h = [
            HallazgoPropuesto(campo="identidad", valor="x", estado=EstadoDato.CONFIRMED,
                               origen=OrigenDato.AGENT, confianza=NivelConfianza.ALTA),
            HallazgoPropuesto(campo="objetivo", valor="y", estado=EstadoDato.CONFIRMED,
                               origen=OrigenDato.FILE, confianza=NivelConfianza.ALTA),
        ]
        actualizado, aplicados, problemas = fusionar_hallazgos(e, h)
        assert aplicados == 1
        assert actualizado.descubrimiento["identidad"].estado == EstadoDato.INFERRED  # sin cambio
        assert actualizado.descubrimiento["objetivo"].estado == EstadoDato.CONFIRMED  # sí se aplicó
        assert any("transición no permitida" in p for p in problemas)

    def test_saneo_de_origen_ocurre_antes_de_validar_la_transicion(self):
        """Un HallazgoPropuesto (siempre viene de un agente) que declara
        `origen=user` para colarse en una transición restringida no lo
        consigue: el saneo a AGENT ocurre ANTES de `transicion_valida()`, así
        que la transición sigue evaluándose como no-usuario y se descarta.
        """
        e = ExpedienteProyecto()
        e.descubrimiento["identidad"] = _dato(EstadoDato.NOT_FOUND)
        h = [HallazgoPropuesto(campo="identidad", valor="x", estado=EstadoDato.NOT_APPLICABLE,
                                origen=OrigenDato.USER, confianza=NivelConfianza.ALTA)]
        actualizado, aplicados, problemas = fusionar_hallazgos(e, h)
        assert aplicados == 0
        assert actualizado.descubrimiento["identidad"].estado == EstadoDato.NOT_FOUND
        assert any("forzado a agent" in p for p in problemas)
        assert any("transición no permitida" in p for p in problemas)
