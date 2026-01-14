"""Test the Unraid Management Agent sensor platform."""

from __future__ import annotations

from unittest.mock import MagicMock, patch

from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant

from custom_components.unraid_management_agent.sensor import (
    UnraidArrayUsageSensor,
    UnraidCPUTemperatureSensor,
    UnraidCPUUsageSensor,
    UnraidRAMUsageSensor,
    UnraidUptimeSensor,
    _is_physical_network_interface,
)


async def test_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test sensor platform setup."""
    with (
        patch(
            "custom_components.unraid_management_agent.AsyncUnraidClient",
            return_value=mock_async_unraid_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify sensor entities are created
    sensor_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("sensor")
        if entity_id.startswith("sensor.unraid_")
    ]

    assert len(sensor_entities) > 0


async def test_cpu_usage_sensor(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test CPU usage sensor."""
    with (
        patch(
            "custom_components.unraid_management_agent.AsyncUnraidClient",
            return_value=mock_async_unraid_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.unraid_test_cpu_usage")
    if state:
        assert state.state == "25.5"
        assert state.attributes.get("unit_of_measurement") == PERCENTAGE


async def test_ram_usage_sensor(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test RAM usage sensor."""
    with (
        patch(
            "custom_components.unraid_management_agent.AsyncUnraidClient",
            return_value=mock_async_unraid_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.unraid_test_ram_usage")
    if state:
        assert state.state == "45.2"
        assert state.attributes.get("unit_of_measurement") == PERCENTAGE


async def test_array_usage_sensor(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test array usage sensor."""
    with (
        patch(
            "custom_components.unraid_management_agent.AsyncUnraidClient",
            return_value=mock_async_unraid_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.unraid_test_array_usage")
    if state:
        # 8000000000000 / 16000000000000 * 100 = 50.0%
        assert state.state == "50.0"


def test_is_physical_network_interface():
    """Test network interface detection."""
    # Physical interfaces
    assert _is_physical_network_interface("eth0") is True
    assert _is_physical_network_interface("eth1") is True
    assert _is_physical_network_interface("wlan0") is True
    assert _is_physical_network_interface("bond0") is True
    assert _is_physical_network_interface("eno1") is True
    assert _is_physical_network_interface("enp2s0") is True

    # Virtual interfaces (should return False)
    assert _is_physical_network_interface("lo") is False
    assert _is_physical_network_interface("docker0") is False
    assert _is_physical_network_interface("br-123abc") is False
    assert _is_physical_network_interface("veth1234") is False
    assert _is_physical_network_interface("virbr0") is False


# Direct sensor class tests for edge cases and coverage


def test_cpu_usage_sensor_no_data() -> None:
    """Test CPU usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_cpu_usage_sensor_with_data() -> None:
    """Test CPU usage sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.cpu_usage_percent = 75.567
    mock_coordinator.data.system.cpu_model = "Intel i7-12700K"
    mock_coordinator.data.system.cpu_cores = 12
    mock_coordinator.data.system.cpu_threads = 20
    mock_coordinator.data.system.cpu_mhz = 4900.0
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 75.6  # Rounded to 1 decimal
    attrs = sensor.extra_state_attributes
    assert attrs["cpu_model"] == "Intel i7-12700K"
    assert attrs["cpu_cores"] == 12
    assert attrs["cpu_threads"] == 20
    assert "cpu_frequency" in attrs


def test_cpu_usage_sensor_fixes_core_count() -> None:
    """Test CPU usage sensor fixes incorrect core count."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.cpu_usage_percent = 50.0
    mock_coordinator.data.system.cpu_model = "Test CPU"
    mock_coordinator.data.system.cpu_cores = 1  # Incorrect: 1 core with 8 threads
    mock_coordinator.data.system.cpu_threads = 8
    mock_coordinator.data.system.cpu_mhz = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUUsageSensor(mock_coordinator, mock_entry)

    attrs = sensor.extra_state_attributes
    # Should be corrected to 4 cores (8 threads / 2)
    assert attrs["cpu_cores"] == 4


def test_ram_usage_sensor_no_data() -> None:
    """Test RAM usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidRAMUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_ram_usage_sensor_with_data() -> None:
    """Test RAM usage sensor with full data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.ram_usage_percent = 65.432
    mock_coordinator.data.system.ram_total_bytes = 32000000000
    mock_coordinator.data.system.ram_used_bytes = 21000000000
    mock_coordinator.data.system.ram_free_bytes = 5000000000
    mock_coordinator.data.system.ram_cached_bytes = 4000000000
    mock_coordinator.data.system.ram_buffers_bytes = 2000000000
    mock_coordinator.data.system.server_model = "Test Server"
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidRAMUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 65.4
    attrs = sensor.extra_state_attributes
    assert "ram_total" in attrs
    assert "ram_used" in attrs
    assert "ram_free" in attrs
    assert "ram_cached" in attrs
    assert "ram_buffers" in attrs
    assert "ram_available" in attrs
    assert attrs["server_model"] == "Test Server"


def test_cpu_temperature_sensor_no_data() -> None:
    """Test CPU temperature sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUTemperatureSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None


def test_cpu_temperature_sensor_with_data() -> None:
    """Test CPU temperature sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.cpu_temp_celsius = 65.0
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidCPUTemperatureSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 65.0


def test_array_usage_sensor_no_data() -> None:
    """Test array usage sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidArrayUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_array_usage_sensor_with_data() -> None:
    """Test array usage sensor with full data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    mock_coordinator.data.array.total_bytes = 16000000000000
    mock_coordinator.data.array.used_bytes = 8000000000000
    mock_coordinator.data.array.free_bytes = 8000000000000
    mock_coordinator.data.array.used_percent = 50.0  # API returns used_percent directly
    mock_coordinator.data.array.state = "started"
    mock_coordinator.data.array.parity_status = "valid"
    mock_coordinator.data.array.num_disks = 4
    mock_coordinator.data.array.num_data_disks = 3
    mock_coordinator.data.array.num_parity_disks = 1
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidArrayUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value == 50.0  # 8TB / 16TB * 100
    attrs = sensor.extra_state_attributes
    assert "total_size" in attrs
    assert "used_size" in attrs
    assert "free_size" in attrs
    assert attrs["array_state"] == "started"
    assert attrs["num_disks"] == 4


def test_array_usage_sensor_zero_total() -> None:
    """Test array usage sensor with zero total (avoids division by zero)."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.array = MagicMock()
    mock_coordinator.data.array.total_bytes = 0
    mock_coordinator.data.array.used_bytes = 0
    mock_coordinator.data.array.free_bytes = 0
    mock_coordinator.data.array.used_percent = None  # No used_percent when array empty
    mock_coordinator.data.array.state = "stopped"
    mock_coordinator.data.array.parity_status = None
    mock_coordinator.data.array.num_disks = 0
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidArrayUsageSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None  # Should handle division by zero gracefully


def test_uptime_sensor_no_data() -> None:
    """Test uptime sensor with no data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = None
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUptimeSensor(mock_coordinator, mock_entry)

    assert sensor.native_value is None
    assert sensor.extra_state_attributes == {}


def test_uptime_sensor_with_data() -> None:
    """Test uptime sensor with data."""
    mock_coordinator = MagicMock()
    mock_coordinator.data = MagicMock()
    mock_coordinator.data.system = MagicMock()
    mock_coordinator.data.system.uptime_seconds = 86400  # 1 day
    mock_entry = MagicMock()
    mock_entry.entry_id = "test_entry"

    sensor = UnraidUptimeSensor(mock_coordinator, mock_entry)

    # Now returns formatted string instead of raw seconds
    assert sensor.native_value == "1 day"
    attrs = sensor.extra_state_attributes
    assert "uptime_seconds" in attrs
    assert attrs["uptime_seconds"] == 86400
    assert attrs["days"] == 1
    assert attrs["hours"] == 0
