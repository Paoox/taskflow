# Prompts de agentes

Ubicación separada de los prompts, aislada de la lógica de negocio
(`CLAUDE.md` §26).

## Convención

- **Un archivo por agente**, nombrado `<nombre>.md` (por ejemplo
  `documentador.md`, `arquitecto.md`).
- El nombre debe ser un identificador simple: solo `[a-z0-9_-]+`. No se admiten
  separadores de ruta ni `..`.
- **Texto plano / Markdown, sin lógica.** Nada de plantillas con código,
  condicionales ni sustituciones dinámicas: eso vive en Python.
- El contenido es el mensaje de sistema / instrucciones del agente.

## Uso

```python
from src.ai.prompts import cargar_prompt

texto = cargar_prompt("documentador")   # lee src/ai/prompts/documentador.md
```

`cargar_prompt` lanza `PromptNoEncontrado` si el nombre es inválido o el archivo
no existe.

## Estado (TF-0021)

Solo existe `ejemplo.md`, usado por las pruebas de `cargar_prompt`. Los prompts
de agentes reales (Documentador, Arquitecto, …) se añadirán en sus propios
tickets.
