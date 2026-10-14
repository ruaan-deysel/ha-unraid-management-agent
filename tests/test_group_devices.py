"""Test the Docker and VMs devices that group containers and VMs under the server."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError
from homeassistant.helpers import area_registry as ar
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers import label_registry as lr
from homeassistant.helpers.translation import async_get_translations
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unraid_management_agent import (
    _async_move_child_devices_to_groups,
    async_remove_config_entry_device,
)
from custom_components.unraid_management_agent.cleanup import (
    _async_remove_empty_devices,
)
from custom_components.unraid_management_agent.const import (
    CONF_ENABLE_CONTAINER_DEVICES,
    CONF_ENABLE_VM_DEVICES,
    CONF_READ_ONLY,
    DOMAIN,
)
from custom_components.unraid_management_agent.entity import (
    DOCKER_DEVICE,
    VMS_DEVICE,
    async_get_or_create_group_device,
    build_container_device_info,
    build_group_device_info,
    build_vm_device_info,
    is_group_device_enabled,
)

from .const import MOCK_CONFIG, MOCK_OPTIONS

ENTRY_ID = "test_entry_id"
SERVER = (DOMAIN, ENTRY_ID)
DOCKER = (DOMAIN, f"{ENTRY_ID}_docker")
VMS = (DOMAIN, f"{ENTRY_ID}_vms")
PLEX = (DOMAIN, f"{ENTRY_ID}_container_plex")
SONARR = (DOMAIN, f"{ENTRY_ID}_container_sonarr")
WIN10 = (DOMAIN, f"{ENTRY_ID}_vm_windows-10")


def _entry(hass: HomeAssistant, **options: bool) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unraid (unraid-test)",
        data=MOCK_CONFIG,
        options={**MOCK_OPTIONS, **options},
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)
    return entry


def _all_devices_on(hass: HomeAssistant) -> MockConfigEntry:
    return _entry(
        hass, **{CONF_ENABLE_CONTAINER_DEVICES: True, CONF_ENABLE_VM_DEVICES: True}
    )


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    assert await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


def _device(hass: HomeAssistant, identifier: tuple[str, str]) -> dr.DeviceEntry:
    device = dr.async_get(hass).async_get_device_by_identifier(identifier, ENTRY_ID)
    assert device is not None
    return device


def _child(hass: HomeAssistant, identifier: tuple[str, str]) -> dr.ChildDeviceEntry:
    child = dr.async_get(hass).async_get_child_device_by_identifier(
        identifier, ENTRY_ID
    )
    assert child is not None
    return child


def _previous_layout(
    hass: HomeAssistant, entry: MockConfigEntry
) -> dict[str, er.RegistryEntry]:
    """
    Build the registry the previous release left, with user customizations.

    Containers and VMs are child devices of the server device; the Docker
    sensors sit on the server device.
    """
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    areas = ar.async_get(hass)
    labels = lr.async_get(hass)
    server = devices.async_get_or_create(
        config_entry_id=ENTRY_ID, identifiers={SERVER}, name="unraid-test"
    )
    plex = devices.async_get_or_create_child(
        config_entry_id=ENTRY_ID,
        identifiers={PLEX},
        name="plex",
        parent_device_id=server.id,
    )
    plex = devices.async_update_child_device(
        plex.id,
        area_id=areas.async_create("Media").id,
        labels={labels.async_create("Streaming").label_id},
        name_by_user="Plex Media Server",
    )
    sonarr = devices.async_get_or_create_child(
        config_entry_id=ENTRY_ID,
        identifiers={SONARR},
        name="sonarr",
        parent_device_id=server.id,
    )
    win10 = devices.async_get_or_create_child(
        config_entry_id=ENTRY_ID,
        identifiers={WIN10},
        name="VM · Windows 10",
        parent_device_id=server.id,
    )

    def entity(domain: str, key: str, object_id: str, device: str) -> er.RegistryEntry:
        return entities.async_get_or_create(
            domain,
            DOMAIN,
            f"{ENTRY_ID}_{key}",
            config_entry=entry,
            device_id=device,
            suggested_object_id=object_id,
        )

    plex_cpu = entity("sensor", "container_plex_cpu", "unraid_test_plex_cpu", plex.id)
    plex_cpu = entities.async_update_entity(
        plex_cpu.entity_id,
        name="Plex CPU",
        area_id=areas.async_create("Rack").id,
        hidden_by=er.RegistryEntryHider.USER,
    )
    plex_restart = entity(
        "button", "container_plex_restart", "unraid_test_plex_restart", plex.id
    )
    plex_restart = entities.async_update_entity(
        plex_restart.entity_id, disabled_by=er.RegistryEntryDisabler.USER
    )
    created = {
        "plex_cpu": plex_cpu,
        "plex_restart": plex_restart,
        "sonarr_cpu": entity(
            "sensor", "container_sonarr_cpu", "unraid_test_sonarr_cpu", sonarr.id
        ),
        "win10_power": entity(
            "switch", "vm_windows_10", "unraid_test_vm_windows_10_power", win10.id
        ),
        "docker_cpu": entity(
            "sensor", "docker_cpu_usage", "unraid_test_docker_cpu_usage", server.id
        ),
    }
    # Disabling the device disables its entities too
    devices.async_update_child_device(
        sonarr.id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    return {key: entities.async_get(entry.entity_id) for key, entry in created.items()}


@pytest.mark.usefixtures(
    "mock_unraid_client_class", "mock_unraid_websocket_client_class"
)
async def test_upgrade_moves_devices_keeping_entities_and_settings(
    hass: HomeAssistant,
) -> None:
    """Container and VM devices move under the Docker and VMs devices intact."""
    entry = _all_devices_on(hass)
    before = _previous_layout(hass, entry)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    old_ids = {
        identifier: _child(hass, identifier).id for identifier in (PLEX, SONARR, WIN10)
    }
    office = ar.async_get(hass).async_create("Office").id
    unraid_label = lr.async_get(hass).async_create("Unraid").label_id
    devices.async_update_device(
        _device(hass, SERVER).id, area_id=office, labels={unraid_label}
    )

    await _setup(hass, entry)

    server = _device(hass, SERVER)
    docker = _device(hass, DOCKER)
    vms = _device(hass, VMS)
    assert docker.via_device_id == server.id
    assert vms.via_device_id == server.id
    assert docker.name == "unraid-test Docker"
    assert vms.name == "unraid-test VMs"
    assert docker.configuration_url == "http://192.168.1.100/Docker"
    assert vms.configuration_url == "http://192.168.1.100/VMs"
    # They start where the server is, so area and label targets keep reaching
    # the Docker sensors and the container and VM devices inheriting from them
    for group in (docker, vms):
        assert group.area_id == office
        assert group.labels == {unraid_label}

    # Same device IDs (device automations keep working) and user settings
    plex = _child(hass, PLEX)
    sonarr = _child(hass, SONARR)
    win10 = _child(hass, WIN10)
    assert {PLEX: plex.id, SONARR: sonarr.id, WIN10: win10.id} == old_ids
    assert plex.parent_device_id == docker.id
    assert sonarr.parent_device_id == docker.id
    assert win10.parent_device_id == vms.id
    assert plex.name_by_user == "Plex Media Server"
    assert plex.area_id == ar.async_get(hass).async_get_area_by_name("Media").id
    assert plex.labels == {
        lr.async_get(hass).async_get_label_by_name("Streaming").label_id
    }
    assert sonarr.disabled_by is dr.DeviceEntryDisabler.USER
    assert dr.async_get_effective_area_id(hass, sonarr) == office
    assert win10.name == "Windows 10"

    # Every entity kept its entity ID, unique ID and user settings
    for old in before.values():
        new = entities.async_get(old.entity_id)
        assert new is not None
        assert new.unique_id == old.unique_id
        assert new.name == old.name
        assert new.area_id == old.area_id
        assert new.disabled_by == old.disabled_by
        assert new.hidden_by == old.hidden_by
    assert entities.async_get(before["plex_cpu"].entity_id).device_id == plex.id
    assert entities.async_get(before["plex_restart"].entity_id).device_id == plex.id
    assert entities.async_get(before["sonarr_cpu"].entity_id).device_id == sonarr.id
    assert entities.async_get(before["win10_power"].entity_id).device_id == win10.id
    assert entities.async_get(before["docker_cpu"].entity_id).device_id == docker.id
    assert not entities.deleted_entities

    # Friendly names: the user's name is kept, the Docker sensors read as
    # before, and a VM entity's full name has the VMs device in front
    plex_cpu = hass.states.get("sensor.unraid_test_plex_cpu")
    assert plex_cpu.attributes["friendly_name"] == "Plex CPU"
    docker_cpu = hass.states.get("sensor.unraid_test_docker_cpu_usage")
    assert docker_cpu.attributes["friendly_name"] == "unraid-test Docker CPU Usage"
    win10_power = hass.states.get("switch.unraid_test_vm_windows_10_power")
    assert win10_power.attributes["friendly_name"] == "Windows 10 Power"
    assert (
        er.async_get_full_entity_name(
            hass, entities.async_get("switch.unraid_test_vm_windows_10_power")
        )
        == "unraid-test VMs Windows 10 Power"
    )

    # Setting up again changes nothing
    assert await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()
    assert _child(hass, PLEX).id == plex.id
    assert _child(hass, PLEX).parent_device_id == docker.id
    assert devices.async_get_device_by_identifier(DOCKER, ENTRY_ID).id == docker.id
    assert not entities.deleted_entities


@pytest.mark.usefixtures(
    "mock_unraid_client_class", "mock_unraid_websocket_client_class"
)
async def test_restored_group_devices_keep_their_own_settings(
    hass: HomeAssistant,
) -> None:
    """Docker and VMs devices removed earlier come back as the user left them."""
    entry = _all_devices_on(hass)
    devices = dr.async_get(hass)
    areas = ar.async_get(hass)
    server = devices.async_get_or_create(
        config_entry_id=ENTRY_ID, identifiers={SERVER}, name="unraid-test"
    )
    devices.async_update_device(
        server.id,
        area_id=areas.async_create("Office").id,
        labels={lr.async_get(hass).async_create("Unraid").label_id},
    )
    docker = devices.async_get_or_create(config_entry_id=ENTRY_ID, identifiers={DOCKER})
    devices.async_update_device(docker.id, area_id=areas.async_create("Rack").id)
    # The user took the VMs device out of the server's area and labels
    vms = devices.async_get_or_create(config_entry_id=ENTRY_ID, identifiers={VMS})
    devices.async_remove_device(docker.id)
    devices.async_remove_device(vms.id)

    await _setup(hass, entry)

    restored = _device(hass, DOCKER)
    assert restored.id == docker.id
    assert restored.area_id == areas.async_get_area_by_name("Rack").id
    assert not restored.labels
    restored = _device(hass, VMS)
    assert restored.id == vms.id
    assert restored.area_id is None
    assert not restored.labels


@pytest.mark.usefixtures(
    "mock_unraid_client_class", "mock_unraid_websocket_client_class"
)
async def test_upgrade_with_the_server_disabled(hass: HomeAssistant) -> None:
    """Devices of a disabled server stay disabled and can be enabled again."""
    entry = _all_devices_on(hass)
    before = _previous_layout(hass, entry)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    devices.async_update_device(
        _device(hass, SERVER).id, disabled_by=dr.DeviceEntryDisabler.USER
    )
    assert _child(hass, PLEX).disabled_by is dr.DeviceEntryDisabler.DEVICE
    plex_cpu = entities.async_get(before["plex_cpu"].entity_id)
    assert plex_cpu.disabled_by is er.RegistryEntryDisabler.DEVICE

    await _setup(hass, entry)

    docker = _device(hass, DOCKER)
    assert docker.disabled_by is dr.DeviceEntryDisabler.USER
    assert _device(hass, VMS).disabled_by is dr.DeviceEntryDisabler.USER
    assert _child(hass, PLEX).disabled_by is dr.DeviceEntryDisabler.DEVICE
    plex_cpu = entities.async_get(before["plex_cpu"].entity_id)
    assert plex_cpu.disabled_by is er.RegistryEntryDisabler.DEVICE

    # Enabling the Docker device enables the container devices and entities
    devices.async_update_device(docker.id, disabled_by=None)
    await hass.async_block_till_done()
    assert _child(hass, PLEX).disabled_by is None
    assert entities.async_get(before["plex_cpu"].entity_id).disabled_by is None


@pytest.mark.usefixtures(
    "mock_unraid_client_class", "mock_unraid_websocket_client_class"
)
async def test_upgrade_with_device_options_off(hass: HomeAssistant) -> None:
    """Left-over devices are moved, then emptied and removed; entities stay."""
    entry = _entry(hass)
    before = _previous_layout(hass, entry)
    entities = er.async_get(hass)

    await _setup(hass, entry)
    server = _device(hass, SERVER)
    # The entities move back to the server device, as the options say
    for key in ("plex_restart", "win10_power"):
        moved = entities.async_get(before[key].entity_id)
        assert moved is not None
        assert moved.device_id == server.id

    entry.runtime_data.coordinator.async_update_listeners()
    await hass.async_block_till_done()

    # Every entity is still registered
    for old in before.values():
        assert entities.async_get(old.entity_id) is not None
    # The emptied VM device is removed, and with it the VMs device, which
    # holds nothing with the option off
    devices = dr.async_get(hass)
    assert devices.async_get_child_device_by_identifier(WIN10, ENTRY_ID) is None
    assert devices.async_get_device_by_identifier(VMS, ENTRY_ID) is None
    # With container devices off, the Docker device is also removed and docker entities reparent to server
    assert devices.async_get_device_by_identifier(DOCKER, ENTRY_ID) is None
    assert entities.async_get(before["docker_cpu"].entity_id).device_id == server.id


@pytest.mark.usefixtures(
    "mock_unraid_client_class", "mock_unraid_websocket_client_class"
)
async def test_upgrade_in_read_only_mode(hass: HomeAssistant) -> None:
    """Read-only mode removes the controls, then the sensors move along."""
    entry = _entry(
        hass,
        **{
            CONF_ENABLE_CONTAINER_DEVICES: True,
            CONF_ENABLE_VM_DEVICES: True,
            CONF_READ_ONLY: True,
        },
    )
    before = _previous_layout(hass, entry)
    entities = er.async_get(hass)

    await _setup(hass, entry)

    assert entities.async_get(before["plex_restart"].entity_id) is None
    assert entities.async_get(before["win10_power"].entity_id) is None
    plex = _child(hass, PLEX)
    assert plex.parent_device_id == _device(hass, DOCKER).id
    assert entities.async_get(before["plex_cpu"].entity_id).device_id == plex.id


@pytest.mark.usefixtures(
    "mock_unraid_client_class", "mock_unraid_websocket_client_class"
)
async def test_devices_only_for_what_the_server_runs(hass: HomeAssistant) -> None:
    """When container devices enabled but VM devices disabled: Docker device exists, no VMs device."""
    entry = _entry(hass, **{CONF_ENABLE_CONTAINER_DEVICES: True})
    await _setup(hass, entry)

    server = _device(hass, SERVER)
    docker = _device(hass, DOCKER)
    assert dr.async_get(hass).async_get_device_by_identifier(VMS, ENTRY_ID) is None
    entities = er.async_get(hass)
    on_docker = {
        e.unique_id
        for e in er.async_entries_for_device(
            entities, docker.id, include_disabled_entities=True
        )
    }
    assert on_docker == {
        f"{ENTRY_ID}_docker_cpu_usage",
        f"{ENTRY_ID}_docker_memory_usage",
    }
    plex = _child(hass, PLEX)
    assert plex.parent_device_id == docker.id
    switch = entities.async_get("switch.unraid_test_docker_plex_running")
    assert switch is not None
    assert switch.device_id == plex.id
    # Neither the server nor the Docker device can be deleted by the user
    assert not await async_remove_config_entry_device(hass, entry, server)
    assert not await async_remove_config_entry_device(hass, entry, docker)


@pytest.mark.usefixtures(
    "mock_unraid_client_class", "mock_unraid_websocket_client_class"
)
async def test_default_options_only_server_device(hass: HomeAssistant) -> None:
    """Default options: neither Docker nor VMs device exists; all entities on server."""
    entry = _entry(hass)
    await _setup(hass, entry)

    server = _device(hass, SERVER)
    devices = dr.async_get(hass)
    assert devices.async_get_device_by_identifier(DOCKER, ENTRY_ID) is None
    assert devices.async_get_device_by_identifier(VMS, ENTRY_ID) is None
    entities = er.async_get(hass)
    switch = entities.async_get("switch.unraid_test_container_plex")
    assert switch is not None
    assert switch.device_id == server.id
    docker_cpu = entities.async_get("sensor.unraid_test_cpu_usage_2")
    assert docker_cpu is not None
    assert docker_cpu.device_id == server.id
    assert not await async_remove_config_entry_device(hass, entry, server)


@pytest.mark.usefixtures(
    "mock_unraid_client_class", "mock_unraid_websocket_client_class"
)
async def test_toggling_group_devices_options_cleans_up_and_restores(
    hass: HomeAssistant,
) -> None:
    """Disabling container/VM options cleans up Docker/VMs devices and reparents entities to server; re-enabling restores them."""
    entry = _all_devices_on(hass)
    await _setup(hass, entry)

    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    server = _device(hass, SERVER)
    docker = _device(hass, DOCKER)
    vms = _device(hass, VMS)
    plex = _child(hass, PLEX)
    win10 = _child(hass, WIN10)

    assert docker.via_device_id == server.id
    assert vms.via_device_id == server.id
    assert plex.parent_device_id == docker.id
    assert win10.parent_device_id == vms.id

    docker_cpu = entities.async_get("sensor.unraid_test_docker_cpu_usage")
    assert docker_cpu is not None
    assert docker_cpu.device_id == docker.id

    plex_switch = entities.async_get("switch.unraid_test_docker_plex_running")
    assert plex_switch is not None
    assert plex_switch.device_id == plex.id

    win10_switch = entities.async_get("switch.unraid_test_vms_windows_10_power")
    assert win10_switch is not None
    assert win10_switch.device_id == win10.id

    # 1. Disable container and VM devices in options and reload
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            CONF_ENABLE_CONTAINER_DEVICES: False,
            CONF_ENABLE_VM_DEVICES: False,
        },
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Docker and VMs devices and child devices are removed
    assert devices.async_get_device_by_identifier(DOCKER, ENTRY_ID) is None
    assert devices.async_get_device_by_identifier(VMS, ENTRY_ID) is None
    assert devices.async_get_child_device_by_identifier(PLEX, ENTRY_ID) is None
    assert devices.async_get_child_device_by_identifier(WIN10, ENTRY_ID) is None

    # Entities are reparented to the server device
    docker_cpu = entities.async_get("sensor.unraid_test_docker_cpu_usage")
    assert docker_cpu is not None
    assert docker_cpu.device_id == server.id

    plex_switch = entities.async_get("switch.unraid_test_docker_plex_running")
    assert plex_switch is not None
    assert plex_switch.device_id == server.id

    win10_switch = entities.async_get("switch.unraid_test_vms_windows_10_power")
    assert win10_switch is not None
    assert win10_switch.device_id == server.id

    # 2. Re-enable container and VM devices in options and reload
    hass.config_entries.async_update_entry(
        entry,
        options={
            **entry.options,
            CONF_ENABLE_CONTAINER_DEVICES: True,
            CONF_ENABLE_VM_DEVICES: True,
        },
    )
    await hass.config_entries.async_reload(entry.entry_id)
    await hass.async_block_till_done()

    # Docker and VMs devices and child devices reappear
    docker = _device(hass, DOCKER)
    vms = _device(hass, VMS)
    plex = _child(hass, PLEX)
    win10 = _child(hass, WIN10)

    assert docker.via_device_id == server.id
    assert vms.via_device_id == server.id
    assert plex.parent_device_id == docker.id
    assert win10.parent_device_id == vms.id

    # Entities are restored to their group and child devices
    docker_cpu = entities.async_get("sensor.unraid_test_docker_cpu_usage")
    assert docker_cpu is not None
    assert docker_cpu.device_id == docker.id

    plex_switch = entities.async_get("switch.unraid_test_docker_plex_running")
    assert plex_switch is not None
    assert plex_switch.device_id == plex.id

    win10_switch = entities.async_get("switch.unraid_test_vms_windows_10_power")
    assert win10_switch is not None
    assert win10_switch.device_id == win10.id


@pytest.mark.usefixtures(
    "mock_unraid_client_class", "mock_unraid_websocket_client_class"
)
async def test_docker_vdisk_and_updates_sensors_on_the_docker_device(
    hass: HomeAssistant, mock_async_unraid_client: MagicMock
) -> None:
    """The Docker vDisk and container updates sensors join the Docker device."""
    vdisk = MagicMock()
    vdisk.role = "docker_vdisk"
    vdisk.name = "docker"
    vdisk.id = "docker_vdisk"
    vdisk.is_physical = False
    vdisk.size_bytes = 100
    vdisk.used_bytes = 25
    vdisk.usage_percent = 25.0
    mock_async_unraid_client.list_disks.return_value = [vdisk]
    updates = MagicMock()
    updates.containers = []
    updates.updates_available = 0
    mock_async_unraid_client.check_all_container_updates.return_value = updates
    entry = _entry(
        hass,
        enable_container_updates=True,
        **{CONF_ENABLE_CONTAINER_DEVICES: True},
    )
    await _setup(hass, entry)

    docker = _device(hass, DOCKER)
    entities = er.async_get(hass)
    for entity_id in (
        "sensor.unraid_test_docker_vdisk_usage",
        "binary_sensor.unraid_test_docker_container_updates_available",
    ):
        entity = entities.async_get(entity_id)
        assert entity is not None, entity_id
        assert entity.device_id == docker.id


@pytest.mark.usefixtures(
    "mock_unraid_client_class", "mock_unraid_websocket_client_class"
)
async def test_cleanup_keeps_group_devices_with_children(hass: HomeAssistant) -> None:
    """A group device with child devices stays; an empty one is removed."""
    entry = _all_devices_on(hass)
    await _setup(hass, entry)
    devices = dr.async_get(hass)
    entities = er.async_get(hass)
    docker = _device(hass, DOCKER)
    vms = _device(hass, VMS)
    # No entities on the group devices themselves, only on their children
    for group in (docker, vms):
        for entity in er.async_entries_for_device(
            entities, group.id, include_disabled_entities=True
        ):
            entities.async_update_entity(entity.entity_id, device_id=None)

    _async_remove_empty_devices(hass, entry)

    assert devices.async_get(docker.id) is not None
    assert devices.async_get(vms.id) is not None
    assert devices.async_get(_child(hass, PLEX).id) is not None

    # Once the VMs are gone too, the VMs device goes in the same pass
    for vm_device in [
        child
        for child in dr.async_child_entries_for_config_entry(devices, ENTRY_ID)
        if child.parent_device_id == vms.id
    ]:
        for entity in er.async_entries_for_device(
            entities, vm_device.id, include_disabled_entities=True
        ):
            entities.async_remove(entity.entity_id)

    _async_remove_empty_devices(hass, entry)

    assert devices.async_get(vms.id) is None
    assert devices.async_get(docker.id) is not None
    assert devices.async_get(_device(hass, SERVER).id) is not None


@pytest.mark.usefixtures(
    "mock_unraid_client_class", "mock_unraid_websocket_client_class"
)
async def test_failed_move_keeps_the_entities(
    hass: HomeAssistant, caplog: pytest.LogCaptureFixture
) -> None:
    """A device that can't be moved is put back, or its entities set up again."""
    entry = _all_devices_on(hass)
    before = _previous_layout(hass, entry)
    entities = er.async_get(hass)
    registry = dr.async_get(hass)
    server = _device(hass, SERVER)
    plex_before = _child(hass, PLEX)
    original = registry.async_get_or_create_child
    calls: list[str] = []

    def fail(**kwargs: object) -> dr.ChildDeviceEntry:
        # Moving plex fails once; sonarr can be neither moved nor put back
        name = str(kwargs.get("name"))
        calls.append(name)
        if (name == "plex" and calls.count("plex") == 1) or name == "sonarr":
            message = "boom"
            raise HomeAssistantError(message)
        return original(**kwargs)  # type: ignore[arg-type]

    with patch.object(registry, "async_get_or_create_child", side_effect=fail):
        _async_move_child_devices_to_groups(
            hass, entry, MagicMock(hass=hass, config_entry=entry, data=None)
        )

    assert "Could not move device plex: boom" in caplog.text
    assert "Could not move device sonarr: boom" in caplog.text
    # Plex is back under the server with its settings and entities
    plex = _child(hass, PLEX)
    assert plex.id == plex_before.id
    assert plex.parent_device_id == server.id
    assert plex.name_by_user == "Plex Media Server"
    assert entities.async_get(before["plex_cpu"].entity_id).device_id == plex.id
    # Sonarr's entities are left without a device
    assert registry.async_get_child_device_by_identifier(SONARR, ENTRY_ID) is None
    assert entities.async_get(before["sonarr_cpu"].entity_id).device_id is None
    assert _child(hass, WIN10).parent_device_id == _device(hass, VMS).id

    # Setting up moves plex and recreates sonarr under the Docker device
    await _setup(hass, entry)
    docker = _device(hass, DOCKER)
    plex = _child(hass, PLEX)
    sonarr = _child(hass, SONARR)
    assert plex.parent_device_id == docker.id
    assert sonarr.parent_device_id == docker.id
    assert entities.async_get(before["plex_cpu"].entity_id).device_id == plex.id
    assert entities.async_get(before["sonarr_cpu"].entity_id).device_id == sonarr.id


async def test_without_server_device_entities_stay_on_the_server(
    hass: HomeAssistant,
) -> None:
    """Without the server device nothing is grouped or moved."""
    entry = _all_devices_on(hass)
    coordinator = MagicMock(hass=hass, config_entry=entry, data=None)
    registry = dr.async_get(hass)
    server_info = {"identifiers": {SERVER}}

    assert is_group_device_enabled(coordinator, "nonexistent") is False
    assert async_get_or_create_group_device(coordinator, DOCKER_DEVICE) is None
    assert build_group_device_info(coordinator, VMS_DEVICE) == server_info
    assert build_container_device_info(coordinator, "plex") == server_info
    assert build_vm_device_info(coordinator, "windows-10", "Windows 10") == (
        server_info
    )

    # A child device whose server device is gone is left alone
    parent = registry.async_get_or_create(
        config_entry_id=ENTRY_ID, identifiers={(DOMAIN, "parent")}
    )
    child = registry.async_get_or_create_child(
        config_entry_id=ENTRY_ID, identifiers={PLEX}, parent_device_id=parent.id
    )
    _async_move_child_devices_to_groups(hass, entry, coordinator)
    assert registry.async_get(child.id) is not None
    assert registry.async_get_device_by_identifier(DOCKER, ENTRY_ID) is None


async def test_group_device_named_unraid_without_hostname(hass: HomeAssistant) -> None:
    """Before the first update the Docker device is named after "Unraid"."""
    entry = _entry(hass, **{CONF_ENABLE_CONTAINER_DEVICES: True})
    await async_get_translations(hass, "en", "device", {DOMAIN})
    server = dr.async_get(hass).async_get_or_create(
        config_entry_id=ENTRY_ID, identifiers={SERVER}, name="unraid-test"
    )
    coordinator = MagicMock(hass=hass, config_entry=entry, data=None)

    docker = async_get_or_create_group_device(coordinator, DOCKER_DEVICE)

    assert docker is not None
    assert docker.name == "Unraid Docker"
    assert docker.via_device_id == server.id
