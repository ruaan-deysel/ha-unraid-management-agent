"""Test the Unraid Management Agent switch platform."""

from __future__ import annotations

import asyncio
from unittest.mock import AsyncMock, patch

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
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
        assert state.state == STATE_ON

    # Check sonarr container switch (stopped)
    state = hass.states.get("switch.unraid_test_container_sonarr")
    if state:
        assert state.state == STATE_OFF


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
        assert state.state == STATE_ON

    # Check Ubuntu Server VM switch (stopped)
    state = hass.states.get("switch.unraid_test_vm_ubuntu_server")
    if state:
        assert state.state == STATE_OFF


async def test_container_switch_turn_on(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test turning on a container switch."""
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

        # Turn on sonarr container (currently stopped)
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.unraid_test_container_sonarr"},
            blocking=True,
        )

    mock_async_unraid_client.start_container.assert_called()


async def test_container_switch_turn_off(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test turning off a container switch."""
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

        # Turn off plex container (currently running)
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.unraid_test_container_plex"},
            blocking=True,
        )

    mock_async_unraid_client.stop_container.assert_called()


@pytest.mark.timeout(5)
async def test_vm_switch_turn_on_calls_api(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test turning on a VM switch calls the API (without waiting for state confirmation)."""
    # Patch sleep to avoid waiting
    with (
        patch(
            "custom_components.unraid_management_agent.AsyncUnraidClient",
            return_value=mock_async_unraid_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
        patch(
            "custom_components.unraid_management_agent.switch.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Turn on Ubuntu VM (currently stopped) - don't block, as the wait loop will run
        hass.async_create_task(
            hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.unraid_test_vm_ubuntu_server"},
                blocking=False,
            )
        )
        # Wait a bit for the call to be initiated
        await asyncio.sleep(0.1)

        # Verify start_vm was called
        mock_async_unraid_client.start_vm.assert_called()


@pytest.mark.timeout(5)
async def test_vm_switch_turn_off_calls_api(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test turning off a VM switch calls the API (without waiting for state confirmation)."""
    with (
        patch(
            "custom_components.unraid_management_agent.AsyncUnraidClient",
            return_value=mock_async_unraid_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
        patch(
            "custom_components.unraid_management_agent.switch.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        # Turn off Windows VM (currently running) - don't block
        hass.async_create_task(
            hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": "switch.unraid_test_vm_windows_10"},
                blocking=False,
            )
        )
        await asyncio.sleep(0.1)

        # Verify stop_vm was called
        mock_async_unraid_client.stop_vm.assert_called()


async def test_switch_attributes(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test switch entity attributes."""
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

    # Check container switch has extra attributes
    state = hass.states.get("switch.unraid_test_container_plex")
    if state:
        attrs = state.attributes
        assert "image" in attrs or "container_id" in attrs or "friendly_name" in attrs

    # Check VM switch has extra attributes
    state = hass.states.get("switch.unraid_test_vm_windows_10")
    if state:
        attrs = state.attributes
        assert "friendly_name" in attrs


async def test_container_switch_turn_on_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test container switch turn on error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.start_container.side_effect = Exception(
        "Container start failed"
    )

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

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.unraid_test_container_sonarr"},
                blocking=True,
            )


async def test_container_switch_turn_off_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test container switch turn off error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.stop_container.side_effect = Exception(
        "Container stop failed"
    )

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

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": "switch.unraid_test_container_plex"},
                blocking=True,
            )


async def test_vm_switch_turn_on_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test VM switch turn on error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.start_vm.side_effect = Exception("VM start failed")

    with (
        patch(
            "custom_components.unraid_management_agent.AsyncUnraidClient",
            return_value=mock_async_unraid_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
        patch(
            "custom_components.unraid_management_agent.switch.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": "switch.unraid_test_vm_ubuntu_server"},
                blocking=True,
            )


async def test_vm_switch_turn_off_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test VM switch turn off error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.stop_vm.side_effect = Exception("VM stop failed")

    with (
        patch(
            "custom_components.unraid_management_agent.AsyncUnraidClient",
            return_value=mock_async_unraid_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
        patch(
            "custom_components.unraid_management_agent.switch.asyncio.sleep",
            new_callable=AsyncMock,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": "switch.unraid_test_vm_windows_10"},
                blocking=True,
            )
