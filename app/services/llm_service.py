"""Groq LLM via official SDK; optional Gemini fallback. No LangChain (avoids LangSmith import issues)."""

from __future__ import annotations

import logging
import time
from typing import Any

from app.config import (
    GOOGLE_API_KEY,
    GROQ_API_KEY,
    GROQ_MAX_TOKENS,
    GROQ_MODEL,
    GROQ_TEMPERATURE,
)

logger = logging.getLogger(__name__)

_groq_client: Any = None
_gemini_model: Any = None


def _get_groq():
    global _groq_client
    if _groq_client is None:
        if not GROQ_API_KEY:
            raise ValueError("GROQ_API_KEY not set")
        from groq import Groq

        _groq_client = Groq(api_key=GROQ_API_KEY)
    return _groq_client


def _get_gemini():
    global _gemini_model
    if _gemini_model is None:
        if not GOOGLE_API_KEY:
            raise ValueError("GOOGLE_API_KEY not set")
        import google.generativeai as genai

        genai.configure(api_key=GOOGLE_API_KEY)
        _gemini_model = genai.GenerativeModel("gemini-1.5-flash")
    return _gemini_model


def _messages_to_groq(messages: list[tuple[str, str]]) -> list[dict[str, str]]:
    out = []
    for role, content in messages:
        r = "system" if role == "system" else "user"
        out.append({"role": r, "content": content})
    return out


def _invoke_groq(messages: list[tuple[str, str]]) -> str:
    client = _get_groq()
    msgs = _messages_to_groq(messages)
    r = client.chat.completions.create(
        model=GROQ_MODEL,
        messages=msgs,
        temperature=GROQ_TEMPERATURE,
        max_tokens=GROQ_MAX_TOKENS,
    )
    return (r.choices[0].message.content or "").strip()


def _invoke_gemini(messages: list[tuple[str, str]]) -> str:
    model = _get_gemini()
    parts = []
    for role, content in messages:
        if role == "system":
            parts.append(f"[System]\n{content}\n")
        else:
            parts.append(content)
    prompt = "\n".join(parts)
    response = model.generate_content(prompt)
    return (response.text or "").strip()


def invoke_with_fallback(
    messages: list[tuple[str, str]],
    use_gemini_fallback: bool = True,
) -> str:
    """
    Call Groq; on rate-limit retry with exponential backoff. If Groq fails,
    fall back to Gemini when use_gemini_fallback and GOOGLE_API_KEY are set.
    """
    last_err: Exception | None = None
    for attempt in range(4):
        try:
            return _invoke_groq(messages)
        except Exception as e:
            last_err = e
            err_str = str(e).lower()
            is_rate_limit = "429" in err_str or "rate" in err_str or "limit" in err_str
            if is_rate_limit and attempt < 3:
                delay = 2**attempt
                logger.warning("Groq rate limit, retrying in %ss (attempt %d)", delay, attempt + 1)
                time.sleep(delay)
                continue
            break

    if use_gemini_fallback and GOOGLE_API_KEY:
        try:
            logger.info("Falling back to Gemini")
            return _invoke_gemini(messages)
        except Exception as gemini_err:
            logger.exception("Gemini fallback failed")
            raise (last_err or gemini_err) from gemini_err

    raise last_err or RuntimeError("LLM invocation failed")
