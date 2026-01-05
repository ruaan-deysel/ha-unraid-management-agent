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
from homeassistant.const import CONF_HOST
from homeassistant.core import HomeAssistant
from homeassistant.helpers.entity import EntityCategory
from homeassistant.helpers.entity_platform import AddEntitiesCallback
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from . import UnraidConfigEntry, UnraidDataUpdateCoordinator
from .const import (
    ATTR_PARITY_CHECK_STATUS,
    DOMAIN,
    ICON_ARRAY,
    ICON_NETWORK,
    ICON_PARITY,
    ICON_UPS,
    ICON_ZFS,
    KEY_ARRAY,
    KEY_NETWORK,
    KEY_SYSTEM,
    KEY_UPS,
    KEY_ZFS_POOLS,
    MANUFACTURER,
)

_LOGGER = logging.getLogger(__name__)

# Coordinator handles updates, so no parallel update limit
PARALLEL_UPDATES = 0


def _is_physical_network_interface(interface_name: str) -> bool:
    """
    Check if the network interface is a physical interface.

    Only include physical interfaces like eth0, eth1, wlan0, bond0, etc.
    Exclude virtual interfaces (veth*, br-*, docker*, virbr*) and loopback (lo).
    """
    # Patterns for physical interfaces
    physical_patterns = [
        r"^eth\d+$",  # Ethernet: eth0, eth1, etc.
        r"^wlan\d+$",  # Wireless: wlan0, wlan1, etc.
        r"^bond\d+$",  # Bonded interfaces: bond0, bond1, etc.
        r"^eno\d+$",  # Onboard Ethernet: eno1, eno2, etc.
        r"^enp\d+s\d+$",  # PCI Ethernet: enp2s0, etc.
    ]

    # Check if interface matches any physical pattern
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

    entities: list[BinarySensorEntity] = []

    # Array binary sensors
    entities.extend(
        [
            UnraidArrayStartedBinarySensor(coordinator, entry),
            UnraidParityCheckRunningBinarySensor(coordinator, entry),
            UnraidParityValidBinarySensor(coordinator, entry),
        ]
    )

    # UPS binary sensor (if UPS exists)
    # Only create if UPS data exists and is not an empty dict
    # When no UPS hardware is present, the API returns null/error and coordinator sets KEY_UPS to {}
    ups_data = coordinator.data.get(KEY_UPS, {})
    if ups_data and isinstance(ups_data, dict) and len(ups_data) > 0:
        entities.append(UnraidUPSConnectedBinarySensor(coordinator, entry))

    # Network interface binary sensors (only physical interfaces)
    for interface in coordinator.data.get(KEY_NETWORK, []):
        interface_name = interface.get("name", "unknown")
        # Only create sensors for physical network interfaces
        if _is_physical_network_interface(interface_name):
            entities.append(
                UnraidNetworkInterfaceBinarySensor(coordinator, entry, interface_name)
            )

    # ZFS binary sensors (if ZFS pools available)
    # Only create if ZFS pools data exists and is not empty
    zfs_pools = coordinator.data.get(KEY_ZFS_POOLS, [])
    if zfs_pools and isinstance(zfs_pools, list) and len(zfs_pools) > 0:
        # ZFS Available binary sensor (indicates ZFS is installed/detected)
        entities.append(UnraidZFSAvailableBinarySensor(coordinator, entry))

    async_add_entities(entities)


class UnraidBinarySensorBase(CoordinatorEntity, BinarySensorEntity):
    """Base class for Unraid binary sensors."""

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the binary sensor."""
        super().__init__(coordinator)
        self._attr_has_entity_name = True
        self._entry = entry

    @property
    def device_info(self) -> dict[str, Any]:
        """Return device information."""
        system_data = self.coordinator.data.get(KEY_SYSTEM, {})
        hostname = system_data.get("hostname", "Unraid")
        version = system_data.get("version", "Unknown")
        host = self._entry.data.get(CONF_HOST, "")

        return {
            "identifiers": {(DOMAIN, self._entry.entry_id)},
            "name": hostname,
            "manufacturer": MANUFACTURER,
            "model": f"Unraid {version}",
            "sw_version": version,
            "configuration_url": f"http://{host}",
        }


# Array Binary Sensors


class UnraidArrayStartedBinarySensor(UnraidBinarySensorBase):
    """Array started binary sensor."""

    _attr_name = "Array Started"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = ICON_ARRAY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_array_started"

    @property
    def is_on(self) -> bool:
        """Return true if array is started."""
        state = self.coordinator.data.get(KEY_ARRAY, {}).get("state", "").lower()
        return state == "started"


class UnraidParityCheckRunningBinarySensor(UnraidBinarySensorBase):
    """Parity check running binary sensor."""

    _attr_name = "Parity Check Running"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = ICON_PARITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_parity_check_running"

    @property
    def is_on(self) -> bool:
        """Return true if parity check is in progress (running or paused)."""
        array_data = self.coordinator.data.get(KEY_ARRAY, {})

        # Check the boolean flag first (if available from API)
        parity_running = array_data.get("parity_check_running")
        if parity_running is True:
            return True

        # Fall back to checking status string
        # Consider both "running" and "paused" as "in progress"
        status = array_data.get("parity_check_status", "").lower()
        return status in ("running", "paused", "checking")

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        array_data = self.coordinator.data.get(KEY_ARRAY, {})
        return {
            ATTR_PARITY_CHECK_STATUS: array_data.get("parity_check_status"),
            "is_paused": array_data.get("parity_check_status", "").lower() == "paused",
        }


class UnraidParityValidBinarySensor(UnraidBinarySensorBase):
    """Parity valid binary sensor."""

    _attr_name = "Parity Valid"
    _attr_device_class = BinarySensorDeviceClass.PROBLEM
    _attr_icon = ICON_PARITY
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_parity_valid"

    @property
    def is_on(self) -> bool:
        """Return true if parity is valid (inverted for problem device class)."""
        # For PROBLEM device class, ON means there IS a problem
        # So we invert: parity_valid=true means NO problem (OFF)
        parity_valid = self.coordinator.data.get(KEY_ARRAY, {}).get(
            "parity_valid", True
        )
        return not parity_valid


# UPS Binary Sensor


class UnraidUPSConnectedBinarySensor(UnraidBinarySensorBase):
    """UPS connected binary sensor."""

    _attr_name = "UPS Connected"
    _attr_device_class = BinarySensorDeviceClass.CONNECTIVITY
    _attr_icon = ICON_UPS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_ups_connected"

    @property
    def is_on(self) -> bool:
        """Return true if UPS is connected."""
        return self.coordinator.data.get(KEY_UPS, {}).get("connected", False)


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
        self._attr_icon = ICON_NETWORK
        self._attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_network_{self._interface_name}"

    @property
    def is_on(self) -> bool:
        """Return true if interface is up."""
        for interface in self.coordinator.data.get(KEY_NETWORK, []):
            if interface.get("name") == self._interface_name:
                # API returns "state" field with values like "up", "down", "lowerlayerdown"
                state = interface.get("state", "down")
                return state == "up"
        return False


# ZFS Binary Sensors


class UnraidZFSAvailableBinarySensor(UnraidBinarySensorBase):
    """Binary sensor indicating if ZFS is available/installed."""

    _attr_name = "ZFS Available"
    _attr_device_class = BinarySensorDeviceClass.RUNNING
    _attr_icon = ICON_ZFS
    _attr_entity_category = EntityCategory.DIAGNOSTIC

    @property
    def unique_id(self) -> str:
        """Return unique ID."""
        return f"{self._entry.entry_id}_zfs_available"

    @property
    def is_on(self) -> bool:
        """Return true if ZFS is available."""
        zfs_pools = self.coordinator.data.get(KEY_ZFS_POOLS, [])
        return isinstance(zfs_pools, list) and len(zfs_pools) > 0

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes."""
        zfs_pools = self.coordinator.data.get(KEY_ZFS_POOLS, [])
        return {
            "pool_count": len(zfs_pools) if isinstance(zfs_pools, list) else 0,
        }
