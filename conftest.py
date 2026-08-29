"""
TF-0005 — Configuración compartida de la suite de pruebas.

Punto clave de aislamiento: `src/database.py` lee
`DATABASE_NAME = os.environ.get('TASKFLOW_DB', 'tareas.db')` a nivel de módulo.
pytest importa este `conftest.py` antes que cualquier módulo de test, así que
fijamos aquí `TASKFLOW_DB` a un archivo temporal para que ningún import del
proyecto toque el `tareas.db` real del repositorio.
"""
import os
import tempfile

import pytest

# Se fija ANTES de cualquier `import app` / `import src.database`.
_SESSION_DB_DIR = tempfile.mkdtemp(prefix="taskflow-tests-")
os.environ["TASKFLOW_DB"] = os.path.join(_SESSION_DB_DIR, "session.db")

from src import database  # noqa: E402  (import tardío intencional)


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
