"""TF-0005 — Smoke de endpoints Flask sobre base temporal."""
from src import database


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
