"""
Utility classes for time-series calculations and data processing.

This module provides stateful calculators for energy integration and
rate computation from counter-based metrics.

Example:
    >>> from custom_components.unraid_management_agent.api import EnergyIntegrator, RateCalculator
    >>>
    >>> integrator = EnergyIntegrator()
    >>> integrator.add_sample(100.0, 1000.0)
    >>> integrator.add_sample(120.0, 2000.0)
    >>> print(f"Total energy: {integrator.total_wh:.1f} Wh")
    >>>
    >>> rate_calc = RateCalculator()
    >>> rate_calc.add_sample(1000, 1000.0)
    >>> rate_calc.add_sample(2000, 2000.0)
    >>> print(f"Rate: {rate_calc.rate_kbps:.1f} kbps")

"""

from __future__ import annotations

from datetime import datetime


class EnergyIntegrator:
    """
    Integrate power readings over time to compute energy in Wh.

    Uses trapezoidal integration to estimate total energy consumption
    from periodic power readings. Samples older than the stale threshold
    (default 3600 seconds) are treated as a new measurement series.

    Example:
        >>> integrator = EnergyIntegrator()
        >>> integrator.add_sample(100.0, 1000.0)
        >>> integrator.add_sample(120.0, 2000.0)
        >>> integrator.total_wh  # ~30.56 Wh (avg 110W over 1000s)
        30.555555555555557

    """

    def __init__(self, stale_threshold_seconds: float = 3600.0) -> None:
        """
        Initialize the integrator.

        Args:
            stale_threshold_seconds: Maximum time gap between samples before
                treating as a new series (default: 3600 seconds = 1 hour).

        """
        self._stale_threshold = stale_threshold_seconds
        self._last_power_watts: float | None = None
        self._last_timestamp: float | None = None
        self._total_wh: float = 0.0

    @property
    def total_wh(self) -> float:
        """
        Get total accumulated energy in watt-hours.

        Returns:
            Total energy in Wh.

        """
        return self._total_wh

    @property
    def last_power_watts(self) -> float | None:
        """Get the most recent power reading used by the integrator."""
        return self._last_power_watts

    @property
    def last_timestamp(self) -> float | None:
        """Get the most recent sample timestamp used by the integrator."""
        return self._last_timestamp

    def add_sample(self, power_watts: float, timestamp: float) -> None:
        """
        Add a power reading sample.

        Args:
            power_watts: Current power draw in watts.
            timestamp: Unix timestamp of the reading.

        """
        if self._last_power_watts is not None and self._last_timestamp is not None:
            dt = timestamp - self._last_timestamp
            if 0 < dt <= self._stale_threshold:
                # Trapezoidal integration
                avg_power = (self._last_power_watts + power_watts) / 2.0
                self._total_wh += avg_power * dt / 3600.0

        self._last_power_watts = power_watts
        self._last_timestamp = timestamp

    def restore_state(
        self,
        *,
        last_power_watts: float | None,
        last_timestamp: float | None,
        total_wh: float = 0.0,
    ) -> None:
        """Restore the integrator state from persisted data."""
        if last_power_watts is None or last_timestamp is None:
            self._last_power_watts = None
            self._last_timestamp = None
        else:
            self._last_power_watts = last_power_watts
            self._last_timestamp = last_timestamp

        self._total_wh = total_wh

    def reset(self) -> None:
        """Reset the integrator to zero."""
        self._last_power_watts = None
        self._last_timestamp = None
        self._total_wh = 0.0


class RateCalculator:
    """
    Calculate transfer rates (kbps) from monotonic byte counters.

    Handles counter wraps for 32-bit and 64-bit counters.

    Example:
        >>> calc = RateCalculator()
        >>> calc.add_sample(1000, 1000.0)
        >>> calc.add_sample(2000, 2000.0)
        >>> calc.rate_kbps  # 1000 bytes / 1000s * 8 / 1000 = 0.008 kbps
        0.008

    """

    COUNTER_32_MAX = 2**32
    COUNTER_64_MAX = 2**64

    def __init__(self, stale_threshold_seconds: float | None = None) -> None:
        """Initialize the rate calculator."""
        self._stale_threshold = stale_threshold_seconds
        self._last_bytes: int | None = None
        self._last_timestamp: float | None = None
        self._rate_kbps: float = 0.0

    @property
    def rate_kbps(self) -> float:
        """
        Get the most recent calculated rate in kilobits per second.

        Returns:
            Rate in kbps, or 0.0 if insufficient samples.

        """
        return self._rate_kbps

    @property
    def last_bytes(self) -> int | None:
        """Get the most recent byte counter sample."""
        return self._last_bytes

    @property
    def last_timestamp(self) -> float | None:
        """Get the most recent sample timestamp."""
        return self._last_timestamp

    def add_sample(self, byte_count: int, timestamp: float) -> None:
        """
        Add a byte counter sample.

        Args:
            byte_count: Current byte counter value.
            timestamp: Unix timestamp of the reading.

        """
        if self._last_bytes is not None and self._last_timestamp is not None:
            dt = timestamp - self._last_timestamp
            if dt > 0:
                if self._stale_threshold is not None and dt > self._stale_threshold:
                    self._rate_kbps = 0.0
                else:
                    delta_bytes = byte_count - self._last_bytes
                    # Handle counter wrap
                    if delta_bytes < 0:
                        if self._last_bytes < self.COUNTER_32_MAX:
                            delta_bytes += self.COUNTER_32_MAX
                        else:
                            delta_bytes += self.COUNTER_64_MAX

                    # Convert bytes/sec to kilobits/sec
                    self._rate_kbps = (delta_bytes / dt) * 8 / 1000

        self._last_bytes = byte_count
        self._last_timestamp = timestamp

    def restore_state(
        self,
        *,
        last_bytes: int | None,
        last_timestamp: float | None,
        rate_kbps: float = 0.0,
    ) -> None:
        """Restore the calculator state from persisted data."""
        self._last_bytes = last_bytes
        self._last_timestamp = last_timestamp
        self._rate_kbps = rate_kbps

    def reset(self) -> None:
        """Reset the calculator state."""
        self._last_bytes = None
        self._last_timestamp = None
        self._rate_kbps = 0.0


def parse_timestamp(value: str) -> datetime | None:
    """
    Parse a timestamp string into a datetime object.

    Supports ISO 8601 format and common Unix timestamp formats.

    Args:
        value: Timestamp string to parse.

    Returns:
        Parsed datetime, or None if parsing fails.

    Example:
        >>> parse_timestamp("2024-01-15T10:30:00")
        datetime.datetime(2024, 1, 15, 10, 30)
        >>> parse_timestamp("1705312200")
        datetime.datetime(...)

    """
    if not value or not isinstance(value, str):
        return None

    value = value.strip()

    # Try ISO 8601 format
    try:
        return datetime.fromisoformat(value)
    except ValueError:
        pass

    # Try Unix timestamp (seconds)
    try:
        ts = float(value)
        # Reasonable range: year 2000 to year 2100
        if 946684800 <= ts <= 4102444800:
            return datetime.fromtimestamp(ts)  # noqa: DTZ006
        # Could be milliseconds
        if 946684800000 <= ts <= 4102444800000:
            return datetime.fromtimestamp(ts / 1000)  # noqa: DTZ006
    except ValueError, OSError, OverflowError:
        pass

    return None
