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
| BL-04 | Sin acción de completar/editar/eliminar tareas en la UI | FEATURE | P2 | OPEN | — | Discusión de tickets |
| BL-05 | Falta `README.md` con arranque local + Docker | DOCS | P2 | OPEN | — | Análisis "siguiente ticket" |
| BL-06 | Contenedor usa el servidor de desarrollo de Flask; falta WSGI de producción | DEVOPS | P2 | OPEN | — | doc TF-0003-01 |
| BL-07 | Imagen base `python:3.8-slim`: Python 3.8 está EOL, sin parches de seguridad | SECURITY/DEVOPS | P2 | OPEN | — | doc TF-0003-01 |
| BL-08 | Suite sin CI ni cobertura (`pytest-cov`); no se ejecuta automáticamente | DEVOPS/TEST | P3 | OPEN | — | TF-0005 |
| BL-09 | `src/database.py` bloque `__main__` hace `os.remove(tareas.db)`: footgun de pérdida de datos + código demo | REFACTOR | P3 | OPEN | — | Lectura de código en TF-0005 |
| BL-10 | `app.py` bloque `__main__` con `debug=True` fijo y sin config por entorno (host/port/debug) | REFACTOR | P3 | OPEN | — | Lectura de código |
| BL-11 | `conftest.py` (raíz) no excluido de la imagen Docker en `.dockerignore` | REFACTOR | P3 | OPEN | — | TF-0005 |
| BL-12 | SQLite sin `PRAGMA foreign_keys=ON`: no se fuerzan las claves foráneas (`tareas.proyecto_id`) a nivel de motor | REFACTOR/DB | P3 | OPEN | — | Análisis TF-0007 |

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

### BL-05 — README de arranque

No existe `README.md`. Debería documentar el arranque local (venv) y con Docker
(`build` / `run`, `TASKFLOW_DB`, volumen `/app/data`). Complementa CLAUDE.md §29.

### BL-06 — WSGI de producción

El `CMD` del contenedor es `flask run` (servidor de desarrollo, con warning
explícito). Para uso no-dev haría falta gunicorn u otro WSGI. Anotado como
"ticket posterior" en `docs/tickets/TF-0003-01.md`.

### BL-07 — Base image Python 3.8 EOL

`python:3.8-slim` ya no recibe parches de seguridad. Un upgrade (3.11 / 3.12)
permitiría además retirar los pines de `importlib-metadata` / `zipp`. Requiere
re-verificar toda la suite y el arranque. Anotado en
`docs/tickets/TF-0003-01.md`.

### BL-08 — CI y cobertura

La suite (`python -m pytest`, 23 tests) solo se ejecuta a mano. Faltan integración
en CI y medición de cobertura.

### BL-09 — `__main__` destructivo en `database.py`

El bloque de demo borra `tareas.db` con `os.remove` antes de recrear tablas.
Ejecutar el módulo por error implica pérdida de datos. Candidato a eliminar o
mover a un script / fixture.

### BL-10 — Config de arranque en `app.py`

`app.run(debug=True)` fijo. Debería tomar host / port / debug de variables de
entorno para no depender de editar código.

### BL-11 — `conftest.py` en la imagen Docker

`conftest.py` (raíz) entra en la imagen vía `COPY . .`. Es inerte en runtime pero
podría excluirse en `.dockerignore` junto con el resto de artefactos de test.

### BL-12 — SQLite sin enforcement de claves foráneas

`crear_tablas()` declara `FOREIGN KEY (proyecto_id) REFERENCES proyectos(id)`,
pero SQLite no aplica las FK salvo que se ejecute `PRAGMA foreign_keys = ON` por
conexión. Por eso es posible insertar tareas con `proyecto_id` huérfano por vías
distintas a `POST /crear`. TF-0007 cubre el caso solo en la capa de aplicación
(validando contra `obtener_proyectos()`). Activar el pragma es un cambio de
comportamiento del motor con impacto transversal (afecta al seed `id=0`, a otras
inserciones y a los tests); se aborda por separado.
