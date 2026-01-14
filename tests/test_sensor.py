"""Test the Unraid Management Agent sensor platform."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.const import PERCENTAGE
from homeassistant.core import HomeAssistant

from custom_components.unraid_management_agent.sensor import (
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
