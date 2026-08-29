"""Endpoints Flask sobre base temporal.

TF-0005 — smoke de endpoints.
TF-0007 — validación server-side de POST /crear.
TF-0008 — protección CSRF de las peticiones POST.
TF-0012 — cookie de sesión.
TF-0013 — completar tarea desde la UI.
TF-0017 — higiene del bloque __main__ (arranque local por entorno).
"""
import runpy

import pytest

import app as app_module
from src import database


def _contar_tareas():
    conn = database.get_connection()
    n = conn.execute("SELECT COUNT(*) FROM tareas").fetchone()[0]
    conn.close()
    return n


def _estado_tarea(tarea_id):
    conn = database.get_connection()
    fila = conn.execute(
        "SELECT estado FROM tareas WHERE id = ?", (tarea_id,)).fetchone()
    conn.close()
    return fila["estado"] if fila else None


VALIDO = {
    "titulo": "Tarea desde POST",
    "descripcion": "creada en test",
    "fecha_limite": "2026-09-01",
    "prioridad": "Alta",
    "proyecto_id": "0",
}


def _datos(csrf, **cambios):
    """Construye el cuerpo del POST con token CSRF; valor None elimina la clave."""
    data = {**VALIDO, "csrf_token": csrf, **cambios}
    return {k: v for k, v in data.items() if v is not None}


def test_get_index_responde_200(client):
    assert client.get("/").status_code == 200


def test_get_crear_responde_200(client):
    assert client.get("/crear").status_code == 200


def test_post_crear_redirige_y_persiste(client, csrf_token):
    resp = client.post("/crear", data=_datos(csrf_token))
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")

    conn = database.get_connection()
    filas = conn.execute(
        "SELECT titulo, prioridad, proyecto_id, estado FROM tareas").fetchall()
    conn.close()
    assert len(filas) == 1
    assert filas[0]["titulo"] == "Tarea desde POST"
    assert filas[0]["prioridad"] == "Alta"
    assert filas[0]["proyecto_id"] == 0
    assert filas[0]["estado"] == "Pendiente"


# --- TF-0007: validación server-side de POST /crear -------------------------

@pytest.mark.parametrize("cambio", [
    {"proyecto_id": None},
    {"proyecto_id": "abc"},
    {"proyecto_id": ""},
    {"proyecto_id": "999"},
    {"titulo": None},
    {"titulo": "   "},
    {"prioridad": "Urgente"},
    {"prioridad": None},
    {"fecha_limite": "no-es-fecha"},
], ids=lambda c: "-".join(f"{k}={v}" for k, v in c.items()))
def test_post_crear_invalido_responde_400_y_no_persiste(client, csrf_token, cambio):
    resp = client.post("/crear", data=_datos(csrf_token, **cambio))
    assert resp.status_code == 400
    assert b"Nueva tarea" in resp.data  # re-render del formulario
    assert _contar_tareas() == 0


def test_post_crear_invalido_conserva_valores_enviados(client, csrf_token):
    resp = client.post("/crear", data=_datos(
        csrf_token, titulo="Mi tarea", proyecto_id="abc"))
    assert resp.status_code == 400
    assert b'value="Mi tarea"' in resp.data


def test_post_crear_valido_sin_fecha_persiste_con_none(client, csrf_token):
    resp = client.post("/crear", data=_datos(csrf_token, fecha_limite=None))
    assert resp.status_code == 302

    conn = database.get_connection()
    fila = conn.execute("SELECT fecha_limite FROM tareas").fetchone()
    conn.close()
    assert fila["fecha_limite"] is None


def test_get_crear_no_falla_con_plantilla_de_validacion(client):
    resp = client.get("/crear")
    assert resp.status_code == 200
    assert b"Nueva tarea" in resp.data


# --- TF-0008: protección CSRF ---------------------------------------------

def test_get_crear_incluye_campo_csrf(client):
    resp = client.get("/crear")
    assert resp.status_code == 200
    assert b'name="csrf_token"' in resp.data
    assert b'name="csrf_token" value=""' not in resp.data


def test_post_crear_sin_token_responde_403_y_no_persiste(client):
    data = {k: v for k, v in VALIDO.items()}  # sin csrf_token
    resp = client.post("/crear", data=data)
    assert resp.status_code == 403
    assert _contar_tareas() == 0


def test_post_crear_token_invalido_responde_403_y_no_persiste(client):
    resp = client.post("/crear", data={**VALIDO, "csrf_token": "token-falso"})
    assert resp.status_code == 403
    assert _contar_tareas() == 0


def test_post_crear_token_valido_datos_validos_302(client, csrf_token):
    resp = client.post("/crear", data=_datos(csrf_token))
    assert resp.status_code == 302
    assert _contar_tareas() == 1


def test_post_crear_token_valido_datos_invalidos_sigue_400(client, csrf_token):
    resp = client.post("/crear", data=_datos(csrf_token, proyecto_id="abc"))
    assert resp.status_code == 400
    assert _contar_tareas() == 0


def test_get_index_no_exige_token(client):
    # before_request solo bloquea POST; GET sigue libre.
    assert client.get("/").status_code == 200


# --- TF-0012: cookie de sesión / no-regresión con SECURE off --------------

def test_cookie_secure_off_por_defecto_y_flujo_csrf_intacto(client, csrf_token):
    import app as app_module

    # En el entorno de test no se define TASKFLOW_COOKIE_SECURE.
    assert app_module.app.config["SESSION_COOKIE_SECURE"] is False

    # Con SECURE off el flujo CSRF sobre HTTP sigue funcionando.
    resp = client.post("/crear", data=_datos(csrf_token))
    assert resp.status_code == 302
    assert _contar_tareas() == 1


# --- TF-0013: completar tarea -------------------------------------------

def _crear_y_obtener_id(client, csrf_token, **cambios):
    assert client.post("/crear", data=_datos(csrf_token, **cambios)).status_code == 302
    conn = database.get_connection()
    tarea_id = conn.execute("SELECT id FROM tareas ORDER BY id DESC LIMIT 1").fetchone()["id"]
    conn.close()
    return tarea_id


def test_completar_tarea_redirige_y_cambia_estado(client, csrf_token):
    tarea_id = _crear_y_obtener_id(client, csrf_token, titulo="Pendiente 1")
    resp = client.post(f"/tareas/{tarea_id}/completar",
                       data={"csrf_token": csrf_token})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    assert _estado_tarea(tarea_id) == "Completada"


def test_completar_tarea_desaparece_de_la_lista_de_pendientes(client, csrf_token):
    tarea_id = _crear_y_obtener_id(client, csrf_token, titulo="Se completa")
    assert b"Se completa" in client.get("/").data
    client.post(f"/tareas/{tarea_id}/completar", data={"csrf_token": csrf_token})
    assert b"Se completa" not in client.get("/").data


def test_completar_tarea_id_inexistente_responde_404(client, csrf_token):
    resp = client.post("/tareas/999999/completar", data={"csrf_token": csrf_token})
    assert resp.status_code == 404


def test_completar_tarea_sin_csrf_responde_403(client, csrf_token):
    tarea_id = _crear_y_obtener_id(client, csrf_token)
    resp = client.post(f"/tareas/{tarea_id}/completar", data={})
    assert resp.status_code == 403
    assert _estado_tarea(tarea_id) == "Pendiente"


def test_completar_tarea_get_no_permitido_405(client):
    resp = client.get("/tareas/1/completar")
    assert resp.status_code == 405


def test_completar_tarea_id_no_numerico_404(client, csrf_token):
    resp = client.post("/tareas/abc/completar", data={"csrf_token": csrf_token})
    assert resp.status_code == 404


# --- TF-0014: editar tarea ---------------------------------------------

def _tarea_row(tarea_id):
    conn = database.get_connection()
    fila = conn.execute(
        "SELECT titulo, descripcion, fecha_limite, prioridad, proyecto_id, "
        "estado, fecha_creacion FROM tareas WHERE id = ?", (tarea_id,)).fetchone()
    conn.close()
    return dict(fila) if fila else None


EDICION = {
    "titulo": "Título editado",
    "descripcion": "Descripción editada",
    "fecha_limite": "2026-12-31",
    "prioridad": "Baja",
    "proyecto_id": "0",
}


def test_get_editar_muestra_formulario_prellenado(client, csrf_token):
    tid = _crear_y_obtener_id(client, csrf_token, titulo="Para editar",
                              descripcion="desc original", prioridad="Alta")
    resp = client.get(f"/tareas/{tid}/editar")
    assert resp.status_code == 200
    assert b'value="Para editar"' in resp.data
    assert b"desc original" in resp.data
    assert b"Editar tarea" in resp.data
    assert b"Guardar cambios" in resp.data
    assert f'action="/tareas/{tid}/editar"'.encode() in resp.data


def test_get_editar_id_inexistente_404(client):
    assert client.get("/tareas/999999/editar").status_code == 404


def test_get_editar_id_no_numerico_404(client):
    assert client.get("/tareas/abc/editar").status_code == 404


def test_post_editar_valido_actualiza_y_redirige(client, csrf_token):
    tid = _crear_y_obtener_id(client, csrf_token, titulo="Antes")
    antes = _tarea_row(tid)

    resp = client.post(f"/tareas/{tid}/editar",
                       data={**EDICION, "csrf_token": csrf_token})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")

    ahora = _tarea_row(tid)
    assert ahora["titulo"] == "Título editado"
    assert ahora["descripcion"] == "Descripción editada"
    assert ahora["fecha_limite"] == "2026-12-31"
    assert ahora["prioridad"] == "Baja"
    assert ahora["proyecto_id"] == 0
    # estado y fecha_creacion intactos
    assert ahora["estado"] == antes["estado"] == "Pendiente"
    assert ahora["fecha_creacion"] == antes["fecha_creacion"]


def test_post_editar_conserva_estado_de_tarea_completada(client, csrf_token):
    tid = _crear_y_obtener_id(client, csrf_token, titulo="Completar y editar")
    assert client.post(f"/tareas/{tid}/completar",
                       data={"csrf_token": csrf_token}).status_code == 302
    assert _tarea_row(tid)["estado"] == "Completada"

    resp = client.post(f"/tareas/{tid}/editar",
                       data={**EDICION, "titulo": "Retocada", "csrf_token": csrf_token})
    assert resp.status_code == 302
    fila = _tarea_row(tid)
    assert fila["titulo"] == "Retocada"
    assert fila["estado"] == "Completada"


def test_post_editar_datos_invalidos_400_y_sin_cambios(client, csrf_token):
    tid = _crear_y_obtener_id(client, csrf_token, titulo="No tocar")
    antes = _tarea_row(tid)

    resp = client.post(f"/tareas/{tid}/editar",
                       data={**EDICION, "titulo": "   ", "csrf_token": csrf_token})
    assert resp.status_code == 400
    assert b"Editar tarea" in resp.data
    assert _tarea_row(tid) == antes


def test_post_editar_proyecto_inexistente_400(client, csrf_token):
    tid = _crear_y_obtener_id(client, csrf_token)
    resp = client.post(f"/tareas/{tid}/editar",
                       data={**EDICION, "proyecto_id": "999", "csrf_token": csrf_token})
    assert resp.status_code == 400
    assert _tarea_row(tid)["proyecto_id"] == 0


def test_post_editar_id_inexistente_404(client, csrf_token):
    resp = client.post("/tareas/999999/editar",
                       data={**EDICION, "csrf_token": csrf_token})
    assert resp.status_code == 404


def test_post_editar_sin_csrf_403_y_sin_cambios(client, csrf_token):
    tid = _crear_y_obtener_id(client, csrf_token, titulo="Sin token")
    antes = _tarea_row(tid)
    resp = client.post(f"/tareas/{tid}/editar", data=dict(EDICION))
    assert resp.status_code == 403
    assert _tarea_row(tid) == antes


def test_index_muestra_enlace_editar(client, csrf_token):
    tid = _crear_y_obtener_id(client, csrf_token, titulo="Con enlace")
    body = client.get("/").data
    assert f'href="/tareas/{tid}/editar"'.encode() in body


# --- TF-0014: no-regresión del flujo de creación tras parametrizar la plantilla

def test_crear_sigue_funcionando_tras_parametrizar_plantilla(client, csrf_token):
    resp = client.get("/crear")
    assert resp.status_code == 200
    assert b"Nueva tarea" in resp.data
    assert b"Crear tarea" in resp.data
    assert b'action="/crear"' in resp.data

    r2 = client.post("/crear", data=_datos(csrf_token, titulo="Creada post-TF0014"))
    assert r2.status_code == 302
    conn = database.get_connection()
    n = conn.execute(
        "SELECT COUNT(*) FROM tareas WHERE titulo = 'Creada post-TF0014'").fetchone()[0]
    conn.close()
    assert n == 1


# --- TF-0016: eliminar tarea -----------------------------------------------

def test_eliminar_tarea_borra_y_redirige(client, csrf_token):
    tid = _crear_y_obtener_id(client, csrf_token, titulo="Para borrar")
    resp = client.post(f"/tareas/{tid}/eliminar", data={"csrf_token": csrf_token})
    assert resp.status_code == 302
    assert resp.headers["Location"].endswith("/")
    assert _tarea_row(tid) is None
    assert _contar_tareas() == 0


def test_eliminar_tarea_desaparece_de_la_lista(client, csrf_token):
    tid = _crear_y_obtener_id(client, csrf_token, titulo="Se borra de la lista")
    assert b"Se borra de la lista" in client.get("/").data
    client.post(f"/tareas/{tid}/eliminar", data={"csrf_token": csrf_token})
    assert b"Se borra de la lista" not in client.get("/").data


def test_eliminar_tarea_id_inexistente_404(client, csrf_token):
    assert client.post("/tareas/999999/eliminar",
                       data={"csrf_token": csrf_token}).status_code == 404


def test_eliminar_tarea_id_no_numerico_404(client, csrf_token):
    assert client.post("/tareas/abc/eliminar",
                       data={"csrf_token": csrf_token}).status_code == 404


def test_eliminar_tarea_get_no_permitido_405(client):
    assert client.get("/tareas/1/eliminar").status_code == 405


def test_eliminar_tarea_sin_csrf_403_y_no_borra(client, csrf_token):
    tid = _crear_y_obtener_id(client, csrf_token, titulo="Sin token no borra")
    resp = client.post(f"/tareas/{tid}/eliminar", data={})
    assert resp.status_code == 403
    assert _tarea_row(tid) is not None


def test_index_muestra_form_eliminar_con_confirm(client, csrf_token):
    tid = _crear_y_obtener_id(client, csrf_token, titulo="Con eliminar")
    body = client.get("/").data
    assert f'action="/tareas/{tid}/eliminar"'.encode() in body
    assert b"confirm(" in body


def test_eliminar_no_afecta_a_otras_tareas(client, csrf_token):
    a = _crear_y_obtener_id(client, csrf_token, titulo="Borrar A")
    _crear_y_obtener_id(client, csrf_token, titulo="Conservar B")
    client.post(f"/tareas/{a}/eliminar", data={"csrf_token": csrf_token})
    body = client.get("/").data
    assert b"Conservar B" in body
    assert b"Borrar A" not in body


# --- TF-0017: higiene del bloque __main__ (BL-10) -------------------------

class TestFlagEntorno:
    """TF-0017 — `_flag_entorno`: activación solo con valor explícito."""

    @pytest.mark.parametrize("valor", ["1", "true", "TRUE", "yes", "on", " on "])
    def test_valores_de_activacion_explicitos(self, valor, monkeypatch):
        monkeypatch.setenv("TASKFLOW_DEBUG", valor)
        assert app_module._flag_entorno("TASKFLOW_DEBUG") is True

    @pytest.mark.parametrize("valor", ["", "0", "false", "no", "off", "x"])
    def test_valor_falso_o_vacio_no_activa(self, valor, monkeypatch):
        monkeypatch.setenv("TASKFLOW_DEBUG", valor)
        assert app_module._flag_entorno("TASKFLOW_DEBUG") is False

    def test_variable_ausente_es_false(self, monkeypatch):
        monkeypatch.delenv("TASKFLOW_DEBUG", raising=False)
        assert app_module._flag_entorno("TASKFLOW_DEBUG") is False


class TestArranqueLocal:
    """TF-0017 — el bloque __main__ toma host/port/debug del entorno."""

    def test_app_no_esta_en_modo_debug_por_defecto(self):
        assert app_module.app.debug is False

    def test_main_pasa_host_port_debug_desde_entorno(self, monkeypatch):
        capturado = {}
        monkeypatch.setattr("flask.Flask.run",
                            lambda self, **kw: capturado.update(kw))
        monkeypatch.setenv("TASKFLOW_HOST", "0.0.0.0")
        monkeypatch.setenv("TASKFLOW_PORT", "8080")
        monkeypatch.setenv("TASKFLOW_DEBUG", "1")
        runpy.run_module("app", run_name="__main__")
        assert capturado == {"host": "0.0.0.0", "port": 8080, "debug": True}

    def test_main_usa_defaults_seguros_sin_entorno(self, monkeypatch):
        capturado = {}
        monkeypatch.setattr("flask.Flask.run",
                            lambda self, **kw: capturado.update(kw))
        for var in ("TASKFLOW_HOST", "TASKFLOW_PORT", "TASKFLOW_DEBUG"):
            monkeypatch.delenv(var, raising=False)
        runpy.run_module("app", run_name="__main__")
        assert capturado == {"host": "127.0.0.1", "port": 5000, "debug": False}
