"""Unit tests for api.calculators.RateCalculator."""

from __future__ import annotations

from custom_components.unraid_management_agent.api import RateCalculator


def test_rate_calculator_two_distinct_samples() -> None:
    """Rate is delta_bytes / dt converted to kbit/s."""
    calc = RateCalculator()
    calc.add_sample(0, 0.0)
    calc.add_sample(125_000, 1.0)  # 125000 B/s * 8 / 1000 = 1000 kbit/s
    assert calc.rate_kbps == 1000.0


def test_rate_calculator_holds_rate_on_unchanged_counter() -> None:
    """A duplicate sample must not reset the rate to 0 (the flapping bug)."""
    calc = RateCalculator()
    calc.add_sample(0, 0.0)
    calc.add_sample(125_000, 1.0)
    assert calc.rate_kbps == 1000.0

    # Counter unchanged on the next poll (source hasn't refreshed yet).
    calc.add_sample(125_000, 2.0)
    assert calc.rate_kbps == 1000.0  # held, not zeroed
    # Baseline must NOT advance, so the next real change spans the true interval.
    assert calc.last_bytes == 125_000
    assert calc.last_timestamp == 1.0


def test_rate_calculator_no_flap_with_fast_polling() -> None:
    """Polling faster than the counter refreshes yields a steady rate, not 0/value flapping."""
    calc = RateCalculator()
    # Counter advances by 6_000_000 bytes every 60s; consumer polls every 30s.
    samples = [
        (0, 0.0),
        (0, 30.0),  # duplicate
        (6_000_000, 60.0),  # real change -> 6e6/60 * 8 / 1000 = 800 kbit/s
        (6_000_000, 90.0),  # duplicate
        (12_000_000, 120.0),  # real change -> 800 kbit/s
    ]
    rates = []
    for byte_count, ts in samples:
        calc.add_sample(byte_count, ts)
        rates.append(calc.rate_kbps)
    # After the first real change, every subsequent reading is the real rate.
    assert rates == [0.0, 0.0, 800.0, 800.0, 800.0]


def test_rate_calculator_zeros_when_stale() -> None:
    """An interface idle past the stale threshold is driven to 0."""
    calc = RateCalculator(stale_threshold_seconds=300.0)
    calc.add_sample(0, 0.0)
    calc.add_sample(125_000, 1.0)
    assert calc.rate_kbps == 1000.0
    # No counter movement for longer than the stale window.
    calc.add_sample(125_000, 400.0)
    assert calc.rate_kbps == 0.0


def test_rate_calculator_handles_counter_wrap() -> None:
    """A 32-bit counter wrap is treated as a positive delta, not a negative one."""
    calc = RateCalculator()
    calc.add_sample(RateCalculator.COUNTER_32_MAX - 1000, 0.0)
    calc.add_sample(0, 1.0)  # wrapped: delta = 1000 bytes
    assert calc.rate_kbps == 1000 * 8 / 1000
