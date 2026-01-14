"""Test the Unraid Management Agent binary sensor platform."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant

from custom_components.unraid_management_agent.binary_sensor import (
    _is_physical_network_interface,
)


async def test_binary_sensor_setup(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test binary sensor platform setup."""
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

    # Verify binary sensor entities are created
    binary_sensor_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("binary_sensor")
        if entity_id.startswith("binary_sensor.unraid_")
    ]

    assert len(binary_sensor_entities) > 0


async def test_array_started_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test array started binary sensor."""
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

    state = hass.states.get("binary_sensor.unraid_test_array_started")
    if state:
        # Array state is "Started" which should result in "on"
        assert state.state == "on"


async def test_ups_connected_binary_sensor(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test UPS connected binary sensor."""
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

    state = hass.states.get("binary_sensor.unraid_test_ups_connected")
    if state:
        # UPS is connected in mock data
        assert state.state == "on"


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
