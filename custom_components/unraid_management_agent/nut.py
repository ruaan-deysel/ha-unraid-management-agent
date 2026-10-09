"""
Helpers for NUT (Network UPS Tools) devices beyond the primary UPS.

The primary UPS keeps its original ``ups_*`` entities, which read ``/ups``.
Every other NUT device the agent reports in ``/nut`` ``statuses`` (a second
UPS, an ATS, ...) gets its own ``nut_<device>_*`` entities.
"""

from __future__ import annotations

from typing import TYPE_CHECKING, Final

from homeassistant.util import slugify

if TYPE_CHECKING:
    from .api.models import NUTDeviceStatus
    from .coordinator import UnraidData

NUT_KEY_PREFIX: Final = "nut_"

# Suffixes of the per-device entity keys: nut_<device>_<suffix>
NUT_SENSOR_SUFFIXES: Final = ("battery", "load", "runtime", "power", "energy")
NUT_BINARY_SENSOR_SUFFIXES: Final = ("connected",)


def nut_device_key(device_name: str) -> str:
    """Return the entity key prefix for a NUT device, e.g. ``nut_ups_gpu``."""
    return f"{NUT_KEY_PREFIX}{slugify(device_name)}"


def _primary_nut_device_name(data: UnraidData) -> str | None:
    """
    Return the NUT device that the ``ups_*`` entities already cover.

    That is the device ``/ups`` reports (``device_name``). Without a device
    name, ``/ups`` comes from apcupsd or an older agent, so no NUT device is
    covered. Without ``/ups`` data at all, the first NUT device is assumed to
    be the primary, as the agent's ``/ups`` uses it.
    """
    if data.ups is not None:
        return data.ups.device_name
    if data.nut is not None and data.nut.statuses:
        return data.nut.statuses[0].device_name
    return None


def secondary_nut_statuses(
    data: UnraidData | None,
) -> list[tuple[str, NUTDeviceStatus]]:
    """Return (name, status) of every NUT device other than the primary UPS."""
    if data is None or data.nut is None or not data.nut.statuses:
        return []
    primary = _primary_nut_device_name(data)
    return [
        (status.device_name, status)
        for status in data.nut.statuses
        if status.device_name and status.device_name != primary
    ]


def secondary_nut_device_names(data: UnraidData) -> set[str]:
    """
    Return the names of NUT devices other than the primary UPS.

    Uses the device list (``upsc -l``) as well as the statuses, so a device
    that misses one query is still known and its entities are kept.
    """
    if data.nut is None:
        return set()
    primary = _primary_nut_device_name(data)
    names = {status.device_name for status in data.nut.statuses or []}
    names.update(device.name for device in data.nut.devices or [])
    return {name for name in names if name and name != primary}


def find_nut_status(
    data: UnraidData | None, device_name: str
) -> NUTDeviceStatus | None:
    """Return the current status of a NUT device, or None if it did not answer."""
    if data is None or data.nut is None:
        return None
    return next(
        (s for s in data.nut.statuses or [] if s.device_name == device_name), None
    )
