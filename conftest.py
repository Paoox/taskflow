"""
TF-0005 — Configuración compartida de la suite de pruebas.

Punto clave de aislamiento: `src/database.py` lee
`DATABASE_NAME = os.environ.get('TASKFLOW_DB', 'tareas.db')` a nivel de módulo.
pytest importa este `conftest.py` antes que cualquier módulo de test, así que
fijamos aquí `TASKFLOW_DB` a un archivo temporal para que ningún import del
proyecto toque el `tareas.db` real del repositorio.
"""
import os
import re
import tempfile

import pytest

# Se fija ANTES de cualquier `import app` / `import src.database`.
_SESSION_DB_DIR = tempfile.mkdtemp(prefix="taskflow-tests-")
os.environ["TASKFLOW_DB"] = os.path.join(_SESSION_DB_DIR, "session.db")
# Clave de sesión fija para los tests (TF-0008): evita el fallback efímero y
# mantiene los tokens CSRF estables durante la sesión de pruebas.
os.environ.setdefault("TASKFLOW_SECRET_KEY", "clave-de-prueba-no-secreta")

from src import database  # noqa: E402  (import tardío intencional)

_CSRF_RE = re.compile(rb'name="csrf_token" value="([^"]+)"')


@pytest.fixture
def db(tmp_path, monkeypatch):
    """DBManager sobre una base SQLite temporal y limpia por test.

    `get_connection()` resuelve el global `DATABASE_NAME` en cada llamada, así que
    parchearlo redirige también las conexiones nuevas del propio DBManager.
    """
    db_path = tmp_path / "test.db"
    monkeypatch.setattr(database, "DATABASE_NAME", str(db_path))
    manager = database.DBManager()  # __init__ ejecuta crear_tablas()
    return manager


@pytest.fixture
def client(tmp_path, monkeypatch):
    """Cliente de pruebas de Flask con la base redirigida a un archivo temporal."""
    db_path = tmp_path / "app.db"
    monkeypatch.setattr(database, "DATABASE_NAME", str(db_path))

    import app as app_module

    # El db_manager del módulo llama a get_connection() en cada operación, que
    # lee el DATABASE_NAME ya parcheado; recreamos las tablas en el archivo nuevo.
    database.crear_tablas()

    app_module.app.config.update(TESTING=True)
    with app_module.app.test_client() as test_client:
        yield test_client


@pytest.fixture
def csrf_token(client):
    """Devuelve un token CSRF válido para el `client`, extraído de GET /crear.

    El `test_client` conserva la cookie de sesión entre peticiones, así que el
    token devuelto es válido para los POST posteriores del mismo `client`.
    """
    resp = client.get("/crear")
    m = _CSRF_RE.search(resp.data)
    assert m, "No se encontró csrf_token en GET /crear"
    return m.group(1).decode()
