"""TF-0026 — Pruebas de `src.proyectos.checklist` (versionado del checklist)."""
import pytest

from src.proyectos.checklist import CHECKLIST_VERSION_ACTUAL, DISCIPLINAS, campos_esperados
from src.proyectos.errores import ErrorProyectos, VersionChecklistNoEncontrada


class TestCamposEsperados:
    def test_version_actual_registrada(self):
        checklist = campos_esperados(CHECKLIST_VERSION_ACTUAL)
        assert "_raiz" in checklist
        for disciplina in DISCIPLINAS:
            assert disciplina in checklist

    def test_campos_son_tuplas_no_vacias(self):
        checklist = campos_esperados(CHECKLIST_VERSION_ACTUAL)
        for campos in checklist.values():
            assert isinstance(campos, tuple)
            assert len(campos) > 0

    def test_version_inexistente_lanza_error_tipado(self):
        with pytest.raises(VersionChecklistNoEncontrada):
            campos_esperados("9.9")

    def test_error_es_subclase_de_error_proyectos_y_value_error(self):
        with pytest.raises(ErrorProyectos):
            campos_esperados("9.9")
        with pytest.raises(ValueError):
            campos_esperados("9.9")

    def test_disciplinas_tiene_las_7_claves_del_diagrama(self):
        assert DISCIPLINAS == (
            "analisis", "ux", "arquitectura", "implementacion",
            "testing", "seguridad", "documentacion",
        )

    def test_dict_devuelto_es_una_copia_no_expone_el_estado_interno(self):
        """Modificar el dict devuelto (agregar/quitar claves, o reemplazar el
        valor de una) no debe afectar `_CHECKLISTS`: una segunda llamada debe
        devolver el checklist original, intacto.
        """
        checklist = campos_esperados(CHECKLIST_VERSION_ACTUAL)
        checklist["_raiz"] = ("manipulado",)
        checklist["disciplina_inventada"] = ("x",)

        checklist_de_nuevo = campos_esperados(CHECKLIST_VERSION_ACTUAL)
        assert checklist_de_nuevo["_raiz"] != ("manipulado",)
        assert "disciplina_inventada" not in checklist_de_nuevo
        assert checklist_de_nuevo == campos_esperados(CHECKLIST_VERSION_ACTUAL)
