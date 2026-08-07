from __future__ import annotations

from dataclasses import dataclass
from typing import Any, Iterator, Protocol


@dataclass(frozen=True)
class Prompt:
    system_instruction: str
    user_content: str
    response_schema: dict[str, Any]
    temperature: float = 0.4
    max_output_tokens: int = 4096


class AIClient(Protocol):
    def generate_json(self, prompt: Prompt) -> dict[str, Any]: ...
    def generate_json_stream(self, prompt: Prompt) -> Iterator[str]: ...


class FakeAIClient:
    """Test double. Queue non-streaming responses with queue_response() and
    streaming ones with queue_stream(); each call pops the next one, in
    order, for its own method. Raises AssertionError if the relevant queue
    runs dry, so an under-specified test fails loudly instead of hanging.
    """

    def __init__(self) -> None:
        self._queue: list[dict[str, Any]] = []
        self._stream_queue: list[list[str]] = []
        self.calls: list[Prompt] = []
        self.stream_calls: list[Prompt] = []

    def queue_response(self, response: dict[str, Any]) -> None:
        self._queue.append(response)

    def queue_stream(self, chunks: list[str]) -> None:
        self._stream_queue.append(chunks)

    def generate_json(self, prompt: Prompt) -> dict[str, Any]:
        self.calls.append(prompt)
        if not self._queue:
            raise AssertionError("FakeAIClient: no queued response left")
        return self._queue.pop(0)

    def generate_json_stream(self, prompt: Prompt) -> Iterator[str]:
        self.stream_calls.append(prompt)
        if not self._stream_queue:
            raise AssertionError("FakeAIClient: no queued stream left")
        return iter(self._stream_queue.pop(0))


_client: AIClient | None = None


def get_ai_client() -> AIClient:
    """FastAPI dependency. Lazily constructs a singleton GeminiClient.

    The import is local (not at module top) because gemini_client.py imports
    Prompt and AIClient from this module — a top-level import here would be
    circular.
    """
    global _client
    if _client is None:
        from ai.gemini_client import GeminiClient

        _client = GeminiClient()
    return _client
