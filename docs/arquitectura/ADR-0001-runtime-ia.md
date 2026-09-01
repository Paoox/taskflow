# ADR-0001 — Capa de abstracción / runtime de IA

- **Estado:** aceptado (2026-08-31, TF-0024).
- **Contexto:** TaskFlow evolucionará hacia una plataforma de gestión y ejecución
  de proyectos de software asistidos por IA (tipo Jira/Asana/Trello orientada a
  desarrollo con IA). La visión es **un solo modelo principal + agentes
  especializados + skills + tools + contexto + memoria + orquestación +
  trazabilidad**, con el modelo ejecutado mediante **Ollama** (modelo local),
  intercambiable mediante una capa desacoplada.

## Decisión

`src/ai/` es el **único punto del sistema consciente del proveedor/runtime de
modelo**. Todo lo demás (runner, agentes, y a futuro skills, tools y orquestador)
depende exclusivamente de la superficie pública de `src/ai/`:

```
crear_cliente() -> ClienteIA
ClienteIA.completar(prompt: str, opciones: OpcionesIA) -> RespuestaIA
ErrorIA (+ ErrorConfiguracionIA, ErrorProveedorNoDisponible, ErrorRespuestaIA)
```

- El **contrato** `ClienteIA` / `OpcionesIA` / `RespuestaIA` (TF-0021) queda
  **congelado**. Cualquier evolución (salida estructurada forzada por el
  proveedor, motivo de finalización, tool-calling nativo, streaming) será
  **aditiva y opcional**, decidida por separado, detrás del mismo seam.
- La selección de proveedor es un **registro** `nombre -> Callable[[], ClienteIA]`
  + una **factoría** `crear_cliente()` que lee `TASKFLOW_AI_PROVIDER`. Añadir un
  proveedor = registrar un adaptador; **no** se toca `src/ai/registro.py`.
- La configuración vive en `TASKFLOW_AI_*` (`PROVIDER`, `BASE_URL`, `MODEL`,
  `TIMEOUT`, `API_KEY`, `MAX_RETRIES`), leída por accessors de `src/config.py`.
  El modelo concreto **nunca** se fija en código.
- El **runner recibe un `ClienteIA` inyectado** y no llama a `crear_cliente()`:
  no sabe si detrás hay `ClienteEco`, Ollama, otro proveedor, otro modelo, un
  modelo cuantizado o un modelo con LoRA.
- `ClienteEco` (doble determinista sin red) es el proveedor `"eco"` por defecto y
  el cliente de **toda la suite de pruebas**. Ningún test toca la red.
- El proveedor objetivo de producción es **Ollama** (adaptador `ClienteOllama`
  en TF-0025, con transporte **stdlib `urllib`**, sin `httpx`). Claude/Anthropic
  **no** forman parte de la arquitectura de producción; solo se usan
  externamente durante el desarrollo del propio TaskFlow.

## Modelo conceptual (referencia canónica)

| Concepto | Qué es | Qué NO es | Dónde vive |
|---|---|---|---|
| **Modelo** | los pesos que razonan (id + parámetros de muestreo) | código; un proveedor | `OpcionesIA.modelo` + `TASKFLOW_AI_MODEL` |
| **Proveedor / Runtime** | el servicio que aloja y ejecuta un modelo y expone una API (servidor Ollama, endpoint OpenAI-compatible, stub) | un razonador; lógica de negocio | `src/ai/` — una implementación de `ClienteIA` por proveedor + registro + factoría |
| **Prompt** | texto plano (instrucciones + contexto) enviado al modelo; sin lógica | código; una skill; memoria | `src/ai/prompts/*.md` + composición determinista |
| **Contexto** | el subconjunto **relevante** de info del proyecto/ticket inyectado en *esta* ejecución; se re-ensambla cada vez | toda la memoria; algo persistente; algo que elige el LLM | ensamblador determinista (futuro) |
| **Memoria** | conocimiento **persistente** del proyecto (requisitos, arquitectura, decisiones/ADR, convenciones, documentación, historial de ejecuciones, aprobaciones) | algo que se envía entero al modelo; un vector store (por ahora) | tablas (`documentos`, `decisiones`, `acciones`) + entidades |
| **Tool** | capacidad **ejecutable determinista** (leer archivo, `pytest`, `git diff`, consultar BD); entrada tipada → `ResultadoTool`; declara permiso y efectos | razona; llama al LLM; decide qué hacer | `src/tools/` (futuro) |
| **Skill** | la **definición de cómo resolver una tarea** usando el modelo + un conjunto acotado de Tools (qué prompt, qué Tools, qué reglas, qué forma de salida); **lógica + contexto**, no un modelo | un agente; una Tool; "su propio modelo" | `src/skills/` (futuro); `Documentador` de TF-0023 es la protoskill |
| **Agente** | **lógica especializada + contexto + un conjunto de Skills** para un rol (analista, arquitecto, tester…); usa **el mismo único modelo**; cambia el prompt de rol, las skills y las reglas | un modelo aparte; un microservicio; una Skill suelta | `src/agentes/` |
| **Orquestador** | el **coordinador determinista** del flujo global (proyecto → fase → agente → skill → tool → validación → siguiente); aplica límites de bucle, gates de aprobación, persistencia y estados terminales | razona el contenido (lo delega al modelo dentro de cada fase); ejecuta Tools directamente | `src/orquestador/` (futuro) |

**Regla rectora:** *determinista → Tool/código; razonamiento → LLM.* Un solo
modelo; la especialización es prompt + tools + código, **no pesos distintos**.
Si en el futuro se incorporan LoRAs, entran sobre esta arquitectura sin
rediseñarla (otro valor de `TASKFLOW_AI_MODEL`).

## Consecuencias

- Cambiar de runtime/modelo = variables de entorno + registrar un adaptador.
  Runner, agentes y contratos de negocio no se tocan.
- El bucle multi-turno (skill ↔ tools) vivirá en el (futuro) ejecutor de skill,
  no en `ClienteIA`: el contrato *single-shot* texto→texto es suficiente porque
  la conversación se re-envía como prompt; el ejecutor acota turnos y contexto.
- Ollama en Docker: la imagen sigue neutral; Ollama corre como proceso/servicio
  aparte (host o `docker-compose` — decisión de TF-0025, dispararía `CLAUDE.md`
  §31). Ollama **nunca** en CI.
- La verificación en vivo contra un modelo real es siempre **manual** y se
  reporta como tal (`CLAUDE.md` §20 / §33).

## Alternativas descartadas

- **Diseñar alrededor de un SDK de proveedor SaaS (Claude/OpenAI):** acopla
  TaskFlow a un proveedor y a su árbol de dependencias; contradice la visión.
- **Ampliar `RespuestaIA`/`OpcionesIA` "por si acaso":** viola `CLAUDE.md` §30 y
  "no romper contratos sin justificación demostrable".
- **`httpx` para el adaptador Ollama:** dependencia + transitivas + matriz
  3.8/3.12; innecesario para un `POST` JSON a `localhost` (stdlib `urllib` basta).
- **Un modelo distinto por capacidad/rol:** multiplica coste y superficie;
  contradice "un solo modelo + capacidades especializadas por código".
- **Base vectorial desde el inicio:** el corpus es pequeño y estructuralmente
  indexable; se revisará solo si crece.
