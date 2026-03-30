"""The Unraid Management Agent integration."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Coroutine
from typing import Any, Final

import voluptuous as vol
from homeassistant.const import CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall
from homeassistant.exceptions import ConfigEntryNotReady, HomeAssistantError
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.util import slugify

from .api import UnraidClient, UnraidConnectionError, UnraidWebSocketClient
from .const import (
    CONF_ENABLE_WEBSOCKET,
    DEFAULT_ENABLE_WEBSOCKET,
    DOMAIN,
)
from .coordinator import (
    UnraidConfigEntry,
    UnraidDataUpdateCoordinator,
    UnraidRuntimeData,
)

# Service field constants
ATTR_CONTAINER_ID: Final = "container_id"
ATTR_VM_ID: Final = "vm_id"

# Service schemas
SERVICE_CONTAINER_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONTAINER_ID): cv.string,
    }
)

SERVICE_VM_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_VM_ID): cv.string,
    }
)

# Re-export for backwards compatibility and for tests to patch
__all__ = [
    "ATTR_CONTAINER_ID",
    "ATTR_VM_ID",
    "UnraidClient",
    "UnraidConfigEntry",
    "UnraidDataUpdateCoordinator",
    "UnraidRuntimeData",
    "UnraidWebSocketClient",
]

_LOGGER = logging.getLogger(__name__)

CONFIG_SCHEMA = cv.config_entry_only_config_schema(DOMAIN)


def _make_entity_name_key(name: str) -> str:
    """Build a stable key from a user-facing name."""
    slug = slugify(name)
    name_hash = hashlib.md5(name.encode(), usedforsecurity=False).hexdigest()[:6]
    return f"{slug}_{name_hash}"


def _make_vm_key(vm_identifier: str, vm_name: str) -> str:
    """Build the canonical VM key used for registry migration."""
    if vm_identifier and vm_identifier != vm_name:
        return slugify(vm_identifier)
    return _make_entity_name_key(vm_name)


def _legacy_disk_key_fragment(disk_id: str) -> str:
    """Build the legacy sanitized disk identifier used by older releases."""
    return disk_id.replace(" ", "_").replace("/", "_").lower()


async def _async_migrate_legacy_entity_unique_ids(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    coordinator: UnraidDataUpdateCoordinator,
) -> None:
    """Migrate legacy entity unique IDs to the current stable schemes."""
    data = coordinator.data
    if data is None:
        return

    registry = er.async_get(hass)
    registry_entries = er.async_entries_for_config_entry(registry, entry.entry_id)
    entries_by_unique_id = {
        (registry_entry.domain, registry_entry.unique_id): registry_entry
        for registry_entry in registry_entries
    }

    def migrate(
        domain: str, old_unique_id: str, new_unique_id: str, label: str
    ) -> None:
        if old_unique_id == new_unique_id:
            return

        source_entry = entries_by_unique_id.get((domain, old_unique_id))
        if source_entry is None:
            return

        if (domain, new_unique_id) in entries_by_unique_id:
            _LOGGER.debug(
                "Skipping legacy unique ID migration for %s because target already exists",
                label,
            )
            return

        try:
            updated_entry = registry.async_update_entity(
                source_entry.entity_id,
                new_unique_id=new_unique_id,
            )
        except ValueError as err:
            _LOGGER.warning(
                "Failed to migrate legacy unique ID for %s: %s",
                label,
                err,
            )
            return

        entries_by_unique_id.pop((domain, old_unique_id), None)
        entries_by_unique_id[(domain, new_unique_id)] = updated_entry
        _LOGGER.info("Migrated legacy unique ID for %s", label)

    if data.containers:
        for container in data.containers:
            container_id = getattr(container, "id", None) or getattr(
                container, "container_id", None
            )
            container_name = getattr(container, "name", None)
            if not container_id or not container_name:
                continue

            migrate(
                "switch",
                f"{entry.entry_id}_container_switch_{container_id}",
                f"{entry.entry_id}_container_{_make_entity_name_key(container_name)}",
                f"container {container_name}",
            )

    if data.vms:
        for vm in data.vms:
            vm_id = getattr(vm, "id", None) or getattr(vm, "name", None)
            vm_name = getattr(vm, "name", None)
            if not vm_id or not vm_name:
                continue

            new_unique_id = f"{entry.entry_id}_vm_{_make_vm_key(vm_id, vm_name)}"

            migrate(
                "switch",
                f"{entry.entry_id}_vm_switch_{vm_id}",
                new_unique_id,
                f"VM {vm_name}",
            )
            migrate(
                "switch",
                f"{entry.entry_id}_vm_{_make_entity_name_key(vm_name)}",
                new_unique_id,
                f"VM {vm_name}",
            )

    if data.disks:
        for disk in data.disks:
            disk_id = getattr(disk, "id", None) or getattr(disk, "name", None)
            if not disk_id:
                continue

            legacy_disk_id = _legacy_disk_key_fragment(disk_id)
            for sensor_type in ("usage", "health", "temperature"):
                migrate(
                    "sensor",
                    f"{entry.entry_id}_disk_{legacy_disk_id}_{sensor_type}",
                    f"{entry.entry_id}_disk_{disk_id}_{sensor_type}",
                    f"disk {disk_id} {sensor_type}",
                )

    if data.system:
        fans = getattr(data.system, "fans", []) or []
        seen_names: set[str] = set()
        for idx, fan in enumerate(fans):
            if isinstance(fan, dict):
                fan_name = fan.get("name") or f"fan_{idx}"
                normalized = fan_name
            else:
                fan_name = getattr(fan, "name", None) or f"fan_{idx}"
                normalized = getattr(fan, "normalized_name", fan_name)

            legacy_fan_name = fan_name
            normalized_key = normalized
            if normalized_key in seen_names:
                normalized_key = f"{normalized}_{idx}"

            seen_names.add(normalized_key)

            migrate(
                "sensor",
                f"{entry.entry_id}_fan_{legacy_fan_name.lower().replace(' ', '_')}",
                f"{entry.entry_id}_fan_{normalized_key.lower().replace(' ', '_')}",
                f"fan {legacy_fan_name}",
            )


PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
]


async def async_setup(hass: HomeAssistant, config: dict) -> bool:
    """Set up Unraid Management Agent integration."""
    # Register services once at integration level (not per entry)
    await async_setup_services(hass)
    return True


async def async_setup_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Set up Unraid Management Agent from a config entry."""
    host = entry.data[CONF_HOST]
    port = entry.data[CONF_PORT]
    enable_websocket = entry.options.get(
        CONF_ENABLE_WEBSOCKET,
        entry.data.get(CONF_ENABLE_WEBSOCKET, DEFAULT_ENABLE_WEBSOCKET),
    )

    # Create UnraidClient using Home Assistant's shared client session (inject-websession)
    session = async_get_clientsession(hass)
    client = UnraidClient(host=host, port=port, session=session)

    # Test connection
    try:
        await client.health_check()
    except UnraidConnectionError as err:
        raise ConfigEntryNotReady(f"Failed to connect to Unraid server: {err}") from err
    except Exception as err:
        raise ConfigEntryNotReady(
            f"Unexpected error connecting to Unraid server: {err}"
        ) from err

    # Create coordinator (now passing entry as per HA best practice)
    coordinator = UnraidDataUpdateCoordinator(
        hass,
        entry=entry,
        client=client,
        enable_websocket=enable_websocket,
    )

    # Fetch initial data
    await coordinator.async_config_entry_first_refresh()

    # Migrate known legacy unique IDs before platforms are set up so existing
    # registry entries keep their original entity_ids instead of creating _2 duplicates.
    await _async_migrate_legacy_entity_unique_ids(hass, entry, coordinator)

    # Store runtime data using the new pattern
    entry.runtime_data = UnraidRuntimeData(coordinator=coordinator, client=client)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, PLATFORMS)

    # Start WebSocket for real-time updates
    if enable_websocket:
        await coordinator.async_start_websocket()

    # Note: We use OptionsFlowWithReload, so no need for manual update listener
    # The reload is handled automatically by Home Assistant

    return True


async def async_unload_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(entry, PLATFORMS):
        # Stop WebSocket if running
        await entry.runtime_data.coordinator.async_stop_websocket()
        # Close the client session
        await entry.runtime_data.client.close()

    return unload_ok


async def async_reload_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> None:
    """Reload config entry when options change."""
    await hass.config_entries.async_reload(entry.entry_id)


async def async_setup_services(hass: HomeAssistant) -> None:
    """Set up services for Unraid Management Agent."""
    # Check if services are already registered
    if hass.services.has_service(DOMAIN, "container_start"):
        return

    def _get_coordinator(call: ServiceCall) -> UnraidDataUpdateCoordinator:
        """Get coordinator from any config entry."""
        entries = hass.config_entries.async_entries(DOMAIN)
        if not entries:
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key="no_config_entries",
            )
        # Use the first entry's coordinator (services are domain-wide)
        entry: UnraidConfigEntry = entries[0]
        return entry.runtime_data.coordinator

    async def _async_service_call(
        call: ServiceCall,
        api_method: Callable[..., Coroutine[Any, Any, Any]],
        translation_key: str,
        *,
        id_attr: str | None = None,
        id_placeholder: str | None = None,
    ) -> None:
        """Execute a service action with standard error handling."""
        coordinator = _get_coordinator(call)
        args: tuple[str, ...] = ()
        placeholders: dict[str, str] | None = None
        if id_attr and id_placeholder:
            resource_id: str = call.data[id_attr]
            args = (resource_id,)
            placeholders = {id_placeholder: resource_id}
        try:
            await api_method(*args)
            await coordinator.async_request_refresh()
        except Exception as err:
            _LOGGER.error("Service %s failed: %s", translation_key, err)
            raise HomeAssistantError(
                translation_domain=DOMAIN,
                translation_key=translation_key,
                translation_placeholders=placeholders,
            ) from err

    # Service definitions: (service_name, api_method_name, translation_key, schema, id_attr, id_placeholder)
    container_services: list[tuple[str, str, str]] = [
        ("container_start", "start_container", "container_start_failed"),
        ("container_stop", "stop_container", "container_stop_failed"),
        ("container_restart", "restart_container", "container_restart_failed"),
        ("container_pause", "pause_container", "container_pause_failed"),
        ("container_resume", "unpause_container", "container_resume_failed"),
    ]

    vm_services: list[tuple[str, str, str]] = [
        ("vm_start", "start_vm", "vm_start_failed"),
        ("vm_stop", "stop_vm", "vm_stop_failed"),
        ("vm_restart", "restart_vm", "vm_restart_failed"),
        ("vm_pause", "pause_vm", "vm_pause_failed"),
        ("vm_resume", "resume_vm", "vm_resume_failed"),
        ("vm_hibernate", "hibernate_vm", "vm_hibernate_failed"),
        ("vm_force_stop", "force_stop_vm", "vm_force_stop_failed"),
    ]

    no_arg_services: list[tuple[str, str, str]] = [
        ("array_start", "start_array", "array_start_failed"),
        ("array_stop", "stop_array", "array_stop_failed"),
        ("parity_check_start", "start_parity_check", "parity_check_start_failed"),
        ("parity_check_stop", "stop_parity_check", "parity_check_stop_failed"),
        ("parity_check_pause", "pause_parity_check", "parity_check_pause_failed"),
        ("parity_check_resume", "resume_parity_check", "parity_check_resume_failed"),
    ]

    def _make_handler(
        method_name: str,
        translation_key: str,
        id_attr: str | None = None,
        id_placeholder: str | None = None,
    ) -> Callable[[ServiceCall], Coroutine[Any, Any, None]]:
        """Create a service handler bound to a specific API method."""

        async def handler(call: ServiceCall) -> None:
            coordinator = _get_coordinator(call)
            await _async_service_call(
                call,
                getattr(coordinator.client, method_name),
                translation_key,
                id_attr=id_attr,
                id_placeholder=id_placeholder,
            )

        return handler

    # Register container services
    for svc_name, method, tkey in container_services:
        hass.services.async_register(
            DOMAIN,
            svc_name,
            _make_handler(method, tkey, ATTR_CONTAINER_ID, "container_id"),
            schema=SERVICE_CONTAINER_SCHEMA,
        )

    # Register VM services
    for svc_name, method, tkey in vm_services:
        hass.services.async_register(
            DOMAIN,
            svc_name,
            _make_handler(method, tkey, ATTR_VM_ID, "vm_id"),
            schema=SERVICE_VM_SCHEMA,
        )

    # Register no-argument services
    for svc_name, method, tkey in no_arg_services:
        hass.services.async_register(
            DOMAIN,
            svc_name,
            _make_handler(method, tkey),
        )

    total = len(container_services) + len(vm_services) + len(no_arg_services)
    _LOGGER.info("Registered %d services for Unraid Management Agent", total)
