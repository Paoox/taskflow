"""TF-0029 — Pruebas de `src.orquestador.evidencia` y de su integración con
`ejecutar_orquestador()`.

Cubre: el recolector determinista sobre archivos reales en `tmp_path`, la
incorporación de la evidencia a `EntradaAgente.contexto`/`archivos_relevantes`,
el registro de trazabilidad con `tipo="recolectar_evidencia"`, y que la
regresión de TF-0027 (comportamiento con `recolector_evidencia=None`) queda
intacta.
"""
import json

from src.agentes.contrato import SalidaAgente
from src.ai.cliente import RespuestaIA
from src.orquestador.contrato import AccionOrquestador
from src.orquestador.evidencia import (
    EvidenciaRecolectada,
    recolector_evidencia_archivos_conocidos,
)
from src.orquestador.orquestador import TIPO_ACCION_RECOLECTAR_EVIDENCIA, ejecutar_orquestador
from src.repositorios.acciones import COMPLETADA, RepositorioAcciones
from src.repositorios.expedientes import RepositorioExpedientes
from src.tools.archivos import LIMITE_CARACTERES_LECTURA


class _AgenteFalso:
    nombre = "descubridor_fake"
    tipo_accion = "descubrimiento_fake"

    def construir_prompt(self, entrada):
        return entrada.contexto  # expone el contexto tal cual para poder inspeccionarlo

    def parsear(self, respuesta, entrada):
        return SalidaAgente(resultado=respuesta.texto)


class _ClienteCapturaPrompt:
    """Guarda el último prompt recibido y devuelve un texto fijo."""

    def __init__(self, texto_respuesta="{}"):
        self.ultimo_prompt = None
        self._texto = texto_respuesta

    def completar(self, prompt, opciones):
        self.ultimo_prompt = prompt
        return RespuestaIA(texto=self._texto, tokens_entrada=1, tokens_salida=1, modelo="fake")


# --- recolector_evidencia_archivos_conocidos (aislado, sin repos) ----------

class TestRecolectorEvidencia:
    def test_lee_archivos_conocidos_presentes_y_los_lista_como_relevantes(self, tmp_path):
        (tmp_path / "README.md").write_text("Taskflow es un gestor de tareas", encoding="utf-8")
        (tmp_path / "pyproject.toml").write_text("[project]\nname='taskflow'", encoding="utf-8")

        recolector = recolector_evidencia_archivos_conocidos(str(tmp_path))
        evidencia = recolector(None, [])

        assert isinstance(evidencia, EvidenciaRecolectada)
        assert set(evidencia.archivos_relevantes) == {"README.md", "pyproject.toml"}
        assert "Taskflow es un gestor de tareas" in evidencia.contexto_adicional
        assert "name='taskflow'" in evidencia.contexto_adicional
        assert "## Estructura del proyecto" in evidencia.contexto_adicional
        assert evidencia.problemas == []

    def test_archivos_conocidos_ausentes_se_ignoran_sin_generar_problema(self, tmp_path):
        recolector = recolector_evidencia_archivos_conocidos(str(tmp_path))
        evidencia = recolector(None, [])
        assert evidencia.archivos_relevantes == []
        assert evidencia.problemas == []  # ausencia esperable, no es un problema

    def test_archivo_truncado_se_reporta_en_problemas(self, tmp_path):
        (tmp_path / "README.md").write_text("x" * (LIMITE_CARACTERES_LECTURA + 10), encoding="utf-8")
        recolector = recolector_evidencia_archivos_conocidos(str(tmp_path))
        evidencia = recolector(None, [])
        assert any("truncado" in p for p in evidencia.problemas)

    def test_no_incluye_archivos_sensibles_aunque_esten_presentes(self, tmp_path):
        (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
        recolector = recolector_evidencia_archivos_conocidos(str(tmp_path))
        evidencia = recolector(None, [])
        assert "SECRET=1" not in evidencia.contexto_adicional
        assert ".env" not in evidencia.archivos_relevantes

    def test_raiz_inexistente_reporta_problema_en_el_listado(self, tmp_path):
        raiz_inexistente = tmp_path / "no_existe"
        recolector = recolector_evidencia_archivos_conocidos(str(raiz_inexistente))
        evidencia = recolector(None, [])
        assert evidencia.contexto_adicional == ""
        assert any("listado de estructura no disponible" in p for p in evidencia.problemas)


# --- integración real con ejecutar_orquestador() ---------------------------

class TestIntegracionConEjecutarOrquestador:
    def test_recolector_none_preserva_comportamiento_de_tf_0027(self, db):
        """Sin `recolector_evidencia` (default None), el contexto que recibe
        el agente es exactamente el de TF-0027: solo las preguntas.
        """
        repo_exp = RepositorioExpedientes()
        repo_acc = RepositorioAcciones()
        codigo = repo_exp.crear("Demo")

        cliente = _ClienteCapturaPrompt()
        resultado = ejecutar_orquestador(codigo, cliente, _AgenteFalso(),
                                          repo_expedientes=repo_exp, repo_acciones=repo_acc)

        assert resultado.accion == AccionOrquestador.INVESTIGAR
        assert "## Estructura del proyecto" not in cliente.ultimo_prompt
        tipos = {a["tipo"] for a in repo_acc.listar(ticket=codigo)}
        assert TIPO_ACCION_RECOLECTAR_EVIDENCIA not in tipos

    def test_recolector_enriquece_contexto_y_archivos_relevantes(self, db, tmp_path):
        (tmp_path / "README.md").write_text("Este proyecto es una CLI de gestión de tareas",
                                             encoding="utf-8")

        repo_exp = RepositorioExpedientes()
        repo_acc = RepositorioAcciones()
        codigo = repo_exp.crear("Demo")

        cliente = _ClienteCapturaPrompt()
        recolector = recolector_evidencia_archivos_conocidos(str(tmp_path))

        resultado = ejecutar_orquestador(codigo, cliente, _AgenteFalso(),
                                          repo_expedientes=repo_exp, repo_acciones=repo_acc,
                                          recolector_evidencia=recolector)

        assert resultado.accion == AccionOrquestador.INVESTIGAR
        assert "Este proyecto es una CLI de gestión de tareas" in cliente.ultimo_prompt
        assert "- identidad:" in cliente.ultimo_prompt  # las preguntas se conservan

        acciones = repo_acc.listar(ticket=codigo)
        recoleccion = [a for a in acciones if a["tipo"] == TIPO_ACCION_RECOLECTAR_EVIDENCIA]
        assert len(recoleccion) == 1
        assert recoleccion[0]["estado"] == COMPLETADA
        resultado_persistido = json.loads(recoleccion[0]["resultado"])
        assert resultado_persistido["archivos_relevantes"] == ["README.md"]

    def test_problemas_del_recolector_llegan_a_resultado_orquestador(self, db, tmp_path):
        (tmp_path / "README.md").write_text("x" * (LIMITE_CARACTERES_LECTURA + 1), encoding="utf-8")

        repo_exp = RepositorioExpedientes()
        repo_acc = RepositorioAcciones()
        codigo = repo_exp.crear("Demo")

        resultado = ejecutar_orquestador(
            codigo, _ClienteCapturaPrompt(), _AgenteFalso(),
            repo_expedientes=repo_exp, repo_acciones=repo_acc,
            recolector_evidencia=recolector_evidencia_archivos_conocidos(str(tmp_path)),
        )
        assert any("truncado" in p for p in resultado.problemas)

    def test_evidencia_real_permite_que_el_agente_confirme_hallazgos(self, db, tmp_path):
        """Punta a punta: evidencia real -> Descubridor-like -> fusion ->
        expediente actualizado, con `Descubridor()` real (no un doble).
        """
        from src.agentes.descubridor import Descubridor

        (tmp_path / "pyproject.toml").write_text(
            '[project]\nname = "taskflow-cli"\n', encoding="utf-8"
        )

        class _ClienteQueLeeElContexto:
            def completar(self, prompt, opciones):
                texto = json.dumps({"hallazgos": [
                    {"campo": "identidad", "valor": "taskflow-cli", "estado": "confirmed",
                     "origen": "file", "confianza": "ALTA",
                     "notas": "leído de pyproject.toml"},
                ]})
                return RespuestaIA(texto=texto, tokens_entrada=1, tokens_salida=1, modelo="fake")

        repo_exp = RepositorioExpedientes()
        repo_acc = RepositorioAcciones()
        codigo = repo_exp.crear("Demo")

        resultado = ejecutar_orquestador(
            codigo, _ClienteQueLeeElContexto(), Descubridor(),
            repo_expedientes=repo_exp, repo_acciones=repo_acc,
            recolector_evidencia=recolector_evidencia_archivos_conocidos(str(tmp_path)),
        )

        assert resultado.hallazgos_aplicados == 1
        expediente = repo_exp.obtener(codigo)
        assert expediente.descubrimiento["identidad"].valor == "taskflow-cli"
        assert expediente.descubrimiento["identidad"].origen.value == "file"
