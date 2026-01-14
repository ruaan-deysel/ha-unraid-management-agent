"""Base entity classes for Unraid Management Agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.config_entries import ConfigEntry
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER

if TYPE_CHECKING:
    from . import UnraidDataUpdateCoordinator


@dataclass
class UnraidData:
    """Container for Unraid coordinator data."""

    system: Any = None
    array: Any = None
    disks: list[Any] | None = None
    containers: list[Any] | None = None
    vms: list[Any] | None = None
    ups: Any = None
    gpu: list[Any] | None = None
    network: list[Any] | None = None
    shares: list[Any] | None = None
    notifications: list[Any] | None = None
    user_scripts: list[Any] | None = None
    zfs_pools: list[Any] | None = None
    zfs_datasets: list[Any] | None = None
    zfs_snapshots: list[Any] | None = None
    zfs_arc: Any = None


@dataclass(frozen=True, kw_only=True)
class UnraidEntityDescription(EntityDescription):
    """Base description for all Unraid entities."""

    available_fn: Callable[[UnraidDataUpdateCoordinator], bool] = lambda _: True
    supported_fn: Callable[[UnraidDataUpdateCoordinator], bool] = lambda _: True


class UnraidBaseEntity(CoordinatorEntity["UnraidDataUpdateCoordinator"]):
    """Base entity for Unraid Management Agent."""

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        key: str,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._attr_unique_id = f"{coordinator.config_entry.entry_id}_{key}"
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> DeviceInfo:
        """Build device info for this entity."""
        data = self.coordinator.data
        system = data.system if data else None

        hostname = "Unraid"
        version = "Unknown"
        agent_version = None
        host = self.coordinator.config_entry.data.get(CONF_HOST, "")

        if system:
            hostname = system.hostname or "Unraid"
            version = system.version or "Unknown"
            agent_version = getattr(system, "agent_version", None)

        device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=hostname,
            manufacturer=MANUFACTURER,
            model=f"Unraid {version}",
            sw_version=version,
            configuration_url=f"http://{host}",
        )

        if agent_version:
            device_info["hw_version"] = agent_version

        return device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )


class UnraidEntity(UnraidBaseEntity):
    """Entity with description support for Unraid Management Agent."""

    entity_description: UnraidEntityDescription

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entity_description: UnraidEntityDescription,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator, entity_description.key)
        self.entity_description = entity_description

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        if super().available:
            return self.entity_description.available_fn(self.coordinator)
        return False


class UnraidLegacyEntity(CoordinatorEntity["UnraidDataUpdateCoordinator"]):
    """
    Legacy entity for backward compatibility (deprecated).

    Use UnraidBaseEntity for new implementations.
    """

    _attr_has_entity_name = True

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: ConfigEntry,
    ) -> None:
        """Initialize the entity."""
        super().__init__(coordinator)
        self._entry = coordinator.config_entry
        self._attr_device_info = self._build_device_info()

    def _build_device_info(self) -> DeviceInfo:
        """Build device info for this entity."""
        data = self.coordinator.data
        system = data.system if data else None

        hostname = "Unraid"
        version = "Unknown"
        agent_version = None
        host = self.coordinator.config_entry.data.get(CONF_HOST, "")

        if system:
            hostname = system.hostname or "Unraid"
            version = system.version or "Unknown"
            agent_version = getattr(system, "agent_version", None)

        device_info = DeviceInfo(
            identifiers={(DOMAIN, self.coordinator.config_entry.entry_id)},
            name=hostname,
            manufacturer=MANUFACTURER,
            model=f"Unraid {version}",
            sw_version=version,
            configuration_url=f"http://{host}",
        )

        if agent_version:
            device_info["hw_version"] = agent_version

        return device_info

    @property
    def available(self) -> bool:
        """Return if entity is available."""
        return (
            self.coordinator.last_update_success and self.coordinator.data is not None
        )
