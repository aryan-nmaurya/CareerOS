from __future__ import annotations

import random
import time
from typing import Callable, TypeVar

from ai.errors import AIUnavailable

T = TypeVar("T")


def call_with_retries(
    fn: Callable[[], T],
    *,
    is_retryable: Callable[[Exception], bool],
    max_attempts: int = 3,
    base_delay: float = 1.0,
    sleep: Callable[[float], None] = time.sleep,
) -> T:
    """Calls fn, retrying exceptions that `is_retryable` accepts, with
    exponential backoff (base_delay * 2**attempt) plus jitter. Raises
    AIUnavailable once max_attempts is exhausted. Non-retryable exceptions
    propagate immediately, unwrapped — this function is provider-agnostic;
    callers decide what counts as transient.
    """
    last_error: Exception | None = None
    for attempt in range(max_attempts):
        try:
            return fn()
        except Exception as exc:
            if not is_retryable(exc):
                raise
            last_error = exc
            if attempt < max_attempts - 1:
                delay = base_delay * (2**attempt) + random.uniform(0, 0.5)
                sleep(delay)
    raise AIUnavailable(str(last_error)) from last_error
