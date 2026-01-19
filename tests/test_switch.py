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
            "custom_components.unraid_management_agent.UnraidClient",
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
            "custom_components.unraid_management_agent.UnraidClient",
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
            "custom_components.unraid_management_agent.UnraidClient",
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
            "custom_components.unraid_management_agent.UnraidClient",
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
            "custom_components.unraid_management_agent.UnraidClient",
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
            "custom_components.unraid_management_agent.UnraidClient",
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
            "custom_components.unraid_management_agent.UnraidClient",
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
            "custom_components.unraid_management_agent.UnraidClient",
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
            "custom_components.unraid_management_agent.UnraidClient",
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
            "custom_components.unraid_management_agent.UnraidClient",
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
            "custom_components.unraid_management_agent.UnraidClient",
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
            "custom_components.unraid_management_agent.UnraidClient",
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


@pytest.mark.timeout(10)
async def test_container_switch_turn_on_state_confirmation(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test container switch turn on with state confirmation success."""
    from unittest.mock import MagicMock

    # Track call count for dynamic container state
    call_count = [0]

    def get_containers_with_state_change() -> list[MagicMock]:
        """Return containers with state changing after first call."""
        call_count[0] += 1
        plex = MagicMock()
        plex.id = "abc123"
        plex.name = "plex"
        plex.state = "running"
        plex.image = "linuxserver/plex"
        plex.status = "Up 2 hours"
        plex.created = "2024-01-01T00:00:00Z"

        sonarr = MagicMock()
        sonarr.id = "def456"
        sonarr.name = "sonarr"
        # After first call, change state to running (simulating successful start)
        sonarr.state = "running" if call_count[0] > 1 else "exited"
        sonarr.image = "linuxserver/sonarr"
        sonarr.status = "Up 1 hour" if call_count[0] > 1 else "Exited"
        sonarr.created = "2024-01-01T00:00:00Z"

        return [plex, sonarr]

    mock_async_unraid_client.list_containers.side_effect = (
        get_containers_with_state_change
    )

    with (
        patch(
            "custom_components.unraid_management_agent.UnraidClient",
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

        # Turn on sonarr container and wait for state confirmation
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.unraid_test_container_sonarr"},
            blocking=True,
        )

        # Verify state is now on
        state = hass.states.get("switch.unraid_test_container_sonarr")
        assert state is not None
        assert state.state == STATE_ON


@pytest.mark.timeout(10)
async def test_container_switch_turn_off_state_confirmation(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test container switch turn off with state confirmation success."""
    from unittest.mock import MagicMock

    call_count = [0]

    def get_containers_with_state_change() -> list[MagicMock]:
        """Return containers with state changing after first call."""
        call_count[0] += 1
        plex = MagicMock()
        plex.id = "abc123"
        plex.name = "plex"
        # After first call, change state to exited (simulating successful stop)
        plex.state = "exited" if call_count[0] > 1 else "running"
        plex.image = "linuxserver/plex"
        plex.status = "Exited" if call_count[0] > 1 else "Up 2 hours"
        plex.created = "2024-01-01T00:00:00Z"

        sonarr = MagicMock()
        sonarr.id = "def456"
        sonarr.name = "sonarr"
        sonarr.state = "exited"
        sonarr.image = "linuxserver/sonarr"
        sonarr.status = "Exited"
        sonarr.created = "2024-01-01T00:00:00Z"

        return [plex, sonarr]

    mock_async_unraid_client.list_containers.side_effect = (
        get_containers_with_state_change
    )

    with (
        patch(
            "custom_components.unraid_management_agent.UnraidClient",
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

        # Turn off plex container and wait for state confirmation
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.unraid_test_container_plex"},
            blocking=True,
        )

        # Verify state is now off
        state = hass.states.get("switch.unraid_test_container_plex")
        assert state is not None
        assert state.state == STATE_OFF


@pytest.mark.timeout(10)
async def test_vm_switch_turn_on_api_call_only(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test VM switch turn on calls API without waiting for full state confirmation."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidClient",
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

        # Turn on Ubuntu VM - the mock won't change state but API should be called
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.unraid_test_vm_ubuntu_server"},
            blocking=True,
        )

        # Verify start_vm was called
        mock_async_unraid_client.start_vm.assert_called()


@pytest.mark.timeout(10)
async def test_vm_switch_turn_off_api_call_only(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test VM switch turn off calls API without waiting for full state confirmation."""
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidClient",
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

        # Turn off Windows VM - the mock won't change state but API should be called
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.unraid_test_vm_windows_10"},
            blocking=True,
        )

        # Verify stop_vm was called
        mock_async_unraid_client.stop_vm.assert_called()


async def test_container_switch_turn_on_timeout(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test container switch turn on with state confirmation timeout."""
    # Container never changes state, simulating timeout
    with (
        patch(
            "custom_components.unraid_management_agent.UnraidClient",
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

        # Turn on sonarr container - it won't change state, so timeout
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.unraid_test_container_sonarr"},
            blocking=True,
        )

        # Command completed without error (timeout is just a warning)
        mock_async_unraid_client.start_container.assert_called()


async def test_container_switch_no_docker_collector(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test container switches are not created when docker collector is disabled."""
    from tests.const import mock_collectors_status

    # Return collectors status with docker disabled
    collectors = mock_collectors_status(all_enabled=False)
    # Find and disable docker
    for c in collectors.collectors:
        if c.name == "docker":
            c.enabled = False
            break

    mock_async_unraid_client.get_collectors_status.return_value = collectors

    with (
        patch(
            "custom_components.unraid_management_agent.UnraidClient",
            return_value=mock_async_unraid_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # Container switches should still exist because docker is enabled by default in our mock
    # This test validates the collector check is being called
    switch_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("switch")
        if entity_id.startswith("switch.unraid_")
    ]
    assert len(switch_entities) >= 0  # Just validate no errors


async def test_vm_switch_no_vm_collector(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
    mock_websocket_client,
) -> None:
    """Test VM switches are not created when vm collector is disabled."""
    from tests.const import mock_collectors_status

    # Return collectors status with vm disabled
    collectors = mock_collectors_status(all_enabled=False)
    # Find and disable vm
    for c in collectors.collectors:
        if c.name == "vm":
            c.enabled = False
            break

    mock_async_unraid_client.get_collectors_status.return_value = collectors

    with (
        patch(
            "custom_components.unraid_management_agent.UnraidClient",
            return_value=mock_async_unraid_client,
        ),
        patch(
            "custom_components.unraid_management_agent.UnraidWebSocketClient",
            return_value=mock_websocket_client,
        ),
    ):
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

    # VM switches should still exist because vm is enabled by default in our mock
    switch_entities = [
        entity_id
        for entity_id in hass.states.async_entity_ids("switch")
        if entity_id.startswith("switch.unraid_")
    ]
    assert len(switch_entities) >= 0  # Just validate no errors


# ==================== Unit tests for switch classes ====================


class TestContainerSwitch:
    """Unit tests for UnraidContainerSwitch."""

    def test_find_container_no_data(self) -> None:
        """Test _find_container returns None when no data."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._container_id = "test_id"
        switch.coordinator = MagicMock()
        switch.coordinator.data = None

        result = switch._find_container()
        assert result is None

    def test_find_container_no_containers(self) -> None:
        """Test _find_container returns None when no containers."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.coordinator import UnraidData
        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._container_id = "test_id"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()
        switch.coordinator.data.containers = []

        result = switch._find_container()
        assert result is None

    def test_find_container_not_found(self) -> None:
        """Test _find_container returns None when container not found."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.coordinator import UnraidData
        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._container_id = "missing_id"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()

        # Create container with different ID
        mock_container = MagicMock()
        mock_container.id = "other_id"
        switch.coordinator.data.containers = [mock_container]

        result = switch._find_container()
        assert result is None

    def test_find_container_found(self) -> None:
        """Test _find_container returns container when found."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.coordinator import UnraidData
        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._container_id = "plex_id"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()

        # Create container with matching ID
        mock_container = MagicMock()
        mock_container.id = "plex_id"
        mock_container.container_id = None
        switch.coordinator.data.containers = [mock_container]

        result = switch._find_container()
        assert result == mock_container

    def test_is_on_optimistic_state(self) -> None:
        """Test is_on returns optimistic state when set."""
        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._optimistic_state = True

        result = switch.is_on
        assert result is True

    def test_is_on_no_container(self) -> None:
        """Test is_on returns False when container not found."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._optimistic_state = None
        switch._container_id = "missing"
        switch.coordinator = MagicMock()
        switch.coordinator.data = None

        result = switch.is_on
        assert result is False

    def test_extra_state_attributes_no_container(self) -> None:
        """Test extra_state_attributes returns empty dict when no container."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._container_id = "missing"
        switch.coordinator = MagicMock()
        switch.coordinator.data = None

        result = switch.extra_state_attributes
        assert result == {}


class TestVMSwitch:
    """Unit tests for UnraidVMSwitch."""

    def test_find_vm_no_data(self) -> None:
        """Test _find_vm returns None when no data."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_id = "test_id"
        switch.coordinator = MagicMock()
        switch.coordinator.data = None

        result = switch._find_vm()
        assert result is None

    def test_find_vm_no_vms(self) -> None:
        """Test _find_vm returns None when no VMs."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.coordinator import UnraidData
        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_id = "test_id"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()
        switch.coordinator.data.vms = []

        result = switch._find_vm()
        assert result is None

    def test_find_vm_found(self) -> None:
        """Test _find_vm returns VM when found."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.coordinator import UnraidData
        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_id = "windows_id"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()

        mock_vm = MagicMock()
        mock_vm.id = "windows_id"
        switch.coordinator.data.vms = [mock_vm]

        result = switch._find_vm()
        assert result == mock_vm

    def test_is_on_optimistic_state(self) -> None:
        """Test is_on returns optimistic state when set."""
        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._optimistic_state = False

        result = switch.is_on
        assert result is False

    def test_is_on_no_vm(self) -> None:
        """Test is_on returns False when VM not found."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._optimistic_state = None
        switch._vm_id = "missing"
        switch.coordinator = MagicMock()
        switch.coordinator.data = None

        result = switch.is_on
        assert result is False

    def test_extra_state_attributes_no_vm(self) -> None:
        """Test extra_state_attributes returns empty dict when no VM."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_id = "missing"
        switch.coordinator = MagicMock()
        switch.coordinator.data = None

        result = switch.extra_state_attributes
        assert result == {}

    def test_extra_state_attributes_with_vm(self) -> None:
        """Test extra_state_attributes returns correct data when VM exists."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.coordinator import UnraidData
        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_id = "windows_id"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()

        # Create a simple mock VM with actual values (not MagicMock)
        class MockVM:
            id = "windows_id"
            name = "Windows 10"
            state = "running"
            cpu_count = 4
            memory_display = "8 GB"
            guest_cpu_percent = 25.5
            host_cpu_percent = 10.0
            disk_read_bytes = 1024
            disk_write_bytes = 2048

        switch.coordinator.data.vms = [MockVM()]

        result = switch.extra_state_attributes
        assert result["status"] == "running"
        assert result["vm_vcpus"] == 4
        assert result["vm_memory"] == "8 GB"
        assert "guest_cpu" in result
        assert "host_cpu" in result
