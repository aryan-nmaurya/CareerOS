from __future__ import annotations

import json
import logging
from typing import Iterator

from google import genai
from google.genai import errors, types

from ai.client import Prompt
from ai.errors import AIInvalidResponse, AIUnavailable
from ai.retry import call_with_retries
from config import settings

log = logging.getLogger(__name__)

_RETRYABLE_CODES = frozenset({429, 500, 502, 503, 504})


def _is_retryable(exc: Exception) -> bool:
    return isinstance(exc, errors.APIError) and exc.code in _RETRYABLE_CODES


class GeminiClient:
    """AIClient implementation backed by Google Gemini. One instance per
    process — the underlying SDK client is safe to reuse across calls."""

    def __init__(self) -> None:
        self._client = genai.Client(api_key=settings.GEMINI_API_KEY)

    def generate_json(self, prompt: Prompt) -> dict:
        def call() -> str:
            response = self._client.models.generate_content(
                model=settings.GEMINI_MODEL,
                contents=prompt.user_content,
                config=types.GenerateContentConfig(
                    system_instruction=prompt.system_instruction,
                    response_mime_type="application/json",
                    response_schema=prompt.response_schema,
                    temperature=prompt.temperature,
                    max_output_tokens=prompt.max_output_tokens,
                    thinking_config=types.ThinkingConfig(thinking_budget=0),
                ),
            )
            if not response.text:
                raise AIInvalidResponse("Gemini returned an empty response")
            return response.text

        try:
            text = call_with_retries(call, is_retryable=_is_retryable)
        except errors.APIError as exc:
            # Non-retryable APIError (e.g. 400 bad request, 404 unknown
            # model) reaches here unwrapped from call_with_retries, since
            # that helper only wraps the retry-exhaustion case.
            log.warning("Gemini API error (non-retryable): %s", exc)
            raise AIUnavailable(str(exc)) from exc

        try:
            return json.loads(text)
        except json.JSONDecodeError as exc:
            raise AIInvalidResponse(f"Gemini returned invalid JSON: {exc}") from exc

    def generate_json_stream(self, prompt: Prompt) -> Iterator[str]:
        def call():
            return self._client.models.generate_content_stream(
                model=settings.GEMINI_MODEL,
                contents=prompt.user_content,
                config=types.GenerateContentConfig(
                    system_instruction=prompt.system_instruction,
                    response_mime_type="application/json",
                    response_schema=prompt.response_schema,
                    temperature=prompt.temperature,
                    max_output_tokens=prompt.max_output_tokens,
                    # Thinking stays enabled here, unlike generate_json — the
                    # spec calls for it on roadmap generation specifically,
                    # since it's a much harder generation task than a single
                    # assessment-grading extraction.
                ),
            )

        try:
            stream = call_with_retries(call, is_retryable=_is_retryable)
            for chunk in stream:
                if chunk.text:
                    yield chunk.text
        except errors.APIError as exc:
            log.warning("Gemini streaming error: %s", exc)
            raise AIUnavailable(str(exc)) from exc
