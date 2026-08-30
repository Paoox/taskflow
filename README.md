# Taskflow

[![CI](https://github.com/Paoox/taskflow/actions/workflows/ci.yml/badge.svg)](https://github.com/Paoox/taskflow/actions/workflows/ci.yml)

Aplicación web para la gestión de proyectos, tareas y flujos de trabajo de
desarrollo. El objetivo inicial es una herramienta sencilla para organizar
tickets y visualizar su progreso.

## Estado actual

Etapa temprana de desarrollo — prototipo en evolución. La aplicación es
funcionalmente un MVP: permite crear, listar, completar, editar y eliminar
tareas desde la interfaz, sobre una base SQLite. La arquitectura es de un solo
servicio:

```text
Docker → Flask → SQLite
```

La dirección arquitectónica, el modelo de tickets y las reglas de trabajo están
en [`CLAUDE.md`](CLAUDE.md).

## Stack

| Capa | Tecnología |
|---|---|
| Backend | Python, Flask 3 |
| Vistas | Jinja2 (templates del lado del servidor) |
| Base de datos | SQLite |
| Frontend | HTML, CSS, JavaScript (sin framework) |
| Entorno | Docker |

Las dependencias directas y transitivas, fijadas para builds reproducibles,
están en [`requirements.txt`](requirements.txt) (runtime) y
[`requirements-dev.txt`](requirements-dev.txt) (tests).

## Estructura del repositorio

```text
taskflow/
├── app.py                  # rutas Flask y arranque local
├── src/
│   ├── database.py         # DBManager: acceso a SQLite, get_connection()
│   ├── modelos.py          # clases Tarea y Proyecto (POO)
│   ├── validaciones.py     # validación server-side del formulario de tarea
│   └── seguridad.py        # token CSRF y resolución de la clave de sesión
├── templates/              # base.html, index.html, formulario_tarea.html
├── static/style.css
├── tests/                  # suite pytest (test_app, test_database, ...)
├── conftest.py             # fixtures compartidas (DB temporal, cliente)
├── pytest.ini
├── requirements.txt / requirements-dev.txt
├── Dockerfile / .dockerignore
├── .env.example            # variables de entorno documentadas (sin valores)
├── docs/
│   ├── BACKLOG.md          # hallazgos pendientes (BL-XX)
│   └── tickets/            # un documento por ticket TF-XXXX
└── CLAUDE.md               # identidad, arquitectura y reglas del proyecto
```

## Requisitos

- **Docker** y **CI**: entorno verificado en **Python 3.12** (imagen
  `python:3.12-slim`; workflow de GitHub Actions con `python-version: "3.12"`).
- **Entorno virtual local**: la suite se verifica actualmente en **Python
  3.8.10**.

El proyecto no declara oficialmente un rango de versiones de Python soportado:
lo anterior describe únicamente los entornos verificados.

Para el arranque local se necesita Python y `pip`. Para el arranque con Docker,
solo Docker.

## Arranque local (entorno virtual)

```bash
# 1. Crear y activar el entorno virtual
python -m venv venv
source venv/bin/activate          # Windows: venv\Scripts\activate

# 2. Instalar dependencias de runtime
pip install -r requirements.txt

# 3. Arrancar la aplicación
python app.py
```

La aplicación queda en <http://127.0.0.1:5000>.

La base de datos SQLite (`tareas.db` en la raíz del proyecto, por defecto) se
crea automáticamente en el primer arranque, con las tablas y un proyecto semilla
`id=0` ("Tareas Generales"). `tareas.db` está en `.gitignore` y no se versiona.

El bloque de arranque de `python app.py` lee tres variables de entorno
(opcionales, con valores por defecto seguros):

| Variable | Por defecto | Efecto |
|---|---|---|
| `TASKFLOW_HOST` | `127.0.0.1` | Interfaz de escucha (solo loopback por defecto). |
| `TASKFLOW_PORT` | `5000` | Puerto de escucha. |
| `TASKFLOW_DEBUG` | *(desactivado)* | Activa el debugger de Werkzeug **solo** con un valor explícito (`1` / `true` / `yes` / `on`). No usar fuera de desarrollo: expone ejecución de código. |

Alternativa con el CLI de Flask (usa el servidor de desarrollo):

```bash
FLASK_APP=app.py flask run
```

Para ejecutar los tests, ver [Tests y CI](#tests-y-ci).

## Arranque con Docker

```bash
# Construir la imagen
docker build -t taskflow .

# Ejecutar el contenedor con un volumen para la base de datos
docker run -p 5000:5000 -v taskflow_data:/app/data taskflow
```

La aplicación queda en <http://localhost:5000>.

- La imagen fija `TASKFLOW_DB=/app/data/tareas.db` y declara `/app/data` como
  volumen, para que la base SQLite no dependa del filesystem efímero del
  contenedor. El volumen `taskflow_data` del ejemplo conserva los datos entre
  recreaciones del contenedor.
- El contenedor arranca con el **servidor de desarrollo de Flask**
  (`flask run`). Es suficiente para la etapa actual; un servidor WSGI de
  producción está pendiente (ver `BL-06` en [`docs/BACKLOG.md`](docs/BACKLOG.md)).
- La imagen es **neutral** por defecto: sin `TASKFLOW_SECRET_KEY` arranca con una
  clave de sesión efímera y un aviso. Para un despliegue tras TLS, el `Dockerfile`
  documenta el contrato de variables a inyectar
  (`TASKFLOW_ENV=production`, `TASKFLOW_SECRET_KEY`, `TASKFLOW_COOKIE_SECURE=1`);
  con `TASKFLOW_ENV=production`, la ausencia de `TASKFLOW_SECRET_KEY` aborta el
  arranque.

## Variables de entorno

Todas están documentadas, sin valores sensibles, en
[`.env.example`](.env.example). Copiar ese archivo a `.env` para desarrollo local
(`.env` no se versiona).

| Variable | Por defecto | Efecto |
|---|---|---|
| `TASKFLOW_DB` | `tareas.db` | Ruta del archivo SQLite. En la imagen Docker: `/app/data/tareas.db`. |
| `TASKFLOW_SECRET_KEY` | *(sin valor)* | Clave de firma de sesión (protege el token CSRF). Si falta y no es producción: clave efímera aleatoria + aviso. Si falta y `TASKFLOW_ENV=production`: el proceso aborta el arranque. |
| `TASKFLOW_ENV` | *(vacío)* | Solo `production` cambia el comportamiento: activa el fail-fast de `TASKFLOW_SECRET_KEY`. |
| `TASKFLOW_COOKIE_SECURE` | *(desactivado)* | Con `1` la cookie de sesión lleva el atributo `Secure` (usar tras TLS). Activarla sobre HTTP impide enviar la cookie y rompe el flujo CSRF. |
| `TASKFLOW_DEBUG` | *(desactivado)* | Debugger de Werkzeug en `python app.py`; solo con `1` / `true` / `yes` / `on`. |
| `TASKFLOW_HOST` | `127.0.0.1` | Interfaz de escucha en `python app.py`. |
| `TASKFLOW_PORT` | `5000` | Puerto de escucha en `python app.py`. |

## Tests y CI

```bash
pip install -r requirements.txt -r requirements-dev.txt
python -m pytest
```

`pytest.ini` fija `testpaths = tests` e incluye un informe de cobertura de `src`
y `app` (`--cov-report=term-missing`). La cobertura es **informativa**: no hay
umbral que rompa el build.

La integración continua ([`.github/workflows/ci.yml`](.github/workflows/ci.yml))
ejecuta `python -m pytest` con Python 3.12 en cada `push` y cada `pull_request`
sobre `main`. El estado del último run se refleja en el badge de la cabecera.

## Funcionalidades y rutas

Gestión de tareas (CRUD completo desde la interfaz) y lista de proyectos de solo
lectura. Toda petición `POST` exige un token CSRF de sesión; los datos del
formulario se validan en el servidor.

| Método | Ruta | Descripción |
|---|---|---|
| `GET` | `/` | Lista las tareas en estado "Pendiente" y los proyectos. |
| `GET` / `POST` | `/crear` | Formulario de creación de tarea y su envío. |
| `POST` | `/tareas/<id>/completar` | Marca la tarea como "Completada". |
| `GET` / `POST` | `/tareas/<id>/editar` | Edita los campos de una tarea (no toca `estado` ni `fecha_creacion`). |
| `POST` | `/tareas/<id>/eliminar` | Elimina la tarea de forma permanente (con confirmación en el cliente). |

## Modelo de trabajo

- [`CLAUDE.md`](CLAUDE.md) — identidad del proyecto, filosofía arquitectónica,
  sistema de tickets `TF-XXXX`, estados, reglas de seguridad y de Docker.
- [`docs/BACKLOG.md`](docs/BACKLOG.md) — hallazgos pendientes (`BL-XX`) y su
  ciclo `OPEN → PLANNED → PROMOTED → DONE`.
- [`docs/tickets/`](docs/tickets/) — un documento persistente por ticket, con
  objetivo, cambios, pruebas, criterios de aceptación y commit asociado.
