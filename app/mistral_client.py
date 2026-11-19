"""Dunne laag over de Mistral Conversations API.

Alle LLM/API-aanroepen zitten hier, zodat tests deze laag kunnen mocken en de
provider vervangbaar blijft (CODING_PRINCIPLES.md).
"""

import json
import logging
from collections.abc import Callable
from dataclasses import dataclass

import requests

logger = logging.getLogger(__name__)

DEFAULT_TIMEOUT = 180  # ruimer (review 2026-11-12: websearch/handoff-runs liepen op 60s in een timeout); bij timeout direct een 502 met melding

# `message` is tekst van de gebruiker of een lijst function.result-entries (#149)
Inputs = str | list[dict]


@dataclass(frozen=True)
class FunctionCall:
    """Een function call van de agent; `arguments` is de JSON-string van het model."""

    tool_call_id: str
    name: str
    arguments: str


def _function_calls(outputs: list) -> list[FunctionCall]:
    calls = []
    for out in outputs:
        if out.get("type") != "function.call":
            continue
        arguments = out.get("arguments", "")
        if not isinstance(arguments, str):
            arguments = json.dumps(arguments)
        calls.append(FunctionCall(str(out.get("tool_call_id", "")), str(out.get("name", "")), arguments))
    return calls


class StreamStartError(RuntimeError):
    """De streaming-call startte niet (connect/HTTP-fout vóór het eerste
    event) — veilig om op terug te vallen op de non-streaming call, want
    Mistral heeft dan niets verwerkt (#93)."""


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
    message: Inputs,
    conversation_id: str | None = None,
    metadata: dict | None = None,
    prompt_cache_key: str | None = None,
    on_function_call: Callable[[FunctionCall], None] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[str, str]:
    """Stuur een bericht naar de agent (non-streaming); geef (mistral_conversation_id, antwoordtekst).

    `metadata` gaat alleen mee bij het starten van een conversatie (bv. de
    app-conversation-id, zodat scripts/trace_conversation.py feedback aan de
    Mistral-geschiedenis kan koppelen). `prompt_cache_key` zet prompt caching
    aan (#88 besluit 6; gecachte input kost 10%). `on_function_call` krijgt
    elke function call uit het antwoord (#149).
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    try:
        if conversation_id:
            body: dict = {"inputs": message}
            if prompt_cache_key:
                body["prompt_cache_key"] = prompt_cache_key
            resp = requests.post(
                f"{base_url}/{conversation_id}",
                headers=headers,
                json=body,
                timeout=timeout,
            )
        else:
            body = {"agent_id": agent_id, "inputs": message}
            if metadata:
                body["metadata"] = metadata
            if prompt_cache_key:
                body["prompt_cache_key"] = prompt_cache_key
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
    outputs = data.get("outputs", [])
    if on_function_call is not None:
        for call in _function_calls(outputs):
            on_function_call(call)
    return new_id, extract_text(outputs)


def stream_answer(
    *,
    api_key: str,
    agent_id: str,
    base_url: str,
    message: Inputs,
    conversation_id: str | None = None,
    metadata: dict | None = None,
    prompt_cache_key: str | None = None,
    on_event: Callable[[str, dict], None] | None = None,
    on_function_call: Callable[[FunctionCall], None] | None = None,
    timeout: int = DEFAULT_TIMEOUT,
) -> tuple[str, str]:
    """POST /v1/conversations met stream: true; consumeer de SSE server-side (#90/#93).

    `on_event(event_type, data)` wordt per SSE-event aangeroepen (de #85-job
    zet ze om in fase-teksten). `on_function_call` krijgt na de stream elke
    function call, samengesteld uit de function.call.delta-events (#149).
    Geef (mistral_conversation_id, antwoordtekst);
    de tekst telt alleen message.output.delta-chunks ná de laatste
    agent.handoff.done (zelfde regel als extract_text). Bij een connect/HTTP-
    fout vóór het eerste event raise StreamStartError (veilig om non-
    streaming te retryen); mid-stream fouten raise RuntimeError. SSE-data
    bevat `type` plus eventvelden op top-level; de oudere `event`/`data`-
    envelop wordt ook geaccepteerd.
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    url = f"{base_url}/{conversation_id}" if conversation_id else base_url
    body: dict = {"inputs": message, "stream": True}
    if not conversation_id:
        body["agent_id"] = agent_id
        if metadata:
            body["metadata"] = metadata
    if prompt_cache_key:
        body["prompt_cache_key"] = prompt_cache_key
    try:
        # (connect, read)-tuple: een stille stream mag niet de hele read-timeout hangen (#90)
        resp = requests.post(
            url, headers=headers, json=body, timeout=(10, timeout), stream=True
        )
        resp.raise_for_status()
    except requests.Timeout as exc:
        raise StreamStartError(
            f"Mistral API timeout na {timeout}s — probeer het opnieuw"
        ) from exc
    except requests.HTTPError as exc:
        raise StreamStartError(
            f"Mistral API error {resp.status_code}: {resp.text[:200]}"
        ) from exc
    except requests.RequestException as exc:
        raise StreamStartError(f"Mistral API niet bereikbaar: {exc}") from exc

    conv_id = conversation_id or ""
    chunks: list[str] = []  # deltas ná de laatste handoff
    kept: list[dict] = []  # fallback: outputs + handoffs in non-stream-vorm
    calls: dict[str, dict] = {}  # tool_call_id -> naam + argument-deltas
    try:
        for raw in resp.iter_lines(decode_unicode=True):
            line = raw.decode("utf-8") if isinstance(raw, bytes) else raw
            if not line or not line.startswith("data:"):
                continue
            try:
                payload = json.loads(line[len("data:"):].strip())
            except json.JSONDecodeError:
                continue
            if "type" in payload:
                event = str(payload["type"])
                data = {key: value for key, value in payload.items() if key != "type"}
            else:
                event = str(payload.get("event") or "")
                data = payload.get("data") or {}
            if not isinstance(data, dict):
                continue
            if on_event is not None:
                try:
                    on_event(event, data)
                except Exception:
                    logger.warning(
                        "on_event-handler gaf een fout; fase-mapping mag de stream niet breken",
                        exc_info=True,
                    )
            if event == "conversation.response.started":
                conv_id = data.get("conversation_id") or conv_id
            elif event == "agent.handoff.done":
                kept.append({"type": "agent.handoff", **data})
                chunks = []
            elif event == "message.output.delta":
                content = data.get("content", "")
                texts = (
                    [content]
                    if isinstance(content, str)
                    else [
                        c.get("text", "")
                        for c in content
                        if isinstance(c, dict) and c.get("type") == "text"
                    ]
                    if isinstance(content, list)
                    else []
                )
                chunks.extend(texts)
                kept.append({"type": "message.output", "content": texts})
            elif event == "message.output.done":
                kept.append({"type": "message.output", **data})
            elif event == "function.call.delta":
                call = calls.setdefault(
                    str(data.get("tool_call_id", "")), {"name": "", "arguments": []}
                )
                call["name"] = call["name"] or str(data.get("name") or "")
                call["arguments"].append(str(data.get("arguments") or ""))
            elif event == "conversation.response.error":
                raise RuntimeError(
                    f"Mistral stream error: {data.get('message', 'onbekende fout')}"
                )
    except RuntimeError:
        raise
    except requests.RequestException as exc:
        raise RuntimeError(f"Mistral stream afgebroken: {exc}") from exc
    text = "".join(chunks) if chunks else extract_text(kept)
    if on_function_call is not None:
        for tool_call_id, call in calls.items():
            on_function_call(FunctionCall(tool_call_id, call["name"], "".join(call["arguments"])))
    return conv_id, text


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


def chat_completion(
    *,
    api_key: str,
    base_url: str,
    model: str,
    system_prompt: str,
    message: str,
    timeout: int = 30,
) -> str:
    """Eén call naar de Chat Completions API (light-model intake, #91).

    Stuurt system_prompt + message met response_format json_object en geef de
    content van de eerste choice terug. Bij elke fout (netwerk, HTTP,
    ongeldige JSON of onverwachte structuur) raise RuntimeError met context —
    de aanroeper (intake.classify_message) vangt af op de veilige fallback.
    """
    headers = {"Authorization": f"Bearer {api_key}", "Content-Type": "application/json"}
    body = {
        "model": model,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": message},
        ],
        "response_format": {"type": "json_object"},
        "temperature": 0,
    }
    try:
        resp = requests.post(base_url, headers=headers, json=body, timeout=timeout)
        resp.raise_for_status()
        data = resp.json()
        return data["choices"][0]["message"]["content"]
    except requests.RequestException as exc:
        raise RuntimeError(f"Mistral Chat Completions-aanroep mislukt: {exc}") from exc
    except (KeyError, IndexError, TypeError) as exc:
        raise RuntimeError(
            f"Mistral Chat Completions gaf een onverwachte structuur terug: {exc}"
        ) from exc
