"""TF-0022 — Repositorios de acceso a datos de infraestructura.

Por ahora solo `RepositorioAcciones` (registro persistente de ejecuciones para la
trazabilidad de `CLAUDE.md` §28). Patrón "una conexión por operación" sobre
`src.database.get_connection()`; sin ORM ni capa de sesión.
"""
