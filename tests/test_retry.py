from __future__ import annotations

import pytest

from research_agent.retry import RetryExhaustedError, retry_call


class TemporaryError(RuntimeError):
    pass


def test_transient_failure_then_success() -> None:
    calls = 0

    def operation() -> str:
        nonlocal calls
        calls += 1
        if calls < 3:
            raise TemporaryError("later")
        return "ok"

    delays: list[float] = []
    result = retry_call(
        operation,
        attempts=3,
        base_seconds=0.1,
        retryable=(TemporaryError,),
        sleeper=delays.append,
        random_value=lambda: 0.5,
    )
    assert result == "ok"
    assert calls == 3
    assert delays == [0.1, 0.2]


def test_retry_exhaustion_is_bounded() -> None:
    calls = 0

    def operation() -> None:
        nonlocal calls
        calls += 1
        raise TemporaryError("still broken")

    with pytest.raises(RetryExhaustedError) as captured:
        retry_call(
            operation,
            attempts=3,
            base_seconds=0.1,
            retryable=(TemporaryError,),
            sleeper=lambda _: None,
        )
    assert calls == 3
    assert captured.value.attempts == 3


def test_permanent_error_is_not_retried() -> None:
    with pytest.raises(ValueError):
        retry_call(
            lambda: (_ for _ in ()).throw(ValueError("permanent")),
            attempts=3,
            base_seconds=0.1,
            retryable=(TemporaryError,),
            sleeper=lambda _: None,
        )

