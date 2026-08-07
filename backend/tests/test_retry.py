import pytest

from ai.errors import AIUnavailable
from ai.retry import call_with_retries


class _Retryable(Exception):
    pass


def _is_retryable(exc: Exception) -> bool:
    return isinstance(exc, _Retryable)


def test_succeeds_without_retry_when_first_call_works():
    calls = []

    def fn():
        calls.append(1)
        return "ok"

    sleeps = []
    result = call_with_retries(fn, is_retryable=_is_retryable, sleep=sleeps.append)

    assert result == "ok"
    assert len(calls) == 1
    assert sleeps == []


def test_retries_then_succeeds():
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise _Retryable("transient")
        return "ok"

    sleeps = []
    result = call_with_retries(
        fn, is_retryable=_is_retryable, max_attempts=3, base_delay=1.0, sleep=sleeps.append
    )

    assert result == "ok"
    assert attempts["n"] == 3
    assert len(sleeps) == 2


def test_backoff_delays_double_each_time():
    attempts = {"n": 0}

    def fn():
        attempts["n"] += 1
        raise _Retryable("still down")

    sleeps = []
    with pytest.raises(AIUnavailable):
        call_with_retries(
            fn, is_retryable=_is_retryable, max_attempts=3, base_delay=1.0, sleep=sleeps.append
        )

    assert len(sleeps) == 2
    # jitter adds 0-0.5s, so check the base progression rather than exact values
    assert 1.0 <= sleeps[0] < 1.5
    assert 2.0 <= sleeps[1] < 2.5


def test_raises_ai_unavailable_after_exhausting_attempts():
    def fn():
        raise _Retryable("still down")

    with pytest.raises(AIUnavailable):
        call_with_retries(fn, is_retryable=_is_retryable, max_attempts=3, sleep=lambda s: None)


def test_non_retryable_error_propagates_immediately_without_sleeping():
    calls = []
    sleeps = []

    def fn():
        calls.append(1)
        raise ValueError("not retryable")

    with pytest.raises(ValueError):
        call_with_retries(fn, is_retryable=_is_retryable, max_attempts=3, sleep=sleeps.append)

    assert len(calls) == 1
    assert sleeps == []
