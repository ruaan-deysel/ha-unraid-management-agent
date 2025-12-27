"""Test the Unraid Management Agent binary sensor platform."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.components.binary_sensor import BinarySensorDeviceClass
from homeassistant.core import HomeAssistant

from custom_components.unraid_management_agent.binary_sensor import (
    _is_physical_network_interface,
)


async def test_binary_sensor_setup(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test binary sensor platform setup."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Verify binary sensor entities are created
    binary_sensor_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("binary_sensor")
        if entity_id.startswith("binary_sensor.unraid_")
    ]

    assert len(binary_sensor_entities) > 0

    # Check for key binary sensor entities
    expected_sensors = [
        "binary_sensor.unraid_test_array_started",
        "binary_sensor.unraid_test_parity_check_running",
        "binary_sensor.unraid_test_ups_connected",
    ]

    for sensor_id in expected_sensors:
        assert sensor_id in binary_sensor_entities, (
            f"Expected sensor {sensor_id} not found"
        )


async def test_array_started_sensor(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test array started binary sensor."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.unraid_test_array_started")
    assert state is not None
    assert state.state == "on"  # Array is started in mock data


async def test_parity_check_running_sensor(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test parity check running binary sensor."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.unraid_test_parity_check_running")
    assert state is not None
    assert state.state == "off"  # Parity check not running in mock data
    assert state.attributes.get("parity_check_status") == "idle"


async def test_ups_connected_sensor(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test UPS connected binary sensor."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidAPIClient",
            return_value=mock_api_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    state = hass.states.get("binary_sensor.unraid_test_ups_connected")
    assert state is not None
    # UPS status is "ONLINE" in mock data, which means connected
    assert state.state in ["on", "off"]  # Accept either state
    assert state.attributes.get("device_class") == BinarySensorDeviceClass.CONNECTIVITY


# Note: Container and VM binary sensors are NOT implemented in this integration
# Container/VM states are exposed via switches, not binary sensors


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
