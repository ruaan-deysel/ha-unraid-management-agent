"""Number platform for Unraid Management Agent — fan speed control."""

from __future__ import annotations

import logging
from typing import Any

from homeassistant.components.number import NumberEntity, NumberMode
from homeassistant.const import PERCENTAGE, EntityCategory
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnraidConfigEntry
from .const import CONF_ENABLE_FAN_CONTROL, DEFAULT_ENABLE_FAN_CONTROL, DOMAIN
from .coordinator import UnraidDataUpdateCoordinator
from .entity import UnraidBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Unraid number entities for fan control."""
    fan_control_enabled = entry.options.get(
        CONF_ENABLE_FAN_CONTROL, DEFAULT_ENABLE_FAN_CONTROL
    )
    if not fan_control_enabled:
        return

    coordinator = entry.runtime_data.coordinator
    data = coordinator.data

    entities: list[NumberEntity] = []

    if data and data.fan_control and data.fan_control.fans:
        for fan in data.fan_control.fans:
            if fan.id and fan.controllable:
                entities.append(
                    UnraidFanSpeedNumber(coordinator, entry, fan.id, fan.name or fan.id)
                )

    if entities:
        _LOGGER.debug("Adding %d Unraid fan speed number entities", len(entities))
    async_add_entities(entities)


class UnraidFanSpeedNumber(UnraidBaseEntity, NumberEntity):
    """Number entity to set a controllable fan's speed percentage."""

    _attr_native_min_value = 0
    _attr_native_max_value = 100
    _attr_native_step = 1
    _attr_native_unit_of_measurement = PERCENTAGE
    _attr_mode = NumberMode.SLIDER
    _attr_icon = "mdi:fan"
    _attr_entity_category = EntityCategory.CONFIG

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
        fan_id: str,
        fan_display_name: str,
    ) -> None:
        """Initialize the fan speed number entity."""
        sanitized = fan_id.lower().replace(" ", "_")
        super().__init__(coordinator, f"fan_speed_{sanitized}")
        self._fan_id = fan_id
        self._fan_display_name = fan_display_name
        self._attr_translation_key = "fan_speed"
        self._attr_translation_placeholders = {"name": fan_display_name}

    def _get_fan_device(self) -> Any:
        """Return the FanDevice matching this entity's fan_id."""
        data = self.coordinator.data
        if not data or not data.fan_control:
            return None
        for fan in data.fan_control.fans or []:
            if fan.id == self._fan_id:
                return fan
        return None

    @property
    def native_value(self) -> float | None:
        """Return the current PWM speed percentage."""
        device = self._get_fan_device()
        if device is not None and device.pwm_percent is not None:
            return round(float(device.pwm_percent), 1)
        return None

    @property
    def extra_state_attributes(self) -> dict[str, Any]:
        """Return extra attributes from fan control data."""
        attrs: dict[str, Any] = {"fan_id": self._fan_id}
        device = self._get_fan_device()
        if device is not None:
            if device.rpm is not None:
                attrs["rpm"] = device.rpm
            if device.mode is not None:
                attrs["mode"] = device.mode
            if device.pwm_value is not None:
                attrs["pwm_value"] = device.pwm_value
        return attrs

    @property
    def available(self) -> bool:
        """Return True only when the fan is in manual mode and controllable."""
        if not super().available:
            return False
        device = self._get_fan_device()
        if device is None:
            return False
        return bool(device.controllable)

    async def async_set_native_value(self, value: float) -> None:
        """Set fan speed percentage via the UMA API."""
        client = self.coordinator.config_entry.runtime_data.client
        try:
            await client.set_fan_speed(self._fan_id, int(value))
        except Exception as err:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="fan_speed_set_failed",
            ) from err
        await self.coordinator.async_request_refresh()
