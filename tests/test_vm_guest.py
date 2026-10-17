"""Test the VM guest agent sensors (data read from inside VMs)."""

from __future__ import annotations

from collections.abc import Generator
from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.helpers.aiohttp_client import async_get_clientsession
from pytest_homeassistant_custom_component.common import MockConfigEntry
from pytest_homeassistant_custom_component.test_util.aiohttp import AiohttpClientMocker

from custom_components.unraid_management_agent.api import UnraidClient
from custom_components.unraid_management_agent.api.constants import EventType
from custom_components.unraid_management_agent.api.events import (
    VMGuestUpdateEvent,
    parse_event,
)
from custom_components.unraid_management_agent.api.models import VMGuestInfo, VMInfo
from custom_components.unraid_management_agent.cleanup import (
    _build_valid_dynamic_entity_keys,
    _unavailable_data_prefixes,
)
from custom_components.unraid_management_agent.const import (
    CONF_ENABLE_VM_DEVICES,
    DOMAIN,
)
from custom_components.unraid_management_agent.coordinator import UnraidData
from custom_components.unraid_management_agent.vm_guest import (
    _ident,
    parse_number,
    vm_guest_descriptions,
    vm_guest_offline_prefixes,
)

from .const import MOCK_CONFIG, MOCK_OPTIONS

ENTRY_ID = "test_entry_id"
WIN11_ID = "0a1b2c3d4e5f60718293a4b5c6d7e8f9"
PREFIX = "sensor.unraid_test_vms_windows_11_"
SERIAL = "E823_8FA6_BF53_0001_001B_448B_4EB4_93E5."
KEY = f"vmguest_{WIN11_ID}_"


def _guest(*, running: bool = True, **overrides: Any) -> dict[str, Any]:
    """Build a guest entry the way the agent reports it (values from the DTO)."""

    def reading(value: Any) -> Any:
        return value if running else None

    payload: dict[str, Any] = {
        "vm_name": "Windows 11",
        "running": running,
        "agent_connected": running,
        "hostname": "WIN11",
        "os_name": "Microsoft Windows 11",
        "filesystems": [
            {
                "mountpoint": "C:\\",
                "type": "NTFS",
                "total_bytes": reading(1073741819904),
                "used_bytes": reading(173512880128),
            }
        ],
        "gpus": [
            {
                "index": 0,
                "name": "NVIDIA GeForce RTX 4090",
                "temperature_celsius": reading(34),
                "utilization_percent": reading(12),
                "memory_used_bytes": reading(13631488),
                "memory_total_bytes": reading(25757220864),
                "power_watts": reading(63.29),
                "fan_percent": reading(0),
                "clock_mhz": reading(2535),
            }
        ],
        "disks": [
            {
                "model": "WD_BLACK SN850X 4000GB",
                "serial": SERIAL,
                "bus": "NVMe",
                "temperature_celsius": reading(35),
                "temperature_max_celsius": 90,
                "wear_percent": reading(1),
            }
        ],
        "sensors": [
            {
                "name": "fps",
                "value": reading("144"),
                "updated_at": "2026-10-14T10:00:00Z",
            },
            {"name": "game", "value": reading("Cyberpunk 2077"), "error": ""},
            {"name": "streaming", "value": None, "error": "exit code 1"},
        ],
        "error": "",
        "timestamp": "2026-10-14T10:00:00Z",
    }
    return {**payload, **overrides}


def _vm(
    *, vm_id: str = WIN11_ID, name: str = "Windows 11", state: str = "running"
) -> VMInfo:
    return VMInfo(
        id=vm_id,
        name=name,
        state=state,
        cpu_count=8,
        memory_allocated_bytes=2**34,
        memory_used_bytes=2**34,
        timestamp="2026-10-14T10:00:00Z",
    )


def _guests(*payloads: dict[str, Any]) -> list[VMGuestInfo]:
    return [VMGuestInfo.model_validate(p) for p in payloads]


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Config entry with "VMs as separate devices" turned on."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unraid (unraid-test)",
        data=MOCK_CONFIG,
        options={**MOCK_OPTIONS, CONF_ENABLE_VM_DEVICES: True},
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def guest_client(mock_async_unraid_client: MagicMock) -> Generator[MagicMock]:
    """Serve a running Windows 11 VM with guest agent data."""
    mock_async_unraid_client.list_vms.return_value = [_vm()]
    mock_async_unraid_client.get_vm_guest.return_value = _guests(_guest())
    return mock_async_unraid_client


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _push(hass: HomeAssistant, entry: MockConfigEntry, **fields: Any) -> None:
    """Deliver new data through the coordinator, as a websocket event would."""
    coordinator = entry.runtime_data.coordinator
    for field, value in fields.items():
        setattr(coordinator.data, field, value)
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()


def _state(hass: HomeAssistant, name: str) -> Any:
    state = hass.states.get(f"{PREFIX}{name}")
    assert state is not None, name
    return state


@pytest.mark.usefixtures("guest_client", "mock_unraid_websocket_client_class")
async def test_sensors_of_a_running_vm(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Every kind of reading becomes a sensor on the VM's device."""
    await _setup(hass, mock_config_entry)

    gpu = _state(hass, "gpu_0_temperature")
    assert gpu.state == "34.0"
    assert gpu.attributes["unit_of_measurement"] == "°C"
    assert gpu.attributes["state_class"] == "measurement"
    assert _state(hass, "gpu_0_utilization").state == "12.0"
    memory = _state(hass, "gpu_0_memory_used")
    assert memory.attributes["unit_of_measurement"] == "GiB"
    assert memory.attributes["memory_total_bytes"] == 25757220864
    assert memory.attributes["gpu_name"] == "NVIDIA GeForce RTX 4090"
    assert _state(hass, "gpu_0_power").state == "63.29"
    assert _state(hass, "gpu_0_fan_speed").state == "0.0"
    assert _state(hass, "gpu_0_clock").state == "2535.0"

    disk = _state(hass, "disk_wd_black_sn850x_4000gb_temperature")
    assert disk.state == "35.0"
    assert disk.attributes["serial"] == SERIAL
    assert disk.attributes["temperature_max_celsius"] == 90
    assert _state(hass, "disk_wd_black_sn850x_4000gb_wear").state == "1.0"
    assert _state(hass, "disk_wd_black_sn850x_4000gb_wear").attributes["bus"] == "NVMe"

    fs = _state(hass, "filesystem_c_used")
    assert float(fs.state) == pytest.approx(16.16, abs=0.01)
    assert fs.attributes["used_bytes"] == 173512880128
    assert fs.attributes["total_bytes"] == 1073741819904

    fps = _state(hass, "fps")
    assert fps.state == "144.0"
    assert fps.attributes["state_class"] == "measurement"
    assert fps.attributes["updated_at"] == "2026-10-14T10:00:00Z"
    assert fps.attributes["error"] is None
    game = _state(hass, "game")
    assert game.state == "Cyberpunk 2077"
    assert "state_class" not in game.attributes
    streaming = _state(hass, "streaming")
    assert streaming.state == "unknown"
    assert streaming.attributes["error"] == "exit code 1"

    hostname = _state(hass, "guest_hostname")
    assert hostname.state == "WIN11"
    assert hostname.attributes["os_name"] == "Microsoft Windows 11"
    assert hostname.attributes["agent_connected"] is True

    entities = er.async_get(hass)
    entity = entities.async_get(f"{PREFIX}gpu_0_temperature")
    assert entity.unique_id == f"{ENTRY_ID}_{KEY}gpu_0_temperature"
    vm_state = entities.async_get(f"{PREFIX}state")
    assert entity.device_id == vm_state.device_id


@pytest.mark.usefixtures("guest_client", "mock_unraid_websocket_client_class")
async def test_entities_stay_available_with_unknown_values_while_vm_is_off(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A VM that is off keeps its entities available with an unknown state."""
    await _setup(hass, mock_config_entry)

    await _push(
        hass,
        mock_config_entry,
        vms=[_vm(state="shut off")],
        vm_guest=_guests(_guest(running=False)),
    )

    for name in (
        "gpu_0_temperature",
        "gpu_0_memory_used",
        "disk_wd_black_sn850x_4000gb_temperature",
        "filesystem_c_used",
        "fps",
        "game",
    ):
        assert _state(hass, name).state == "unknown", name
    assert _state(hass, "guest_hostname").attributes["agent_connected"] is False


@pytest.mark.usefixtures("guest_client", "mock_unraid_websocket_client_class")
async def test_entities_unavailable_when_agent_is_unreachable(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    guest_client: MagicMock,
) -> None:
    """Failed updates make the sensors unavailable, like the other entities."""
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator.last_update_success = False
    coordinator.async_update_listeners()
    await hass.async_block_till_done()

    assert _state(hass, "gpu_0_temperature").state == "unavailable"
    assert _state(hass, "fps").state == "unavailable"


@pytest.mark.usefixtures("guest_client", "mock_unraid_websocket_client_class")
async def test_sensors_unavailable_when_the_vm_is_no_longer_reported(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A VM dropped from the guest agent config leaves its sensors unavailable."""
    await _setup(hass, mock_config_entry)
    await _push(hass, mock_config_entry, vm_guest=[])
    assert _state(hass, "fps").state == "unavailable"
    await _push(hass, mock_config_entry, vm_guest=None)
    assert _state(hass, "fps").state == "unavailable"


@pytest.mark.usefixtures("guest_client", "mock_unraid_websocket_client_class")
async def test_values_follow_updates_and_number_or_text(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A custom sensor is numeric while its output parses as a number."""
    await _setup(hass, mock_config_entry)

    long_text = "x" * 400
    sensors = [
        {"name": "fps", "value": "not a number"},
        {"name": "game", "value": "NaN"},
        {"name": "streaming", "value": long_text},
    ]
    await _push(hass, mock_config_entry, vm_guest=_guests(_guest(sensors=sensors)))

    fps = _state(hass, "fps")
    assert fps.state == "not a number"
    assert "state_class" not in fps.attributes
    assert _state(hass, "game").state == "NaN"
    assert _state(hass, "streaming").state == "x" * 255

    sensors = [{"name": "fps", "value": " 60 "}]
    await _push(hass, mock_config_entry, vm_guest=_guests(_guest(sensors=sensors)))
    fps = _state(hass, "fps")
    assert fps.state == "60.0"
    assert fps.attributes["state_class"] == "measurement"
    assert _state(hass, "game").state == "unknown"


@pytest.mark.usefixtures("guest_client", "mock_unraid_websocket_client_class")
async def test_filesystem_without_size_is_unknown(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A filesystem with no total size has no used percent."""
    await _setup(hass, mock_config_entry)
    filesystems = [{"mountpoint": "C:\\", "total_bytes": 0, "used_bytes": 0}]
    await _push(
        hass,
        mock_config_entry,
        vm_guest=_guests(_guest(filesystems=filesystems)),
    )
    assert _state(hass, "filesystem_c_used").state == "unknown"


@pytest.mark.usefixtures("guest_client", "mock_unraid_websocket_client_class")
async def test_new_entries_get_sensors_without_reload(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A GPU reported after setup (VM first booted with it) gets sensors."""
    await _setup(hass, mock_config_entry)
    assert hass.states.get(f"{PREFIX}gpu_1_temperature") is None

    gpus = [{"index": 1, "name": "RTX", "temperature_celsius": 40}]
    await _push(hass, mock_config_entry, vm_guest=_guests(_guest(gpus=gpus)))
    assert _state(hass, "gpu_1_temperature").state == "40.0"


@pytest.mark.usefixtures("guest_client", "mock_unraid_websocket_client_class")
async def test_removed_sensor_is_recreated(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A sensor removed from the registry comes back on the next update."""
    await _setup(hass, mock_config_entry)
    entities = er.async_get(hass)
    entities.async_remove(f"{PREFIX}fps")
    await hass.async_block_till_done()
    assert hass.states.get(f"{PREFIX}fps") is None

    await _push(hass, mock_config_entry)
    assert _state(hass, "fps").state == "144.0"


@pytest.mark.usefixtures("guest_client", "mock_unraid_websocket_client_class")
async def test_renamed_vm_keeps_its_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Sensors follow the VM by UUID when it is renamed."""
    await _setup(hass, mock_config_entry)
    await _push(
        hass,
        mock_config_entry,
        vms=[_vm(name="Gaming")],
        vm_guest=_guests(_guest(vm_name="Gaming")),
    )
    assert _state(hass, "fps").state == "144.0"


@pytest.mark.usefixtures("guest_client", "mock_unraid_websocket_client_class")
async def test_vm_reusing_a_removed_vms_name_does_not_feed_its_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Readings of a replacement VM (new UUID, same name) are not shown."""
    await _setup(hass, mock_config_entry)
    await _push(hass, mock_config_entry, vms=[_vm(vm_id="f" * 32)])
    assert _state(hass, "fps").state == "unavailable"


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_option_off_fetches_and_creates_nothing(
    hass: HomeAssistant, mock_async_unraid_client: MagicMock
) -> None:
    """With VM devices off (default) the endpoint is not polled."""
    mock_async_unraid_client.list_vms.return_value = [_vm()]
    mock_async_unraid_client.get_vm_guest.return_value = _guests(_guest())
    entry = MockConfigEntry(
        domain=DOMAIN,
        data=MOCK_CONFIG,
        options={**MOCK_OPTIONS, CONF_ENABLE_VM_DEVICES: False},
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)
    await _setup(hass, entry)

    mock_async_unraid_client.get_vm_guest.assert_not_awaited()
    assert hass.states.get(f"{PREFIX}fps") is None


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_agent_without_the_endpoint_creates_nothing(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """An older agent answers 404: no guest entities, VM sensors unaffected."""
    mock_async_unraid_client.list_vms.return_value = [_vm()]
    mock_async_unraid_client.get_vm_guest.side_effect = Exception("404")
    await _setup(hass, mock_config_entry)

    assert mock_async_unraid_client.get_vm_guest.await_count >= 1
    assert mock_config_entry.runtime_data.coordinator.data.vm_guest is None
    assert _state(hass, "state").state == "running"
    registered = er.async_entries_for_config_entry(er.async_get(hass), ENTRY_ID)
    assert not [e for e in registered if KEY in e.unique_id]


@pytest.mark.usefixtures("guest_client", "mock_unraid_websocket_client_class")
async def test_turning_vm_devices_off_removes_guest_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Turning the option off removes the guest sensors with the VM devices."""
    await _setup(hass, mock_config_entry)
    assert hass.states.get(f"{PREFIX}fps") is not None

    hass.config_entries.async_update_entry(
        mock_config_entry, options={**MOCK_OPTIONS, CONF_ENABLE_VM_DEVICES: False}
    )
    await hass.config_entries.async_reload(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    registered = er.async_entries_for_config_entry(er.async_get(hass), ENTRY_ID)
    assert not [e for e in registered if KEY in e.unique_id]


def test_cleanup_keys() -> None:
    """Guest sensor keys are valid while reported and VM devices are on."""
    data = UnraidData(vms=[_vm()], vm_guest=_guests(_guest()))
    fps = f"{KEY}sensor_{_ident('fps')}"
    assert fps in _build_valid_dynamic_entity_keys(data, vm_devices=True)
    assert fps not in _build_valid_dynamic_entity_keys(data, vm_devices=False)
    assert fps not in _build_valid_dynamic_entity_keys(
        UnraidData(vms=[_vm()], vm_guest=[]), vm_devices=True
    )

    assert "vmguest_" not in _unavailable_data_prefixes(data)
    for missing in (
        UnraidData(vms=[_vm()], vm_guest=None),
        UnraidData(vms=None, vm_guest=_guests(_guest())),
    ):
        assert "vmguest_" in _unavailable_data_prefixes(missing)


def test_cleanup_keeps_sensors_of_offline_guest() -> None:
    """A VM whose guest agent is not connected keeps its guest sensors."""
    offline = UnraidData(vms=[_vm()], vm_guest=_guests(_guest(running=False, gpus=[])))
    assert KEY in _unavailable_data_prefixes(offline)
    assert KEY not in _unavailable_data_prefixes(
        UnraidData(vms=[_vm()], vm_guest=_guests(_guest()))
    )
    # A guest entry without its VM in the VM list protects nothing.
    assert not vm_guest_offline_prefixes(
        UnraidData(vms=[], vm_guest=_guests(_guest(running=False)))
    )


def test_descriptions_skip_what_has_no_identity() -> None:
    """Unknown VMs and items without an index, serial, mount point or name are skipped."""
    assert vm_guest_descriptions(None) == []
    assert vm_guest_descriptions(UnraidData(vms=[_vm()])) == []

    unknown_vm = UnraidData(vms=[_vm()], vm_guest=_guests(_guest(vm_name="Other")))
    assert vm_guest_descriptions(unknown_vm) == []

    odd = _guest(
        gpus=[{"name": "no index"}, {"index": 0}, {"index": 0}],
        disks=[{"model": "no serial"}, {"serial": "S1"}],
        filesystems=[{"type": "no mount point"}, {"mountpoint": "D:\\"}],
        sensors=[{"value": "1"}, {"name": "up", "value": "1"}],
    )
    keys = [
        d.key
        for d in vm_guest_descriptions(UnraidData(vms=[_vm()], vm_guest=_guests(odd)))
    ]
    assert keys.count(f"{KEY}gpu_0_temperature") == 1
    assert f"{KEY}gpu_None_temperature" not in keys
    assert f"{KEY}disk_{_ident('S1')}_temperature" in keys
    assert f"{KEY}fs_{_ident('D:\\')}_used" in keys
    assert f"{KEY}sensor_{_ident('up')}" in keys
    assert len(keys) == len(set(keys))

    # Names that slugify alike keep separate sensors
    alike = _guest(sensors=[{"name": "CPU Temp"}, {"name": "CPU-Temp"}])
    alike_keys = [
        d.key
        for d in vm_guest_descriptions(UnraidData(vms=[_vm()], vm_guest=_guests(alike)))
        if "_sensor_" in d.key
    ]
    assert len(alike_keys) == 2

    # A VM without a UUID is identified by its name
    named = UnraidData(vms=[VMInfo(name="Windows 11")], vm_guest=_guests(_guest()))
    assert vm_guest_descriptions(named)[0].vm_identifier == "Windows 11"


@pytest.mark.parametrize(
    ("value", "expected"),
    [
        ("144", 144.0),
        (" 1.5 ", 1.5),
        ("x", None),
        ("", None),
        ("inf", None),
        ("nan", None),
        (None, None),
    ],
)
def test_parse_number(value: str | None, expected: float | None) -> None:
    """Only finite numbers count as numeric."""
    assert parse_number(value) == expected


def test_websocket_event_parses_and_updates(hass: HomeAssistant) -> None:
    """vm_guest_update carries the full list, and null means an empty one."""
    event = parse_event(
        {
            "event": "vm_guest_update",
            "timestamp": "2026-10-14T10:00:00Z",
            "data": [_guest()],
        }
    )
    assert isinstance(event, VMGuestUpdateEvent)
    assert event.event_type == EventType.VM_GUEST_UPDATE
    assert event.data[0].gpus[0].name == "NVIDIA GeForce RTX 4090"
    assert event.data[0].sensors[2].value is None

    empty = parse_event({"event": "vm_guest_update", "data": None})
    assert isinstance(empty, VMGuestUpdateEvent)
    assert empty.data == []


@pytest.mark.usefixtures("guest_client", "mock_unraid_websocket_client_class")
async def test_websocket_event_updates_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A vm_guest_update frame refreshes the sensors without a poll."""
    await _setup(hass, mock_config_entry)
    sensors = [{"name": "fps", "value": "75"}]
    mock_config_entry.runtime_data.coordinator._handle_raw_message(
        {
            "event": "vm_guest_update",
            "timestamp": "2026-10-14T10:01:00Z",
            "data": [_guest(sensors=sensors)],
        }
    )
    await hass.async_block_till_done()
    assert _state(hass, "fps").state == "75.0"


async def test_client_get_vm_guest(
    hass: HomeAssistant, aioclient_mock: AiohttpClientMocker
) -> None:
    """The client parses GET /vm/guest, and null as no VMs."""
    url = "http://192.0.2.10:8043/api/v1/vm/guest"
    client = UnraidClient("192.0.2.10", 8043, session=async_get_clientsession(hass))

    aioclient_mock.get(url, json=[_guest()])
    guests = await client.get_vm_guest()
    assert guests[0].vm_name == "Windows 11"
    assert guests[0].disks[0].serial == SERIAL

    aioclient_mock.clear_requests()
    aioclient_mock.get(url, text="null", headers={"Content-Type": "application/json"})
    assert await client.get_vm_guest() == []
