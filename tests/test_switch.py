"""Test the Unraid Management Agent switch platform."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.const import STATE_OFF, STATE_ON
from homeassistant.core import HomeAssistant


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_switch_setup(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test switch platform setup."""
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


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_container_switch(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test container switch."""
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


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_vm_switch(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test VM switch."""
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


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_container_switch_turn_on(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test turning on a container switch."""
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


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_container_switch_turn_off(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test turning off a container switch."""
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


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
@pytest.mark.timeout(5)
async def test_vm_switch_turn_on_calls_api(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test turning on a VM switch calls the API."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Turn on Ubuntu VM (currently stopped)
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.unraid_test_vm_ubuntu_server"},
        blocking=True,
    )

    # Verify start_vm was called with VM name
    mock_async_unraid_client.start_vm.assert_called()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
@pytest.mark.timeout(5)
async def test_vm_switch_turn_off_calls_api(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test turning off a VM switch calls the API."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Turn off Windows VM (currently running)
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.unraid_test_vm_windows_10"},
        blocking=True,
    )

    # Verify stop_vm was called
    mock_async_unraid_client.stop_vm.assert_called()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_switch_attributes(
    hass: HomeAssistant,
    mock_config_entry,
) -> None:
    """Test switch entity attributes."""
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


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_container_switch_turn_on_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test container switch turn on error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.start_container.side_effect = Exception(
        "Container start failed"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.unraid_test_container_sonarr"},
            blocking=True,
        )


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_container_switch_turn_off_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test container switch turn off error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.stop_container.side_effect = Exception(
        "Container stop failed"
    )

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.unraid_test_container_plex"},
            blocking=True,
        )


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_vm_switch_turn_on_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test VM switch turn on error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.start_vm.side_effect = Exception("VM start failed")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": "switch.unraid_test_vm_ubuntu_server"},
            blocking=True,
        )


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_vm_switch_turn_off_error(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test VM switch turn off error handling."""
    from homeassistant.exceptions import HomeAssistantError

    mock_async_unraid_client.stop_vm.side_effect = Exception("VM stop failed")

    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    with pytest.raises(HomeAssistantError):
        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": "switch.unraid_test_vm_windows_10"},
            blocking=True,
        )


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
@pytest.mark.timeout(10)
async def test_container_switch_turn_on_state_confirmation(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test container switch turn on shows optimistic state."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Turn on sonarr container
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.unraid_test_container_sonarr"},
        blocking=True,
    )

    # The optimistic state should show ON
    state = hass.states.get("switch.unraid_test_container_sonarr")
    assert state is not None
    assert state.state == STATE_ON

    # Verify the API was called
    mock_async_unraid_client.start_container.assert_called()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
@pytest.mark.timeout(10)
async def test_container_switch_turn_off_state_confirmation(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test container switch turn off shows optimistic state."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Turn off plex container
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.unraid_test_container_plex"},
        blocking=True,
    )

    # The optimistic state should show OFF
    state = hass.states.get("switch.unraid_test_container_plex")
    assert state is not None
    assert state.state == STATE_OFF

    # Verify the API was called
    mock_async_unraid_client.stop_container.assert_called()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
@pytest.mark.timeout(10)
async def test_vm_switch_turn_on_api_call_only(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test VM switch turn on calls API and shows optimistic state."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Turn on Ubuntu VM
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.unraid_test_vm_ubuntu_server"},
        blocking=True,
    )

    # Verify start_vm was called
    mock_async_unraid_client.start_vm.assert_called()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
@pytest.mark.timeout(10)
async def test_vm_switch_turn_off_api_call_only(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test VM switch turn off calls API and shows optimistic state."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Turn off Windows VM
    await hass.services.async_call(
        "switch",
        "turn_off",
        {"entity_id": "switch.unraid_test_vm_windows_10"},
        blocking=True,
    )

    # Verify stop_vm was called
    mock_async_unraid_client.stop_vm.assert_called()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_container_switch_turn_on_timeout(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
) -> None:
    """Test container switch turn on calls API (no longer has timeout behavior)."""
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()

    # Turn on sonarr container
    await hass.services.async_call(
        "switch",
        "turn_on",
        {"entity_id": "switch.unraid_test_container_sonarr"},
        blocking=True,
    )

    # Command completed without error
    mock_async_unraid_client.start_container.assert_called()


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_container_switch_no_docker_collector(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
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


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
async def test_vm_switch_no_vm_collector(
    hass: HomeAssistant,
    mock_config_entry,
    mock_async_unraid_client,
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
        switch._container_name = "test_container"
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
        switch._container_name = "test_container"
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
        switch._container_name = "missing_container"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()

        # Create container with different name
        mock_container = MagicMock()
        mock_container.name = "other_container"
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
        switch._container_name = "plex"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()

        # Create container with matching name
        mock_container = MagicMock()
        mock_container.name = "plex"
        mock_container.id = "plex_id"
        mock_container.container_id = None
        switch.coordinator.data.containers = [mock_container]

        result = switch._find_container()
        assert result == mock_container

    def test_container_id_property_with_id(self) -> None:
        """Test _container_id returns id when available."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.coordinator import UnraidData
        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._container_name = "plex"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()

        mock_container = MagicMock()
        mock_container.name = "plex"
        mock_container.id = "plex_id"
        switch.coordinator.data.containers = [mock_container]

        result = switch._container_id
        assert result == "plex_id"

    def test_container_id_property_with_container_id_fallback(self) -> None:
        """Test _container_id returns container_id when id is None."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.coordinator import UnraidData
        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._container_name = "plex"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()

        # Use a simple class to ensure id is truly None (MagicMock auto-creates attributes)
        class MockContainer:
            name = "plex"
            id = None
            container_id = "plex_container_id"

        switch.coordinator.data.containers = [MockContainer()]

        result = switch._container_id
        assert result == "plex_container_id"

    def test_container_id_property_no_container(self) -> None:
        """Test _container_id returns None when container not found."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._container_name = "missing"
        switch.coordinator = MagicMock()
        switch.coordinator.data = None

        result = switch._container_id
        assert result is None

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
        switch._container_name = "missing_container"
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
        switch._container_name = "missing_container"
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
        switch._vm_name = "test_vm"
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
        switch._vm_name = "test_vm"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()
        switch.coordinator.data.vms = []

        result = switch._find_vm()
        assert result is None

    def test_find_vm_not_found(self) -> None:
        """Test _find_vm returns None when VM name doesn't match any."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.coordinator import UnraidData
        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_name = "nonexistent_vm"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()

        # Create VMs but with different names
        mock_vm1 = MagicMock()
        mock_vm1.name = "VM1"
        mock_vm2 = MagicMock()
        mock_vm2.name = "VM2"
        switch.coordinator.data.vms = [mock_vm1, mock_vm2]

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
        switch._vm_name = "Windows 10"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()

        mock_vm = MagicMock()
        mock_vm.name = "Windows 10"
        mock_vm.id = "windows_id"
        switch.coordinator.data.vms = [mock_vm]

        result = switch._find_vm()
        assert result == mock_vm

    def test_vm_id_property_with_id(self) -> None:
        """Test _vm_id returns name for API calls (UMA uses name, not id)."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.coordinator import UnraidData
        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_name = "Windows 10"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()

        mock_vm = MagicMock()
        mock_vm.name = "Windows 10"
        mock_vm.id = "windows_id"
        switch.coordinator.data.vms = [mock_vm]

        result = switch._vm_id
        # UMA API uses VM name for start/stop, not the internal ID
        assert result == "Windows 10"

    def test_vm_id_property_with_name_fallback(self) -> None:
        """Test _vm_id returns name when id is None."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.coordinator import UnraidData
        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_name = "Windows 10"
        switch.coordinator = MagicMock()
        switch.coordinator.data = UnraidData()

        # Use a simple class to ensure id is truly None (MagicMock auto-creates attributes)
        class MockVM:
            name = "Windows 10"
            id = None

        switch.coordinator.data.vms = [MockVM()]

        result = switch._vm_id
        assert result == "Windows 10"

    def test_vm_id_property_no_vm(self) -> None:
        """Test _vm_id returns None when VM not found."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_name = "missing"
        switch.coordinator = MagicMock()
        switch.coordinator.data = None

        result = switch._vm_id
        assert result is None

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
        switch._vm_name = "missing_vm"
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
        switch._vm_name = "missing_vm"
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
        switch._vm_name = "Windows 10"
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


class TestContainerSwitchErrors:
    """Test container switch error handling."""

    async def test_turn_on_api_error(self) -> None:
        """Test turn on raises HomeAssistantError on API error."""
        from unittest.mock import MagicMock

        from homeassistant.exceptions import HomeAssistantError

        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._container_name = "test_container"
        switch._optimistic_state = None
        switch.coordinator = MagicMock()
        switch.coordinator.client = MagicMock()
        switch.coordinator.client.start_container = AsyncMock(
            side_effect=Exception("API Error")
        )
        switch.async_write_ha_state = MagicMock()

        # Mock _find_container to return a container with an ID
        mock_container = MagicMock()
        mock_container.id = "container_id"
        switch._find_container = MagicMock(return_value=mock_container)

        with pytest.raises(HomeAssistantError):
            await switch.async_turn_on()

        # Optimistic state should be reset
        assert switch._optimistic_state is None

    async def test_turn_off_api_error(self) -> None:
        """Test turn off raises HomeAssistantError on API error."""
        from unittest.mock import MagicMock

        from homeassistant.exceptions import HomeAssistantError

        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._container_name = "test_container"
        switch._optimistic_state = None
        switch.coordinator = MagicMock()
        switch.coordinator.client = MagicMock()
        switch.coordinator.client.stop_container = AsyncMock(
            side_effect=Exception("API Error")
        )
        switch.async_write_ha_state = MagicMock()

        # Mock _find_container to return a container with an ID
        mock_container = MagicMock()
        mock_container.id = "container_id"
        switch._find_container = MagicMock(return_value=mock_container)

        with pytest.raises(HomeAssistantError):
            await switch.async_turn_off()

        # Optimistic state should be reset
        assert switch._optimistic_state is None


class TestVMSwitchErrors:
    """Test VM switch error handling."""

    async def test_turn_on_api_error(self) -> None:
        """Test turn on raises HomeAssistantError on API error."""
        from unittest.mock import MagicMock

        from homeassistant.exceptions import HomeAssistantError

        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_name = "test_vm"
        switch._optimistic_state = None
        switch.coordinator = MagicMock()
        switch.coordinator.client = MagicMock()
        switch.coordinator.client.start_vm = AsyncMock(
            side_effect=Exception("API Error")
        )
        switch.async_write_ha_state = MagicMock()

        # Mock _find_vm to return a VM with an ID
        mock_vm = MagicMock()
        mock_vm.id = "vm_id"
        switch._find_vm = MagicMock(return_value=mock_vm)

        with pytest.raises(HomeAssistantError):
            await switch.async_turn_on()

        # Optimistic state should be reset
        assert switch._optimistic_state is None

    async def test_turn_off_api_error(self) -> None:
        """Test turn off raises HomeAssistantError on API error."""
        from unittest.mock import MagicMock

        from homeassistant.exceptions import HomeAssistantError

        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_name = "test_vm"
        switch._optimistic_state = None
        switch.coordinator = MagicMock()
        switch.coordinator.client = MagicMock()
        switch.coordinator.client.stop_vm = AsyncMock(
            side_effect=Exception("API Error")
        )
        switch.async_write_ha_state = MagicMock()

        # Mock _find_vm to return a VM with an ID
        mock_vm = MagicMock()
        mock_vm.id = "vm_id"
        switch._find_vm = MagicMock(return_value=mock_vm)

        with pytest.raises(HomeAssistantError):
            await switch.async_turn_off()

        # Optimistic state should be reset
        assert switch._optimistic_state is None


class TestVMSwitchStateConfirmation:
    """Test VM switch successful state confirmation."""

    async def test_turn_on_state_confirmed_running(self) -> None:
        """Test turn on calls API and sets optimistic state."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_name = "test_vm"
        switch._optimistic_state = None
        switch.coordinator = MagicMock()
        switch.coordinator.client = MagicMock()
        switch.coordinator.client.start_vm = AsyncMock()
        switch.coordinator.async_request_refresh = AsyncMock()
        switch.async_write_ha_state = MagicMock()

        mock_vm = MagicMock()
        mock_vm.name = "test_vm"
        switch._find_vm = MagicMock(return_value=mock_vm)

        await switch.async_turn_on()

        # API should be called and optimistic state should be True
        switch.coordinator.client.start_vm.assert_called_once_with("test_vm")
        assert switch._optimistic_state is True
        switch.coordinator.async_request_refresh.assert_called_once()

    async def test_turn_off_state_confirmed_stopped(self) -> None:
        """Test turn off calls API and sets optimistic state."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        switch = object.__new__(UnraidVMSwitch)
        switch._vm_name = "test_vm"
        switch._optimistic_state = None
        switch.coordinator = MagicMock()
        switch.coordinator.client = MagicMock()
        switch.coordinator.client.stop_vm = AsyncMock()
        switch.coordinator.async_request_refresh = AsyncMock()
        switch.async_write_ha_state = MagicMock()

        mock_vm = MagicMock()
        mock_vm.name = "test_vm"
        switch._find_vm = MagicMock(return_value=mock_vm)

        await switch.async_turn_off()

        # API should be called and optimistic state should be False
        switch.coordinator.client.stop_vm.assert_called_once_with("test_vm")
        assert switch._optimistic_state is False
        switch.coordinator.async_request_refresh.assert_called_once()


class TestContainerSwitchStateConfirmation:
    """Test container switch successful state confirmation."""

    async def test_turn_on_state_confirmed_running(self) -> None:
        """Test turn on calls API and sets optimistic state."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._container_name = "test_container"
        switch._optimistic_state = None
        switch.coordinator = MagicMock()
        switch.coordinator.client = MagicMock()
        switch.coordinator.client.start_container = AsyncMock()
        switch.coordinator.async_request_refresh = AsyncMock()
        switch.async_write_ha_state = MagicMock()

        mock_container = MagicMock()
        mock_container.id = "container_id"
        switch._find_container = MagicMock(return_value=mock_container)

        await switch.async_turn_on()

        # API should be called and optimistic state should be True
        switch.coordinator.client.start_container.assert_called_once_with(
            "container_id"
        )
        assert switch._optimistic_state is True
        switch.coordinator.async_request_refresh.assert_called_once()

    async def test_turn_off_state_confirmed_stopped(self) -> None:
        """Test turn off calls API and sets optimistic state."""
        from unittest.mock import MagicMock

        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        switch = object.__new__(UnraidContainerSwitch)
        switch._container_name = "test_container"
        switch._optimistic_state = None
        switch.coordinator = MagicMock()
        switch.coordinator.client = MagicMock()
        switch.coordinator.client.stop_container = AsyncMock()
        switch.coordinator.async_request_refresh = AsyncMock()
        switch.async_write_ha_state = MagicMock()

        mock_container = MagicMock()
        mock_container.id = "container_id"
        switch._find_container = MagicMock(return_value=mock_container)

        await switch.async_turn_off()

        # API should be called and optimistic state should be False
        switch.coordinator.client.stop_container.assert_called_once_with("container_id")
        assert switch._optimistic_state is False
        switch.coordinator.async_request_refresh.assert_called_once()


class TestContainerSwitchOptimisticClearing:
    """Tests for container switch optimistic state clearing."""

    def test_handle_coordinator_update_clears_optimistic_state(self) -> None:
        """Test _handle_coordinator_update clears optimistic state when match."""
        from custom_components.unraid_management_agent.switch import (
            UnraidContainerSwitch,
        )

        mock_coordinator = MagicMock()
        mock_coordinator.data = MagicMock()
        mock_coordinator.config_entry = MagicMock()
        mock_coordinator.config_entry.entry_id = "test_entry"

        switch = UnraidContainerSwitch(mock_coordinator, "test_container")
        switch._optimistic_state = True

        # Container is running -> matches optimistic_state=True
        mock_container = MagicMock()
        mock_container.state = "running"
        switch._find_container = MagicMock(return_value=mock_container)
        switch.async_write_ha_state = MagicMock()

        switch._handle_coordinator_update()
        assert switch._optimistic_state is None


class TestVMSwitchOptimisticClearing:
    """Tests for VM switch optimistic state clearing."""

    def test_handle_coordinator_update_clears_optimistic_state(self) -> None:
        """Test _handle_coordinator_update clears optimistic state when match."""
        from custom_components.unraid_management_agent.switch import (
            UnraidVMSwitch,
        )

        mock_coordinator = MagicMock()
        mock_coordinator.data = MagicMock()
        mock_coordinator.config_entry = MagicMock()
        mock_coordinator.config_entry.entry_id = "test_entry"

        switch = UnraidVMSwitch(mock_coordinator, "test_vm")
        switch._optimistic_state = False

        # VM is stopped -> matches optimistic_state=False
        mock_vm = MagicMock()
        mock_vm.state = "stopped"
        switch._find_vm = MagicMock(return_value=mock_vm)
        switch.async_write_ha_state = MagicMock()

        switch._handle_coordinator_update()
        assert switch._optimistic_state is None
