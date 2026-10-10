"""Tests for the SAS storage topology devices and entities."""

from __future__ import annotations

import json
from collections.abc import Callable
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock

import pytest
from homeassistant.const import (
    STATE_OFF,
    STATE_ON,
    STATE_UNAVAILABLE,
    STATE_UNKNOWN,
)
from homeassistant.core import HomeAssistant
from homeassistant.helpers import device_registry as dr
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unraid_management_agent import (
    async_remove_config_entry_device,
)
from custom_components.unraid_management_agent.api.models import (
    CollectorDetails,
    CollectorStatus,
    StorageTopology,
)
from custom_components.unraid_management_agent.cleanup import (
    async_cleanup_stale_entities,
)
from custom_components.unraid_management_agent.const import DOMAIN
from custom_components.unraid_management_agent.storage import (
    StorageContext,
    _attached_to,
    _pcie_link,
    _slot_errors,
    _throughput_attrs,
    _throughput_value,
    _utilization_attrs,
    build_storage_device_info,
    current_storage_ids,
)

from .const import MOCK_CONFIG, MOCK_OPTIONS

ENTRY_ID = "test_entry_id"
FIXTURE = Path(__file__).parent / "fixtures" / "storage_topology.json"
SHELF1 = "50050ccb33cbcba2"  # e242, I/O module firmware 0281
SHELF2 = "500a098aa6236e71"  # e245, I/O module firmware 0260
HPT = "500605bbd7eb76e8"  # HighPoint NVMe enclosure (SES only)


def _topology(
    mutate: Callable[[dict[str, Any]], None] | None = None,
) -> StorageTopology:
    """Load the topology the agent produced from the captured fixtures."""
    data = json.loads(FIXTURE.read_text())
    if mutate:
        mutate(data)
    return StorageTopology.model_validate(data)


def _enclosure(data: dict[str, Any], enclosure_id: str) -> dict[str, Any]:
    return next(e for e in data["enclosures"] if e["id"] == enclosure_id)


@pytest.fixture
def mock_config_entry(hass: HomeAssistant) -> MockConfigEntry:
    """Config entry for the test server."""
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unraid (unraid-test)",
        data=MOCK_CONFIG,
        options=MOCK_OPTIONS,
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)
    return entry


@pytest.fixture
def storage_client(mock_async_unraid_client: MagicMock) -> MagicMock:
    """Serve the captured two-shelf topology."""
    mock_async_unraid_client.get_storage_topology.return_value = _topology()
    return mock_async_unraid_client


async def _setup(hass: HomeAssistant, entry: MockConfigEntry) -> None:
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()


async def _push(hass: HomeAssistant, entry: MockConfigEntry, topology: Any) -> None:
    """Deliver new topology data through the coordinator."""
    coordinator = entry.runtime_data.coordinator
    coordinator.data.storage_topology = topology
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()


def _storage_entities(hass: HomeAssistant) -> list[er.RegistryEntry]:
    return [
        e
        for e in er.async_entries_for_config_entry(er.async_get(hass), ENTRY_ID)
        if e.unique_id.startswith(f"{ENTRY_ID}_storage_")
    ]


def _entity_id(hass: HomeAssistant, platform: str, key: str) -> str:
    entity_id = er.async_get(hass).async_get_entity_id(
        platform, DOMAIN, f"{ENTRY_ID}_{key}"
    )
    assert entity_id is not None, key
    return entity_id


def _state(hass: HomeAssistant, platform: str, key: str) -> Any:
    state = hass.states.get(_entity_id(hass, platform, key))
    assert state is not None, key
    return state


@pytest.mark.usefixtures("storage_client", "mock_unraid_websocket_client_class")
async def test_devices_are_children_of_the_server(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Controller and enclosures are child devices; entity counts stay small."""
    await _setup(hass, mock_config_entry)

    devices = dr.async_get(hass)
    server = devices.async_get_device_by_identifier((DOMAIN, ENTRY_ID), ENTRY_ID)
    assert server is not None
    names = {}
    for kind, owner in (
        ("controller", "DLP9672282"),
        ("enclosure", SHELF1),
        ("enclosure", SHELF2),
        ("enclosure", HPT),
    ):
        device = devices.async_get_child_device_by_identifier(
            (DOMAIN, f"{ENTRY_ID}_storage_{kind}_{owner}"), ENTRY_ID
        )
        assert device is not None
        assert device.parent_device_id == server.id
        names[owner] = device.name
    assert names == {
        "DLP9672282": "MegaRAID 9580-8i8e (c0)",
        SHELF1: "NETAPP DS424IOM12A (e242)",
        SHELF2: "NETAPP DS424IOM12A (e245)",
        HPT: "HPT R1528D (eb76e8)",
    }

    entities = _storage_entities(hass)
    enabled = [e for e in entities if e.disabled_by is None]
    # 1 controller: 7 sensors + status. Each shelf: 12 binary sensors + 5 sensors.
    # The HighPoint enclosure: status, fans, cabling, temperature, fan speed.
    assert len(enabled) == 8 + 2 * 17 + 5
    # Per-element readings (2 x 36 + 6) and per-slot sensors (43 x 2).
    assert len(entities) - len(enabled) == 2 * 36 + 6 + 43 * 2


@pytest.mark.usefixtures("storage_client", "mock_unraid_websocket_client_class")
async def test_controller_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Controller temperature, PCIe link, firmware and HBA ports."""
    await _setup(hass, mock_config_entry)
    ctrl = "storage_controller_dlp9672282"

    assert _state(hass, "sensor", f"{ctrl}_temperature").state == "63.0"
    assert _state(hass, "sensor", f"{ctrl}_pcie_link").state == "16.0 GT/s PCIe x8"
    firmware = _state(hass, "sensor", f"{ctrl}_firmware")
    assert firmware.state == "5.310.02-4101"
    assert firmware.attributes["driver_name"] == "megaraid_sas"

    port0 = _state(hass, "sensor", f"{ctrl}_port_0_link_rate")
    assert port0.state == "12.0"
    assert port0.name == "MegaRAID 9580-8i8e (c0) Port 0 Link Rate"
    assert port0.attributes["attached_enclosure"] == "NETAPP DS424IOM12A (e242)"
    assert port0.attributes["attached_iom"] == 1
    assert _state(hass, "sensor", f"{ctrl}_port_1_width").state == "4"

    status = _state(hass, "binary_sensor", f"{ctrl}_status")
    assert status.state == STATE_OFF
    assert status.attributes["physical_drives"] == 43


@pytest.mark.usefixtures("storage_client", "mock_unraid_websocket_client_class")
async def test_enclosure_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Healthy shelves, the firmware difference and the cable map."""
    await _setup(hass, mock_config_entry)
    shelf = f"storage_enclosure_{SHELF1}"

    assert _state(hass, "binary_sensor", f"{shelf}_status").state == STATE_OFF
    psu = _state(hass, "binary_sensor", f"{shelf}_power_supply_0_power_supply")
    assert psu.state == STATE_OFF
    assert psu.name == "NETAPP DS424IOM12A (e242) Power Supply 0"
    assert psu.attributes["rated_watts"] == 580
    assert psu.attributes["flags"] == []
    iom = _state(hass, "binary_sensor", f"{shelf}_iom_1_iom")
    assert iom.state == STATE_OFF
    assert iom.attributes["firmware"] == "0281"
    assert _state(hass, "binary_sensor", f"{shelf}_fans").state == STATE_OFF
    assert _state(hass, "binary_sensor", f"{shelf}_path_redundancy").state == STATE_OFF
    assert _state(hass, "binary_sensor", f"{shelf}_drive_health").state == STATE_OFF

    # The two shelves run different I/O module firmware.
    firmware = _state(hass, "binary_sensor", f"{shelf}_iom_firmware")
    assert firmware.state == STATE_ON
    assert firmware.attributes["firmware"] == ["0281"]
    assert firmware.attributes["peer_firmware"] == ["0260"]
    assert firmware.attributes["mismatch_within_enclosure"] is False

    cabling = _state(hass, "binary_sensor", f"{shelf}_cabling")
    assert cabling.state == STATE_OFF
    connectors = {c["connector"]: c for c in cabling.attributes["connectors"]}
    assert connectors[7]["attached_to"] == "MegaRAID 9580-8i8e (c0) port 0"
    assert connectors[7]["cable"] == "THE MATE COMPANY C5555-1M+00"
    assert connectors[0]["attached_to"] == "NETAPP DS424IOM12A (e245) I/O module 0"

    assert _state(hass, "sensor", f"{shelf}_highest_temperature").state == "63.0"
    assert _state(hass, "sensor", f"{shelf}_lowest_fan_speed").state == "2170"
    below = _state(hass, "sensor", f"{shelf}_drives_below_max_link_rate")
    assert below.state == "13"
    assert 0 in below.attributes["slots"]
    assert _state(hass, "sensor", f"{shelf}_drive_media_errors").state == "0"
    other = _state(hass, "sensor", f"{shelf}_drive_other_errors")
    assert other.state == "14"
    assert other.attributes["slots"]["16"] == 2

    # The HighPoint card reports an over-temperature sensor.
    hpt = _state(hass, "binary_sensor", f"storage_enclosure_{HPT}_status")
    assert hpt.state == STATE_ON
    assert hpt.attributes["problems"] == [
        "temperature sensor 0: Critical (84 °C, over critical, over warning)"
    ]
    assert (
        _state(hass, "sensor", f"storage_enclosure_{HPT}_highest_temperature").state
        == "84.0"
    )


@pytest.mark.usefixtures("storage_client", "mock_unraid_websocket_client_class")
async def test_disabled_detail_entities(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Per-element and per-slot sensors exist but are disabled by default."""
    await _setup(hass, mock_config_entry)
    registry = er.async_get(hass)
    shelf = f"storage_enclosure_{SHELF1}"
    for key in (
        f"{shelf}_temperature_3_temperature",
        f"{shelf}_fan_0_speed",
        f"{shelf}_voltage_1_voltage",
        f"{shelf}_current_0_current",
        f"{shelf}_slot_0_link_rate",
        f"{shelf}_slot_16_errors",
    ):
        entry = registry.async_get(_entity_id(hass, "sensor", key))
        assert entry is not None
        assert entry.disabled_by is er.RegistryEntryDisabler.INTEGRATION


@pytest.mark.usefixtures("storage_client", "mock_unraid_websocket_client_class")
async def test_detail_entity_values(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Enabled detail sensors report element and slot values."""
    registry = er.async_get(hass)
    shelf = f"storage_enclosure_{SHELF1}"
    keys = {
        "temperature": f"{shelf}_temperature_3_temperature",
        "fan": f"{shelf}_fan_0_speed",
        "voltage": f"{shelf}_voltage_1_voltage",
        "current": f"{shelf}_current_0_current",
        "slot_link": f"{shelf}_slot_0_link_rate",
        "slot_errors": f"{shelf}_slot_16_errors",
        "hpt_voltage": f"storage_enclosure_{HPT}_voltage_0_voltage",
    }
    for key in keys.values():
        registry.async_get_or_create(
            "sensor", DOMAIN, f"{ENTRY_ID}_{key}", config_entry=mock_config_entry
        )
    await _setup(hass, mock_config_entry)

    assert _state(hass, "sensor", keys["temperature"]).state == "42.0"
    assert _state(hass, "sensor", keys["fan"]).state == "3370"
    assert _state(hass, "sensor", keys["voltage"]).state == "12.22"
    assert _state(hass, "sensor", keys["current"]).attributes["status"] == "OK"
    slot = _state(hass, "sensor", keys["slot_link"])
    assert slot.state == "6.0"
    assert slot.attributes["device"] == "sdy"
    assert slot.attributes["max_link_rate_gbps"] == 12.0
    assert slot.attributes["controller_ports"] == [1, 0]
    errors = _state(hass, "sensor", keys["slot_errors"])
    assert errors.state == "2"
    assert errors.attributes["other_errors"] == 2
    # A voltage element without a valid reading: unknown value, status kept.
    hpt_voltage = _state(hass, "sensor", keys["hpt_voltage"])
    assert hpt_voltage.state == "unknown"
    assert hpt_voltage.attributes["status"] == "Critical"


def _break_things(data: dict[str, Any]) -> None:
    """Simulate a PSU, fan, I/O module, cable and drive failure on shelf 1."""
    data["controllers"][0]["status"] = "Degraded"
    shelf = _enclosure(data, SHELF1)
    shelf["power_supplies"][2].update(status="Critical", problem=True, ac_fail=True)
    shelf["fans"][5].update(status="Critical", problem=True, fail=True)
    shelf["ioms"][0].update(status="Critical", problem=True)
    shelf["connectors"][7].update(status="Critical", problem=True, fail=True)
    shelf["iom_firmware_mismatch"] = True
    shelf["redundancy"].update(
        degraded=True, active_paths=1, reasons=["only 1 of 2 host paths active"]
    )
    shelf["problems"] = ["power supply 2: Critical (AC fail)"]
    data["drives"][3].update(predictive_failures=1)


@pytest.mark.usefixtures("storage_client", "mock_unraid_websocket_client_class")
async def test_problems_turn_binary_sensors_on(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Each failure shows up on its problem binary sensor."""
    await _setup(hass, mock_config_entry)
    await _push(hass, mock_config_entry, _topology(_break_things))

    shelf = f"storage_enclosure_{SHELF1}"
    for key in (
        "storage_controller_dlp9672282_status",
        f"{shelf}_status",
        f"{shelf}_power_supply_2_power_supply",
        f"{shelf}_fans",
        f"{shelf}_iom_0_iom",
        f"{shelf}_cabling",
        f"{shelf}_path_redundancy",
        f"{shelf}_drive_health",
    ):
        assert _state(hass, "binary_sensor", key).state == STATE_ON, key
    psu = _state(hass, "binary_sensor", f"{shelf}_power_supply_2_power_supply")
    assert psu.attributes["flags"] == ["ac_fail"]
    redundancy = _state(hass, "binary_sensor", f"{shelf}_path_redundancy")
    assert redundancy.attributes["reasons"] == ["only 1 of 2 host paths active"]
    assert _state(hass, "binary_sensor", f"{shelf}_drive_health").attributes[
        "slots"
    ] == [3]
    firmware = _state(hass, "binary_sensor", f"{shelf}_iom_firmware")
    assert firmware.attributes["mismatch_within_enclosure"] is True
    # Unaffected shelf stays healthy.
    shelf2 = f"storage_enclosure_{SHELF2}"
    assert _state(hass, "binary_sensor", f"{shelf2}_status").state == STATE_OFF


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_no_entities_without_the_endpoint(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """An agent without /storage/topology (404) yields no storage entities or errors."""
    await _setup(hass, mock_config_entry)

    assert mock_async_unraid_client.get_storage_topology.await_count >= 1
    assert not _storage_entities(hass)
    assert not dr.async_child_entries_for_config_entry(dr.async_get(hass), ENTRY_ID)


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_entities_appear_after_the_first_collection(
    hass: HomeAssistant,
    mock_config_entry: MockConfigEntry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """While the agent's topology is pending there are no entities; then they appear."""
    mock_async_unraid_client.get_storage_topology.return_value = (
        StorageTopology.model_validate({"state": "pending"})
    )
    await _setup(hass, mock_config_entry)
    assert not _storage_entities(hass)

    await _push(hass, mock_config_entry, _topology())
    assert len(_storage_entities(hass)) > 0
    assert _state(hass, "binary_sensor", f"storage_enclosure_{SHELF1}_status")


@pytest.mark.usefixtures("storage_client", "mock_unraid_websocket_client_class")
async def test_disabled_collector_makes_entities_unavailable(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The agent keeps serving its last snapshot when the collector is disabled."""
    await _setup(hass, mock_config_entry)
    coordinator = mock_config_entry.runtime_data.coordinator
    coordinator.data.collectors = CollectorStatus(
        collectors=[CollectorDetails(name="storage_topology", enabled=False)]
    )
    coordinator.async_set_updated_data(coordinator.data)
    await hass.async_block_till_done()

    state = _state(hass, "binary_sensor", f"storage_enclosure_{SHELF1}_status")
    assert state.state == STATE_UNAVAILABLE


@pytest.mark.usefixtures("storage_client", "mock_unraid_websocket_client_class")
async def test_missing_enclosure_is_unavailable_not_removed(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """A shelf that disappears goes unavailable and survives stale cleanup."""
    await _setup(hass, mock_config_entry)

    def drop_shelf2(data: dict[str, Any]) -> None:
        data["enclosures"] = [e for e in data["enclosures"] if e["id"] != SHELF2]
        data["controllers"][0]["ports"] = data["controllers"][0]["ports"][:1]

    await _push(hass, mock_config_entry, _topology(drop_shelf2))
    status = f"storage_enclosure_{SHELF2}_status"
    assert _state(hass, "binary_sensor", status).state == STATE_UNAVAILABLE
    port1 = "storage_controller_dlp9672282_port_1_link_rate"
    assert _state(hass, "sensor", port1).state == STATE_UNAVAILABLE

    coordinator = mock_config_entry.runtime_data.coordinator
    async_cleanup_stale_entities(hass, mock_config_entry, coordinator)
    assert _entity_id(hass, "binary_sensor", status)


@pytest.mark.usefixtures("storage_client", "mock_unraid_websocket_client_class")
async def test_remove_storage_device_only_when_gone(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Users can delete a controller or enclosure device once it is no longer reported."""
    await _setup(hass, mock_config_entry)
    devices = dr.async_get(hass)

    def device(kind: str, owner: str) -> Any:
        found = devices.async_get_child_device_by_identifier(
            (DOMAIN, f"{ENTRY_ID}_storage_{kind}_{owner}"), ENTRY_ID
        )
        assert found is not None
        return found

    shelf2 = device("enclosure", SHELF2)
    controller = device("controller", "DLP9672282")
    assert not await async_remove_config_entry_device(hass, mock_config_entry, shelf2)
    assert not await async_remove_config_entry_device(
        hass, mock_config_entry, controller
    )

    def drop(data: dict[str, Any]) -> None:
        data["enclosures"] = [e for e in data["enclosures"] if e["id"] != SHELF2]
        data["controllers"] = []

    await _push(hass, mock_config_entry, _topology(drop))
    assert await async_remove_config_entry_device(hass, mock_config_entry, shelf2)
    assert await async_remove_config_entry_device(hass, mock_config_entry, controller)
    shelf1 = device("enclosure", SHELF1)
    assert not await async_remove_config_entry_device(hass, mock_config_entry, shelf1)


async def test_device_info_falls_back_to_server_when_server_missing(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Without a registered server device, storage entities stay on the server."""
    coordinator = MagicMock()
    coordinator.hass = hass
    coordinator.config_entry = mock_config_entry

    info = build_storage_device_info(coordinator, "enclosure", SHELF1, "Shelf")

    assert info == {"identifiers": {(DOMAIN, ENTRY_ID)}}


def test_helpers_handle_missing_data() -> None:
    """Helpers cope with absent topology, link, port and error data."""
    topology = _topology()
    assert current_storage_ids(None, "controller") == set()
    assert current_storage_ids(topology, "enclosure") == {SHELF1, SHELF2, HPT}

    controller = topology.controllers[0].model_copy(update={"pcie_link_speed": None})
    assert _pcie_link(StorageContext(topology, controller, None)) is None
    controller = topology.controllers[0].model_copy(update={"pcie_link_width": None})
    assert _pcie_link(StorageContext(topology, controller, None)) == "16.0 GT/s PCIe"

    connector = _topology().enclosures[0].connectors[7]
    ctx = StorageContext(topology, topology.enclosures[0], None)
    no_port = connector.model_copy(update={"attached_port": None})
    assert _attached_to(ctx, no_port) == "MegaRAID 9580-8i8e (c0)"
    unknown = connector.model_copy(update={"attached_id": "gone", "attached_port": 2})
    assert _attached_to(ctx, unknown) == "gone port 2"

    drive = topology.drives[0].model_copy(
        update={"media_errors": None, "other_errors": None}
    )
    assert _slot_errors(StorageContext(topology, topology.enclosures[0], drive)) is None


THROUGHPUT_FIXTURE = Path(__file__).parent / "fixtures" / "storage_throughput.json"
THROUGHPUT_KEYS = ("read_throughput", "write_throughput", "throughput")
CTRL = "storage_controller_dlp9672282"


def _add_throughput(data: dict[str, Any]) -> None:
    """Add the agent's throughput to the controller, shelf 1 and the HighPoint card."""
    throughput = json.loads(THROUGHPUT_FIXTURE.read_text())
    for owner in [*data["controllers"], *data["enclosures"]]:
        if owner["id"] in throughput:
            owner["throughput"] = throughput[owner["id"]]


def _throughput_keys(prefix: str) -> list[str]:
    return [f"{prefix}_{key}" for key in (*THROUGHPUT_KEYS, "link_utilization")]


@pytest.fixture
def throughput_client(mock_async_unraid_client: MagicMock) -> MagicMock:
    """Serve the two-shelf topology with throughput (second agent cycle on)."""
    mock_async_unraid_client.get_storage_topology.return_value = _topology(
        _add_throughput
    )
    return mock_async_unraid_client


def test_throughput_model_is_optional() -> None:
    """Older agents and the first collection cycle have no throughput."""
    topology = _topology()
    assert topology.controllers[0].throughput is None
    assert all(e.throughput is None for e in topology.enclosures)

    throughput = _topology(_add_throughput).enclosures[0].throughput
    assert throughput is not None
    assert throughput.read_bytes_per_sec == 262144000.0
    assert throughput.drives == 22
    assert throughput.interval_seconds == 30.02


@pytest.mark.usefixtures("throughput_client", "mock_unraid_websocket_client_class")
async def test_throughput_sensors(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Read, write and total throughput and link utilization, enabled by default."""
    await _setup(hass, mock_config_entry)
    shelf = f"storage_enclosure_{SHELF1}"

    read = _state(hass, "sensor", f"{shelf}_read_throughput")
    assert read.name == "NETAPP DS424IOM12A (e242) Read Throughput"
    assert float(read.state) == pytest.approx(262.144)
    assert read.attributes["unit_of_measurement"] == "MB/s"
    assert read.attributes["device_class"] == "data_rate"
    assert read.attributes["state_class"] == "measurement"
    assert read.attributes["drives"] == 22
    assert read.attributes["interval_seconds"] == 30.02
    write = _state(hass, "sensor", f"{shelf}_write_throughput")
    assert write.name == "NETAPP DS424IOM12A (e242) Write Throughput"
    assert float(write.state) == pytest.approx(1.048576)
    total = _state(hass, "sensor", f"{shelf}_throughput")
    assert total.name == "NETAPP DS424IOM12A (e242) Throughput"
    assert float(total.state) == pytest.approx(263.192576)
    assert total.attributes["unit_of_measurement"] == "MB/s"

    utilization = _state(hass, "sensor", f"{shelf}_link_utilization")
    assert utilization.name == "NETAPP DS424IOM12A (e242) Link Utilization"
    assert float(utilization.state) == pytest.approx(5.48317867)
    assert utilization.attributes["unit_of_measurement"] == "%"
    assert utilization.attributes["state_class"] == "measurement"
    assert utilization.attributes["capacity_bytes_per_sec"] == 4800000000.0
    assert utilization.attributes["drives"] == 22

    assert float(_state(hass, "sensor", f"{CTRL}_throughput").state) == (
        pytest.approx(450.0)
    )
    controller = _state(hass, "sensor", f"{CTRL}_link_utilization")
    assert controller.name == "MegaRAID 9580-8i8e (c0) Link Utilization"
    assert float(controller.state) == pytest.approx(2.856417418)

    registry = er.async_get(hass)
    for key in [*_throughput_keys(shelf), *_throughput_keys(CTRL)]:
        entry = registry.async_get(_entity_id(hass, "sensor", key))
        assert entry is not None
        assert entry.disabled_by is None
        assert entry.entity_category is None

    # Shelf 2 reports no throughput, so it gets no throughput entities.
    for key in _throughput_keys(f"storage_enclosure_{SHELF2}"):
        assert (
            registry.async_get_entity_id("sensor", DOMAIN, f"{ENTRY_ID}_{key}") is None
        )


@pytest.mark.usefixtures("throughput_client", "mock_unraid_websocket_client_class")
async def test_link_utilization_unknown_without_capacity(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Utilization is unknown when the agent cannot work out the link capacity."""
    await _setup(hass, mock_config_entry)
    hpt = f"storage_enclosure_{HPT}"

    utilization = _state(hass, "sensor", f"{hpt}_link_utilization")
    assert utilization.state == STATE_UNKNOWN
    assert utilization.attributes["capacity_bytes_per_sec"] is None
    assert utilization.attributes["drives"] == 2
    assert float(_state(hass, "sensor", f"{hpt}_read_throughput").state) == 0.0
    assert float(_state(hass, "sensor", f"{hpt}_throughput").state) == (
        pytest.approx(5.24288)
    )


@pytest.mark.usefixtures("storage_client", "mock_unraid_websocket_client_class")
async def test_throughput_sensors_appear_after_the_first_cycle(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """The first collection has no throughput; the sensors appear with the next."""
    await _setup(hass, mock_config_entry)
    registry = er.async_get(hass)
    shelf = f"storage_enclosure_{SHELF1}"
    keys = [*_throughput_keys(shelf), *_throughput_keys(CTRL)]
    for key in keys:
        assert (
            registry.async_get_entity_id("sensor", DOMAIN, f"{ENTRY_ID}_{key}") is None
        )

    await _push(hass, mock_config_entry, _topology(_add_throughput))
    for key in keys:
        assert _state(hass, "sensor", key).state != STATE_UNAVAILABLE
    assert float(_state(hass, "sensor", f"{shelf}_read_throughput").state) == (
        pytest.approx(262.144)
    )


@pytest.mark.usefixtures("throughput_client", "mock_unraid_websocket_client_class")
async def test_throughput_unavailable_when_it_disappears(
    hass: HomeAssistant, mock_config_entry: MockConfigEntry
) -> None:
    """Throughput that is no longer reported is unavailable and survives cleanup."""
    await _setup(hass, mock_config_entry)
    shelf = f"storage_enclosure_{SHELF1}"
    keys = [*_throughput_keys(shelf), *_throughput_keys(CTRL)]

    # E.g. an agent downgrade: the controller and shelf are still reported.
    await _push(hass, mock_config_entry, _topology())
    for key in keys:
        state = _state(hass, "sensor", key)
        assert state.state == STATE_UNAVAILABLE
        assert "drives" not in state.attributes
    assert _state(hass, "binary_sensor", f"{shelf}_status").state == STATE_OFF

    coordinator = mock_config_entry.runtime_data.coordinator
    async_cleanup_stale_entities(hass, mock_config_entry, coordinator)
    for key in keys:
        assert _entity_id(hass, "sensor", key)

    await _push(hass, mock_config_entry, _topology(_add_throughput))
    assert float(_state(hass, "sensor", f"{shelf}_throughput").state) == (
        pytest.approx(263.192576)
    )


def test_throughput_helpers_without_throughput() -> None:
    """Value and attribute helpers cope with an owner without throughput."""
    topology = _topology()
    ctx = StorageContext(topology, topology.enclosures[0], None)
    assert _throughput_value("total_bytes_per_sec")(ctx) is None
    assert _throughput_attrs(ctx) == {}
    assert _utilization_attrs(ctx) == {}
