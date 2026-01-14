"""Binary sensor platform for Unraid Management Agent."""

from __future__ import annotations

import logging
import re
from typing import Any

from homeassistant.components.binary_sensor import (
    BinarySensorDeviceClass,
    BinarySensorEntity,
)
from homeassistant.config_entries import ConfigEntry
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback

from . import UnraidConfigEntry, UnraidDataUpdateCoordinator
from .const import ATTR_PARITY_CHECK_STATUS
from .entity import UnraidEntity

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, so no parallel update limit
PARALLEL_UPDATES = 0


def _is_physical_network_interface(interface_name: str) -> bool:
    """Check if the network interface is a physical interface."""
    physical_patterns = [
        r"^eth\d+$",
        r"^wlan\d+$",
        r"^bond\d+$",
        r"^eno\d+$",
        r"^enp\d+s\d+$",
    ]
    for pattern in physical_patterns:
        if re.match(pattern, interface_name):
            return True
    return False


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddEntitiesCallback,
) -> None:
    """Set up Unraid binary sensor entities."""
    coordinator = entry.runtime_data.coordinator
    data = coordinator.data

    entities: list[BinarySensorEntity] = []

    # Array binary sensors
    entities.extend(
        [
            UnraidArrayStartedBinarySensor(coordinator, entry),
            UnraidParityCheckRunningBinarySensor(coordinator, entry),
            UnraidParityValidBinarySensor(coordinator, entry),
        ]
    )

    # UPS binary sensor (only if UPS is connected)
    if data and data.ups and getattr(data.ups, "connected", False):
        entities.append(UnraidUPSConnectedBinarySensor(coordinator, entry))

    # Network interface binary sensors (only physical interfaces)
    for interface in (data.network if data else []) or []:
        interface_name = getattr(interface, "name", "unknown")
        if _is_physical_network_interface(interface_name):
            entities.append(
                UnraidNetworkInterfaceBinarySensor(coordinator, entry, interface_name)
            )

    # ZFS available binary sensor (if ZFS pools exist)
    zfs_pools = data.zfs_pools if data else []
    if zfs_pools and len(zfs_pools) > 0:
        entities.append(UnraidZFSAvailableBinarySensor(coordinator, entry))

    _LOGGER.debug("Adding %d Unraid binary sensor entities", len(entities))
    async_add_entities(entities)


class UnraidBinarySensorBase(UnraidEntity, BinarySensorEntity):
    """Base class for Unraid binary sensors."""


# Array Binary Sensors


class UnraidArrayStartedBinarySensor(UnraidBinarySensorBase):
    """Array started binary sensor."""

    _attr_name = "Array Started"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:harddisk"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_array_started"

    @property
    def is_on(self) -> bool:
        """Return true if array is started."""
        data = self.coordinator.data
        if data and data.array:
            state = getattr(data.array, "state", "").lower()
            return state == "started"
        return False


class UnraidParityCheckRunningBinarySensor(UnraidBinarySensorBase):
    """Parity check running binary sensor."""

    _attr_name = "Parity Check Running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:shield-check"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_parity_check_running"

    @property
    def is_on(self) -> bool:
        """Return true if parity check is in progress."""
        data = self.coordinator.data
        if not data or not data.array:
            return False

        # Check if parity check status exists
        parity_status = getattr(data.array, "parity_check_status", None)
        if parity_status:
            status = getattr(parity_status, "status", "").lower()
            return status in ("running", "paused", "checking")
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.array:
            return {}

        parity_status = getattr(data.array, "parity_check_status", None)
        if not parity_status:
            return {}

        status = getattr(parity_status, "status", None)
        return {
            ATTR_PARITY_CHECK_STATUS: status,
            "is_paused": status.lower() == "paused" if status else False,
        }


class UnraidParityValidBinarySensor(UnraidBinarySensorBase):
    """Parity valid binary sensor."""

    _attr_name = "Parity Valid"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = "mdi:shield-check"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_parity_valid"

    @property
    def is_on(self) -> bool:
        """Return true if parity has a problem (inverted for PROBLEM device class)."""
        data = self.coordinator.data
        if data and data.array:
            # For PROBLEM device class, ON means there IS a problem
            parity_valid = getattr(data.array, "parity_valid", True)
            return not parity_valid
        return False


# UPS Binary Sensor


class UnraidUPSConnectedBinarySensor(UnraidBinarySensorBase):
    """UPS connected binary sensor."""

    _attr_name = "UPS Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = "mdi:battery"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ups_connected"

    @property
    def is_on(self) -> bool:
        """Return true if UPS is connected."""
        data = self.coordinator.data
        if data and data.ups:
            return getattr(data.ups, "connected", False)
        return False


# Network Interface Binary Sensors


class UnraidNetworkInterfaceBinarySensor(UnraidBinarySensorBase):
    """Network interface up/down binary sensor."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
        interface_name: str,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator, entry)
        self._interface_name = interface_name
        self._attr_name = f"Network {interface_name}"
        self._attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
        self._attr_icon = "mdi:ethernet"
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_network_{self._interface_name}"

    @property
    def is_on(self) -> bool:
        """Return true if interface is up."""
        data = self.coordinator.data
        if not data or not data.network:
            return False

        for interface in data.network:
            if getattr(interface, "name", "") == self._interface_name:
                state = getattr(interface, "state", "down")
                return state == "up"
        return False


# ZFS Binary Sensors


class UnraidZFSAvailableBinarySensor(UnraidBinarySensorBase):
    """Binary sensor indicating if ZFS is available/installed."""

    _attr_name = "ZFS Available"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = "mdi:database"
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_zfs_available"

    @property
    def is_on(self) -> bool:
        """Return true if ZFS is available."""
        data = self.coordinator.data
        if data and data.zfs_pools:
            return len(data.zfs_pools) > 0
        return False

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        data = self.coordinator.data
        if not data or not data.zfs_pools:
            return {"pool_count": 0}
        return {"pool_count": len(data.zfs_pools)}
