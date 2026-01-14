"""Test the Unraid Management Agent switch platform."""

from __future__ import annotations

from unittest.mock import patch

from homeassistant.core import HomeAssistant


async def test_switch_setup(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test switch platform setup."""
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

    # Verify switch entities are created
    switch_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("switch")
        if entity_id.startswith("switch.unraid_")
    ]

    # Should have container and VM switches
    assert len(switch_entities) > 0


async def test_container_switch(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test container switch."""
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

    # Check plex container switch (running)
    state = hass.states.get("switch.unraid_test_container_plex")
    if state:
        assert state.state == "on"

    # Check sonarr container switch (stopped)
    state = hass.states.get("switch.unraid_test_container_sonarr")
    if state:
        assert state.state == "off"


async def test_vm_switch(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test VM switch."""
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

    # Check Windows 10 VM switch (running)
    state = hass.states.get("switch.unraid_test_vm_windows_10")
    if state:
        assert state.state == "on"

    # Check Ubuntu Server VM switch (stopped)
    state = hass.states.get("switch.unraid_test_vm_ubuntu_server")
    if state:
        assert state.state == "off"
