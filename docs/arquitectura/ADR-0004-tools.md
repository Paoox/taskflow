# ADR-0004 — Tools de adquisición de evidencia (filesystem, solo lectura)

- **Estado:** aceptado (2026-09-02, TF-0029).
- **Contexto:** ADR-0001 ya definía "Tool" (`src/tools/`, marcada "futuro")
  como *"capacidad ejecutable determinista... entrada tipada → `ResultadoTool`;
  declara permiso y efectos"*. TF-0028 dejó explícitamente pendiente que
  `Descubridor` no tenía ninguna evidencia real que investigar —solo la lista
  de preguntas pendientes que le arma `ejecutar_orquestador()`—, y marcó esa
  limitación como intencional hasta que existieran Tools. TF-0029 activa esa
  pieza.

## Decisión

### Alcance: solo lectura de filesystem, determinista, sandboxed

Dos Tools concretas (`src/tools/archivos.py`), ambas sin efectos secundarios:

- `LeerArchivoTool` — lee un archivo de texto dentro de una `raiz_permitida`.
- `ListarArchivosTool` — lista el árbol de un directorio, con profundidad
  limitada, ignorando `.git`/`__pycache__`/`venv`/`.venv`/`node_modules`.

Ninguna Tool ejecuta shell/subprocess, red, ni escribe nada. Ninguna
excepción esperable escapa de `ejecutar()`: toda condición de error (fuera
de sandbox, ausente, binario, excluido) se devuelve como
`ResultadoTool(exito=False, error=...)`, nunca como excepción — mismo
principio de tolerancia que ya aplican `fusion.py` (TF-0027) y `runner.py`.

### `raiz_permitida` configurable, no el propio repo de Taskflow

Cada Tool recibe su `raiz_permitida` en el constructor. Taskflow está
pensado para orquestar proyectos de terceros, no solo auto-documentarse, así
que el sandbox nunca queda hardcodeado al propio repositorio de Taskflow.

### Sandbox: `Path.resolve()` + `relative_to()`, cubre symlinks

```python
def _resolver_dentro_de_raiz(raiz, ruta_relativa):
    if PurePath(ruta_relativa).is_absolute():
        return None
    candidato = (raiz / ruta_relativa).resolve()
    try:
        candidato.relative_to(raiz)
    except ValueError:
        return None
    return candidato
```

`Path.resolve()` sigue symlinks; comparar los dos caminos ya resueltos cubre
en una sola verificación: rutas absolutas (rechazadas antes de unir), `../`
(el `resolve()` las colapsa y `relative_to()` detecta la fuga), y symlinks
que apunten fuera del sandbox (se resuelven a su destino real antes de
comparar). Es más robusto que el regex de nombre simple de
`src/ai/prompts/__init__.py` (`cargar_prompt`) porque aquí hace falta
sandboxear una ruta anidada, no solo validar un nombre de archivo plano —
pero es el mismo principio de fondo: nunca confiar en la ruta tal cual llega.

### Blacklist explícita de archivos sensibles

`LeerArchivoTool` rechaza por nombre (ya resuelto, tras symlinks)
`.env`/`.env.*`, `id_rsa`/`id_dsa`/`id_ecdsa`/`id_ed25519`, y cualquier
`*.pem`/`*.key`/`*.pfx`/`*.p12`, **sin importar si son legibles** —
protección explícita contra que la primera Tool de lectura real termine
filtrando un secreto local hacia el prompt de un LLM (`CLAUDE.md` §21/§25.3).

### Solo texto, truncado determinista

Un archivo que no decodifica como UTF-8 se rechaza (`"archivo no es texto
plano"`) en vez de volcar bytes crudos al contexto de un agente. Una lectura
que exceda `LIMITE_CARACTERES_LECTURA` (8000, constante fija) se trunca —
nunca es un error, es evidencia parcial (`truncado=True`).

### Sin catálogo/registro dinámico

Con 2 Tools concretas y un único consumidor (`src.orquestador.evidencia`,
que las importa directamente por nombre), un registro tipo
`src.ai.registro` anticiparía una necesidad que no existe todavía (§30). Se
revisará cuando exista una tercera Tool o un futuro ejecutor de skill que
necesite elegir Tools dinámicamente.

### Sin tool-calling del modelo: el recolector decide, no el LLM

`src/orquestador/evidencia.py` fija una lista **cerrada y determinista** de
nombres de archivo conocidos (`README.md`, `package.json`, `pyproject.toml`,
`requirements.txt`, `Dockerfile`, `CLAUDE.md`, `go.mod`, `Cargo.toml`,
`composer.json`) e intenta leer los que existan, más un listado superficial
de la raíz. El **código** decide qué mirar; el modelo nunca elige qué Tool
invocar — coherente con "determinista → Tool/código; razonamiento → LLM"
(ADR-0001). Una ausencia esperable (el archivo no existe) no se reporta como
problema; un truncado sí se reporta (en `EvidenciaRecolectada.problemas`).

### Integración con `ejecutar_orquestador()`: parámetro opcional, aditivo

`recolector_evidencia: Optional[RecolectorEvidencia] = None` — única
modificación a un archivo existente en TF-0029. Con `None` (default), el
comportamiento es **idéntico byte a byte** al de TF-0027 (verificado: los 41
tests de `test_orquestador.py` no se tocaron y siguen pasando). Si se
inyecta, se invoca justo antes de construir `EntradaAgente`, enriqueciendo
`contexto`/`archivos_relevantes`; sus `problemas` se agregan a los de
`ResultadoOrquestador` (mismo campo ya existente, sin canal nuevo).

`ejecutar_orquestador()` sigue sin "ejecutar Tools directamente" en el
sentido de ADR-0001: nunca importa `src.tools`, solo invoca la función que le
inyectan — exactamente igual a como ya invoca `cliente.completar()` sin
saber qué proveedor hay detrás. Quien sí conoce `src.tools` es
`src.orquestador.evidencia` (la fábrica del recolector), no
`orquestador.py`.

### Trazabilidad

Cuando `recolector_evidencia` está presente, se registra **una acción
adicional** (`tipo="recolectar_evidencia"`, `actor="orquestador"`) vía
`RepositorioAcciones` — mismo patrón exacto que `TIPO_ACCION_ORQUESTAR`
(TF-0027), sin ninguna API nueva de persistencia.

### `Descubridor` no cambia

Cero cambios a `src/agentes/descubridor.py` ni a su prompt. Desde su
perspectiva, evidencia real y "solo preguntas" son indistintamente texto en
`entrada.contexto`/`archivos_relevantes` — confirma retroactivamente que el
contrato de TF-0028 ya estaba listo para este ticket.

## Consecuencias

- Un futuro `src/skills/` (ejecutor de skill con bucle multi-turno, donde el
  LLM sí decida qué Tool invocar) podrá reutilizar `src/tools/archivos.py`
  sin cambios: el contrato de Tool (entrada tipada → `ResultadoTool`) no
  asume quién decide invocarla.
- Nuevas Tools (git log/diff, ejecutar pytest, consultar BD) son el momento
  natural de introducir el catálogo/registro que hoy se descarta.
- El `raiz_permitida` configurable es lo que permitirá, en un ticket futuro,
  apuntar Taskflow a un proyecto de terceros en vez de a sí mismo.

## Alternativas descartadas

- **Regex de nombre simple (como `cargar_prompt`) en vez de
  `resolve()`+`relative_to()`:** insuficiente para una ruta anidada
  (`sub/../../fuera.txt`) y no cubre symlinks.
- **Lista blanca de extensiones en vez de blacklist de nombres sensibles:**
  más restrictiva pero más frágil de mantener (haría falta enumerar cada
  extensión de texto legítima); la blacklist ataca directamente el riesgo
  real (secretos conocidos) sin bloquear archivos de texto legítimos con
  extensiones no anticipadas.
- **Registro dinámico de Tools desde ya:** descartado por prematuro (§30);
  ver sección de decisión.
- **Que el LLM decida qué archivo pedir (tool-calling real):** exigiría
  rediseñar `DefinicionAgente`/`ejecutar_agente` (bucle multi-turno) —
  explícitamente fuera de alcance de TF-0029.
