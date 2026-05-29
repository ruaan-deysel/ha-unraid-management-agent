"""Event platform for Unraid Management Agent — Unraid notification events."""

from __future__ import annotations

import logging
from typing import Any, ClassVar

from homeassistant.components.event import EventEntity
from homeassistant.core import HomeAssistant, callback
from homeassistant.helpers.entity_platform import AddConfigEntryEntitiesCallback

from . import UnraidConfigEntry
from .coordinator import UnraidDataUpdateCoordinator
from .entity import UnraidBaseEntity

_LOGGER = logging.getLogger(__name__)

PARALLEL_UPDATES = 0


async def async_setup_entry(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    async_add_entities: AddConfigEntryEntitiesCallback,
) -> None:
    """Set up Unraid event entities."""
    coordinator = entry.runtime_data.coordinator
    async_add_entities([UnraidNotificationEvent(coordinator, entry)])


class UnraidNotificationEvent(UnraidBaseEntity, EventEntity):
    """Event entity that fires when Unraid notifications arrive."""

    _attr_translation_key = "notification_event"
    _attr_event_types: ClassVar[list[str]] = ["info", "warning", "alert"]
    _attr_icon = "mdi:bell-ring"

    def __init__(
        self,
        coordinator: UnraidDataUpdateCoordinator,
        entry: UnraidConfigEntry,
    ) -> None:
        """Initialize the event entity."""
        super().__init__(coordinator, "notification_event")
        self._seen_ids: set[str] = set()

    @callback
    def _handle_coordinator_update(self) -> None:
        """Fire an HA event for each new Unraid notification."""
        data = self.coordinator.data
        if not data or not data.notifications:
            super()._handle_coordinator_update()
            return

        notifications_response = data.notifications
        notif_list = getattr(notifications_response, "notifications", None) or []

        new_notifications = [
            n for n in notif_list if n.id and n.id not in self._seen_ids
        ]

        if new_notifications:
            for notif in new_notifications:
                if notif.id:
                    self._seen_ids.add(notif.id)
                importance = (notif.importance or "info").lower()
                event_type = (
                    importance if importance in self._attr_event_types else "info"
                )
                event_data: dict[str, Any] = {}
                if notif.id:
                    event_data["id"] = notif.id
                if notif.subject:
                    event_data["subject"] = notif.subject
                if notif.description:
                    event_data["description"] = notif.description
                if notif.importance:
                    event_data["importance"] = notif.importance
                if notif.timestamp:
                    event_data["timestamp"] = notif.timestamp
                self._trigger_event(event_type, event_data)

        super()._handle_coordinator_update()
