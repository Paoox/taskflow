"""Pruebas de las heurísticas sintácticas baratas (`src.formulario.heuristicas`).

TF-0033. Funciones puras: no requieren base de datos.
"""
from src.formulario.heuristicas import es_respuesta_vaga, sugiere_enumeracion


class TestEsRespuestaVaga:
    def test_texto_vacio_no_es_vago(self):
        assert es_respuesta_vaga("") is False
        assert es_respuesta_vaga("   ") is False

    def test_verbo_generico_y_corta_es_vaga(self):
        assert es_respuesta_vaga("administrar") is True
        assert es_respuesta_vaga("dar mantenimiento") is True

    def test_texto_largo_no_es_vago_aunque_use_un_verbo_generico(self):
        texto = "administrar el inventario completo de productos y proveedores todos los días"
        assert es_respuesta_vaga(texto) is False

    def test_texto_corto_sin_verbo_generico_no_es_vago(self):
        assert es_respuesta_vaga("registrar un pedido") is False


class TestSugiereEnumeracion:
    def test_texto_vacio_no_sugiere_enumeracion(self):
        assert sugiere_enumeracion("") is False
        assert sugiere_enumeracion("   ") is False

    def test_coma_sugiere_enumeracion(self):
        assert sugiere_enumeracion("vender cursos, cobrar suscripciones") is True

    def test_conector_tambien_sugiere_enumeracion(self):
        assert sugiere_enumeracion("vende cursos y también cobra comisión") is True

    def test_dos_conjunciones_y_sugieren_enumeracion(self):
        assert sugiere_enumeracion("suma y resta y multiplica") is True

    def test_frase_simple_no_sugiere_enumeracion(self):
        assert sugiere_enumeracion("llevar el control de mis gastos personales") is False
