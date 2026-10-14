"""The Unraid Management Agent integration."""

from __future__ import annotations

import hashlib
import logging
from collections.abc import Callable, Coroutine
from typing import Any, Final

import voluptuous as vol
from homeassistant.config_entries import ConfigEntryState
from homeassistant.const import CONF_API_TOKEN, CONF_HOST, CONF_PORT, Platform
from homeassistant.core import HomeAssistant, ServiceCall, callback
from homeassistant.exceptions import (
    ConfigEntryAuthFailed,
    ConfigEntryNotReady,
    HomeAssistantError,
    ServiceValidationError,
)
from homeassistant.helpers import config_validation as cv
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from homeassistant.helpers.typing import ConfigType
from homeassistant.util import slugify

from .api import (
    UnraidAuthenticationError,
    UnraidClient,
    UnraidConnectionError,
    UnraidWebSocketClient,
)
from .cleanup import async_cleanup_stale_entities, async_remove_empty_devices
from .const import (
    CONF_ENABLE_WEBSOCKET,
    CONF_READ_ONLY,
    DEFAULT_ENABLE_WEBSOCKET,
    DEFAULT_READ_ONLY,
    DOMAIN,
    MANUFACTURER,
)
from .coordinator import (
    UnraidConfigEntry,
    UnraidDataUpdateCoordinator,
    UnraidRuntimeData,
)
from .entity import (
    DOCKER_DEVICE,
    VMS_DEVICE,
    async_get_or_create_group_device,
    gpu_device_identifier,
    gpu_device_keys,
    group_device_identifier,
    hwmon_controller_identifier,
    is_group_device_enabled,
    zfs_pool_device_identifier,
)
from .frontend import async_register_frontend
from .hwmon import hid_drivers_without_ids, hwmon_controller_of
from .nic import async_remove_nic_devices, current_card_ids
from .nic import device_identifier as nic_device_identifier
from .storage import CONTROLLER, ENCLOSURE, current_storage_ids, device_identifier

# Service field constants
ATTR_CONTAINER_ID: Final = "container_id"
ATTR_VM_ID: Final = "vm_id"
ATTR_ENABLED: Final = "enabled"
ATTR_REMOVE_IMAGE: Final = "remove_image"

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

SERVICE_CONTAINER_AUTOSTART_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONTAINER_ID): cv.string,
        vol.Required(ATTR_ENABLED): cv.boolean,
    }
)

SERVICE_CONTAINER_REMOVE_SCHEMA = vol.Schema(
    {
        vol.Required(ATTR_CONTAINER_ID): cv.string,
        vol.Optional(ATTR_REMOVE_IMAGE, default=False): cv.boolean,
    }
)

# Re-export for backwards compatibility and for tests to patch
__all__ = [
    "ATTR_CONTAINER_ID",
    "ATTR_ENABLED",
    "ATTR_REMOVE_IMAGE",
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

    # GPU sensors migrated from single-GPU IDs to per-GPU indexed IDs.
    migrate(
        "sensor",
        f"{entry.entry_id}_gpu_utilization",
        f"{entry.entry_id}_gpu_0_utilization",
        "GPU utilization",
    )
    migrate(
        "sensor",
        f"{entry.entry_id}_gpu_temperature",
        f"{entry.entry_id}_gpu_0_temperature",
        "GPU temperature",
    )
    migrate(
        "sensor",
        f"{entry.entry_id}_gpu_power",
        f"{entry.entry_id}_gpu_0_power",
        "GPU power",
    )
    migrate(
        "sensor",
        f"{entry.entry_id}_gpu_energy",
        f"{entry.entry_id}_gpu_0_energy",
        "GPU energy",
    )


PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.SWITCH,
    Platform.BUTTON,
    Platform.NUMBER,
    Platform.EVENT,
    Platform.UPDATE,
]

# Platforms that only report state. In read-only mode nothing that can change
# the server (switches, buttons, numbers) is created. Update entities are kept:
# they still report available updates, but do not offer to install them.
READ_ONLY_PLATFORMS: list[Platform] = [
    Platform.SENSOR,
    Platform.BINARY_SENSOR,
    Platform.EVENT,
    Platform.UPDATE,
]
CONTROL_DOMAINS: frozenset[str] = frozenset(
    str(platform) for platform in PLATFORMS if platform not in READ_ONLY_PLATFORMS
)


def _is_read_only(entry: UnraidConfigEntry) -> bool:
    """Return True when the entry is configured to only create sensors."""
    return bool(entry.options.get(CONF_READ_ONLY, DEFAULT_READ_ONLY))


@callback
def _async_remove_control_entities(
    hass: HomeAssistant, entry: UnraidConfigEntry
) -> None:
    """Remove switch/button/number entities left from before read-only was enabled."""
    registry = er.async_get(hass)
    for entity in er.async_entries_for_config_entry(registry, entry.entry_id):
        if entity.domain in CONTROL_DOMAINS:
            registry.async_remove(entity.entity_id)


@callback
def _async_cleanup_disabled_option_devices(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    coordinator: UnraidDataUpdateCoordinator,
) -> None:
    """Clean up child devices and entities when their corresponding options are disabled."""
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    server = device_registry.async_get_device_by_identifier(
        (DOMAIN, entry.entry_id), entry.entry_id
    )
    if server is None:
        return

    # 1. Container devices option disabled: reparent container and Docker group entities to server device, remove devices
    if not coordinator.is_container_devices_enabled():
        container_prefix = f"{entry.entry_id}_container_"
        docker_group_identifier = group_device_identifier(entry.entry_id, DOCKER_DEVICE)
        for device in (
            *dr.async_child_entries_for_config_entry(device_registry, entry.entry_id),
            *dr.async_entries_for_config_entry(device_registry, entry.entry_id),
        ):
            if device.id == server.id:
                continue
            if any(
                domain == DOMAIN
                and (
                    identifier.startswith(container_prefix)
                    or identifier == docker_group_identifier
                )
                for domain, identifier in device.identifiers
            ):
                for entity in er.async_entries_for_device(
                    entity_registry, device.id, include_disabled_entities=True
                ):
                    entity_registry.async_update_entity(
                        entity.entity_id, device_id=server.id
                    )
                device_registry.async_remove_device(device.id)

    # 2. VM devices option disabled: remove per-VM sensors, reparent VM switches/buttons and VMs group entities to server, remove devices
    if not coordinator.is_vm_devices_enabled():
        vm_prefix = f"{entry.entry_id}_vm_"
        vms_group_identifier = group_device_identifier(entry.entry_id, VMS_DEVICE)
        for entity in er.async_entries_for_config_entry(
            entity_registry, entry.entry_id
        ):
            if entity.domain == "sensor" and entity.unique_id.startswith(vm_prefix):
                entity_registry.async_remove(entity.entity_id)

        for device in (
            *dr.async_child_entries_for_config_entry(device_registry, entry.entry_id),
            *dr.async_entries_for_config_entry(device_registry, entry.entry_id),
        ):
            if device.id == server.id:
                continue
            if any(
                domain == DOMAIN
                and (
                    identifier.startswith(vm_prefix)
                    or identifier == vms_group_identifier
                )
                for domain, identifier in device.identifiers
            ):
                for entity in er.async_entries_for_device(
                    entity_registry, device.id, include_disabled_entities=True
                ):
                    entity_registry.async_update_entity(
                        entity.entity_id, device_id=server.id
                    )
                device_registry.async_remove_device(device.id)

    # 3. GPU devices option disabled: reparent GPU entities to server device, remove GPU devices
    if not coordinator.is_gpu_devices_enabled():
        gpu_prefix = gpu_device_identifier(entry.entry_id, "")
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            if device.id == server.id:
                continue
            if any(
                domain == DOMAIN and identifier.startswith(gpu_prefix)
                for domain, identifier in device.identifiers
            ):
                for entity in er.async_entries_for_device(
                    entity_registry, device.id, include_disabled_entities=True
                ):
                    entity_registry.async_update_entity(
                        entity.entity_id, device_id=server.id
                    )
                device_registry.async_remove_device(device.id)

    # 4. Hwmon devices option disabled: reparent hwmon entities to server device, remove hwmon devices
    if not coordinator.is_hwmon_devices_enabled():
        hwmon_prefix = f"{entry.entry_id}_hwmon_"
        for device in dr.async_entries_for_config_entry(
            device_registry, entry.entry_id
        ):
            if device.id == server.id:
                continue
            if any(
                domain == DOMAIN and identifier.startswith(hwmon_prefix)
                for domain, identifier in device.identifiers
            ):
                for entity in er.async_entries_for_device(
                    entity_registry, device.id, include_disabled_entities=True
                ):
                    entity_registry.async_update_entity(
                        entity.entity_id, device_id=server.id
                    )
                device_registry.async_remove_device(device.id)


@callback
def _async_move_child_devices_to_groups(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    coordinator: UnraidDataUpdateCoordinator,
) -> None:
    """
    Move container and VM child devices under the Docker and VMs devices.

    Earlier releases made them child devices of the server device. The device
    registry can't reparent a child device, and removing a device removes its
    entities, so each one's entities are detached first, the child device is
    removed and created again under its new parent, and the entities are
    attached to it again. Entities keep their unique and entity IDs, settings
    and history. The registry restores the removed device from its deleted
    devices, so the device keeps its ID (and the device automations using it),
    area, name, labels and disabled state.
    """
    device_registry = dr.async_get(hass)
    entity_registry = er.async_get(hass)
    children = dr.async_child_entries_for_config_entry(device_registry, entry.entry_id)
    for group, prefix in (
        (DOCKER_DEVICE, f"{entry.entry_id}_container_"),
        (VMS_DEVICE, f"{entry.entry_id}_vm_"),
    ):
        if not is_group_device_enabled(coordinator, group):
            continue
        to_move = [
            child
            for child in children
            if any(
                domain == DOMAIN and identifier.startswith(prefix)
                for domain, identifier in child.identifiers
            )
        ]
        if not to_move:
            continue
        parent = async_get_or_create_group_device(coordinator, group)
        if parent is None:
            continue
        for child in to_move:
            if child.parent_device_id == parent.id:
                continue
            entity_ids = [
                entity.entity_id
                for entity in er.async_entries_for_device(
                    entity_registry, child.id, include_disabled_entities=True
                )
            ]
            for entity_id in entity_ids:
                entity_registry.async_update_entity(entity_id, device_id=None)
            device_registry.async_remove_device(child.id)
            try:
                moved = device_registry.async_get_or_create_child(
                    config_entry_id=entry.entry_id,
                    config_subentry_id=child.config_subentry_id,
                    identifiers=set(child.identifiers),
                    name=child.name,
                    parent_device_id=parent.id,
                )
            except HomeAssistantError as err:
                _LOGGER.warning("Could not move device %s: %s", child.name, err)
                try:
                    # Put it back where it was, with its entities
                    moved = device_registry.async_get_or_create_child(
                        config_entry_id=entry.entry_id,
                        config_subentry_id=child.config_subentry_id,
                        identifiers=set(child.identifiers),
                        name=child.name,
                        parent_device_id=child.parent_device_id,
                    )
                except HomeAssistantError:
                    # The entities stay, without a device, until their
                    # platform sets them up again on the device it creates.
                    continue
            for entity_id in entity_ids:
                entity_registry.async_update_entity(entity_id, device_id=moved.id)
            _LOGGER.debug("Moved device %s under %s", child.name, parent.name)


async def async_setup(hass: HomeAssistant, config: ConfigType) -> bool:
    """Set up Unraid Management Agent integration."""
    # Register dashboard card frontend
    await async_register_frontend(hass)
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
    client = UnraidClient(
        host=host,
        port=port,
        session=session,
        api_token=entry.data.get(CONF_API_TOKEN),
    )

    # Test connection
    try:
        await client.health_check()
    except UnraidConnectionError as err:
        raise ConfigEntryNotReady(f"Failed to connect to Unraid server: {err}") from err
    except UnraidAuthenticationError as err:
        # Start reauth instead of retrying setup forever with a rejected token
        raise ConfigEntryAuthFailed(
            translation_domain=DOMAIN,
            translation_key="auth_failed",
        ) from err
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
    read_only = _is_read_only(entry)
    platforms = READ_ONLY_PLATFORMS if read_only else PLATFORMS
    entry.runtime_data = UnraidRuntimeData(
        coordinator=coordinator, client=client, platforms=platforms
    )
    if read_only:
        _async_remove_control_entities(hass, entry)
    if not coordinator.is_nic_devices_enabled():
        # Network card devices were turned off (or never on): drop leftovers.
        async_remove_nic_devices(hass, entry)

    # Register the server device up front: the Docker and VMs devices link to
    # it and storage child devices reference it by registry id, so it must
    # exist before any platform loads.
    system = coordinator.data.system if coordinator.data else None
    dr.async_get(hass).async_get_or_create(
        config_entry_id=entry.entry_id,
        identifiers={(DOMAIN, entry.entry_id)},
        name=(system.hostname if system else None) or "Unraid",
        manufacturer=MANUFACTURER,
    )
    _async_cleanup_disabled_option_devices(hass, entry, coordinator)
    _async_move_child_devices_to_groups(hass, entry, coordinator)

    # Set up platforms
    await hass.config_entries.async_forward_entry_setups(entry, platforms)
    async_remove_empty_devices(hass, entry)

    # Start WebSocket for real-time updates
    if enable_websocket:
        await coordinator.async_start_websocket()

    # Register stale entity cleanup: runs on every successful coordinator update
    # and removes entity registry entries for items no longer returned by the API.
    @callback
    def _on_coordinator_update() -> None:
        async_cleanup_stale_entities(hass, entry, coordinator)

    entry.async_on_unload(coordinator.async_add_listener(_on_coordinator_update))

    return True


async def async_remove_config_entry_device(
    hass: HomeAssistant,
    entry: UnraidConfigEntry,
    device_entry: dr.DeviceEntry,
) -> bool:
    """
    Allow removing a VM, container, GPU, storage, ZFS pool, network card or sensor controller device once gone.

    The server device itself, and VMs, containers, GPUs, storage controllers,
    enclosures, ZFS pools, network cards or USB sensor controllers that the agent
    still reports, cannot be removed.
    """
    data = entry.runtime_data.coordinator.data
    vm_prefix = f"{entry.entry_id}_vm_"
    container_prefix = f"{entry.entry_id}_container_"
    gpu_prefix = gpu_device_identifier(entry.entry_id, "")
    hwmon_prefix = f"{entry.entry_id}_hwmon_"
    nic_prefix = nic_device_identifier(entry.entry_id, "")
    zfs_pool_prefix = zfs_pool_device_identifier(entry.entry_id, "")
    topology = data.storage_topology if data else None
    for domain, identifier in device_entry.identifiers:
        if domain != DOMAIN:
            continue
        if identifier.startswith(nic_prefix):
            cards = data.network_cards if data else None
            if cards is None or cards.state != "ok":
                return False
            return identifier[len(nic_prefix) :] not in current_card_ids(cards)
        for kind in (CONTROLLER, ENCLOSURE):
            prefix = device_identifier(entry.entry_id, kind, "")
            if identifier.startswith(prefix):
                if topology is None or topology.state != "ok":
                    return False
                return identifier[len(prefix) :] not in current_storage_ids(
                    topology, kind
                )
        if identifier.startswith(vm_prefix):
            current_vms = {
                getattr(vm, "id", None) or getattr(vm, "name", None)
                for vm in ((data.vms if data else None) or [])
            }
            return identifier[len(vm_prefix) :] not in current_vms
        if identifier.startswith(gpu_prefix):
            gpus = data.gpu if data else None
            if gpus is None:
                return False
            return identifier[len(gpu_prefix) :] not in gpu_device_keys(gpus).values()
        if identifier.startswith(container_prefix):
            current_containers = {
                getattr(container, "name", None)
                for container in ((data.containers if data else None) or [])
            }
            return identifier[len(container_prefix) :] not in current_containers
        if identifier.startswith(hwmon_prefix):
            system = data.system if data else None
            if (
                system is None
                or system.fans is None
                or system.temperatures is None
                or hid_drivers_without_ids([*system.fans, *system.temperatures])
            ):
                # Not a complete inventory: the controller may still be there.
                return False
            current_controllers = {
                hwmon_controller_identifier(entry.entry_id, *controller)
                for item in [*(system.fans or []), *(system.temperatures or [])]
                if (controller := hwmon_controller_of(item)) is not None
            }
            return identifier not in current_controllers
        if identifier.startswith(zfs_pool_prefix):
            if data is None or data.zfs_pools is None:
                return False
            current_pools = {pool.name for pool in data.zfs_pools}
            return identifier[len(zfs_pool_prefix) :] not in current_pools
    return False


async def async_unload_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> bool:
    """Unload a config entry."""
    if unload_ok := await hass.config_entries.async_unload_platforms(
        entry, entry.runtime_data.platforms
    ):
        # Stop WebSocket if running
        await entry.runtime_data.coordinator.async_stop_websocket()
        # Close the client session
        await entry.runtime_data.client.close()

    return unload_ok


async def async_remove_entry(hass: HomeAssistant, entry: UnraidConfigEntry) -> None:
    """Delete the share repair issues of a removed config entry."""
    from .repairs import async_delete_share_issues

    async_delete_share_issues(hass, entry.entry_id)


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
        # Only a loaded entry has runtime data (and a coordinator) to act on
        if entry.state is not ConfigEntryState.LOADED:
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="entry_not_loaded",
                translation_placeholders={"title": entry.title},
            )
        # Every service changes the server, so none run against an entry that
        # is in read-only mode
        if _is_read_only(entry):
            raise ServiceValidationError(
                translation_domain=DOMAIN,
                translation_key="read_only_mode",
                translation_placeholders={"title": entry.title},
            )
        return entry.runtime_data.coordinator

    async def _async_service_call(
        coordinator: UnraidDataUpdateCoordinator,
        api_call: Callable[[], Coroutine[Any, Any, Any]],
        translation_key: str,
        *,
        placeholders: dict[str, str] | None = None,
    ) -> None:
        """Execute a service action with standard error handling."""
        try:
            await api_call()
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
        ("vm_reset", "reset_vm", "vm_reset_failed"),
    ]

    no_arg_services: list[tuple[str, str, str]] = [
        ("array_start", "start_array", "array_start_failed"),
        ("array_stop", "stop_array", "array_stop_failed"),
        (
            "array_clear_disk_stats",
            "clear_array_disk_stats",
            "array_clear_disk_stats_failed",
        ),
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
            args: tuple[Any, ...] = ()
            placeholders: dict[str, str] | None = None
            if id_attr and id_placeholder:
                resource_id: str = call.data[id_attr]
                args = (resource_id,)
                placeholders = {id_placeholder: resource_id}

            async def _api_call() -> Any:
                return await getattr(coordinator.client, method_name)(*args)

            await _async_service_call(
                coordinator,
                _api_call,
                translation_key,
                placeholders=placeholders,
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

    async def _handle_container_remove(call: ServiceCall) -> None:
        coordinator = _get_coordinator(call)
        container_id: str = call.data[ATTR_CONTAINER_ID]
        remove_image: bool = call.data[ATTR_REMOVE_IMAGE]

        async def _api_call() -> Any:
            return await coordinator.client.remove_container(
                container_id,
                remove_image=remove_image,
            )

        await _async_service_call(
            coordinator,
            _api_call,
            "container_remove_failed",
            placeholders={"container_id": container_id},
        )

    async def _handle_container_set_autostart(call: ServiceCall) -> None:
        coordinator = _get_coordinator(call)
        container_id: str = call.data[ATTR_CONTAINER_ID]
        enabled: bool = call.data[ATTR_ENABLED]

        async def _api_call() -> Any:
            return await coordinator.client.set_container_autostart(
                container_id, enabled=enabled
            )

        await _async_service_call(
            coordinator,
            _api_call,
            "container_set_autostart_failed",
            placeholders={"container_id": container_id},
        )

    hass.services.async_register(
        DOMAIN,
        "container_remove",
        _handle_container_remove,
        schema=SERVICE_CONTAINER_REMOVE_SCHEMA,
    )
    hass.services.async_register(
        DOMAIN,
        "container_set_autostart",
        _handle_container_set_autostart,
        schema=SERVICE_CONTAINER_AUTOSTART_SCHEMA,
    )

    total = len(container_services) + len(vm_services) + len(no_arg_services) + 2
    _LOGGER.info("Registered %d services for Unraid Management Agent", total)
