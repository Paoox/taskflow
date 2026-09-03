# ADR-0003 — Orquestador (descubrimiento raíz)

- **Estado:** aceptado (2026-09-02, TF-0027).
- **Contexto:** ADR-0001 ya reservaba `src/orquestador/` como "el coordinador
  determinista del flujo global"; ADR-0002/TF-0026 entregaron la fuente de
  verdad (`ExpedienteProyecto`) y su lectura de progreso (`SaludProyecto` +
  `workflow`). TF-0027 construye el primer coordinador real sobre esa base:
  la dimensión que `workflow.DEPENDENCIA_ETAPA["ORQUESTADOR"]` ya le asigna
  — el descubrimiento raíz (`ExpedienteProyecto.descubrimiento`).

## Decisión

`src/orquestador/` consume `src.proyectos.*` y `src.agentes.*`/`src.ai.*` por
sus **APIs públicas**, sin reimplementar ninguna regla de TF-0026. Es la capa
de integración: a diferencia de `src/proyectos/`, que se mantiene aislado de
agentes/IA, `src/orquestador/` sí los conoce — es exactamente su función.

### Alcance: solo el descubrimiento raíz

El Orquestador de TF-0027 gestiona **únicamente** `ExpedienteProyecto.
descubrimiento` — no las `disciplinas`. Es la única responsabilidad que el
propio `workflow.py` (TF-0026) ya le asignaba a la etapa `"ORQUESTADOR"`
(`DEPENDENCIA_ETAPA["ORQUESTADOR"] == "_raiz"`). Un hallazgo propuesto para
un campo de `disciplinas` se descarta (no está en `campos_esperados()["_raiz"]`)
— esos datos pertenecen a agentes especializados (Arquitecto, UX, …) que no
existen todavía.

### `ejecutar_orquestador()`: un ciclo, no un bucle

Mismo patrón que `ejecutar_agente()` (TF-0023): una llamada = una decisión +
sus efectos. Repetir el ciclo (sondear el expediente periódicamente, o
llamarlo de nuevo tras una respuesta humana) es responsabilidad del
llamador — no hay ningún `while` ni scheduler dentro de `src/orquestador/`.

### Inyección de dependencias (cliente + agente)

`ejecutar_orquestador(codigo, cliente: ClienteIA, agente_descubrimiento:
DefinicionAgente, ...)` recibe ambos inyectados, igual que `ejecutar_agente()`
ya hacía. El Orquestador no importa `src.ai.ollama`, no llama a
`crear_cliente()` y no importa ningún agente concreto — la selección de
proveedor/modelo/agente es responsabilidad exclusiva del llamador (punto 15
del checkpoint). Verificado con un test de aislamiento (`TestSinAcoplamientoAFlask`
en `tests/test_orquestador.py`).

### Sin agente de descubrimiento real todavía

TF-0027 define el **contrato** que debe cumplir `SalidaAgente.resultado` de
cualquier agente de descubrimiento (`{"hallazgos": [...]}`, ver
`src/orquestador/fusion.py`) y la lógica de fusión contra ese contrato, pero
**no implementa ningún agente concreto** (prompt real, inspección de
filesystem/git). Eso —junto con las Tools de inspección que ADR-0001 ya
marca como "futuro"— queda para **TF-0028**. Los tests usan un
`DefinicionAgente`/`ClienteIA` de prueba sin red.

### Matriz de decisión (checkpoint revisado, sin ambigüedad)

```
1. ¿hay pending_decision en la raíz?                -> BLOQUEADO
2. ¿salud.next_agent != "ORQUESTADOR"?               -> HANDOFF
3. ¿ya existe una investigación previa terminal
   (COMPLETADA o FALLIDA) para este codigo?
     NO  -> INVESTIGAR
     SÍ  -> PREGUNTAR
```

Es **total** por el invariante de `preguntas_pendientes()`: si el avance de
la raíz es menor a 1.0 y no hay `pending_decision`, esa función nunca
devuelve una lista vacía (cubre los 5 estados de `EstadoDato` con peso `<1.0`
en `PESO_ESTADO_COMPLETITUD` más el caso "ausente"; el sexto, `pending_decision`,
se resuelve en el paso 1). `HANDOFF` se decide comparando únicamente
`next_agent` (no `readiness`): `readiness` es una métrica agregada de *todo*
el proyecto y puede estar `BLOCKED`/`INCOMPLETE` por una disciplina que no le
compete al Orquestador (p. ej. `arquitectura`); `next_agent` ya encapsula
exactamente "¿mi propia etapa está superada?" como su primer chequeo interno
en `workflow.determinar_siguiente_agente()`.

### `preguntas_pendientes()`: 5 motivos, sin estado propio

Cubre `ausente` (`nunca_investigado`), `unknown` (`sigue_desconocido`),
`not_found` (`confirmar_no_encontrado`), `inferred` (`confirmar_inferencia`)
e `incomplete` (`completar_informacion`). No persiste nada aparte: se deriva
en cada llamada a partir de `ExpedienteProyecto` + `campos_esperados()` — sin
una fuente de verdad paralela que pueda desincronizarse. `pending_decision`
no genera pregunta (genera `BLOQUEADO`: requiere una decisión explícita, no
una respuesta factual).

`confirmar_inferencia` es la vía por la que `inferred` puede llegar a
`confirmed`: activa exactamente el mecanismo que TF-0026 ya construyó
(`inferred → confirmed` exige `origen=USER`) en vez de inventar uno nuevo.

### Fusión de hallazgos: pre-validación antes de persistir

`RepositorioExpedientes.guardar()` (TF-0026) valida **todo el expediente
antes de escribir**: una sola transición inválida en un lote de hallazgos
abortaría el lote entero. `fusionar_hallazgos()` evita esto pre-validando
cada hallazgo (checklist raíz vigente, saneo de `origen` — un agente nunca
puede reclamar `origen=user`, se reescribe a `AGENT` — y
`transicion_valida()`) **antes** de mutar una copia en memoria del
expediente; solo el subconjunto válido llega a `guardar()`. El resto se
reporta en `problemas`, nunca aborta el lote. Como red de seguridad ante una
carrera real (BL-19: el expediente pudo cambiar en la base entre el
`obtener()` inicial del ciclo y este `guardar()`), `ejecutar_orquestador()`
sigue capturando `TransicionEstadoInvalida` alrededor de `guardar()` — no
debería dispararse en un escenario sin concurrencia, y los tests la fuerzan
deliberadamente (inyectando un repositorio que falla) para no dejarla como
código sin ejercitar.

### Trazabilidad con `RepositorioAcciones` (API real verificada)

`RepositorioAcciones.listar(ticket=...)` (única firma real: filtra solo por
`ticket`, sin parámetro de `tipo`) devuelve todas las acciones de ese
`ticket`; el filtrado por `tipo`/`estado` se hace en Python. El Orquestador
registra su propia acción **solo cuando decide `INVESTIGAR`**, con un
`tipo` (`TIPO_ACCION_ORQUESTAR = "orquestar_descubrimiento"`) y `actor`
(`"orquestador"`) **propios**, independientes del `tipo_accion`/`nombre` del
agente inyectado — así "¿ya investigamos antes?" no depende de qué agente
concreto se use. Cuenta `COMPLETADA` y `FALLIDA` como intento realizado;
`EN_CURSO` no cuenta (pudo no haber terminado, p. ej. por un crash). Las
demás acciones (`HANDOFF`/`PREGUNTAR`/`BLOQUEADO`) no registran una acción
propia: son decisiones puras sin efecto más allá de persistir el snapshot de
`SaludProyecto` (ya visible en `expedientes.salud`/`readiness`).

### `responder_pregunta()`: el único origen=USER legítimo

Función separada, invocada por quien recoja la respuesta de una persona.
Construye el `Dato` con `origen=OrigenDato.USER` explícitamente — es el único
punto del sistema (fuera de una prueba deliberada) donde ese origen se
produce. Acepta cualquier `EstadoDato` (por defecto `CONFIRMED`): "no sé" se
registra como `UNKNOWN`, nunca como `NOT_APPLICABLE`.

## Consecuencias

- TF-0028 (futuro) implementará el primer agente de descubrimiento real
  (prompt + eventualmente Tools de inspección) satisfaciendo el contrato de
  `fusion.py` ya fijado aquí, sin tocar `src/orquestador/`.
- Cuando existan agentes especializados (Arquitecto, UX, …), su integración
  seguirá el mismo patrón de inyección de dependencias, no uno nuevo.
- `src/orquestador/` es el primer paquete del repo que integra
  deliberadamente `src.proyectos` + `src.agentes` + `src.ai` + `src.repositorios`
  — es la capa de integración prevista por ADR-0001, no una capa aislada.

## Alternativas descartadas

- **Gatear `HANDOFF` con `salud.readiness`** en vez de con `salud.next_agent`:
  descartado — dejaría al Orquestador esperando indefinidamente algo que no
  le compete (una disciplina bloqueada que no es la raíz).
- **Registrar una acción del Orquestador en cada ciclo** (incluidos
  `HANDOFF`/`PREGUNTAR`/`BLOQUEADO`): descartado — usar el mismo `tipo` para
  todas rompería la detección de "¿ya investigamos?" (cualquier ciclo, no
  solo uno de investigación, la volvería `True`); usar `tipo`s distintos por
  acción no aporta trazabilidad que `expedientes.salud` no dé ya, a cambio de
  más filas y más superficie de mantenimiento.
- **`inferred`/`incomplete` resueltos con más reintentos automáticos de
  investigación** en vez de una pregunta: descartado para `inferred`
  (`inferred → confirmed` está restringida a `origen=user` por diseño de
  TF-0026: preguntar es la única vía legítima); para `incomplete` se prefirió
  la misma vía por simplicidad (evita inventar una política de reintentos
  "hasta cuántas veces" sin necesidad demostrada).
