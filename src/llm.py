"""
Provider-agnostic LLM call.

The rest of the codebase talks to call_llm() and never imports a vendor SDK
directly, so switching providers is a change in one file.
"""

import os
import time

from dotenv import load_dotenv
from google import genai
from google.genai import types
from src.trace import span

load_dotenv()

MODEL = os.getenv("LLM_MODEL", "gemini-3.6-flash")
_client = None

# Free tier is limited per minute and per day. Space calls out to stay under
# the per-minute cap; the per-day cap is handled by caching, not by waiting.
MIN_INTERVAL_SECONDS = 8.0
_last_call_at = 0.0


def _get_client():
    global _client
    if _client is None:
        key = os.getenv("GEMINI_API_KEY")
        if not key:
            raise RuntimeError("GEMINI_API_KEY is not set in .env")
        _client = genai.Client(api_key=key)
    return _client


def _throttle() -> None:
    global _last_call_at
    elapsed = time.time() - _last_call_at
    if elapsed < MIN_INTERVAL_SECONDS:
        time.sleep(MIN_INTERVAL_SECONDS - elapsed)
    _last_call_at = time.time()


def call_llm(prompt: str, system: str = "", attempts: int = 3) -> str:
    """Send a prompt, return the text response.

    Retries only on genuinely transient server errors (500, 503). A 429 is
    a quota decision, not a blip — retrying it burns more quota than it
    recovers, so it fails immediately. Raises rather than returning an error
    string, so a broken run never scores as a bad diagnosis.
    """
    client = _get_client()
    config = types.GenerateContentConfig(
        system_instruction=system) if system else None

    last_error = None
    for attempt in range(attempts):
        _throttle()
        try:
            with span(MODEL, kind="llm") as sp:
                response = client.models.generate_content(
                    model=MODEL,
                    contents=prompt,
                    config=config,
                )
                usage = getattr(response, "usage_metadata", None)
                if usage:
                    sp.record(
                        tokens_in=getattr(usage, "prompt_token_count", 0),
                        tokens_out=getattr(usage, "candidates_token_count", 0),
                    )
                sp.record(attempt=attempt + 1)
            return response.text
        except Exception as e:
            last_error = e
            if not any(code in str(e) for code in ("503", "500")):
                raise
            time.sleep(2 ** attempt * 5)

    raise RuntimeError(f"LLM call failed after {attempts} attempts: {last_error}")