# ADR-0005 — Política epistemológica del Expediente Maestro

## Estado

Aceptado (TF-0032).

## Contexto

Discovery nuevo (TF-0030/031) escribe `Perfil`/`Requisito`/`Restriccion`/
`Dato` con trazabilidad (`FuenteDirecta`, `confianza`), pero hasta TF-0032
no existía ningún mecanismo para que el Expediente Maestro representara
huecos, ambigüedades o contradicciones como hechos de primera clase — solo
podía "verse limpio" incluso cuando algo importante quedaba sin resolver
(caso auditado `DISC-5eb5f65b`: una contradicción real entre monetización y
datos a recordar no dejaba ningún rastro).

TF-0032 conecta `Gap` y `Contradiccion` (ya definidos en
`src.expediente.modelo`, sin llamador hasta ahora) al flujo real. Este ADR
fija la política que decide qué puede hacer un agente posterior con cada
estado epistémico — sin esta política, "fuente de verdad" es solo una
frase, no una garantía verificable.

## Decisión

Cinco estados epistémicos, ninguno nuevo respecto al modelo ya existente:

| Estado | Cómo se identifica hoy | Puede usarlo un agente posterior como... |
|---|---|---|
| **Confirmado** | `naturaleza=DECLARADO`, `origen=USER` | Requisito duro, directo. |
| **Deducido** | `naturaleza=DEDUCIDO` | Solo si la regla que lo produjo pasó la *prueba de necesidad* (¿puede construirse un escenario coherente, con la misma información ya declarada, donde la conclusión sea falsa? si sí, no es una deducción válida — TF-0032, corrección A2). Un Deducido válido se puede usar, pero el agente debe propagar su procedencia hacia adelante ("esto se infirió de X, no se confirmó") — nunca disfrazarlo de Confirmado en un entregable posterior. |
| **Pendiente** | `Gap` con `estado=DOCUMENTADO_NO_BLOQUEANTE`, o una respuesta "no sé"/"todavía no decidido" | Nunca con un valor por defecto silencioso. El agente bloquea y lo señala, o avanza con una suposición propia explícita y trazable — que a su vez debe regresar al mecanismo de `Gap` de Discovery, no quedarse enterrada en el código o el diseño del agente. |
| **Contradictorio** | `Contradiccion` con `estado=ABIERTA`, o `Gap` con `estado=ABIERTO` | Nunca. Bloquea cualquier trabajo que dependa de ese hecho hasta que una persona lo resuelva (`Contradiccion.resolver()`/`Gap.marcar_estado()`) — ningún agente ni Qwen elige un lado por su cuenta. |
| **No aplica** | Puerta de un dominio condicional respondida "No"/"no aplica" | Tan sólido como un Confirmado, solo que en negativo. |

Esta tabla es una **política única y compartida**: todo agente posterior la
recibe como parte de su contrato (junto con Ticket/Objetivo/Contexto/
Restricciones/Criterios de aceptación, CLAUDE.md §27) — no se reinventa por
agente, para no producir comportamiento inconsistente entre Arquitecto,
Coder, Tester, etc. (que todavía no existen como agentes reales; esta
política queda lista para cuando se implementen).

## Frontera de detección (quién produce cada estado)

- **Código determinista** (`src.discovery.reglas_consecuencia`): compara
  respuestas ya CERRADAS entre sí. Nunca infiere una regla de negocio que
  no sea lógicamente forzosa (A2) — ver la prueba de necesidad arriba.
- **Qwen/Discovery** (`InterpreteFormulario`, tipo de salida `"hallazgo"`):
  cualquier caso que involucre al menos una respuesta de texto libre.
  Nunca produce una `Contradiccion` directamente — solo señala un
  `dominio.etiqueta` como `Gap`; comparar dos afirmaciones ya conocidas
  para producir una `Contradiccion` sigue siendo trabajo determinista.
- **Agentes posteriores:** nunca detectan ni resuelven huecos de
  requisitos por su cuenta — cualquier hallazgo que descubran durante su
  propio trabajo se reporta de vuelta al mecanismo de `Gap`/`Contradiccion`
  de Discovery, nunca se resuelve unilateralmente.

## Qué nunca se inventa

- Un valor para algo nunca declarado.
- Una resolución de contradicción sin que una persona la haya zanjado
  (`Contradiccion.resolver()` exige `resolucion_accion_id`).
- Un `pregunta_id` fuera del catálogo ya existente (A1) — un hallazgo sin
  pregunta catalogada queda registrado tal cual, visible para revisión
  humana del catálogo, nunca con una pregunta inventada.
- Un valor por defecto en un campo opcional no declarado (ej.
  `temporalidad`/`sensibilidad` de un `Dato`) solo para "completar el
  registro".

## Consecuencias

- `Gap`/`Contradiccion` pasan de "definidos en el modelo" a "realmente
  usados" — primer llamador real: `src.discovery.discovery`.
- El estado de una corrida (`EstadoDiscovery`, ver `discovery.py`) es
  independiente de la readiness de cualquier fase posterior — nunca se
  mezclan ambos vocabularios (evita que un agente futuro confunda "sin
  contradicciones" con "listo para construirse").
