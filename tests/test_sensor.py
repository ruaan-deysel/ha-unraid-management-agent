"""Test the Unraid Management Agent sensor platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, patch

from homeassistant.components.sensor import SensorDeviceClass, SensorStateClass
from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant

from custom_components.unraid_management_agent.sensor import (
    _is_physical_network_interface,
)

from .const import MOCK_SYSTEM_DATA


async def test_sensor_setup(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test sensor platform setup."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
        patch(
            "custom_components.unraid_management_agent.async_setup_services",
            new=AsyncMock(),
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

    # Check for key sensor entities
    expected_sensors = [
        "sensor.unraid_unraid_test_cpu_usage",
        "sensor.unraid_unraid_test_ram_usage",
        "sensor.unraid_unraid_test_array_usage",
    ]

    for sensor_id in expected_sensors:
        assert sensor_id in sensor_entities, f"Expected sensor {sensor_id} not found"


async def test_sensor_setup_handles_none_fans(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Ensure setup succeeds when fans data is None."""
    mock_api_client.get_system_info.return_value = {
        **MOCK_SYSTEM_DATA,
        "fans": None,
    }

    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
        patch(
            "custom_components.unraid_management_agent.async_setup_services",
            new=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.unraid_unraid_test_cpu_usage")
    assert state is not None

    fan_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("sensor")
        if "fan" in entity_id
    ]
    assert not fan_entities


async def test_cpu_usage_sensor(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test CPU usage sensor."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
        patch(
            "custom_components.unraid_management_agent.async_setup_services",
            new=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.unraid_unraid_test_cpu_usage")
    assert state is not None
    assert state.state == "25.5"  # From MOCK_SYSTEM_DATA
    assert state.attributes.get("unit_of_measurement") == PERCENTAGE
    assert state.attributes.get("state_class") == SensorStateClass.MEASUREMENT


async def test_ram_usage_sensor(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test RAM usage sensor."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
        patch(
            "custom_components.unraid_management_agent.async_setup_services",
            new=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.unraid_unraid_test_ram_usage")
    assert state is not None
    assert state.state == "45.2"  # From MOCK_SYSTEM_DATA
    assert state.attributes.get("unit_of_measurement") == PERCENTAGE
    assert state.attributes.get("state_class") == SensorStateClass.MEASUREMENT


async def test_temperature_sensor(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test temperature sensor."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
        patch(
            "custom_components.unraid_management_agent.async_setup_services",
            new=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.unraid_unraid_test_cpu_temperature")
    assert state is not None
    assert state.state == "55.0"
    assert state.attributes.get("device_class") == SensorDeviceClass.TEMPERATURE
    assert state.attributes.get("state_class") == SensorStateClass.MEASUREMENT


async def test_array_usage_sensor(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test array usage sensor."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
        patch(
            "custom_components.unraid_management_agent.async_setup_services",
            new=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("sensor.unraid_unraid_test_array_usage")
    assert state is not None
    assert state.state == "50.0"  # 8TB used / 16TB total = 50%
    assert state.attributes.get("unit_of_measurement") == PERCENTAGE
    assert state.attributes.get("state_class") == SensorStateClass.MEASUREMENT


async def test_disk_usage_sensor(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test disk usage sensor."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
        patch(
            "custom_components.unraid_management_agent.async_setup_services",
            new=AsyncMock(),
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Check for disk1 sensor (uses "name" field from mock data)
    state = hass.states.get("sensor.unraid_unraid_test_disk_disk1_usage")
    assert state is not None
    assert state.state == "50.0"  # From MOCK_DISKS_DATA
    assert state.attributes.get("unit_of_measurement") == PERCENTAGE


def test_is_physical_network_interface() -> None:
    """Test physical network interface detection."""
    # Physical interfaces
    assert _is_physical_network_interface("eth0") is True
    assert _is_physical_network_interface("eth1") is True
    assert _is_physical_network_interface("wlan0") is True
    assert _is_physical_network_interface("bond0") is True
    assert _is_physical_network_interface("eno1") is True
    assert _is_physical_network_interface("enp2s0") is True

    # Virtual interfaces
    assert _is_physical_network_interface("veth0") is False
    assert _is_physical_network_interface("br-123") is False
    assert _is_physical_network_interface("docker0") is False
    assert _is_physical_network_interface("virbr0") is False
    assert _is_physical_network_interface("lo") is False
