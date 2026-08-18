from __future__ import annotations

import random
import time
from collections.abc import Callable


class RetryExhaustedError(RuntimeError):
    def __init__(self, attempts: int, cause: Exception) -> None:
        super().__init__(f"operation failed after {attempts} attempts: {cause}")
        self.attempts = attempts
        self.cause = cause


def retry_call[T](
    operation: Callable[[], T],
    *,
    attempts: int,
    base_seconds: float,
    retryable: tuple[type[Exception], ...],
    on_retry: Callable[[int, Exception, float], None] | None = None,
    sleeper: Callable[[float], None] = time.sleep,
    random_value: Callable[[], float] = random.random,
) -> T:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            return operation()
        except retryable as error:
            last_error = error
            if attempt == attempts:
                break
            delay = base_seconds * (2 ** (attempt - 1)) * (0.5 + random_value())
            if on_retry:
                on_retry(attempt, error, delay)
            sleeper(delay)
    assert last_error is not None
    raise RetryExhaustedError(attempts, last_error) from last_error
