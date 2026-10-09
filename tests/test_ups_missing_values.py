"""UPS readings the UPS does not report are unknown, not 0."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

import pytest
from homeassistant.const import STATE_UNKNOWN
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unraid_management_agent.api import EnergyIntegrator
from custom_components.unraid_management_agent.api.events import (
    EventType,
    UPSStatusUpdateEvent,
    identify_event_type,
    parse_event,
)
from custom_components.unraid_management_agent.api.models import UPSInfo
from custom_components.unraid_management_agent.const import DOMAIN
from custom_components.unraid_management_agent.coordinator import UnraidData
from custom_components.unraid_management_agent.sensor import (
    UnraidUPSEnergySensor,
    _get_ups_battery,
    _get_ups_load,
    _get_ups_power,
    _get_ups_runtime,
)

from .const import MOCK_CONFIG, MOCK_OPTIONS

ENTRY_ID = "test_entry_id"

# /api/v1/ups from an agent with the fix, for an APC Smart-UPS X 3000 that
# reports battery data but no ups.load / ups.realpower / nominal power.
UPS_PAYLOAD_NULLS = {
    "connected": True,
    "status": "OL",
    "load_percent": None,
    "battery_charge_percent": 100,
    "runtime_left_seconds": 623,
    "power_watts": None,
    "nominal_power_watts": None,
    "model": "Smart-UPS X 3000",
    "timestamp": "2026-10-09T10:00:00Z",
}
# The same UPS from an older agent, which sends 0 for the missing readings.
UPS_PAYLOAD_OLD_AGENT = {
    **UPS_PAYLOAD_NULLS,
    "load_percent": 0,
    "power_watts": 0,
    "nominal_power_watts": 0,
}
# A future agent might leave the keys out instead of sending null.
UPS_PAYLOAD_OMITTED = {
    k: v
    for k, v in UPS_PAYLOAD_NULLS.items()
    if k not in ("load_percent", "power_watts", "nominal_power_watts")
}


def _entry(hass: HomeAssistant) -> MockConfigEntry:
    entry = MockConfigEntry(
        domain=DOMAIN,
        title="Unraid (unraid-test)",
        data=MOCK_CONFIG,
        options=MOCK_OPTIONS,
        entry_id=ENTRY_ID,
    )
    entry.add_to_hass(hass)
    return entry


def _energy_sensor(ups: UPSInfo | None) -> UnraidUPSEnergySensor:
    coordinator = MagicMock()
    coordinator.data = UnraidData(ups=ups)
    return UnraidUPSEnergySensor(coordinator, MagicMock())


def _set_power(sensor: UnraidUPSEnergySensor, watts: float | None) -> None:
    sensor.coordinator.data = UnraidData(
        ups=UPSInfo.model_validate({**UPS_PAYLOAD_NULLS, "power_watts": watts})
    )


@pytest.mark.parametrize("payload", [UPS_PAYLOAD_NULLS, UPS_PAYLOAD_OMITTED])
def test_value_functions_return_none_for_missing_readings(payload: dict) -> None:
    """Null or omitted readings give None (unknown); reported ones are kept."""
    data = UnraidData(ups=UPSInfo.model_validate(payload))

    assert _get_ups_load(data) is None
    assert _get_ups_power(data) is None
    assert _get_ups_battery(data) == 100
    assert _get_ups_runtime(data) == 10  # 623 s


def test_value_functions_keep_zero_from_old_agent() -> None:
    """An older agent's 0 cannot be told apart from a real 0 and is shown."""
    data = UnraidData(ups=UPSInfo.model_validate(UPS_PAYLOAD_OLD_AGENT))

    assert _get_ups_load(data) == 0
    assert _get_ups_power(data) == 0


@pytest.mark.parametrize("payload", [UPS_PAYLOAD_NULLS, UPS_PAYLOAD_OMITTED])
def test_websocket_event_with_missing_readings_is_a_ups_event(payload: dict) -> None:
    """Null or omitted readings still give a UPS event with None values."""
    assert identify_event_type(payload) == EventType.UPS_STATUS_UPDATE

    event = parse_event(payload)

    assert isinstance(event, UPSStatusUpdateEvent)
    assert event.data.load_percent is None
    assert event.data.power_watts is None
    assert event.data.battery_charge_percent == 100


def test_energy_sensor_unknown_when_power_never_reported() -> None:
    """A UPS without a power reading has unknown energy, not 0.000 kWh."""
    sensor = _energy_sensor(UPSInfo.model_validate(UPS_PAYLOAD_NULLS))

    sensor._update_energy()

    assert sensor.native_value is None
    assert sensor._energy_integrator.total_wh == 0.0
    assert "current_power_watts" not in sensor.extra_state_attributes


def test_energy_sensor_pauses_while_power_unknown() -> None:
    """No energy is added while power is unknown, and the gap is not interpolated."""
    sensor = _energy_sensor(None)
    sensor._total_energy = 1.0  # restored total

    with patch("custom_components.unraid_management_agent.sensor.dt_util") as mock_dt:
        clock = mock_dt.utcnow.return_value.timestamp
        for timestamp, watts in ((0.0, 100.0), (1800.0, 100.0)):
            clock.return_value = timestamp
            _set_power(sensor, watts)
            sensor._update_energy()
        assert sensor.native_value == pytest.approx(1.05)  # +50 Wh

        clock.return_value = 2400.0
        _set_power(sensor, None)
        sensor._update_energy()
        assert sensor.native_value is None
        assert sensor._last_power is None
        # The accumulated total survives a restart while power is unknown.
        assert sensor.extra_restore_state_data.native_value == pytest.approx(1.05)

        # Power returns: the 600 s gap is skipped, integration restarts.
        clock.return_value = 3000.0
        _set_power(sensor, 100.0)
        sensor._update_energy()
        assert sensor.native_value == pytest.approx(1.05)

        clock.return_value = 3600.0
        sensor._update_energy()
        assert sensor.native_value == pytest.approx(
            1.05 + 100 * 600 / 3600 / 1000, abs=1e-3
        )


def test_energy_integrator_break_series_keeps_total() -> None:
    """break_series() forgets the last sample but keeps the accumulated total."""
    integrator = EnergyIntegrator()
    integrator.add_sample(100.0, 0.0)
    integrator.add_sample(100.0, 3600.0)

    integrator.break_series()

    assert integrator.total_wh == pytest.approx(100.0)
    assert integrator.last_power_watts is None
    assert integrator.last_timestamp is None
    integrator.add_sample(100.0, 3700.0)
    assert integrator.total_wh == pytest.approx(100.0)


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
async def test_ups_entities_unknown_for_missing_readings(
    hass: HomeAssistant,
    entity_registry: er.EntityRegistry,
    mock_async_unraid_client: MagicMock,
) -> None:
    """Load, power and energy are unknown; battery and runtime have values."""
    mock_async_unraid_client.get_ups_info.return_value = UPSInfo.model_validate(
        UPS_PAYLOAD_NULLS
    )
    entry = _entry(hass)
    await hass.config_entries.async_setup(entry.entry_id)
    await hass.async_block_till_done()

    def state(key: str) -> str:
        entity_id = entity_registry.async_get_entity_id(
            "sensor", DOMAIN, f"{ENTRY_ID}_{key}"
        )
        assert entity_id is not None, key
        current = hass.states.get(entity_id)
        assert current is not None, entity_id
        return current.state

    assert state("ups_load") == STATE_UNKNOWN
    assert state("ups_power") == STATE_UNKNOWN
    assert state("ups_energy") == STATE_UNKNOWN
    assert float(state("ups_battery")) == 100
    assert float(state("ups_runtime")) == 10
