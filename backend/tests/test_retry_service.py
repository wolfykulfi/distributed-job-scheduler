import pytest

from app.models.retry_policy import RetryStrategy
from app.services.retry_service import compute_backoff_seconds


def test_fixed_strategy_is_constant():
    assert compute_backoff_seconds(RetryStrategy.FIXED, 1, base_delay_seconds=10, max_delay_seconds=999, multiplier=2) == 10
    assert compute_backoff_seconds(RetryStrategy.FIXED, 5, base_delay_seconds=10, max_delay_seconds=999, multiplier=2) == 10


def test_linear_strategy_scales_with_attempt():
    assert compute_backoff_seconds(RetryStrategy.LINEAR, 1, base_delay_seconds=10, max_delay_seconds=999, multiplier=2) == 10
    assert compute_backoff_seconds(RetryStrategy.LINEAR, 3, base_delay_seconds=10, max_delay_seconds=999, multiplier=2) == 30


def test_exponential_strategy_doubles_each_attempt():
    assert compute_backoff_seconds(RetryStrategy.EXPONENTIAL, 1, base_delay_seconds=10, max_delay_seconds=999, multiplier=2) == 10
    assert compute_backoff_seconds(RetryStrategy.EXPONENTIAL, 2, base_delay_seconds=10, max_delay_seconds=999, multiplier=2) == 20
    assert compute_backoff_seconds(RetryStrategy.EXPONENTIAL, 4, base_delay_seconds=10, max_delay_seconds=999, multiplier=2) == 80


def test_delay_is_capped_at_max_delay_seconds():
    delay = compute_backoff_seconds(RetryStrategy.EXPONENTIAL, 10, base_delay_seconds=10, max_delay_seconds=60, multiplier=2)
    assert delay == 60


def test_unknown_strategy_raises():
    with pytest.raises(ValueError):
        compute_backoff_seconds("bogus", 1, base_delay_seconds=10, max_delay_seconds=60, multiplier=2)
