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

load_dotenv()

MODEL = os.getenv("LLM_MODEL", "gemini-3.6-flash")
_client = None

# Free tier allows ~15 requests/minute. Space calls out to stay under it.
MIN_INTERVAL_SECONDS = 4.5
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


def call_llm(prompt: str, system: str = "") -> str:
    """Send a prompt, return the text response.

    Raises on failure rather than returning an error string — a silent
    failure would score as a bad diagnosis instead of a broken run.
    """
    client = _get_client()
    _throttle()

    config = types.GenerateContentConfig(
        system_instruction=system) if system else None

    response = client.models.generate_content(
        model=MODEL,
        contents=prompt,
        config=config,
    )
    return response.text