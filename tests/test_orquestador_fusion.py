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


# --- parsear_hallazgos: JSON Lines (TF-0029) ----------------------------
# Un objeto JSON de hallazgo por línea, sin array ni clave "hallazgos"
# envolvente. Reemplaza el contrato anterior ({"hallazgos": [...]} en un
# único documento) tras la investigación del 2026-09-02: un error de
# sintaxis en un solo hallazgo invalidaba el documento entero. Con JSON
# Lines cada línea se parsea de forma independiente.

def _linea(**kw):
    return json.dumps(_hallazgo(**kw))


class TestParsearHallazgos:
    def test_una_linea_valida(self):
        hallazgos, problemas = parsear_hallazgos(_linea(campo="identidad"))
        assert len(hallazgos) == 1
        assert problemas == []
        assert isinstance(hallazgos[0], HallazgoPropuesto)
        assert hallazgos[0].campo == "identidad"
        assert hallazgos[0].estado == EstadoDato.CONFIRMED
        assert hallazgos[0].origen == OrigenDato.FILE
        assert hallazgos[0].confianza == NivelConfianza.ALTA

    def test_varias_lineas_validas(self):
        texto = "\n".join([_linea(campo="identidad"), _linea(campo="objetivo")])
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 2
        assert problemas == []
        assert {h.campo for h in hallazgos} == {"identidad", "objetivo"}

    def test_lineas_vacias_se_ignoran(self):
        texto = "\n\n" + _linea(campo="identidad") + "\n\n\n" + _linea(campo="objetivo") + "\n\n"
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 2
        assert problemas == []

    def test_texto_vacio_no_produce_ni_hallazgos_ni_problemas(self):
        hallazgos, problemas = parsear_hallazgos("")
        assert hallazgos == []
        assert problemas == []

    def test_linea_invalida_entre_lineas_validas_no_aborta_las_demas(self):
        texto = "\n".join([
            _linea(campo="identidad"),
            "esto no es json en absoluto {",
            _linea(campo="objetivo"),
        ])
        hallazgos, problemas = parsear_hallazgos(texto)
        assert {h.campo for h in hallazgos} == {"identidad", "objetivo"}
        assert len(problemas) == 1
        assert "línea 2" in problemas[0]

    def test_linea_con_enum_invalido_entre_lineas_validas(self):
        malo = _hallazgo(campo="identidad")
        malo["estado"] = "no-es-un-estado-valido"
        texto = "\n".join([json.dumps(malo), _linea(campo="objetivo")])
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 1
        assert hallazgos[0].campo == "objetivo"
        assert len(problemas) == 1
        assert "línea 1" in problemas[0]

    def test_linea_json_valida_pero_hallazgo_invalido_campo_faltante(self):
        malo = _hallazgo()
        del malo["campo"]
        texto = "\n".join([json.dumps(malo), _linea(campo="objetivo")])
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 1
        assert hallazgos[0].campo == "objetivo"
        assert len(problemas) == 1

    def test_linea_que_no_es_un_objeto_json(self):
        texto = "\n".join(['"solo un string"', _linea(campo="identidad")])
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 1
        assert len(problemas) == 1
        assert "no es un objeto" in problemas[0]

    def test_json_invalido_no_recuperable_ninguna_linea_util(self):
        texto = "Esto es una respuesta completamente en prosa.\nSin ningún JSON en absoluto."
        hallazgos, problemas = parsear_hallazgos(texto)
        assert hallazgos == []
        assert len(problemas) == 2  # una por línea no vacía


# --- parsear_hallazgos: desenvolvimiento estricto de bloques Markdown ------
# (comportamiento real observado con qwen2.5:3b pese a que el prompt pide no
# usarlo)

class TestParsearHallazgosBloqueMarkdown:
    def test_markdown_envolviendo_todo_el_jsonl_se_acepta(self):
        cuerpo = "\n".join([_linea(campo="identidad"), _linea(campo="objetivo")])
        texto = f"```json\n{cuerpo}\n```"
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 2
        assert problemas == []
        assert {h.campo for h in hallazgos} == {"identidad", "objetivo"}

    def test_markdown_sin_etiqueta_de_lenguaje_se_acepta(self):
        cuerpo = _linea(campo="identidad")
        texto = f"```\n{cuerpo}\n```"
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 1
        assert problemas == []

    def test_espacios_y_saltos_de_linea_alrededor_del_bloque_se_toleran(self):
        cuerpo = _linea(campo="identidad")
        texto = f"\n\n   ```json\n{cuerpo}\n```   \n\n"
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 1
        assert problemas == []

    def test_bloque_markdown_con_una_linea_no_json_dentro(self):
        texto = "```json\nesto no es json\n```"
        hallazgos, problemas = parsear_hallazgos(texto)
        assert hallazgos == []
        assert len(problemas) == 1

    def test_prosa_como_propia_linea_antes_se_rechaza_sin_bloquear_las_demas(self):
        """Comportamiento nuevo respecto al contrato anterior: una línea de
        prosa nunca se interpreta como hallazgo, pero ya NO invalida el
        documento completo — solo se pierde esa línea. Es precisamente la
        propiedad que motivó el cambio a JSON Lines."""
        texto = "\n".join(["Aquí está mi respuesta:", _linea(campo="identidad")])
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 1
        assert hallazgos[0].campo == "identidad"
        assert len(problemas) == 1
        assert "línea 1" in problemas[0]

    def test_prosa_como_propia_linea_despues_se_rechaza_sin_bloquear_las_demas(self):
        texto = "\n".join([_linea(campo="identidad"), "Espero que esto ayude."])
        hallazgos, problemas = parsear_hallazgos(texto)
        assert len(hallazgos) == 1
        assert len(problemas) == 1
        assert "línea 2" in problemas[0]

    def test_no_hace_extraccion_difusa_de_json_dentro_de_una_linea_de_prosa(self):
        """Un `{...}` incrustado en medio de una frase en la MISMA línea
        nunca se extrae: la línea completa debe ser JSON, no una parte de
        ella."""
        texto = ('Un ejemplo sería {"campo": "identidad", "valor": "x", '
                  '"estado": "confirmed", "origen": "file", "confianza": "ALTA"} '
                  'dentro del texto.')
        hallazgos, problemas = parsear_hallazgos(texto)
        assert hallazgos == []
        assert len(problemas) == 1

    def test_json_normal_de_una_linea_sin_envoltorio_sigue_funcionando(self):
        """Regresión: una sola línea válida, sin markdown."""
        hallazgos, problemas = parsear_hallazgos(_linea(campo="identidad"))
        assert len(hallazgos) == 1
        assert problemas == []

    def test_texto_no_json_existente_sigue_siendo_invalido(self):
        """Regresión explícita del caso preexistente."""
        hallazgos, problemas = parsear_hallazgos("esto no es json {")
        assert hallazgos == []
        assert len(problemas) == 1


# --- Regresión dirigida: la causa raíz que motivó JSON Lines (2026-09-02) --
# Smoke test real contra qwen2.5:3b: 6 hallazgos, uno de ellos
# (`stack_declarado`) citaba literalmente `pyproject.toml` con comillas sin
# escapar dentro de "notas", rompiendo la sintaxis JSON de esa línea. Con el
# contrato anterior ({"hallazgos": [...]} en un documento) esto hacía perder
# los 6 hallazgos (5 de ellos correctos). Con JSON Lines se pierde solo 1.

class TestRegresionGranularidadDeLinea:
    def test_una_linea_con_comillas_sin_escapar_no_destruye_las_demas(self):
        buenas = [
            _linea(campo="identidad", valor="Gestor-CLI"),
            _linea(campo="tipo_proyecto", valor="CLI"),
            _linea(campo="objetivo", valor="organizar tareas personales desde la terminal"),
            _linea(campo="usuarios", valor="desconocido", estado=EstadoDato.UNKNOWN,
                   origen=OrigenDato.INFERENCE, confianza=NivelConfianza.BAJA),
            _linea(campo="contexto_negocio", valor="organizar tareas personales"),
        ]
        # Línea rota: comillas sin escapar dentro de "notas", igual que en el
        # smoke test real (cita literal de `dependencies = ["click"]`).
        linea_rota = (
            '{"campo": "stack_declarado", "valor": "Python", "estado": "confirmed", '
            '"origen": "file", "confianza": "ALTA", "notas": "Stack declarado en '
            'pyproject.toml: dependencies = ["click"]"}'
        )
        texto = "\n".join(buenas + [linea_rota])

        hallazgos, problemas = parsear_hallazgos(texto)

        assert len(hallazgos) == 5
        assert {h.campo for h in hallazgos} == {
            "identidad", "tipo_proyecto", "objetivo", "usuarios", "contexto_negocio",
        }
        assert len(problemas) == 1
        assert "línea 6" in problemas[0]
        assert "no es JSON válido" in problemas[0]

    def test_la_misma_linea_rota_tambien_sobrevive_la_fusion_completa(self):
        """Punta a punta: parsear_hallazgos() + fusionar_hallazgos() sobre un
        ExpedienteProyecto real — el beneficio llega hasta el expediente
        actualizado, no solo hasta el parseo."""
        buenas = [_linea(campo="identidad", valor="Gestor-CLI"),
                  _linea(campo="tipo_proyecto", valor="CLI")]
        linea_rota = (
            '{"campo": "stack_declarado", "valor": "Python", "estado": "confirmed", '
            '"origen": "file", "confianza": "ALTA", "notas": "cita con comillas '
            'sin escapar: ["click"] adentro"}'
        )
        texto = "\n".join(buenas + [linea_rota])

        hallazgos, problemas_parseo = parsear_hallazgos(texto)
        assert len(hallazgos) == 2
        assert len(problemas_parseo) == 1

        expediente, aplicados, problemas_fusion = fusionar_hallazgos(ExpedienteProyecto(), hallazgos)
        assert aplicados == 2
        assert problemas_fusion == []
        assert expediente.descubrimiento["identidad"].valor == "Gestor-CLI"
        assert expediente.descubrimiento["tipo_proyecto"].valor == "CLI"


# --- Integración parsear + fusionar: el checklist actúa en la etapa correcta

class TestParsearYFusionarCampoFueraDeChecklist:
    def test_linea_fuera_del_checklist_entre_lineas_validas(self):
        """`parsear_hallazgos()` no conoce el checklist raíz (eso es
        responsabilidad de `fusionar_hallazgos()`): una línea con un campo
        fuera del checklist parsea bien como HallazgoPropuesto, y se descarta
        recién en la fusión — sin afectar a las líneas válidas."""
        texto = "\n".join([
            _linea(campo="identidad"),
            _linea(campo="campo_que_no_existe_en_el_checklist"),
            _linea(campo="objetivo"),
        ])
        hallazgos, problemas_parseo = parsear_hallazgos(texto)
        assert len(hallazgos) == 3
        assert problemas_parseo == []

        expediente, aplicados, problemas_fusion = fusionar_hallazgos(ExpedienteProyecto(), hallazgos)
        assert aplicados == 2
        assert set(expediente.descubrimiento) == {"identidad", "objetivo"}
        assert any("campo_que_no_existe_en_el_checklist" in p for p in problemas_fusion)


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
