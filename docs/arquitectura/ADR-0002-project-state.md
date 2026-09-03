# ADR-0002 — PROJECT_STATE / PROJECT_HEALTH

- **Estado:** aceptado (2026-09-02, TF-0026).
- **Contexto:** el Orquestador (primer agente del flujo de coordinación,
  ADR-0001) necesita una fuente de verdad estructurada por proyecto que
  sobreviva a la conversación original con el usuario. Esa fuente de verdad es
  `PROJECT_STATE`; `PROJECT_HEALTH` es su lectura determinista de progreso.

## Decisión

`src/proyectos/` es el único paquete consciente de PROJECT_STATE. Nada de él
importa Flask, `src.agentes`, `src.ai` ni red; solo
`src/repositorios/expedientes.py` conoce `src.database`.

### Frontera PROJECT_STATE vs `*_STATE`

`ExpedienteProyecto` (PROJECT_STATE) es memoria de **coordinación**, no el
trabajo detallado de ninguna disciplina:

```text
PROJECT_STATE  = identidad + lo mínimo para enrutar
                 (cobertura, completitud, avance, blockers, next_agent)

ARCHITECTURE_STATE, UX_STATE, ANALYSIS_STATE, IMPLEMENTATION_STATE,
TEST_STATE, SECURITY_STATE, DOCUMENTATION_STATE
               = el trabajo real de cada disciplina
               = NO viven dentro de ExpedienteProyecto
               = fuera de alcance de TF-0026
```

`ResumenDisciplina.referencia_estado` es el puntero (futuro) al `*_STATE`
especializado; en TF-0026 queda siempre en `None` porque ningún `*_STATE`
existe todavía. `ResumenDisciplina.datos` solo admite las claves de
`campos_esperados()` — un checklist de coordinación deliberadamente pequeño
(3-6 campos por dimensión), no una bolsa abierta.

### `Mockup`: contrato independiente, no colgado de `ResumenDisciplina`

`Mockup` (`src/proyectos/estado.py`) fija la forma de los metadatos de un
artefacto de UX versionable, pero **no** es un campo de `ResumenDisciplina` ni
de `ExpedienteProyecto`. Decisión explícita del checkpoint de revisión de
TF-0026: PROJECT_STATE se mantiene estrictamente acotado al checklist de
coordinación (`campos_esperados()`); no se agregan campos nuevos durante la
implementación sin decisión explícita, aunque el concepto ya esté aprobado
arquitectónicamente. Dónde vive un `Mockup` en la práctica (¿tabla propia?,
¿colgado de un futuro `UX_STATE`?) y cómo se versiona el archivo físico
(`docs/proyectos/<codigo>/mockups/`, del diseño original) quedan para un
ticket posterior de UX/estado especializado — TF-0026 no implementa
persistencia de mockups.

### Checklist versionado (`src/proyectos/checklist.py`)

`_CHECKLISTS` es un diccionario `version -> checklist`. Una versión publicada
(`"1.0"`) queda **congelada**: evolucionar el checklist es agregar una clave
nueva (`"1.1"`), nunca editar `"1.0"`. `ExpedienteProyecto.checklist_version`
se fija en `RepositorioExpedientes.crear()` y `calcular_salud()` siempre
resuelve contra esa versión, nunca contra `CHECKLIST_VERSION_ACTUAL`
directamente. Así, publicar un checklist nuevo no cambia silenciosamente el
porcentaje histórico de un expediente ya creado. Migrar un expediente entre
versiones queda fuera de TF-0026; el seam es esta estructura versionada.

`campos_esperados(version)` **nunca devuelve la referencia interna** a
`_CHECKLISTS[version]`: construye y devuelve un `dict` nuevo
(`{dimension: tuple(campos) for ...}`) en cada llamada. Es la única forma de
que "congelado" sea real — sin esto, cualquier consumidor que hiciera
`campos_esperados("1.0")["_raiz"] = (...)` (o agregara una clave) mutaría el
estado interno del módulo para toda ejecución posterior del proceso.

### Cobertura vs. completitud vs. avance (`src/proyectos/salud.py`)

Separar "cuánto se investigó" de "qué tan bien resuelto está lo investigado"
evita que un campo nunca tocado produzca un 100% engañoso:

```text
cobertura   = campos investigados / campos esperados
completitud = calidad ponderada, solo sobre lo investigado y aplicable
avance      = cobertura * completitud
```

Pesos de completitud (corrección explícita de `not_found`, que **no** es
"resuelto" — "no encontré el logo" no implica "no tiene logo"):

| Categoría | Estados | Peso |
|---|---|---|
| Resuelto | `confirmed`, `discovered` | 1.0 |
| Parcial | `inferred`, `incomplete` | 0.5 |
| Pendiente | `unknown`, `pending_decision` | 0.0 |
| Pendiente + advertencia | `not_found` | 0.0 (+ warning) |
| Excluido | `not_applicable` | fuera del cálculo de completitud |

`estado_general` pondera el avance de la raíz (peso fijo 1.0, siempre
aplicable) y de cada disciplina según su `aplicabilidad`:
`required=1.0`, `conditional=PESO_APLICABILIDAD_CONDITIONAL(0.5)`,
`unknown=1.0` (conservador: no premia lo no resuelto excluyéndolo),
`not_applicable` excluida por completo (ni numerador ni denominador).

### Transiciones restringidas

`(inferred→confirmed)`, `(not_found→not_applicable)`, `(unknown→not_applicable)`
solo son válidas si `origen == user`: nunca ocurren automáticamente por un
agente/modelo (`src.proyectos.estado.transicion_valida` +
`TRANSICIONES_RESTRINGIDAS`). Cualquier otra transición —incluida
`not_found → confirmed`, que un descubrimiento posterior sí puede resolver
sin pasar por una persona— es válida sin restricción de origen.
`RepositorioExpedientes.guardar()` las valida contra el registro ya
persistido, campo por campo (raíz y cada disciplina), **antes** de escribir
nada: ante una transición inválida levanta `TransicionEstadoInvalida` y no
toca la fila. Las 3 transiciones están probadas tanto de forma aislada
(`transicion_valida()`) como en integración real contra SQLite vía
`guardar()`.

### Workflow oficial (`src/proyectos/workflow.py`)

Pieza independiente y reutilizable — `salud.py` no reimplementa el orden de
etapas, delega en `determinar_siguiente_agente()` con una sola llamada:

```text
ORQUESTADOR → ARQUITECTO → UX_UI → ANALISTA → DEVELOPER → TESTER →
SECURITY → DOCUMENTACION → CIERRE
```

Una etapa está "lista" cuando su disciplina dependiente tiene
`avance >= UMBRAL_AVANCE_LISTO (0.8)` y no tiene blockers propios — **excepto**
si la disciplina es `not_applicable`, en cuyo caso se considera lista
**independientemente de su avance** (una disciplina correctamente excluida no
debe bloquear el recorrido). `unknown` nunca se considera lista.

`workflow.py` no importa `salud.py` a nivel de módulo (evita el ciclo, ya que
`salud.py` importa `workflow.py`); los tipos de `salud.py` usados solo para
anotaciones se importan bajo `TYPE_CHECKING`. `UMBRAL_AVANCE_LISTO` y
`PESO_APLICABILIDAD_CONDITIONAL` viven en `src/proyectos/constantes.py`,
compartidas por ambos módulos sin crear el ciclo.

### Vocabulario de enums

`EstadoDato`, `OrigenDato`, `AplicabilidadDisciplina`, `Readiness` y
`EstadoAprobacionMockup` usan valores literales en **inglés**, sin traducir.
`NivelConfianza` (`ALTA`/`MEDIA`/`BAJA`) es la única excepción: se mantiene en
español, consistente con el resto del repositorio (`EN_CURSO`, `COMPLETADA`,
`FALLIDA`).

### Persistencia

Tabla `expedientes` (patrón idéntico a `acciones`, TF-0022): relacional para
lo que se filtra/ordena (`readiness`, `estado_general`, timestamps) + JSON en
`contenido`/`salud` para el árbol anidado. Sin FK hacia `tareas`/`proyectos`
(dominios distintos). `codigo` (`"PROY-001"`, …) se deriva del `id`
autoincremental (`_codigo_desde_id`), único y permanente, nunca generado a
mano ni almacenado como columna aparte.

`RepositorioExpedientes.crear()` ejecuta `INSERT` (fila mínima) y luego
`UPDATE` (con el `contenido` completo, ya con el `codigo` asignado) sobre la
**misma conexión, sin `commit()` intermedio**: ambas sentencias comparten la
transacción implícita de `sqlite3` y se confirman juntas. Verificado
empíricamente que un fallo entre ambas (excepción o crash antes del
`commit()` final) no deja ninguna fila persistida — ni siquiera el `INSERT`
inicial —, así que no hay riesgo de un expediente a medio construir.

`guardar()` y `guardar_salud()` lanzan `ExpedienteNoEncontrado`
(`ErrorProyectos` + `ValueError`) si el `codigo` no corresponde a ningún
expediente existente, **antes** de intentar cualquier `UPDATE`. Antes de esta
decisión, ambos métodos eran no-ops silenciosos (`UPDATE ... WHERE id = ?`
sobre 0 filas, sin señal de error ni de retorno) — inconsistente con
`RepositorioAcciones.marcar()`, que sí comunica si el `id` existía. Se decidió
fail-fast (excepción) en vez de un `bool` de retorno porque, a diferencia de
`marcar()`, no existe un caso de negocio legítimo para llamar a
`guardar()`/`guardar_salud()` con un `codigo` que no salió de
`crear()`/`obtener()` — es casi siempre un error del llamador.

## Consecuencias

- El futuro Orquestador consume `ExpedienteProyecto` +
  `calcular_salud()` + `determinar_siguiente_agente()` sin reimplementar
  ninguna de las tres reglas.
- Ningún `*_STATE` especializado existe todavía: cuando se implemente el
  primero (probablemente `ARCHITECTURE_STATE`), su ticket deberá decidir su
  propio esquema de persistencia y poblar `referencia_estado`.
- Migraciones de checklist (mover un expediente de `"1.0"` a una futura
  `"1.1"`) quedan como trabajo explícito, no implementado.
- El futuro Orquestador debe capturar `ExpedienteNoEncontrado` (o dejarla
  subir) al llamar `guardar()`/`guardar_salud()`: un `codigo` inválido ya no
  se descubre tarde por un `SaludProyecto` que nunca se actualizó.

## Alternativas descartadas

- **`ResumenDisciplina.datos` como bolsa abierta sin checklist:** produciría
  un PROJECT_STATE agnóstico pero sin forma de calcular cobertura real
  (¿cobertura de qué, si no hay un total?).
- **Cobertura/completitud como un solo número:** oculta exactamente el caso
  que motivó la corrección ("35% investigado, de eso 90% resuelto" ≠ "31.5%
  de avance real" si se colapsan en un promedio simple).
- **`next_agent` calculado dentro de `calcular_salud()`:** acoplaría
  PROJECT_HEALTH a un orden de etapas que puede evolucionar por separado del
  cálculo numérico.
- **Un solo peso "resuelto" también para `not_found`:** confunde "no lo
  encontré" con "no existe"; corregido explícitamente en este ticket.
- **`guardar()`/`guardar_salud()` devolviendo `bool` (como `RepositorioAcciones.
  marcar()`) en vez de lanzar `ExpedienteNoEncontrado`:** descartado porque,
  a diferencia de `marcar()`, no hay un caso de negocio real donde llamar con
  un `codigo` inexistente sea válido — un `bool` ignorable habría permitido
  que el error siguiera pasando desapercibido.
