import json
import logging
import os
from datetime import datetime, timezone

import requests


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"


def _configured_models() -> list[str]:
    primary = (os.getenv("OPENROUTER_MODEL") or "").strip()
    fallback_raw = (os.getenv("OPENROUTER_FALLBACK_MODELS") or "").strip()
    fallbacks = [m.strip() for m in fallback_raw.split(",") if m.strip()]

    models: list[str] = []
    if primary:
        models.append(primary)

    for model in fallbacks:
        if model not in models:
            models.append(model)

    return models


def get_primary_model_id() -> str:
    models = _configured_models()
    return models[0] if models else ""

service_logger = logging.getLogger("service_errors")


def _utc_now_iso() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace("+00:00", "Z")


def _log_client_error(error: Exception, context: dict | None = None) -> None:
    payload = {
        "timestamp": _utc_now_iso(),
        "severity": "high",
        "category": "service_error",
        "class_name": "openrouter_client",
        "method_name": "call_llm",
        "error_type": type(error).__name__,
        "error_message": str(error),
        "context": context or {},
    }
    service_logger.critical(json.dumps(payload, ensure_ascii=True, default=str))


def call_llm(system_prompt: str, data_block: str) -> str:
    """
    POST to OpenRouter chat/completions and return the model content.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    models = _configured_models()
    if not models:
        raise RuntimeError(
            "No OpenRouter model configured. Set OPENROUTER_MODEL"
            " (and optionally OPENROUTER_FALLBACK_MODELS)."
        )

    last_error = None
    for model_id in models:
        response = None
        try:
            response = requests.post(
                OPENROUTER_URL,
                headers={
                    "Authorization": f"Bearer {api_key}",
                    "Content-Type": "application/json",
                },
                json={
                    "model": model_id,
                    "messages": [
                        {"role": "system", "content": system_prompt},
                        {"role": "user", "content": data_block},
                    ],
                },
                timeout=30,
            )
            response.raise_for_status()

            payload = response.json()
            return payload["choices"][0]["message"]["content"]
        except Exception as error:
            last_error = error
            status_code = None
            response_preview = None
            if response is not None:
                status_code = response.status_code
                response_preview = (response.text or "")[:600]

            _log_client_error(
                error,
                context={
                    "url": OPENROUTER_URL,
                    "model": model_id,
                    "status_code": status_code,
                    "response_preview": response_preview,
                    "system_prompt_length": len(system_prompt or ""),
                    "data_block_length": len(data_block or ""),
                },
            )

            no_endpoint_error = (
                status_code == 404
                and response_preview is not None
                and "no endpoints found" in response_preview.lower()
            )
            if no_endpoint_error:
                continue

            raise

    raise RuntimeError(
        "No available OpenRouter endpoint for configured models: "
        f"{', '.join(models)}"
    ) from last_error
