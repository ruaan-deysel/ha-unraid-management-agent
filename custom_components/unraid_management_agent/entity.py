"""Base entity classes for Unraid Management Agent."""

from __future__ import annotations

from collections.abc import Callable
from dataclasses import dataclass
from typing import TYPE_CHECKING, Any

from homeassistant.components.sensor import SensorEntityDescription
from homeassistant.const import CONF_HOST
from homeassistant.helpers.device_registry import DeviceInfo
from homeassistant.helpers.entity import EntityDescription
from homeassistant.helpers.update_coordinator import CoordinatorEntity

from .const import DOMAIN, MANUFACTURER

if TYPE_CHECKING:
    from .coordinator import UnraidData, UnraidDataUpdateCoordinator


@dataclass(frozen=True, kw_only=True)
class UnraidEntityDescription(EntityDescription):
    """Base description for all Unraid entities."""

    available_fn: Callable[[UnraidDataUpdateCoordinator], bool] = lambda _: True
    supported_fn: Callable[[UnraidDataUpdateCoordinator], bool] = lambda _: True


@dataclass(frozen=True, kw_only=True)
class UnraidSensorEntityDescription(SensorEntityDescription):
    """Description for Unraid sensor entities with value_fn pattern."""

    value_fn: Callable[[UnraidData], Any] = lambda _: None
    extra_state_attributes_fn: Callable[[UnraidData], dict[str, Any]] | None = None
    available_fn: Callable[[UnraidData], bool] = lambda data: data is not None
    supported_fn: Callable[[UnraidData], bool] = lambda _: True


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


# Export these for external use
__all__ = [
    "UnraidBaseEntity",
    "UnraidEntity",
    "UnraidEntityDescription",
    "UnraidSensorEntityDescription",
]
