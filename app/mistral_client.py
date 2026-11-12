"""Dunne laag over de Mistral Conversations API.

Alle LLM/API-aanroepen zitten hier, zodat tests deze laag kunnen mocken en de
provider vervangbaar blijft (CODING_PRINCIPLES.md).
"""

import requests

DEFAULT_TIMEOUT = 60  # kortere worst-case: bij timeout direct een 502 met melding


def extract_text(outputs: list) -> str:
    """Plak de tekst-chunks van een Conversations-antwoord aan elkaar.

    Shape van POST /v1/conversations: outputs[]-entries met
    type == "message.output" en top-level "content" (string of list of
    chunks; alleen chunks met type == "text" zijn antwoordtekst,
    "thinking"-chunks niet meenemen). Tekst vóór de laatste
    "agent.handoff" telt niet mee: dat is een aankondiging van de
    doorverwijzende agent, het antwoord komt van de agent erna.
    """
    handoffs = [i for i, out in enumerate(outputs) if out.get("type") == "agent.handoff"]
    if handoffs:
        outputs = outputs[handoffs[-1] + 1:]
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
    metadata: dict | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[str, str]:
    """Stuur een bericht naar de agent; geef (mistral_conversation_id, antwoordtekst).

    `metadata` gaat alleen mee bij het starten van een conversatie (bv. de
    app-conversation-id, zodat scripts/trace_conversation.py feedback aan de
    Mistral-geschiedenis kan koppelen).
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        if conversation_id:
            resp = requests.post(
                f"{base_url}/{conversation_id}",
                headers=headers,
                json={"inputs": message},
                timeout=timeout,
            )
        else:
            body = {"agent_id": agent_id, "inputs": message}
            if metadata:
                body["metadata"] = metadata
            resp = requests.post(base_url, headers=headers, json=body, timeout=timeout)
    except requests.Timeout as exc:
        raise RuntimeError(f"Mistral API timeout na {timeout}s — probeer het opnieuw") from exc
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
