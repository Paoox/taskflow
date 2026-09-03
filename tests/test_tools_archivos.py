"""TF-0029 — Pruebas de `src.tools.archivos` (Tools de filesystem).

Cubre sandbox/traversal/symlinks fuera de la raíz, lista negra de archivos
sensibles, rechazo de binarios, truncado determinista, listado con
profundidad limitada e ignorando directorios de infraestructura.
"""
import os

import pytest

from src.tools.archivos import LIMITE_CARACTERES_LECTURA, LeerArchivoTool, ListarArchivosTool
from src.tools.contrato import EntradaListarArchivos, EntradaLeerArchivo


@pytest.fixture
def raiz(tmp_path):
    (tmp_path / "README.md").write_text("Hola mundo", encoding="utf-8")
    (tmp_path / ".env").write_text("SECRET=1", encoding="utf-8")
    (tmp_path / "id_rsa").write_text("clave privada falsa", encoding="utf-8")
    (tmp_path / "sub").mkdir()
    (tmp_path / "sub" / "a.py").write_text("print(1)", encoding="utf-8")
    (tmp_path / "sub" / "profundo").mkdir()
    (tmp_path / "sub" / "profundo" / "b.py").write_text("print(2)", encoding="utf-8")
    (tmp_path / "__pycache__").mkdir()
    (tmp_path / "__pycache__" / "x.pyc").write_bytes(b"\x00")
    (tmp_path / "node_modules").mkdir()
    (tmp_path / "node_modules" / "paquete.js").write_text("x", encoding="utf-8")
    (tmp_path / ".git").mkdir()
    (tmp_path / ".git" / "HEAD").write_text("ref: refs/heads/main", encoding="utf-8")
    (tmp_path / "binario.dat").write_bytes(b"\xff\xfe\x00\x01\x80")
    (tmp_path / "grande.txt").write_text("x" * (LIMITE_CARACTERES_LECTURA + 500), encoding="utf-8")
    return tmp_path


class TestLeerArchivoTool:
    def test_lee_archivo_existente(self, raiz):
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo("README.md"))
        assert r.exito is True
        assert r.contenido == "Hola mundo"
        assert r.ruta == "README.md"
        assert r.truncado is False
        assert r.error is None

    def test_archivo_inexistente(self, raiz):
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo("no_existe.txt"))
        assert r.exito is False
        assert r.error == "archivo no encontrado"

    def test_directorio_no_es_archivo(self, raiz):
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo("sub"))
        assert r.exito is False
        assert r.error == "archivo no encontrado"

    @pytest.mark.parametrize("ruta", ["../fuera.txt", "sub/../../fuera.txt"])
    def test_traversal_rechazado(self, raiz, ruta):
        (raiz.parent / "fuera.txt").write_text("no debería leerse", encoding="utf-8")
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo(ruta))
        assert r.exito is False
        assert r.error == "ruta fuera del alcance permitido"

    def test_ruta_absoluta_rechazada(self, raiz):
        fuera = raiz.parent / "fuera_abs.txt"
        fuera.write_text("no debería leerse", encoding="utf-8")
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo(str(fuera)))
        assert r.exito is False
        assert r.error == "ruta fuera del alcance permitido"

    def test_symlink_fuera_de_la_raiz_rechazado(self, raiz):
        fuera = raiz.parent / "secreto_fuera.txt"
        fuera.write_text("contenido secreto", encoding="utf-8")
        os.symlink(str(fuera), raiz / "enlace")
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo("enlace"))
        assert r.exito is False
        assert r.error == "ruta fuera del alcance permitido"

    def test_symlink_dentro_de_la_raiz_se_permite(self, raiz):
        os.symlink(str(raiz / "README.md"), raiz / "enlace_interno")
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo("enlace_interno"))
        assert r.exito is True
        assert r.contenido == "Hola mundo"

    @pytest.mark.parametrize("nombre", [".env", "id_rsa"])
    def test_archivos_sensibles_rechazados(self, raiz, nombre):
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo(nombre))
        assert r.exito is False
        assert r.error == "archivo excluido por política de seguridad"

    def test_variante_env_tambien_rechazada(self, raiz):
        (raiz / ".env.production").write_text("SECRET=2", encoding="utf-8")
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo(".env.production"))
        assert r.exito is False
        assert r.error == "archivo excluido por política de seguridad"

    def test_clave_pem_rechazada(self, raiz):
        (raiz / "certificado.pem").write_text("-----BEGIN-----", encoding="utf-8")
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo("certificado.pem"))
        assert r.exito is False
        assert r.error == "archivo excluido por política de seguridad"

    def test_error_de_lectura_por_permisos_no_lanza(self, raiz):
        sin_permiso = raiz / "sin_permiso.txt"
        sin_permiso.write_text("contenido", encoding="utf-8")
        sin_permiso.chmod(0o000)
        try:
            r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo("sin_permiso.txt"))
        finally:
            sin_permiso.chmod(0o644)
        assert r.exito is False
        assert r.error.startswith("error de lectura:")

    def test_binario_no_utf8_rechazado(self, raiz):
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo("binario.dat"))
        assert r.exito is False
        assert r.error == "archivo no es texto plano"

    def test_archivo_grande_se_trunca_de_forma_determinista(self, raiz):
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo("grande.txt"))
        assert r.exito is True
        assert r.truncado is True
        assert len(r.contenido) == LIMITE_CARACTERES_LECTURA

    def test_limite_configurable(self, raiz):
        r = LeerArchivoTool(str(raiz), limite_caracteres=5).ejecutar(EntradaLeerArchivo("README.md"))
        assert r.truncado is True
        assert r.contenido == "Hola "

    def test_to_dict_serializable(self, raiz):
        r = LeerArchivoTool(str(raiz)).ejecutar(EntradaLeerArchivo("README.md"))
        d = r.to_dict()
        assert d == {
            "exito": True, "contenido": "Hola mundo", "ruta": "README.md",
            "error": None, "truncado": False,
        }


class TestListarArchivosTool:
    def test_lista_la_raiz_por_defecto(self, raiz):
        r = ListarArchivosTool(str(raiz)).ejecutar(EntradaListarArchivos())
        assert r.exito is True
        assert "README.md" in r.contenido
        assert "sub/" in r.contenido

    def test_ignora_directorios_de_infraestructura(self, raiz):
        r = ListarArchivosTool(str(raiz)).ejecutar(EntradaListarArchivos())
        for ignorado in ("__pycache__", "node_modules", ".git"):
            assert ignorado not in r.contenido

    def test_respeta_profundidad_maxima(self, raiz):
        r1 = ListarArchivosTool(str(raiz)).ejecutar(EntradaListarArchivos(profundidad_maxima=1))
        assert "sub/" in r1.contenido
        assert "sub/a.py" not in r1.contenido

        r2 = ListarArchivosTool(str(raiz)).ejecutar(EntradaListarArchivos(profundidad_maxima=2))
        assert "sub/a.py" in r2.contenido
        assert "sub/profundo/b.py" not in r2.contenido

    def test_subdirectorio_sin_permiso_se_omite_sin_lanzar(self, raiz):
        (raiz / "sub_sin_permiso").mkdir()
        (raiz / "sub_sin_permiso" / "oculto.txt").write_text("x", encoding="utf-8")
        (raiz / "sub_sin_permiso").chmod(0o000)
        try:
            r = ListarArchivosTool(str(raiz)).ejecutar(EntradaListarArchivos())
        finally:
            (raiz / "sub_sin_permiso").chmod(0o755)
        assert r.exito is True
        assert "sub_sin_permiso/" in r.contenido
        assert "oculto.txt" not in r.contenido

    def test_lista_subdirectorio(self, raiz):
        r = ListarArchivosTool(str(raiz)).ejecutar(EntradaListarArchivos(directorio="sub"))
        assert r.exito is True
        assert "a.py" in r.contenido

    def test_directorio_inexistente(self, raiz):
        r = ListarArchivosTool(str(raiz)).ejecutar(EntradaListarArchivos(directorio="no_existe"))
        assert r.exito is False
        assert r.error == "directorio no encontrado"

    def test_traversal_rechazado(self, raiz):
        r = ListarArchivosTool(str(raiz)).ejecutar(EntradaListarArchivos(directorio=".."))
        assert r.exito is False
        assert r.error == "ruta fuera del alcance permitido"

    def test_ruta_absoluta_rechazada(self, raiz):
        r = ListarArchivosTool(str(raiz)).ejecutar(EntradaListarArchivos(directorio=str(raiz.parent)))
        assert r.exito is False
        assert r.error == "ruta fuera del alcance permitido"

    def test_listar_archivo_como_si_fuera_directorio(self, raiz):
        r = ListarArchivosTool(str(raiz)).ejecutar(EntradaListarArchivos(directorio="README.md"))
        assert r.exito is False
        assert r.error == "directorio no encontrado"
