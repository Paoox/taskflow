"""TF-0029 — Tools: capacidades ejecutables deterministas, de solo lectura.

Una Tool (`ADR-0001`) es código puro que adquiere evidencia real (leer un
archivo, listar un directorio) — nunca razona, nunca decide, nunca llama al
modelo. Declara una entrada tipada y devuelve siempre un `ResultadoTool`
(nunca lanza excepciones por errores esperables: archivo ausente, fuera de
sandbox, binario, etc. son datos, no excepciones).

Este paquete es intencionalmente aislado: no importa Flask, `src.app`,
`src.database`, `src.repositorios`, `src.agentes`, `src.ai` ni
`src.orquestador`. El único consumidor previsto en TF-0029 es
`src.orquestador.evidencia`, que sí puede importar `src.tools`.

Alcance de TF-0029: solo lectura de filesystem (`archivos.py`). Sin shell,
sin red, sin escritura, sin catálogo/registro dinámico, sin que el modelo
decida qué Tool invocar (eso sigue siendo código determinista).
"""
