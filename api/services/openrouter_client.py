import os

import requests


OPENROUTER_URL = "https://openrouter.ai/api/v1/chat/completions"
OPENROUTER_MODEL_ID = os.getenv("OPENROUTER_MODEL", "meta-llama/llama-3.3-8b-instruct:free")


def call_llm(system_prompt: str, data_block: str) -> str:
    """
    POST to OpenRouter chat/completions and return the model content.
    """
    api_key = os.getenv("OPENROUTER_API_KEY")
    if not api_key:
        raise RuntimeError("OPENROUTER_API_KEY is not configured")

    response = requests.post(
        OPENROUTER_URL,
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": OPENROUTER_MODEL_ID,
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
