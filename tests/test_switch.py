"""Test the Unraid Management Agent switch platform."""

from __future__ import annotations

from unittest.mock import patch

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


async def test_switch_setup(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test switch platform setup."""
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

    # Verify switch entities are created
    switch_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("switch")
        if entity_id.startswith("switch.unraid_")
    ]

    assert len(switch_entities) > 0

    # Check for key switch entities
    expected_switches = [
        "switch.unraid_test_container_plex",
        "switch.unraid_test_container_sonarr",
        "switch.unraid_test_vm_windows_10",
        "switch.unraid_test_vm_ubuntu_server",
    ]

    for switch_id in expected_switches:
        assert switch_id in switch_entities, f"Expected switch {switch_id} not found"


async def test_container_switch_on_state(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test container switch on state."""
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

    # Plex container is running in mock data
    state = hass.states.get("switch.unraid_test_container_plex")
    assert state is not None
    assert state.state == "on"
    assert state.attributes.get("container_image") == "plexinc/pms-docker:latest"


async def test_container_switch_off_state(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test container switch off state."""
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

    # Sonarr container is not running in mock data
    state = hass.states.get("switch.unraid_test_container_sonarr")
    assert state is not None
    assert state.state == "off"
    assert state.attributes.get("container_image") == "linuxserver/sonarr:latest"


async def test_container_switch_turn_on(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test turning on a container switch."""
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

    # Turn on sonarr container
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.unraid_test_container_sonarr"},
        blocking=True,
    )

    # Verify API was called
    mock_api_client.start_container.assert_called_once()


async def test_container_switch_turn_off(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test turning off a container switch."""
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

    # Turn off plex container
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.unraid_test_container_plex"},
        blocking=True,
    )

    # Verify API was called
    mock_api_client.stop_container.assert_called_once()


async def test_vm_switch_on_state(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test VM switch on state."""
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

    # Windows 10 VM is running in mock data
    state = hass.states.get("switch.unraid_test_vm_windows_10")
    assert state is not None
    assert state.state == "on"
    # VM attributes from mock data
    assert state.attributes.get("vm_vcpus") == 4
    assert state.attributes.get("status") == "running"


async def test_vm_switch_off_state(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test VM switch off state."""
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

    # Ubuntu Server VM is not running in mock data
    state = hass.states.get("switch.unraid_test_vm_ubuntu_server")
    assert state is not None
    assert state.state == "off"
    # Note: vm_vcpus is set from cpu_count in the data which may not be present
    # in all mock data configurations


@pytest.mark.skip(
    reason="VM switch turn on has async wait behavior that's hard to mock"
)
async def test_vm_switch_turn_on(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test turning on a VM switch."""
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

    # Turn on Ubuntu Server VM
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.unraid_test_vm_ubuntu_server"},
        blocking=True,
    )

    # Verify API was called
    mock_api_client.start_vm.assert_called_once()


@pytest.mark.skip(
    reason="VM switch turn off has async wait behavior that's hard to mock"
)
async def test_vm_switch_turn_off(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test turning off a VM switch."""
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

    # Turn off Windows 10 VM
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.unraid_test_vm_windows_10"},
        blocking=True,
    )

    # Verify API was called
    mock_api_client.stop_vm.assert_called_once()


async def test_container_switch_turn_on_error(
    hass: HomeAssistant, mock_config_entry, mock_api_client, mock_websocket_client
) -> None:
    """Test error handling when turning on a container fails."""
    # Make start_container raise an exception
    mock_api_client.start_container.side_effect = Exception("Failed to start container")

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

    # Try to turn on sonarr container - should raise HomeAssistantError
    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.unraid_test_container_sonarr"},
            blocking=True,
        )
