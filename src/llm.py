"""
Provider-agnostic LLM call.

The rest of the codebase talks to call_llm() and never imports a vendor SDK
directly, so switching providers is a change in one file. Anthropic is used
when a key is present; Gemini remains as a fallback.
"""

import os
import time

from dotenv import load_dotenv

from src.trace import span

load_dotenv()

ANTHROPIC_KEY = os.getenv("ANTHROPIC_API_KEY", "")
GEMINI_KEY = os.getenv("GEMINI_API_KEY", "")
PROVIDER = "anthropic" if ANTHROPIC_KEY else "gemini"

DEFAULT_MODEL = {
    "anthropic": "claude-haiku-4-5-20251001",
    "gemini": "gemini-3.6-flash",
}[PROVIDER]

MODEL = os.getenv("LLM_MODEL", DEFAULT_MODEL)
MAX_TOKENS = 1024

# Gemini's free tier needs pacing. A paid Anthropic key does not.
MIN_INTERVAL_SECONDS = 0.0 if PROVIDER == "anthropic" else 8.0
_last_call_at = 0.0
_client = None


def _get_client():
    global _client
    if _client is not None:
        return _client

    if PROVIDER == "anthropic":
        import anthropic
        _client = anthropic.Anthropic(api_key=ANTHROPIC_KEY)
    else:
        from google import genai
        if not GEMINI_KEY:
            raise RuntimeError("No ANTHROPIC_API_KEY or GEMINI_API_KEY in .env")
        _client = genai.Client(api_key=GEMINI_KEY)

    return _client


def _throttle() -> None:
    global _last_call_at
    if MIN_INTERVAL_SECONDS <= 0:
        return
    elapsed = time.time() - _last_call_at
    if elapsed < MIN_INTERVAL_SECONDS:
        time.sleep(MIN_INTERVAL_SECONDS - elapsed)
    _last_call_at = time.time()


def _call_anthropic(client, prompt: str, system: str, sp) -> str:
    kwargs = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": [{"role": "user", "content": prompt}],
    }
    if system:
        kwargs["system"] = system

    response = client.messages.create(**kwargs)
    sp.record(
        tokens_in=response.usage.input_tokens,
        tokens_out=response.usage.output_tokens,
    )
    return "".join(b.text for b in response.content if b.type == "text")


def _call_gemini(client, prompt: str, system: str, sp) -> str:
    from google.genai import types

    config = types.GenerateContentConfig(system_instruction=system) if system else None
    response = client.models.generate_content(
        model=MODEL, contents=prompt, config=config
    )
    usage = getattr(response, "usage_metadata", None)
    if usage:
        sp.record(
            tokens_in=getattr(usage, "prompt_token_count", 0),
            tokens_out=getattr(usage, "candidates_token_count", 0),
        )
    return response.text


def call_llm(prompt: str, system: str = "", attempts: int = 3) -> str:
    """Send a prompt, return the text response.

    Retries only on genuinely transient server errors. A 429 is a quota
    decision, not a blip — retrying it burns more quota than it recovers,
    so it fails immediately. Raises rather than returning an error string,
    so a broken run never scores as a bad diagnosis.
    """
    client = _get_client()
    last_error = None

    for attempt in range(attempts):
        _throttle()
        try:
            with span(MODEL, kind="llm") as sp:
                sp.record(provider=PROVIDER, attempt=attempt + 1)
                if PROVIDER == "anthropic":
                    return _call_anthropic(client, prompt, system, sp)
                return _call_gemini(client, prompt, system, sp)
        except Exception as e:
            last_error = e
            if not any(code in str(e) for code in ("503", "500", "overloaded")):
                raise
            time.sleep(2 ** attempt * 5)

    raise RuntimeError(f"LLM call failed after {attempts} attempts: {last_error}")

def call_llm_tools(messages: list, tools: list, system: str = "") -> dict:
    """Tool-use turn. Returns the raw content blocks plus what the model decided.

    Anthropic only — the tool-use message format differs enough between
    providers that pretending otherwise would hide bugs.
    """
    if PROVIDER != "anthropic":
        raise RuntimeError("Tool use requires ANTHROPIC_API_KEY")

    client = _get_client()

    kwargs = {
        "model": MODEL,
        "max_tokens": MAX_TOKENS,
        "messages": messages,
    }
    if system:
        kwargs["system"] = system
    if tools:
        kwargs["tools"] = tools

    response = client.messages.create(**kwargs)

    text = "".join(b.text for b in response.content if b.type == "text")
    tool_calls = [
        {"id": b.id, "name": b.name, "input": b.input}
        for b in response.content
        if b.type == "tool_use"
    ]

    return {
        "content": response.content,
        "text": text,
        "tool_calls": tool_calls,
        "stop_reason": response.stop_reason,
        "tokens_in": response.usage.input_tokens,
        "tokens_out": response.usage.output_tokens,
    }