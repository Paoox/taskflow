"""TF-0025 — Adaptador `ClienteOllama`: proveedor real de IA.

Implementa `ClienteIA` (TF-0021) sobre un servidor Ollama local, hablando
``POST {base_url}/api/generate`` con ``stream: false``. Transporte: stdlib
`urllib.request` (decisión DA-2 de TF-0024); sin `httpx`, sin dependencias
nuevas.

Este módulo es el único punto de TaskFlow que sabe qué es Ollama y cómo se le
habla. Registra el proveedor ``"ollama"`` en `src.ai.registro` **al importarse**
(no al importar `src.ai`): así el import base de `src.ai` sigue sin tocar red,
sockets ni `urllib` (TF-0024, `TestSinAcoplamiento`). Para usar este proveedor,
algo debe importar explícitamente `src.ai.ollama` antes de llamar a
`crear_cliente()`.

`ClienteOllama` no importa `src.config` (DA-12): recibe `base_url`, `modelo`,
`timeout` y `reintentos` como parámetros explícitos de `__init__`; el `lambda`
registrado al final de este archivo es quien lee `TASKFLOW_AI_*`.
"""
from __future__ import annotations

import json
import urllib.error
import urllib.request

from src import config
from src.ai.cliente import OpcionesIA, RespuestaIA
from src.ai.errores import (
    ErrorConfiguracionIA,
    ErrorProveedorNoDisponible,
    ErrorRespuestaIA,
)
from src.ai.registro import registrar

__all__ = ["ClienteOllama"]


class ClienteOllama:
    """`ClienteIA` real sobre un servidor Ollama local.

    El modelo y la URL base son fijos por instancia (configuración, DA-1):
    `opciones.modelo` y `opciones.timeout` no se usan (igual que `ClienteEco`
    los ignora); solo `opciones.max_tokens` y `opciones.temperatura` viajan en
    cada llamada. `opciones.timeout`, al ser un valor genérico del contrato
    congelado sin significado propio para este proveedor, se descarta a favor
    del timeout de configuración (`TASKFLOW_AI_TIMEOUT`).
    """

    def __init__(self, base_url: str, modelo: str, timeout: float,
                 reintentos: int = 0):
        base_url = (base_url or "").strip()
        modelo = (modelo or "").strip()
        if not base_url:
            raise ErrorConfiguracionIA(
                "proveedor 'ollama' requiere TASKFLOW_AI_BASE_URL"
            )
        if not modelo:
            raise ErrorConfiguracionIA(
                "proveedor 'ollama' requiere TASKFLOW_AI_MODEL"
            )
        self._base_url = base_url.rstrip("/")
        self._modelo = modelo
        self._timeout = timeout
        self._reintentos = max(0, int(reintentos))

    def completar(self, prompt: str, opciones: OpcionesIA) -> RespuestaIA:
        payload = {
            "model": self._modelo,
            "prompt": prompt,
            "stream": False,
            "options": {
                "temperature": opciones.temperatura,
                "num_predict": opciones.max_tokens,
            },
        }
        peticion = urllib.request.Request(
            f"{self._base_url}/api/generate",
            data=json.dumps(payload).encode("utf-8"),
            headers={"Content-Type": "application/json"},
            method="POST",
        )

        crudo = self._enviar_con_reintentos(peticion)
        datos = self._parsear_respuesta(crudo)

        texto = datos.get("response")
        if not isinstance(texto, str) or not texto:
            raise ErrorRespuestaIA(
                "respuesta del proveedor de IA no contiene texto"
            )
        if datos.get("done_reason") == "length":
            raise ErrorRespuestaIA(
                "respuesta del proveedor de IA truncada por límite de tokens"
            )

        return RespuestaIA(
            texto=texto,
            tokens_entrada=int(datos.get("prompt_eval_count") or 0),
            tokens_salida=int(datos.get("eval_count") or 0),
            modelo=self._modelo,
            coste_estimado=0.0,
        )

    def _enviar_con_reintentos(self, peticion: "urllib.request.Request") -> bytes:
        intentos_totales = self._reintentos + 1
        for intento in range(1, intentos_totales + 1):
            try:
                with urllib.request.urlopen(
                    peticion, timeout=self._timeout
                ) as respuesta:
                    return respuesta.read()
            except urllib.error.HTTPError as exc:
                raise ErrorProveedorNoDisponible(
                    f"proveedor de IA respondió con error HTTP {exc.code}"
                ) from None
            except (urllib.error.URLError, OSError):
                if intento == intentos_totales:
                    raise ErrorProveedorNoDisponible(
                        "no se pudo contactar al proveedor de IA tras "
                        f"{intentos_totales} intento(s)"
                    ) from None

    def _parsear_respuesta(self, crudo: bytes) -> dict:
        try:
            datos = json.loads(crudo.decode("utf-8"))
        except (UnicodeDecodeError, json.JSONDecodeError):
            raise ErrorRespuestaIA(
                "respuesta del proveedor de IA no es JSON válido"
            ) from None
        if not isinstance(datos, dict):
            raise ErrorRespuestaIA(
                "respuesta del proveedor de IA con forma inesperada"
            )
        return datos


# Registro explícito (DA-12): solo ocurre si algo importa este módulo, nunca
# al importar `src.ai` a secas.
registrar(
    "ollama",
    lambda: ClienteOllama(
        base_url=config.ai_base_url(),
        modelo=config.ai_model(),
        timeout=config.ai_timeout(),
        reintentos=config.ai_max_retries(),
    ),
)
