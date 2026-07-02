"""Pure backoff-calculation logic, kept separate from the ORM so it's trivially unit-testable."""

from app.models.retry_policy import RetryStrategy


def compute_backoff_seconds(
    strategy: RetryStrategy, attempt_number: int, base_delay_seconds: int, max_delay_seconds: int, multiplier: float
) -> int:
    """attempt_number is the attempt that just failed (1-indexed); returns delay before the next one."""
    if strategy == RetryStrategy.FIXED:
        delay = base_delay_seconds
    elif strategy == RetryStrategy.LINEAR:
        delay = base_delay_seconds * attempt_number
    elif strategy == RetryStrategy.EXPONENTIAL:
        delay = base_delay_seconds * (multiplier ** (attempt_number - 1))
    else:
        raise ValueError(f"Unknown retry strategy: {strategy}")
    return min(int(delay), max_delay_seconds)
