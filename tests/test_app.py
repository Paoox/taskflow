"""Endpoints Flask sobre base temporal.

TF-0005 — smoke de endpoints.
TF-0007 — validación server-side de POST /crear.
"""
import pytest

from src import database


def _contar_tareas():
    conn = database.get_connection()
    n = conn.execute("SELECT COUNT(*) FROM tareas").fetchone()[0]
    conn.close()
    return n


VALIDO = {
    "titulo": "Tarea desde POST",
    "descripcion": "creada en test",
    "fecha_limite": "2026-09-01",
    "prioridad": "Alta",
    "proyecto_id": "0",
}


def test_get_index_responde_200(client):
    assert client.get("/").status_code == 200


def test_get_crear_responde_200(client):
    assert client.get("/crear").status_code == 200


def test_post_crear_redirige_y_persiste(client):
    resp = client.post("/crear", data={
        "titulo": "Tarea desde POST",
        "descripcion": "creada en test",
        "fecha_limite": "2026-09-01",
        "prioridad": "Alta",
        "proyecto_id": "0",
    })
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
def test_post_crear_invalido_responde_400_y_no_persiste(client, cambio):
    data = {k: v for k, v in {**VALIDO, **cambio}.items() if v is not None}
    resp = client.post("/crear", data=data)
    assert resp.status_code == 400
    assert b"Nueva tarea" in resp.data  # re-render del formulario
    assert _contar_tareas() == 0


def test_post_crear_invalido_conserva_valores_enviados(client):
    resp = client.post("/crear", data={**VALIDO, "titulo": "Mi tarea",
                                       "proyecto_id": "abc"})
    assert resp.status_code == 400
    assert b'value="Mi tarea"' in resp.data


def test_post_crear_valido_sin_fecha_persiste_con_none(client):
    data = {k: v for k, v in VALIDO.items() if k != "fecha_limite"}
    resp = client.post("/crear", data=data)
    assert resp.status_code == 302

    conn = database.get_connection()
    fila = conn.execute("SELECT fecha_limite FROM tareas").fetchone()
    conn.close()
    assert fila["fecha_limite"] is None


def test_get_crear_no_falla_con_plantilla_de_validacion(client):
    resp = client.get("/crear")
    assert resp.status_code == 200
    assert b"Nueva tarea" in resp.data
