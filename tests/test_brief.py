"""Pruebas de `src.proyectos.brief`: contrato puro `EntradaBrief`/`TipoEntradaBrief`.

Sin DB (no usa la fixture `db`): estas pruebas solo verifican el dataclass,
igual criterio que `test_contrato.py`/las pruebas de `src.proyectos.estado`
que no tocan persistencia.
"""
import pytest

from src.proyectos.brief import EntradaBrief, TipoEntradaBrief
from src.proyectos.estado import OrigenDato


def _entrada(**kw):
    base = dict(
        id=1, codigo="PROY-001", ronda=1, tipo=TipoEntradaBrief.INICIAL,
        texto="Quiero un proyecto nuevo que sea una calculadora "
              "que solo suma números negativos.",
        origen=OrigenDato.USER, recibido_en="2026-09-04 10:00:00",
    )
    base.update(kw)
    return EntradaBrief(**base)


class TestTipoEntradaBrief:
    def test_valores_son_str(self):
        # (str, Enum), mismo criterio que los enums de src.proyectos.estado:
        # el valor ES el texto que se guarda/serializa, sin codificador a medida.
        assert TipoEntradaBrief.INICIAL == "inicial"
        assert TipoEntradaBrief.RESPUESTA_CLIENTE == "respuesta_cliente"
        assert isinstance(TipoEntradaBrief.INICIAL, str)


class TestEntradaBriefCreacion:
    def test_creacion_valida(self):
        e = _entrada()
        assert e.codigo == "PROY-001"
        assert e.ronda == 1
        assert e.tipo == TipoEntradaBrief.INICIAL
        assert e.origen == OrigenDato.USER

    def test_conserva_el_texto_exacto(self):
        texto = "Quiero un proyecto nuevo que sea una calculadora que solo suma números negativos."
        e = _entrada(texto=texto)
        assert e.texto == texto  # verbatim: ni recortado ni normalizado

    def test_es_inmutable(self):
        e = _entrada()
        with pytest.raises(Exception):  # dataclasses.FrozenInstanceError (subclase de AttributeError)
            e.texto = "otro texto"


class TestSerializacion:
    def test_to_dict_from_dict_simetrico(self):
        e = _entrada()
        assert EntradaBrief.from_dict(e.to_dict()) == e

    def test_to_dict_produce_valores_planos_serializables(self):
        d = _entrada().to_dict()
        assert d["tipo"] == "inicial"
        assert d["origen"] == "user"

    def test_from_dict_reconstruye_enums(self):
        d = _entrada(tipo=TipoEntradaBrief.RESPUESTA_CLIENTE).to_dict()
        e = EntradaBrief.from_dict(d)
        assert e.tipo is TipoEntradaBrief.RESPUESTA_CLIENTE
        assert e.origen is OrigenDato.USER

    def test_id_puede_ser_none_antes_de_persistir(self):
        e = _entrada(id=None)
        assert EntradaBrief.from_dict(e.to_dict()).id is None
