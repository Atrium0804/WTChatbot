"""Dunne laag over de Mistral Conversations API.

Alle LLM/API-aanroepen zitten hier, zodat tests deze laag kunnen mocken en de
provider vervangbaar blijft (CODING_PRINCIPLES.md).
"""

import requests

DEFAULT_TIMEOUT = 180


def extract_text(outputs: list) -> str:
    """Plak de tekst-chunks van een Conversations-antwoord aan elkaar.

    Shape van POST /v1/conversations: outputs[]-entries met
    type == "message.output" en top-level "content" (string of list of
    chunks; alleen chunks met type == "text" zijn antwoordtekst,
    "thinking"-chunks niet meenemen).
    """
    texts = []
    for out in outputs:
        if out.get("type") != "message.output":
            continue
        content = out.get("content", "")
        if isinstance(content, str):
            texts.append(content)
        elif isinstance(content, list):
            for chunk in content:
                if isinstance(chunk, dict) and chunk.get("type") == "text":
                    texts.append(chunk.get("text", ""))
    return "\n".join(texts)


def answer_question(
    *,
    api_key: str,
    agent_id: str,
    base_url: str,
    message: str,
    conversation_id: str | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[str, str]:
    """Stuur een bericht naar de agent; geef (mistral_conversation_id, antwoordtekst)."""
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    if conversation_id:
        resp = requests.post(
            f"{base_url}/{conversation_id}",
            headers=headers,
            json={"inputs": message},
            timeout=timeout,
        )
    else:
        resp = requests.post(
            base_url,
            headers=headers,
            json={"agent_id": agent_id, "inputs": message},
            timeout=timeout,
        )
    try:
        resp.raise_for_status()
    except requests.HTTPError as exc:
        raise RuntimeError(
            f"Mistral API error {resp.status_code}: {resp.text[:200]}"
        ) from exc
    data = resp.json()
    new_id = data.get("conversation_id") or conversation_id or ""
    return new_id, extract_text(data.get("outputs", []))


def check_reachable(*, api_key: str, base_url: str, timeout: int = 10) -> bool:
    """Lichte check voor /healthz: is de Mistral API bereikbaar met deze key?"""
    models_url = base_url.replace("/conversations", "/models")
    try:
        resp = requests.get(
            models_url, headers={"Authorization": f"Bearer {api_key}"}, timeout=timeout
        )
        return resp.status_code == 200
    except requests.RequestException:
        return False
