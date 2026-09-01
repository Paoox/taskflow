"""TF-0021 — Pruebas del contrato de agentes (`CLAUDE.md` §27).

Sin Flask ni base de datos. Cubren: campos exactos del §27, round-trip
`to_dict`/`from_dict`, JSON-serializabilidad sin `default=`, obligatorios vs
opcionales, valores por defecto y ausencia de acoplamiento con el núcleo web.
"""
import ast
import dataclasses
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from src.agentes.contrato import (
    Artefacto,
    EntradaAgente,
    Meta,
    ResumenPruebas,
    SalidaAgente,
)

_RAIZ = Path(__file__).resolve().parents[1]
_MODULOS_NUEVOS = [
    "src/agentes/__init__.py",
    "src/agentes/contrato.py",
    "src/ai/__init__.py",
    "src/ai/cliente.py",
    "src/ai/prompts/__init__.py",
]


def _nombres(clase):
    return [f.name for f in dataclasses.fields(clase)]


# --- CA-1: campos exactos del §27 -----------------------------------

class TestCamposDelContrato:
    def test_entrada_agente_campos_del_27(self):
        assert _nombres(EntradaAgente) == [
            "ticket", "objetivo", "contexto", "restricciones",
            "criterios_aceptacion", "archivos_relevantes",
        ]

    def test_salida_agente_campos_27_mas_artefactos_y_meta(self):
        assert _nombres(SalidaAgente) == [
            "resultado", "cambios", "pruebas", "problemas",
            "recomendaciones", "artefactos", "meta",
        ]

    def test_auxiliares_minimos(self):
        assert _nombres(Artefacto) == ["ruta", "contenido", "tipo"]
        assert _nombres(ResumenPruebas) == ["ejecutadas", "fallidas", "no_ejecutadas"]
        assert _nombres(Meta) == [
            "modelo", "tokens", "coste_estimado", "duracion_s", "correlation_id",
        ]


# --- CA-1 (cont.): obligatorios vs opcionales / defaults ----------

class TestObligatoriosYDefaults:
    def test_entrada_minima_y_defaults(self):
        e = EntradaAgente(ticket="TF-0021", objetivo="andamiaje")
        assert e.contexto == ""
        assert e.restricciones == []
        assert e.criterios_aceptacion == []
        assert e.archivos_relevantes == []

    def test_entrada_exige_ticket_y_objetivo(self):
        with pytest.raises(TypeError):
            EntradaAgente(ticket="TF-0021")

    def test_salida_minima_y_defaults(self):
        s = SalidaAgente(resultado="ok")
        assert s.cambios == [] and s.problemas == [] and s.recomendaciones == []
        assert s.artefactos == []
        assert isinstance(s.pruebas, ResumenPruebas)
        assert isinstance(s.meta, Meta)
        assert s.meta.coste_estimado == 0.0 and s.meta.correlation_id == ""

    def test_salida_exige_resultado(self):
        with pytest.raises(TypeError):
            SalidaAgente()

    def test_default_factories_no_comparten_estado(self):
        a = SalidaAgente(resultado="a")
        b = SalidaAgente(resultado="b")
        a.cambios.append("x")
        a.pruebas.ejecutadas.append("t")
        a.meta.tokens = 5
        assert b.cambios == []
        assert b.pruebas.ejecutadas == []
        assert b.meta.tokens == 0


# --- CA-2 / CA-3: round-trip y JSON ------------------------------

def _salida_completa():
    return SalidaAgente(
        resultado="hecho",
        cambios=["app.py", "src/x.py"],
        pruebas=ResumenPruebas(
            ejecutadas=["test_a"],
            fallidas=[],
            no_ejecutadas=[{"prueba": "manual", "motivo": "sin entorno"}],
        ),
        problemas=["ninguno"],
        recomendaciones=["revisar y"],
        artefactos=[Artefacto(ruta="docs/x.md", contenido="# X", tipo="markdown")],
        meta=Meta(modelo="eco", tokens=12, coste_estimado=0.0,
                  duracion_s=0.01, correlation_id="abc123"),
    )


class TestRoundTrip:
    @pytest.mark.parametrize("obj", [
        EntradaAgente(ticket="TF-0021", objetivo="x"),
        EntradaAgente(ticket="TF-0021", objetivo="x", contexto="c",
                      restricciones=["r1"], criterios_aceptacion=["c1"],
                      archivos_relevantes=["f1"]),
        SalidaAgente(resultado="ok"),
        _salida_completa(),
    ])
    def test_from_dict_de_to_dict_es_identidad(self, obj):
        assert type(obj).from_dict(obj.to_dict()) == obj

    def test_to_dict_es_estructura_plana(self):
        d = _salida_completa().to_dict()
        assert isinstance(d, dict)
        assert isinstance(d["pruebas"], dict)
        assert isinstance(d["artefactos"], list) and isinstance(d["artefactos"][0], dict)
        assert isinstance(d["meta"], dict)

    def test_json_dumps_sin_argumento_default(self):
        for obj in (EntradaAgente(ticket="T", objetivo="o"), _salida_completa()):
            texto = json.dumps(obj.to_dict())
            assert type(obj).from_dict(json.loads(texto)) == obj

    def test_from_dict_tolera_claves_ausentes(self):
        assert SalidaAgente.from_dict({"resultado": "r"}) == SalidaAgente(resultado="r")
        assert (EntradaAgente.from_dict({"ticket": "T", "objetivo": "o"})
                == EntradaAgente(ticket="T", objetivo="o"))

    def test_listas_vacias_sobreviven_al_round_trip(self):
        s = SalidaAgente(resultado="r", cambios=[], artefactos=[],
                         pruebas=ResumenPruebas())
        assert SalidaAgente.from_dict(s.to_dict()) == s


# --- CA-7: sin acoplamiento con el núcleo web ni con la red -------

class TestSinAcoplamiento:
    def test_los_modulos_nuevos_no_importan_flask_db_app_ni_red(self):
        # Se inspecta el grafo de imports declarado (AST), no el texto libre:
        # los docstrings mencionan "Flask" / "src.database" al explicar la regla.
        exactos = {"flask", "socket", "urllib", "requests", "httpx",
                   "app", "src.database", "src.app"}
        prefijos = ("flask.", "urllib.", "http.client", "src.database.", "src.app.")
        for rel in _MODULOS_NUEVOS:
            arbol = ast.parse((_RAIZ / rel).read_text(encoding="utf-8"), filename=rel)
            modulos = set()
            for nodo in ast.walk(arbol):
                if isinstance(nodo, ast.Import):
                    modulos.update(a.name for a in nodo.names)
                elif isinstance(nodo, ast.ImportFrom):
                    modulos.add(nodo.module or "")
            for m in modulos:
                assert m not in exactos, f"{rel} importa {m!r}"
                assert not m.startswith(prefijos), f"{rel} importa {m!r}"

    def test_import_aislado_no_arrastra_el_nucleo_ni_tiene_efectos(self):
        codigo = (
            "import sys\n"
            "import src.agentes.contrato, src.ai.cliente, src.ai.prompts\n"
            "malo = [m for m in sys.modules if m == 'flask' or m.startswith('flask.') "
            "or m in ('src.database', 'app')]\n"
            "assert not malo, malo\n"
            "print('ok')\n"
        )
        r = subprocess.run(
            [sys.executable, "-c", codigo],
            cwd=str(_RAIZ), capture_output=True, text=True,
            env={**os.environ, "PYTHONPATH": str(_RAIZ)},
        )
        assert r.returncode == 0, r.stderr
        assert r.stdout.strip().endswith("ok")
