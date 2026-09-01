# Taskflow — Backlog de hallazgos

Registro persistente de bugs, mejoras, features y refactors detectados durante el
desarrollo y aún no abordados. Los ítems son candidatos; el trabajo comprometido
vive como ticket en `docs/tickets/TF-XXXX.md`.

- **IDs** `BL-XX`, independientes de la numeración `TF-XXXX`.
- **Ciclo de estados:** `OPEN → PLANNED → PROMOTED → DONE`.
- **Columna `Ticket`:** al promover un ítem se enlaza aquí su `TF-XXXX`.
- Ver `CLAUDE.md` §29.2.

| ID | Título | Tipo | Prio | Estado | Ticket | Origen |
|----|--------|------|------|--------|--------|--------|
| BL-01 | `/crear` sin validación de entrada (500 con `proyecto_id` inválido/ausente) | BUG/SECURITY | P1 | PROMOTED | TF-0007 | Análisis "siguiente ticket" |
| BL-02 | `obtener_tareas()` no preserva `fecha_creacion` al leer (se regenera con `now()`) | BUG/REFACTOR | P2 | PROMOTED | TF-0009 | Análisis TF-0005 |
| BL-03 | Formulario POST `/crear` sin protección CSRF | SECURITY | P2 | PROMOTED | TF-0008 | Análisis "siguiente ticket" |
| BL-04 | Sin acción de completar/editar/eliminar tareas en la UI | FEATURE | P2 | DONE | TF-0013 (04a), TF-0014 (04b), TF-0016 (04c) | Discusión de tickets |
| BL-05 | Falta `README.md` con arranque local + Docker | DOCS | P2 | DONE | TF-0018 | Análisis "siguiente ticket" |
| BL-06 | Contenedor usa el servidor de desarrollo de Flask; falta WSGI de producción | DEVOPS | P2 | OPEN | — | doc TF-0003-01 |
| BL-07 | Imagen base `python:3.8-slim`: Python 3.8 está EOL, sin parches de seguridad | SECURITY/DEVOPS | P2 | PROMOTED | TF-0011 | doc TF-0003-01 |
| BL-08 | Suite sin CI ni cobertura (`pytest-cov`); no se ejecuta automáticamente | DEVOPS/TEST | P2 | PROMOTED | TF-0010 | TF-0005 |
| BL-09 | `src/database.py` bloque `__main__` hace `os.remove(tareas.db)`: footgun de pérdida de datos + código demo | REFACTOR | P3 | DONE | TF-0017 | Lectura de código en TF-0005 |
| BL-10 | `app.py` bloque `__main__` con `debug=True` fijo y sin config por entorno (host/port/debug) | REFACTOR | P3 | DONE | TF-0017 | Lectura de código |
| BL-11 | `conftest.py` (raíz) y `docs/` no excluidos de la imagen Docker en `.dockerignore` | REFACTOR | P3 | PROMOTED | TF-0012 | TF-0005 |
| BL-12 | SQLite sin `PRAGMA foreign_keys=ON`: no se fuerzan las claves foráneas (`tareas.proyecto_id`) a nivel de motor | REFACTOR/DB | P3 | PROMOTED | TF-0015 | Análisis TF-0007 |
| BL-13 | El contenedor arranca con clave de sesión efímera: `Dockerfile` no define `TASKFLOW_SECRET_KEY` ni hay guía de despliegue que la inyecte | SECURITY/DEVOPS | P2 | PROMOTED | TF-0012 | Estado del repo tras TF-0008 |
| BL-14 | Configuración de entorno dispersa (`os.environ.get` en `app.py`, `src/database.py`, `src/seguridad.py`) + parseo "truthy" duplicado; falta punto único | REFACTOR | P2 | PROMOTED | TF-0019 | Análisis arquitectura de agentes |
| BL-15 | Sin configuración de `logging` ni identificador de correlación por petición; solo un `logger.warning` suelto | DEVOPS | P2 | DONE | TF-0020 | Análisis arquitectura de agentes |
| BL-16 | Falta el andamiaje de la capa de agentes: contrato `CLAUDE.md` §27, interfaz de proveedor IA desacoplada (§26), cliente eco sin red y prompts separados | ARCH/AI | P2 | DONE | TF-0021 | Análisis arquitectura de agentes |
| BL-17 | Sin registro persistente de ejecuciones/acciones para la trazabilidad `CLAUDE.md` §28 (qué actor hizo qué y por qué) | ARCH | P2 | PROMOTED | TF-0022 | Análisis arquitectura de agentes |

---

## Detalle

### BL-01 — `/crear` sin validación de entrada

`crear_tarea_web` en `app.py` ejecuta `int(request.form.get('proyecto_id'))` sin
comprobaciones: con el campo ausente o no numérico lanza `ValueError` / `TypeError`
→ HTTP 500. Tampoco se validan `titulo`, `fecha_limite` ni `prioridad`.
CLAUDE.md §21 (validar datos del usuario).

### BL-02 — `obtener_tareas()` regenera `fecha_creacion`

Al reconstruir cada `Tarea` desde la fila SQL no se pasa `fecha_creacion`, así que
el modelo la sobreescribe con `datetime.now()`. La fecha real almacenada por
`crear_tarea()` nunca se devuelve en lecturas. Detectado y acotado en TF-0005
(los tests no asumen que se preserve).

### BL-03 — Sin CSRF en `/crear`

El formulario POST no incluye token CSRF ni hay protección a nivel de aplicación.
CLAUDE.md §21.

### BL-04 — Gestión de tareas en la UI

El modelo tiene `marcar_como_completada()` pero no hay ruta ni control en la
interfaz; `index()` solo muestra tareas en estado "Pendiente". No hay editar,
eliminar ni vista de detalle.

Completado en 3 slices (**BL-04 DONE**):

- **04a — completar** (`TF-0013`): `DBManager.marcar_tarea_completada(id)`
  + `POST /tareas/<id>/completar` + botón "Completar" en `index.html`.
- **04b — editar** (`TF-0014`): `DBManager.obtener_tarea(id)` +
  `actualizar_tarea(id, datos)` + `GET|POST /tareas/<id>/editar` reutilizando
  `formulario_tarea.html` parametrizada + enlace "Editar" en `index.html`. No
  toca `estado` ni `fecha_creacion`.
- **04c — eliminar** (`TF-0016`): `DBManager.eliminar_tarea(id)` +
  `POST /tareas/<id>/eliminar` + botón "Eliminar" (con `confirm()` de JS) en
  `index.html`. Borrado permanente; sin papelera/undo. Borrar una tarea (hijo de
  la FK) no afecta a `proyectos`.

Nota: BL-12 no era un bloqueo real de 04c — borrar una *tarea* no toca la FK
`tareas.proyecto_id`; solo lo sería borrar *proyectos* (no hay tal función).

### BL-05 — README de arranque

No existe `README.md`. Debería documentar el arranque local (venv) y con Docker
(`build` / `run`, `TASKFLOW_DB`, volumen `/app/data`). Complementa CLAUDE.md §29.

Promovido a **TF-0018** y **DONE** (commit `1bc4964` en `origin/main`, CI #10 en
verde): se crea `README.md` en la raíz (español) con descripción y estado, stack,
estructura del repo, requisitos, arranque local con venv, arranque con Docker
(volumen `/app/data`, `TASKFLOW_DB`), tabla de las variables de `.env.example`,
tests + CI, badge de GitHub Actions, funcionalidades y rutas, aclaración de que
Docker usa el servidor de desarrollo de Flask (WSGI de producción pendiente en
BL-06) y enlaces a `CLAUDE.md` / `docs/BACKLOG.md` / `docs/tickets/`. Además se
añade `README.md` a `.dockerignore` (fuera de la imagen, mismo criterio que
BL-11). Sin cambios de código. Verificado en Docker (build OK, `GET /` → HTTP
200, Python 3.12.14, `README.md` excluido de la imagen) y en GitHub Actions CI
#10.

### BL-06 — WSGI de producción

El `CMD` del contenedor es `flask run` (servidor de desarrollo, con warning
explícito). Para uso no-dev haría falta gunicorn u otro WSGI. Anotado como
"ticket posterior" en `docs/tickets/TF-0003-01.md`.

### BL-07 — Base image Python 3.8 EOL

`python:3.8-slim` ya no recibe parches de seguridad. Un upgrade (3.11 / 3.12)
permitiría además retirar los pines de `importlib-metadata` / `zipp`. Requiere
re-verificar toda la suite y el arranque. Anotado en
`docs/tickets/TF-0003-01.md`.

Promovido a **TF-0011**: `Dockerfile` y CI → `python:3.12`; se eliminan
`importlib-metadata` y `zipp` de `requirements.txt`. La validación en Python 3.12
se hizo con `python:3.12-slim` (el host de desarrollo no tiene 3.12); la
recreación del venv local en 3.12 queda pendiente hasta instalarlo en el host.

### BL-08 — CI y cobertura

La suite (`python -m pytest`, 90 tests a fecha de la promoción) solo se ejecuta a
mano. Faltan integración en CI y medición de cobertura.

Promovido a **TF-0010**: GitHub Actions (`push` + `pull_request` sobre `main`),
`pytest` + `pytest-cov` con cobertura informativa (sin umbral), solo Python 3.8.

### BL-09 — `__main__` destructivo en `database.py`

El bloque de demo borra `tareas.db` con `os.remove` antes de recrear tablas.
Ejecutar el módulo por error implica pérdida de datos. Candidato a eliminar o
mover a un script / fixture.

Promovido a **TF-0017** y **DONE** (commit `6a0b269`): se elimina el bloque
`__main__` completo. Sin sustituto (la init de la base ya ocurre en
`DBManager.__init__ → crear_tablas()`; no se añade `scripts/` ni seed).
Regresión: `python -m src.database` sobre una DB poblada ya no la borra ni la
muta (test en `tests/test_database.py`).

### BL-10 — Config de arranque en `app.py`

`app.run(debug=True)` fijo. Debería tomar host / port / debug de variables de
entorno para no depender de editar código.

Promovido a **TF-0017** y **DONE** (commit `6a0b269`): el bloque `__main__` toma
`host` / `port` / `debug` de `TASKFLOW_HOST` / `TASKFLOW_PORT` / `TASKFLOW_DEBUG`
con defaults seguros (`127.0.0.1:5000`, debugger desactivado salvo valor de
activación explícito). Docker no se ve afectado (usa `flask run`; verificado:
`GET /` → HTTP 200 en el contenedor). Variables documentadas en `.env.example`.

### BL-11 — `conftest.py` y `docs/` en la imagen Docker

`conftest.py` (raíz) y `docs/` entran en la imagen vía `COPY . .`. Son inertes en
runtime pero son peso muerto. Alcance ampliado en TF-0012 para excluir ambos en
`.dockerignore` junto con el resto de artefactos no-runtime.

Promovido a **TF-0012** (de remolque del endurecimiento del contenedor).

### BL-12 — SQLite sin enforcement de claves foráneas

`crear_tablas()` declara `FOREIGN KEY (proyecto_id) REFERENCES proyectos(id)`,
pero SQLite no aplica las FK salvo que se ejecute `PRAGMA foreign_keys = ON` por
conexión. Por eso es posible insertar tareas con `proyecto_id` huérfano por vías
distintas a `POST /crear`. TF-0007 cubre el caso solo en la capa de aplicación
(validando contra `obtener_proyectos()`).

Promovido a **TF-0015**: `get_connection()` ejecuta `PRAGMA foreign_keys = ON` en
toda conexión. Sin tocar el esquema, la FK declarada ni `ON DELETE`/`ON UPDATE`.
Impacto verificado nulo sobre datos existentes (`tareas.db` sin huérfanos); el
seed `id=0` se crea igual y todos los tests insertan con `proyecto_id=0`.

### BL-13 — El contenedor arranca con clave de sesión efímera

Desde TF-0008, `app.secret_key` se resuelve con `obtener_secret_key()`: si
`TASKFLOW_SECRET_KEY` no está definida, genera una clave efímera aleatoria y
registra un `warning`. El `Dockerfile` define `TASKFLOW_DB` como `ENV` pero **no**
`TASKFLOW_SECRET_KEY`, y no hay `docker-compose` ni guía de `docker run` que la
inyecte. Consecuencia: un contenedor arranca siempre en modo desarrollo respecto a
la sesión — los tokens CSRF y las sesiones no sobreviven a un reinicio ni son
consistentes entre réplicas. Incluir también, para despliegue tras TLS, fijar
`SESSION_COOKIE_SECURE = True` (hoy sin definir → la cookie viaja sobre HTTP).

Promovido a **TF-0012**: `obtener_secret_key()` con fail-fast en producción
(`TASKFLOW_ENV=production` sin `TASKFLOW_SECRET_KEY` → `RuntimeError`);
`SESSION_COOKIE_SECURE` controlado por `TASKFLOW_COOKIE_SECURE`; `Dockerfile`
neutral por defecto + contrato de despliegue documentado. Sin `docker-compose` y
sin almacén de sesiones (la clave fija + cookie firmada de Flask basta para que la
sesión sobreviva a un reinicio).

### BL-14 — Configuración de entorno dispersa

`os.environ.get(...)` se lee en tres módulos (`app.py`, `src/database.py`,
`src/seguridad.py`) y el parseo de valores "truthy" está duplicado
(`_VALORES_VERDADEROS` en `app.py`, `_VERDADEROS` en `src/seguridad.py`). No hay
un punto único de configuración. La incorporación de agentes añadirá varias
variables (`TASKFLOW_AI_*`, nivel de log) y necesita un lugar único donde
declararlas.

Detectado en el análisis de arquitectura para agentes (2026-08-29).

Promovido a **TF-0019**: nuevo `src/config.py` con un helper booleano único y un
accessor por variable, con **late binding** (lee `os.environ` en cada llamada,
para no romper el aislamiento de `conftest.py` ni los `monkeypatch` de
`test_seguridad.py`). Sin cambiar nombres, defaults ni comportamiento; sin tocar
`conftest.py`. Es el cimiento de TF-0020, TF-0021 y TF-0022.

### BL-15 — Sin observabilidad configurada

No hay configuración de `logging`: la única traza es `app.logger.warning(...)` en
`obtener_secret_key()`. No hay formato consistente, nivel por entorno ni
identificador de correlación. `CLAUDE.md` §26 ("registrar errores") y §28
(trazabilidad) no son realizables en ese estado.

Detectado en el análisis de arquitectura para agentes (2026-08-29).

Promovido a **TF-0020**: nuevo `src/observabilidad.py` con `configurar_logging()`
idempotente (biblioteca estándar, sin dependencias), nivel por
`TASKFLOW_LOG_LEVEL`, y un `correlation_id` **por petición HTTP** (`contextvars`)
más un helper reutilizable. En esta etapa **no** se construye trazabilidad
específica de agentes; el único consumidor es la app web.

**DONE** (2026-08-31): `src/observabilidad.py` (logger central `"taskflow"`,
filtro de `correlation_id` en el logger para compatibilidad con `caplog`,
`ContextVar` con fallback `"-"`), accessor `config.nivel_log()` con late binding,
integración en `app.py` (`before_request` sin log + `teardown_request` que limpia
el contextvar aun con excepción), y el warning de clave efímera al logger central
sin cambiar firma/texto/condición. Suite: 248 passed, cobertura 100 % (incluida
`src/observabilidad.py`). Sin tocar `conftest.py`, `pytest.ini`, Docker/CI ni
tests existentes. Commit `65e3632`. Ver `docs/tickets/TF-0020.md` para el detalle.

### BL-16 — Falta el andamiaje de la capa de agentes

No existe ninguna capa de IA/agentes. Para incorporar el primer agente hace falta,
como andamiaje mínimo y en Python puro: las estructuras del contrato de `CLAUDE.md`
§27 (entrada/salida), una interfaz de proveedor de IA desacoplada del núcleo
(§26), una implementación eco sin red ni coste para validar contrato e
integración, y la ubicación separada de los prompts (§26).

Detectado en el análisis de arquitectura para agentes (2026-08-29).

Promovido a **TF-0021**: `src/agentes/contrato.py` (dataclasses `EntradaAgente` /
`SalidaAgente`, mínimas y alineadas con §27), `src/ai/cliente.py` (`ClienteIA`
como `Protocol` + `ClienteEco` deliberadamente simple y determinista, sin red) y
`src/ai/prompts/` (convención + helper `cargar_prompt`). **Sin** proveedor real,
SDK, API ni infraestructura. **No** se implementan Documentador, Arquitecto,
Orquestador ni runner. `pytest.ini` no se modifica automáticamente: se documenta
si `--cov=src` recoge los módulos nuevos y, si no, el cambio de una línea se
somete a revisión.

**DONE** (2026-08-31, commit `3a9cebd`): contrato con `SalidaAgente` =
5 campos de §27 + `artefactos` + `meta` (Opción A del checkpoint, justificados
por §26/§28/§29.1 y consumidos por TF-0022); `to_dict` = `dataclasses.asdict`,
`from_dict` a mano; `ClienteIA` como `typing.Protocol` `@runtime_checkable`;
`ClienteEco` eco recortado a 500, determinista, sin red, coste 0, logger
opcional; `cargar_prompt` con validación anti path-traversal y error tipado
`PromptNoEncontrado(FileNotFoundError)`. Suite 289 passed, cobertura 100 % (incl.
los 5 módulos nuevos). `--cov=src` los recoge sin tocar `pytest.ini`. Sin
dependencias nuevas. Ver `docs/tickets/TF-0021.md`.

### BL-17 — Sin registro persistente de ejecuciones

`CLAUDE.md` §28 exige poder relacionar toda acción relevante con un ticket y, más
adelante, registrar "qué agente realizó qué acción y por qué". Hoy esa
información solo vive en Git y en los Markdown de `docs/`. No hay ningún registro
máquina-legible.

Detectado en el análisis de arquitectura para agentes (2026-08-29).

Promovido a **TF-0022**: una única tabla nueva `acciones`
(`id, ticket, actor, tipo, entrada, resultado, estado, creado_en,
actualizado_en`) creada en `crear_tablas()` con el patrón actual
(`CREATE TABLE IF NOT EXISTS`, sin ORM ni migraciones) y un
`RepositorioAcciones` que trabaja con **JSON genérico** (no importa las
dataclasses de TF-0021). Sin FK sobre `ticket` (es un `TF-XXXX` textual, no una
fila de `tareas`/`proyectos`). Es infraestructura de trazabilidad, no parte del
dominio de tareas. La concurrencia (WAL / `busy_timeout`) queda fuera de alcance
para un ticket posterior.
