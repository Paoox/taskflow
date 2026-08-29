# TF-0003-01 — Contenedorizacion inicial de Taskflow
# Arquitectura de esta etapa:  Docker -> Flask -> SQLite  (un solo servicio)
#
# TF-0011: runtime actualizado a Python 3.12 (3.8 quedo EOL, sin parches desde
# 2024-10). La imagen es la referencia del entorno; el host de desarrollo no
# tiene Python 3.12 instalado y la verificacion se hizo con python:3.12-slim.
FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    FLASK_APP=app.py \
    TASKFLOW_DB=/app/data/tareas.db

WORKDIR /app

# Dependencias primero para aprovechar la cache de capas de Docker.
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Codigo de la aplicacion.
COPY . .

# Directorio de datos para la base SQLite. Se declara como volumen para que
# tareas.db no dependa del filesystem efimero del contenedor (CLAUDE.md 25.5).
RUN mkdir -p /app/data
VOLUME ["/app/data"]

EXPOSE 5000

# TF-0012 — Contrato de despliegue (la imagen es NEUTRAL por defecto):
#   Desarrollo:  docker run -p 5000:5000 -v taskflow_data:/app/data taskflow
#                -> clave de sesion efimera + warning; NO usar asi en produccion.
#   Produccion:  docker run ... \
#                  -e TASKFLOW_ENV=production \
#                  -e TASKFLOW_SECRET_KEY=<clave real, p.ej. secrets.token_hex(32)> \
#                  -e TASKFLOW_COOKIE_SECURE=1 \
#                  -v taskflow_data:/app/data taskflow
#                Con TASKFLOW_ENV=production, la ausencia de TASKFLOW_SECRET_KEY
#                aborta el arranque (fail-fast).

# Servidor de desarrollo de Flask. Suficiente para la etapa actual;
# un WSGI de produccion se evaluara en un ticket posterior (BL-06).
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
