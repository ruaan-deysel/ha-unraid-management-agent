"""
Formatting utilities for human-readable display values.

This module provides utility functions to format raw API values for display
in UIs, dashboards, and logs.

Example:
    >>> from custom_components.unraid_management_agent.api.formatting import format_bytes, format_duration
    >>> format_bytes(4000000000000)
    '3.6 TB'
    >>> format_duration(432000)
    '5 days'

"""

from __future__ import annotations


def format_bytes(
    value: float,
    precision: int = 1,
    binary: bool = True,
) -> str:
    """
    Format a byte value to a human-readable string.

    Args:
        value: The number of bytes to format
        precision: Number of decimal places (default: 1)
        binary: If True, use binary units (1024). If False, use decimal (1000)

    Returns:
        Formatted string with appropriate unit (B, KB, MB, GB, TB, PB)

    Example:
        >>> format_bytes(4000000000000)
        '3.6 TB'
        >>> format_bytes(536870912)
        '512.0 MB'
        >>> format_bytes(1024, precision=0)
        '1 KB'

    """
    base = 1024 if binary else 1000
    units = ["B", "KB", "MB", "GB", "TB", "PB"]

    abs_value = abs(value)
    sign = "-" if value < 0 else ""

    for unit in units[:-1]:
        if abs_value < base:
            if precision == 0:
                return f"{sign}{int(round(abs_value))} {unit}"
            return f"{sign}{abs_value:.{precision}f} {unit}"
        abs_value /= base

    # Last unit (PB)
    if precision == 0:
        return f"{sign}{int(round(abs_value))} {units[-1]}"
    return f"{sign}{abs_value:.{precision}f} {units[-1]}"


def format_duration(seconds: float, short: bool = False) -> str:
    """
    Format a duration in seconds to a human-readable string.

    Args:
        seconds: Duration in seconds
        short: If True, use short format (e.g., "5d 3h 12m")

    Returns:
        Formatted duration string

    Example:
        >>> format_duration(432000)
        '5 days'
        >>> format_duration(3661)
        '1 hour, 1 minute, 1 second'
        >>> format_duration(432000, short=True)
        '5d 0h 0m'

    """
    seconds = max(seconds, 0)

    seconds = int(seconds)

    days = seconds // 86400
    seconds %= 86400
    hours = seconds // 3600
    seconds %= 3600
    minutes = seconds // 60
    secs = seconds % 60

    if short:
        return f"{days}d {hours}h {minutes}m"

    parts = []
    if days > 0:
        parts.append(f"{days} day{'s' if days != 1 else ''}")
    if hours > 0:
        parts.append(f"{hours} hour{'s' if hours != 1 else ''}")
    if minutes > 0:
        parts.append(f"{minutes} minute{'s' if minutes != 1 else ''}")
    if secs > 0 or not parts:
        parts.append(f"{secs} second{'s' if secs != 1 else ''}")

    return ", ".join(parts)


def format_speed(mbps: float) -> str:
    """
    Format a network speed in Mbps to a human-readable string.

    Args:
        mbps: Speed in megabits per second

    Returns:
        Formatted speed string (Mbps, Gbps, or Tbps)

    Example:
        >>> format_speed(1000)
        '1 Gbps'
        >>> format_speed(100)
        '100 Mbps'
        >>> format_speed(2500)
        '2.5 Gbps'

    """
    abs_mbps = abs(mbps)
    sign = "-" if mbps < 0 else ""

    if abs_mbps >= 1000000:
        value = abs_mbps / 1000000
        if value == int(value):
            return f"{sign}{int(value)} Tbps"
        return f"{sign}{value:.1f} Tbps".rstrip("0").rstrip(".")
    if abs_mbps >= 1000:
        value = abs_mbps / 1000
        if value == int(value):
            return f"{sign}{int(value)} Gbps"
        return f"{sign}{value:.1f} Gbps".rstrip("0").rstrip(".")
    if abs_mbps == int(abs_mbps):
        return f"{sign}{int(abs_mbps)} Mbps"
    return f"{sign}{abs_mbps:.1f} Mbps".rstrip("0").rstrip(".")


def format_percentage(value: float, precision: int = 1) -> str:
    """
    Format a percentage value with a percent symbol.

    Args:
        value: The percentage value
        precision: Number of decimal places (default: 1)

    Returns:
        Formatted percentage string

    Example:
        >>> format_percentage(85.555)
        '85.6%'
        >>> format_percentage(50.0, precision=0)
        '50%'

    """
    if precision == 0:
        return f"{round(value)}%"
    return f"{value:.{precision}f}%"


def format_temperature(
    celsius: float,
    precision: int = 1,
    fahrenheit: bool = False,
) -> str:
    """
    Format a temperature value with unit symbol.

    Args:
        celsius: Temperature in Celsius
        precision: Number of decimal places (default: 1)
        fahrenheit: If True, convert to Fahrenheit

    Returns:
        Formatted temperature string

    Example:
        >>> format_temperature(45.5)
        '45.5°C'
        >>> format_temperature(0.0, fahrenheit=True)
        '32.0°F'

    """
    if fahrenheit:
        value = (celsius * 9 / 5) + 32
        unit = "°F"
    else:
        value = celsius
        unit = "°C"

    if precision == 0:
        return f"{round(value)}{unit}"
    return f"{value:.{precision}f}{unit}"
