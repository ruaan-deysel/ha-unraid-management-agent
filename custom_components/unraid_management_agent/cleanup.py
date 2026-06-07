"""
Stale entity registry cleanup for the Unraid Management Agent integration.

Dynamic entities (containers, VMs, disks, fans, etc.) are created at setup
and whenever new items appear. When items are permanently removed from Unraid,
their HA entity registry entries linger indefinitely. This module removes them.

Cleanup runs on every successful coordinator update and is a no-op when the
coordinator has no data (server unreachable), preventing false removal during
transient outages.
"""

from __future__ import annotations

import hashlib
import logging
import re
from typing import TYPE_CHECKING

from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers import entity_registry as er
from homeassistant.util import slugify

if TYPE_CHECKING:
    from .coordinator import UnraidConfigEntry, UnraidData, UnraidDataUpdateCoordinator

_LOGGER = logging.getLogger(__name__)

# Prefixes that identify entity keys belonging to dynamic entities.
# Any key that starts with one of these AND is absent from the valid-key set
# is a stale entity eligible for removal.
_DYNAMIC_KEY_PREFIXES: tuple[str, ...] = (
    "container_",
    "vm_",
    "disk_",
    "fan_",  # covers fan_{name} sensors and fan_speed_{id} numbers
    "gpu_",
    "network_service_",
    "network_",  # per-interface binary sensors + rx/tx sensors
    "share_",
    "zfs_",  # covers dynamic pool sensors; static zfs_available/zfs_arc_* added to valid set
    "remote_share_",
    "unassigned_device_",
    "user_script_",
)

# Static entity keys that start with a dynamic prefix and must never be removed.
# Adding them to the valid set prevents accidental removal.
_ALWAYS_VALID_KEYS: frozenset[str] = frozenset(
    [
        "zfs_available",  # binary_sensor - static, key starts with "zfs_"
        "zfs_arc_hit_ratio",  # sensor - static, key starts with "zfs_"
        "zfs_arc_configured_max",  # sensor - static, key starts with "zfs_"
    ]
)


def _container_switch_key(name: str) -> str:
    """Return the container switch entity key suffix for a given container name."""
    slug = slugify(name)
    name_hash = hashlib.md5(name.encode(), usedforsecurity=False).hexdigest()[:6]
    return f"container_{slug}_{name_hash}"


def _sanitize_for_sensor(name: str) -> str:
    """Return name sanitized the way UnraidContainerSensorBase does."""
    return re.sub(r"[^a-z0-9_]", "_", name.lower())


def _user_script_key(name: str) -> str:
    """Return the user script button entity key suffix."""
    return f"user_script_{re.sub(r'[^a-z0-9_]', '_', name.lower())}"


def _build_valid_dynamic_entity_keys(data: UnraidData) -> set[str]:
    """
    Compute the complete set of valid dynamic entity key suffixes from coordinator data.

    Each entry is the portion of a unique_id that follows ``{entry_id}_``.  Only
    keys for currently-present dynamic items are included; static entity keys are
    handled by ``_ALWAYS_VALID_KEYS`` and by not matching any dynamic prefix.

    Args:
        data: Current coordinator data snapshot.

    Returns:
        Set of valid entity key suffixes.

    """
    keys: set[str] = set(_ALWAYS_VALID_KEYS)

    # ── Containers ──────────────────────────────────────────────────────────
    for container in data.containers or []:
        name = getattr(container, "name", None)
        if not name:
            continue
        switch_key = _container_switch_key(name)  # already includes "container_" prefix
        safe_sensor = _sanitize_for_sensor(name)
        safe_slug = slugify(name)
        keys.add(switch_key)  # switch: "container_{slug}_{hash}"
        keys.add(f"{switch_key}_autostart")  # switch: autostart
        keys.add(f"container_{safe_slug}_restart")  # button
        keys.add(f"container_{safe_sensor}_cpu")  # sensor
        keys.add(f"container_{safe_sensor}_memory")  # sensor
        keys.add(f"container_{safe_sensor}_memory_percent")  # sensor
        keys.add(f"container_{safe_sensor}_restart_count")  # sensor
        keys.add(f"container_{safe_sensor}_network_rx_rate")  # sensor
        keys.add(f"container_{safe_sensor}_network_tx_rate")  # sensor

    # ── Virtual Machines ─────────────────────────────────────────────────────
    for vm in data.vms or []:
        vm_id = getattr(vm, "id", None) or getattr(vm, "name", None)
        vm_name = getattr(vm, "name", None)
        if not vm_id or not vm_name:
            continue

        # Switch key (mirrors _make_vm_unique_key in switch.py)
        if vm_id != vm_name:
            switch_safe = slugify(vm_id)
        else:
            vm_slug = slugify(vm_name)
            vm_hash = hashlib.md5(vm_name.encode(), usedforsecurity=False).hexdigest()[
                :6
            ]
            switch_safe = f"{vm_slug}_{vm_hash}"
        keys.add(f"vm_{switch_safe}")  # switch

        # Button keys (mirrors _UnraidVMButtonBase in button.py)
        short_hash = hashlib.md5(vm_id.encode(), usedforsecurity=False).hexdigest()[:8]
        vm_slug = slugify(vm_name)
        for suffix in ("force_stop", "restart", "pause", "resume", "reset"):
            keys.add(f"vm_{vm_slug}_{short_hash}_{suffix}")  # button

    # ── Disks ────────────────────────────────────────────────────────────────
    for disk in data.disks or []:
        if not getattr(disk, "is_physical", False):
            continue
        disk_id = str(getattr(disk, "id", None) or getattr(disk, "name", ""))
        disk_name = str(getattr(disk, "name", ""))
        if not disk_id:
            continue
        disk_role = str(getattr(disk, "role", "") or "")
        slug = slugify(disk_name)

        keys.add(f"disk_{slug}_spin")  # switch
        keys.add(f"disk_{disk_id}_health")  # sensor
        keys.add(f"disk_{disk_id}_temperature")  # sensor
        keys.add(f"disk_{disk_id}_smart_errors")  # sensor
        keys.add(f"disk_{disk_id}_read_bytes")  # sensor
        keys.add(f"disk_{disk_id}_write_bytes")  # sensor
        if disk_role not in ("parity", "parity2"):
            keys.add(f"disk_{disk_id}_usage")  # sensor

    # ── Fans (RPM sensors from system info) ───────────────────────────────────
    if data.system and data.system.fans:
        seen_normalized: set[str] = set()
        for idx, fan in enumerate(data.system.fans):
            if isinstance(fan, dict):
                normalized = fan.get("name") or f"fan_{idx}"
            elif isinstance(fan, (int, float)):
                normalized = f"fan_{idx}"
            else:
                raw = getattr(fan, "name", None) or f"fan_{idx}"
                normalized = getattr(fan, "normalized_name", None) or raw
            if normalized in seen_normalized:
                normalized = f"{normalized}_{idx}"
            seen_normalized.add(normalized)
            sanitized = normalized.lower().replace(" ", "_")
            keys.add(f"fan_{sanitized}")  # sensor

    # ── Fan speed numbers (from fan_control) ──────────────────────────────────
    if data.fan_control and data.fan_control.fans:
        for fan in data.fan_control.fans:
            fan_id = getattr(fan, "id", None)
            if fan_id and getattr(fan, "controllable", False):
                sanitized = fan_id.lower().replace(" ", "_")
                keys.add(f"fan_speed_{sanitized}")  # number

    # ── GPUs ─────────────────────────────────────────────────────────────────
    for idx, gpu in enumerate(data.gpu or []):
        gpu_index = getattr(gpu, "index", None)
        if gpu_index is None:
            gpu_index = idx
        for sensor_type in ("utilization", "temperature", "power", "energy"):
            keys.add(f"gpu_{gpu_index}_{sensor_type}")  # sensor

    # ── Network interfaces ────────────────────────────────────────────────────
    for interface in data.network or []:
        iface_name = getattr(interface, "name", None)
        if iface_name and getattr(interface, "is_physical", False):
            keys.add(f"network_{iface_name}")  # binary sensor
            # RX/TX sensors are only created for "up" interfaces, but keep their
            # keys valid even if the interface is down to avoid removal during
            # transient link drops.
            keys.add(f"network_{iface_name}_rx")  # sensor
            keys.add(f"network_{iface_name}_tx")  # sensor

    # ── Network services ──────────────────────────────────────────────────────
    if data.network_services:
        for service_key in (
            "smb",
            "nfs",
            "afp",
            "ftp",
            "ssh",
            "telnet",
            "avahi",
            "netbios",
            "wsd",
            "wireguard",
            "upnp",
            "ntp",
            "syslog",
        ):
            if getattr(data.network_services, service_key, None) is not None:
                keys.add(f"network_service_{slugify(service_key)}")  # binary sensor

    # ── User shares ───────────────────────────────────────────────────────────
    for share in data.shares or []:
        name = getattr(share, "name", None)
        if name:
            keys.add(f"share_{name}_usage")  # sensor

    # ── ZFS pools ─────────────────────────────────────────────────────────────
    for pool in data.zfs_pools or []:
        name = getattr(pool, "name", None)
        if name:
            keys.add(f"zfs_{name}_usage")  # sensor
            keys.add(f"zfs_{name}_health")  # sensor
            keys.add(f"zfs_{name}_corrupted_files")  # sensor

    # ── Remote shares ─────────────────────────────────────────────────────────
    for share in data.remote_shares or []:
        name = getattr(share, "name", None)
        if name:
            slug = slugify(name)
            keys.add(f"remote_share_{slug}_mounted")  # binary sensor
            keys.add(f"remote_share_{slug}_mount")  # switch
            keys.add(f"remote_share_{slug}_usage")  # sensor

    # ── Unassigned devices ────────────────────────────────────────────────────
    for device in data.unassigned_devices or []:
        device_name = getattr(device, "name", None) or getattr(device, "device", None)
        if device_name:
            slug = slugify(device_name)
            keys.add(f"unassigned_device_{slug}_mounted")  # binary sensor
            keys.add(f"unassigned_device_{slug}_size")  # sensor

    # ── User scripts ──────────────────────────────────────────────────────────
    for script in data.user_scripts or []:
        name = getattr(script, "name", "") or ""
        if name:
            keys.add(_user_script_key(name))  # button

    return keys


def _is_dynamic_key(key: str) -> bool:
    """Return True if *key* belongs to a dynamic entity type that can become stale."""
    return any(key.startswith(prefix) for prefix in _DYNAMIC_KEY_PREFIXES)


@callback
def async_cleanup_stale_entities(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    coordinator: UnraidDataUpdateCoordinator,
) -> None:
    """
    Remove entity registry entries for items no longer present in coordinator data.

    Guards:
    - Runs only when ``coordinator.last_update_success`` is True (server reachable).
    - Runs only when ``coordinator.data`` is not None (first fetch completed).
    - Skips static entities (those whose key does not start with a dynamic prefix).

    Args:
        hass: Home Assistant instance.
        entry: Config entry for this integration instance.
        coordinator: Data coordinator with current data.

    """
    if not coordinator.last_update_success or coordinator.data is None:
        return

    registry = er.async_get(hass)
    entry_prefix = f"{entry.entry_id}_"
    valid_keys = _build_valid_dynamic_entity_keys(coordinator.data)

    removed = 0
    for entity_entry in er.async_entries_for_config_entry(registry, entry.entry_id):
        unique_id = entity_entry.unique_id
        if not unique_id.startswith(entry_prefix):
            continue

        key = unique_id[len(entry_prefix) :]

        if _is_dynamic_key(key) and key not in valid_keys:
            _LOGGER.debug(
                "Removing stale entity %s (unique_id=%s)",
                entity_entry.entity_id,
                unique_id,
            )
            registry.async_remove(entity_entry.entity_id)
            removed += 1

    if removed:
        _LOGGER.info(
            "Removed %d stale %s entity registry entries",
            removed,
            entry.title,
        )
