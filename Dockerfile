# TF-0003-01 — Contenedorizacion inicial de Taskflow
# Arquitectura de esta etapa:  Docker -> Flask -> SQLite  (un solo servicio)
#
# Python 3.8 para coincidir con el entorno verificado en requirements.txt
# (los pines de importlib-metadata / zipp asumen Python < 3.10).
FROM python:3.8-slim

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

# Servidor de desarrollo de Flask. Suficiente para la etapa actual;
# un WSGI de produccion se evaluara en un ticket posterior.
CMD ["flask", "run", "--host=0.0.0.0", "--port=5000"]
