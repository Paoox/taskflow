# TASKFLOW — CLAUDE.md

## 1. Identidad del proyecto

**Nombre:** Taskflow

**Repositorio:** `Paoox/taskflow`

Taskflow es una aplicación web para gestión de proyectos, tareas y flujos de trabajo de desarrollo.

El objetivo inicial es construir una herramienta sencilla para organizar tickets y visualizar su progreso.

El objetivo a largo plazo es evolucionar Taskflow hacia una plataforma capaz de coordinar procesos de desarrollo asistidos por IA y agentes especializados.

La arquitectura debe permitir esta evolución sin introducir complejidad innecesaria durante las primeras etapas.

---

# 2. Estado actual del proyecto

Taskflow se encuentra en una etapa temprana de desarrollo.

La estructura actual es pequeña y debe considerarse un prototipo en evolución.

Actualmente existen, entre otros:

```text
app.py
src/
tareas.db
.gitignore
```

Antes de modificar cualquier parte del proyecto, Claude debe inspeccionar la implementación actual y no asumir que la arquitectura futura ya existe.

La aplicación debe evolucionar de forma incremental.

---

# 3. Stack tecnológico

La tecnología principal actual es:

```text
Python
Flask
Jinja2
SQLite
HTML
CSS
JavaScript
```

### Backend

Utilizar Flask como framework web principal.

### Templates

Utilizar Jinja2 mediante el sistema de templates de Flask.

No introducir un framework frontend separado durante las primeras etapas salvo que exista una necesidad técnica clara y se apruebe previamente.

### Base de datos

La base de datos inicial es SQLite.

El archivo actual es:

```text
tareas.db
```

La persistencia debe mantenerse simple durante la etapa inicial.

La migración futura a PostgreSQL u otra base de datos podrá realizarse cuando las necesidades del proyecto lo justifiquen.

---

# 4. Filosofía arquitectónica

Taskflow debe seguir una arquitectura progresiva.

No se debe implementar desde el inicio una arquitectura compleja solamente pensando en necesidades futuras.

Principios:

* simplicidad;
* modularidad;
* separación de responsabilidades;
* bajo acoplamiento;
* facilidad de testing;
* facilidad de evolución;
* mínima complejidad necesaria.

La arquitectura debe poder crecer sin obligarnos a reescribir el proyecto completo.

---

# 5. Evolución esperada de la arquitectura

La arquitectura puede evolucionar progresivamente desde:

```text
Flask
  │
  ├── Routes
  ├── Templates
  ├── Logic
  └── SQLite
```

hacia una estructura más modular:

```text
Flask
│
├── Routes / Controllers
│
├── Services
│
├── Models / Repository
│
├── Templates
│
├── Static
│
└── Database
```

Más adelante, si el proyecto lo requiere:

```text
Frontend
     │
     ▼
API
     │
     ▼
Services
     │
     ├── Database
     ├── AI
     └── Agents
```

Claude debe evolucionar la arquitectura únicamente cuando exista una necesidad real.

---

# 6. Organización propuesta

Cuando el proyecto crezca, se recomienda aproximarse progresivamente a una estructura similar a:

```text
taskflow/
│
├── app.py
├── requirements.txt
├── .env
├── .gitignore
├── CLAUDE.md
│
├── src/
│   ├── routes/
│   ├── services/
│   ├── models/
│   ├── repositories/
│   ├── templates/
│   └── static/
│
├── tests/
│
└── instance/
```

Esta estructura es una dirección arquitectónica, no una obligación inmediata.

No crear carpetas vacías o capas abstractas antes de necesitarlas.

---

# 7. Flask y Jinja2

Flask es el framework web principal durante la primera etapa.

Jinja2 debe utilizarse para renderizar las vistas del servidor.

Preferir:

```text
Flask route
    ↓
Service / lógica necesaria
    ↓
Template Jinja2
```

sobre introducir un frontend separado sin necesidad.

Las templates deben mantenerse enfocadas principalmente en presentación.

Evitar colocar lógica de negocio compleja dentro de Jinja2.

Jinja2 puede utilizarse para:

* renderizar datos;
* mostrar estados;
* generar listas;
* mostrar mensajes;
* construir componentes visuales reutilizables;
* controlar condiciones simples de presentación.

La lógica de negocio debe permanecer en Python.

---

# 8. Frontend inicial

Durante la etapa inicial se utilizará:

```text
HTML
CSS
JavaScript
Jinja2
```

La interfaz debe priorizar:

* claridad;
* usabilidad;
* navegación sencilla;
* responsive design;
* componentes reutilizables;
* consistencia visual.

No introducir React, Vue, Angular u otro framework frontend sin una decisión explícita de arquitectura.

---

# 9. Base de datos

SQLite será utilizada durante la etapa inicial.

El código de acceso a datos debe diseñarse de forma que posteriormente sea posible migrar a PostgreSQL sin reescribir toda la lógica de negocio.

Cuando sea apropiado, separar:

```text
Model
Repository / Data access
Service
Route
```

No es obligatorio implementar todas estas capas para cada funcionalidad desde el inicio.

---

# 10. Sistema de tickets

Todo trabajo relevante debe estar asociado a un ticket.

Formato:

```text
TF-XXXX
```

Ejemplos:

```text
TF-0001
TF-0002
TF-0003
```

Subtareas:

```text
TF-0003-01
TF-0003-02
TF-0003-03
```

Cada ticket debe representar una unidad de trabajo concreta.

---

# 11. Tipos de tickets

Tipos disponibles:

```text
FEATURE
BUG
REFACTOR
UI
TEST
SECURITY
DOCS
ARCH
AI
DEVOPS
```

---

# 12. Prioridades

```text
P0 — Crítica
P1 — Alta
P2 — Normal
P3 — Baja
```

---

# 13. Estados

Flujo estándar:

```text
BACKLOG
    ↓
ANALYSIS
    ↓
PLANNED
    ↓
IN_PROGRESS
    ↓
TESTING
    ↓
REVIEW
    ↓
DONE
```

Un ticket puede regresar a un estado anterior.

Ejemplo:

```text
TESTING
   ↓
IN_PROGRESS
```

cuando se detecta un problema.

---

# 14. Ciclo de trabajo de Claude

Claude debe trabajar siguiendo este ciclo:

```text
1. ANALIZAR
       ↓
2. PROPONER PLAN
       ↓
3. IMPLEMENTAR
       ↓
4. PROBAR
       ↓
5. REVISAR
       ↓
6. REPORTAR
```

No saltarse directamente a modificar código cuando el ticket implique cambios importantes.

---

# 15. Fase 1 — Análisis

Antes de modificar:

* revisar estructura;
* revisar archivos relacionados;
* revisar código existente;
* identificar dependencias;
* identificar impacto;
* revisar persistencia;
* identificar riesgos.

Claude debe evitar asumir cómo funciona el sistema cuando puede inspeccionarlo directamente.

---

# 16. Fase 2 — Plan

Antes de una modificación significativa, Claude debe indicar:

```text
Objetivo
Archivos afectados
Implementación propuesta
Pruebas necesarias
Riesgos
```

Si existe una decisión arquitectónica importante:

```text
NO IMPLEMENTAR TODAVÍA
```

Claude debe presentar la propuesta y solicitar aprobación.

---

# 17. Fase 3 — Implementación

Claude debe:

* modificar únicamente lo necesario;
* mantener el alcance del ticket;
* respetar el código existente;
* evitar duplicación;
* reutilizar funciones existentes cuando corresponda;
* evitar dependencias innecesarias;
* evitar reescrituras completas sin justificación.

---

# 18. Regla de alcance

Si durante un ticket aparece un problema diferente:

NO incorporarlo silenciosamente.

Ejemplo:

```text
Ticket actual:
TF-0010

Problema encontrado:
El sistema necesita autenticación.

Acción:
No implementar autenticación dentro de TF-0010.

Crear propuesta:
TF-0015 — Sistema de autenticación.
```

Esto permite mantener los cambios aislados y rastreables.

---

# 19. Testing

Toda funcionalidad nueva debe considerar pruebas.

Durante la etapa inicial se recomienda utilizar:

```text
pytest
```

cuando el proyecto alcance suficiente lógica para justificarlo.

Claude debe priorizar pruebas para:

* lógica de negocio;
* servicios;
* validaciones;
* endpoints;
* operaciones de persistencia;
* funcionalidades críticas.

No es obligatorio crear tests para cada cambio visual trivial.

---

# 20. Verificación

Claude debe diferenciar entre:

```text
VERIFICADO
```

y:

```text
NO VERIFICADO
```

Nunca afirmar que una funcionalidad funciona si no fue comprobada.

Si una prueba no puede ejecutarse, debe indicarse claramente.

---

# 21. Seguridad

Nunca almacenar secretos en el repositorio.

El archivo:

```text
.env
```

es para configuración local y secretos.

No colocar:

```text
API keys
passwords
tokens
credentials
private keys
```

directamente en el código.

Validar siempre los datos provenientes del usuario.

Prestar especial atención a:

* SQL injection;
* XSS;
* CSRF;
* autenticación;
* autorización;
* manejo de sesiones;
* exposición de información;
* archivos subidos por usuarios;
* secretos.

---

# 22. Git

Repositorio:

```text
Paoox/taskflow
```

Rama principal:

```text
main
```

Antes de trabajar:

```bash
git status
```

Claude debe evitar operaciones destructivas sin autorización explícita.

No ejecutar sin autorización:

```bash
git reset --hard
git clean -fd
git push --force
```

Los commits deben ser pequeños y relacionados con el ticket.

Formato recomendado:

```text
TF-XXXX: descripción breve
```

Ejemplo:

```text
TF-0004: crear estados de tareas
```

No mezclar múltiples funcionalidades independientes en un mismo commit cuando pueda evitarse.

---

# 23. Dependencias

Antes de instalar una dependencia:

1. Revisar si ya existe una solución en el proyecto.
2. Evaluar si realmente es necesaria.
3. Considerar mantenimiento.
4. Considerar seguridad.
5. Explicar brevemente su propósito.

No instalar paquetes por conveniencia si la funcionalidad puede resolverse razonablemente con Flask, Python o las herramientas existentes.

---

# 24. Configuración Python

El entorno virtual debe permanecer fuera del repositorio.

El `.gitignore` actual contiene:

```text
venv/
__pycache__/
*.pyc
.env
```

Estos elementos deben permanecer ignorados.

Cuando se agreguen dependencias, mantener un archivo:

```text
requirements.txt
```

actualizado.

---

# 25. IA y agentes

La IA no debe introducirse prematuramente en todas las capas del proyecto.

Cuando se incorporen funcionalidades de IA:

* mantenerlas desacopladas del núcleo;
* evitar depender de un único proveedor;
* permitir cambiar de modelo cuando sea posible;
* separar prompts de lógica de negocio;
* registrar errores;
* considerar costos;
* considerar latencia;
* considerar privacidad;
* diseñar las integraciones para permitir agentes especializados.

La arquitectura futura debe permitir integrar modelos locales, APIs externas y agentes especializados sin reescribir el núcleo de Taskflow.

---

# 26. Filosofía para agentes futuros

Taskflow eventualmente podrá coordinar agentes especializados.

Posibles agentes:

```text
ARCHITECT
CODER
TESTER
SECURITY
DOCUMENTATION
REVIEWER
```

Los agentes no deben tener acceso ilimitado al proyecto.

Cada agente debe recibir:

```text
Ticket
Objetivo
Contexto
Restricciones
Criterios de aceptación
Archivos relevantes
```

Y devolver:

```text
Resultado
Cambios
Pruebas
Problemas
Recomendaciones
```

El sistema debe priorizar trazabilidad.

---

# 27. Trazabilidad

Toda acción relevante debe poder relacionarse con un ticket.

Idealmente:

```text
Ticket
   ↓
Plan
   ↓
Cambios
   ↓
Tests
   ↓
Review
   ↓
Commit
```

Esto permitirá posteriormente que Taskflow registre qué agente realizó qué acción y por qué.

---

# 28. Documentación

Documentar decisiones importantes.

Especialmente:

* arquitectura;
* estructura del proyecto;
* APIs;
* modelos;
* integraciones;
* IA;
* agentes;
* decisiones de seguridad.

La documentación debe describir el comportamiento real del sistema.

---

# 29. Regla de mínima complejidad

No implementar una solución compleja solamente porque podría ser útil en el futuro.

Preferir:

```text
solución simple
        ↓
validación
        ↓
crecimiento
        ↓
refactor cuando sea necesario
```

sobre:

```text
arquitectura compleja
        ↓
problemas hipotéticos
        ↓
sobreingeniería
```

---

# 30. Decisiones autónomas

Claude puede tomar decisiones pequeñas y reversibles cuando exista suficiente contexto.

Debe solicitar aprobación antes de:

* cambiar arquitectura principal;
* introducir un framework importante;
* migrar base de datos;
* eliminar funcionalidad;
* cambiar contratos de API;
* introducir autenticación;
* modificar infraestructura;
* realizar cambios de seguridad de alto impacto;
* introducir una dependencia importante.

---

# 31. Reporte de trabajo

Al finalizar un ticket:

```text
Ticket:
TF-XXXX

Estado:
DONE / BLOCKED / NEEDS_REVIEW

Resumen:
...

Cambios:
- ...

Archivos modificados:
- ...

Pruebas:
- ...

Resultado:
...

Problemas:
...

Pendientes:
...
```

---

# 32. Regla de honestidad

Claude nunca debe inventar:

* resultados de pruebas;
* archivos modificados;
* funcionalidades implementadas;
* comportamiento observado;
* errores;
* decisiones del usuario.

Si algo no se sabe:

```text
NO VERIFICADO
```

Si algo requiere decisión:

```text
REQUIERE APROBACIÓN
```

---

# 33. Principio general

Taskflow está siendo construido para ser utilizado por humanos y, posteriormente, por agentes de IA.

Por lo tanto, el código debe priorizar:

```text
Claridad
Trazabilidad
Modularidad
Seguridad
Testabilidad
Mantenibilidad
Simplicidad
```

El objetivo no es solamente construir una aplicación que funcione.

El objetivo es construir una aplicación que pueda evolucionar hacia un sistema de coordinación de trabajo humano + IA.

---

# 34. Pregunta de control antes de modificar código

Antes de realizar cambios importantes, Claude debe poder responder:

1. ¿Qué ticket estoy resolviendo?
2. ¿Cuál es su objetivo?
3. ¿Qué archivos están involucrados?
4. ¿Cómo funciona actualmente esa parte?
5. ¿Cuál es el cambio mínimo necesario?
6. ¿Cómo voy a comprobarlo?
7. ¿Estoy introduciendo una decisión arquitectónica?
8. ¿Necesito aprobación de Pao?
9. ¿Estoy dejando cambios fuera del alcance del ticket?
10. ¿El resultado mantiene el proyecto simple y mantenible?

Si alguna respuesta crítica no está clara, Claude debe detenerse y analizar antes de implementar.
