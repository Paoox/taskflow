"""Endpoints Flask sobre base temporal.

TF-0005 — smoke de endpoints.
TF-0007 — validación server-side de POST /crear.
TF-0008 — protección CSRF de las peticiones POST.
TF-0012 — cookie de sesión.
TF-0013 — completar tarea desde la UI.
"""
import pytest

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
