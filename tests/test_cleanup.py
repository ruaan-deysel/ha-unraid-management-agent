"""Tests for stale entity cleanup (cleanup.py) and entity lifecycle safety (#83)."""

from __future__ import annotations

from datetime import timedelta
from unittest.mock import MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.helpers import entity_registry as er
from homeassistant.util import dt as dt_util
from pytest_homeassistant_custom_component.common import MockConfigEntry

from custom_components.unraid_management_agent.cleanup import (
    STALE_REMOVAL_GRACE,
    _unavailable_data_prefixes,
    async_cleanup_stale_entities,
    async_prune_seen_names,
)
from custom_components.unraid_management_agent.const import DOMAIN
from custom_components.unraid_management_agent.coordinator import (
    UnraidData,
    UnraidDataUpdateCoordinator,
)

from .const import mock_system_info


def _make_coordinator(data: UnraidData | None) -> MagicMock:
    """Create a minimal coordinator stub for cleanup tests."""
    coordinator = MagicMock()
    coordinator.data = data
    coordinator.last_update_success = data is not None
    coordinator.in_reboot_grace_period = False
    coordinator.stale_entity_candidates = {}
    return coordinator


def _register_entity(
    hass: HomeAssistant, entry, platform: str, key: str
) -> er.RegistryEntry:
    """Create an entity registry entry for the config entry with the given key."""
    registry = er.async_get(hass)
    return registry.async_get_or_create(
        platform,
        DOMAIN,
        f"{entry.entry_id}_{key}",
        config_entry=entry,
    )


# ── _unavailable_data_prefixes ────────────────────────────────────────────────


def test_unavailable_prefixes_all_none() -> None:
    """Every dynamic prefix is protected when all source data is None."""
    prefixes = _unavailable_data_prefixes(UnraidData())
    assert "container_" in prefixes
    assert "vm_" in prefixes
    assert "disk_" in prefixes
    assert "remote_share_" in prefixes
    assert "unassigned_device_" in prefixes
    assert "fan_" in prefixes


def test_unavailable_prefixes_empty_list_not_protected() -> None:
    """An empty list means the fetch succeeded, so the category is not protected."""
    data = UnraidData(containers=[], remote_shares=[])
    prefixes = _unavailable_data_prefixes(data)
    assert "container_" not in prefixes
    assert "remote_share_" not in prefixes
    # Other categories are still None and stay protected
    assert "vm_" in prefixes


def test_unavailable_prefixes_fan_requires_both_sources() -> None:
    """fan_ stays protected unless both system and fan_control data are present."""
    data = UnraidData(system=mock_system_info())
    assert "fan_" in _unavailable_data_prefixes(data)

    data = UnraidData(system=mock_system_info(), fan_control=MagicMock())
    assert "fan_" not in _unavailable_data_prefixes(data)


# ── async_cleanup_stale_entities ──────────────────────────────────────────────


async def test_no_removal_when_update_failed(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Cleanup is a no-op when the last coordinator update failed."""
    entry = mock_config_entry
    _register_entity(hass, entry, "switch", "container_ghost_abc123")

    coordinator = _make_coordinator(UnraidData(containers=[]))
    coordinator.last_update_success = False

    async_cleanup_stale_entities(hass, entry, coordinator)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}_container_ghost_abc123"
    )


async def test_no_removal_when_category_data_unavailable(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Entities whose source data is None (fetch failed) are never candidates."""
    entry = mock_config_entry
    _register_entity(hass, entry, "switch", "container_ghost_abc123")

    # containers is None -> docker fetch failed; absence is not meaningful
    coordinator = _make_coordinator(UnraidData(containers=None))

    async_cleanup_stale_entities(hass, entry, coordinator)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}_container_ghost_abc123"
    )
    assert not coordinator.stale_entity_candidates


async def test_removal_deferred_until_grace_elapsed(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """A missing item is only removed after STALE_REMOVAL_GRACE, not on first miss."""
    entry = mock_config_entry
    _register_entity(hass, entry, "switch", "container_ghost_abc123")
    unique_id = f"{entry.entry_id}_container_ghost_abc123"

    # containers == [] -> docker responded and the container is genuinely gone
    coordinator = _make_coordinator(UnraidData(containers=[]))

    # First pass: tracked as candidate but NOT removed
    async_cleanup_stale_entities(hass, entry, coordinator)
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("switch", DOMAIN, unique_id)
    assert unique_id in coordinator.stale_entity_candidates

    # Simulate the grace period having elapsed
    coordinator.stale_entity_candidates[unique_id] = (
        dt_util.utcnow() - STALE_REMOVAL_GRACE - timedelta(seconds=1)
    )

    async_cleanup_stale_entities(hass, entry, coordinator)
    assert registry.async_get_entity_id("switch", DOMAIN, unique_id) is None
    assert unique_id not in coordinator.stale_entity_candidates


async def test_candidate_cleared_when_item_reappears(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """A tracked candidate is dropped if its data becomes valid again."""
    entry = mock_config_entry
    _register_entity(hass, entry, "binary_sensor", "remote_share_media_mounted")
    unique_id = f"{entry.entry_id}_remote_share_media_mounted"

    coordinator = _make_coordinator(UnraidData(remote_shares=[]))
    async_cleanup_stale_entities(hass, entry, coordinator)
    assert unique_id in coordinator.stale_entity_candidates

    # Share comes back before the grace elapses
    share = MagicMock()
    share.name = "media"
    coordinator.data = UnraidData(remote_shares=[share])

    async_cleanup_stale_entities(hass, entry, coordinator)
    assert unique_id not in coordinator.stale_entity_candidates
    registry = er.async_get(hass)
    assert registry.async_get_entity_id("binary_sensor", DOMAIN, unique_id)


async def test_no_removal_during_reboot_grace_period(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Cleanup is suppressed entirely while in the post-reboot grace period."""
    entry = mock_config_entry
    _register_entity(hass, entry, "switch", "container_ghost_abc123")

    coordinator = _make_coordinator(UnraidData(containers=[]))
    coordinator.in_reboot_grace_period = True

    async_cleanup_stale_entities(hass, entry, coordinator)

    registry = er.async_get(hass)
    assert registry.async_get_entity_id(
        "switch", DOMAIN, f"{entry.entry_id}_container_ghost_abc123"
    )
    assert not coordinator.stale_entity_candidates


# ── async_prune_seen_names ────────────────────────────────────────────────────


async def test_prune_seen_names_drops_missing_entities(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """Names whose registry entity is gone are pruned; existing ones are kept."""
    entry = mock_config_entry
    _register_entity(hass, entry, "binary_sensor", "remote_share_kept_mounted")

    seen = {"kept", "deleted"}
    async_prune_seen_names(
        hass,
        "binary_sensor",
        seen,
        lambda name: f"{entry.entry_id}_remote_share_{name}_mounted",
    )

    assert seen == {"kept"}


async def test_prune_seen_names_allows_recreation(
    hass: HomeAssistant, mock_config_entry
) -> None:
    """After registry removal, pruning empties the set so entities can be re-created."""
    entry = mock_config_entry
    entity = _register_entity(
        hass, entry, "binary_sensor", "remote_share_media_mounted"
    )
    seen = {"media"}

    registry = er.async_get(hass)
    registry.async_remove(entity.entity_id)

    async_prune_seen_names(
        hass,
        "binary_sensor",
        seen,
        lambda name: f"{entry.entry_id}_remote_share_{name}_mounted",
    )
    assert seen == set()


# ── Coordinator failure semantics (#83) ───────────────────────────────────────


@pytest.mark.usefixtures("mock_unraid_websocket_client_class")
class TestCoordinatorFailureSemantics:
    """The coordinator must fail (not return empty data) when the server is gone."""

    async def _make_coordinator(
        self, hass: HomeAssistant, entry: MockConfigEntry, client: MagicMock
    ) -> UnraidDataUpdateCoordinator:
        return UnraidDataUpdateCoordinator(
            hass, entry=entry, client=client, enable_websocket=False
        )

    async def test_update_failed_when_core_endpoints_unreachable(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client: MagicMock,
    ) -> None:
        """All-endpoints-down raises UpdateFailed instead of returning empty data."""
        from homeassistant.helpers.update_coordinator import UpdateFailed

        mock_async_unraid_client.get_system_info.side_effect = Exception("down")
        mock_async_unraid_client.get_array_status.side_effect = Exception("down")

        coordinator = await self._make_coordinator(
            hass, mock_config_entry, mock_async_unraid_client
        )

        with pytest.raises(UpdateFailed):
            await coordinator._async_update_data()
        assert coordinator.consecutive_failed_updates == 1

    async def test_partial_fetch_failure_preserves_none(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client: MagicMock,
    ) -> None:
        """A failed category fetch yields None (not []) so cleanup can tell them apart."""
        mock_async_unraid_client.list_containers.side_effect = Exception("stalled")

        coordinator = await self._make_coordinator(
            hass, mock_config_entry, mock_async_unraid_client
        )

        data = await coordinator._async_update_data()
        assert data.containers is None
        assert data.vms is not None
        assert coordinator.consecutive_failed_updates == 0
        assert coordinator.last_successful_update is not None

    async def test_ws_reconnect_triggers_debounced_refresh(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client: MagicMock,
    ) -> None:
        """WebSocket connect schedules one refresh; rapid reconnects are debounced."""
        coordinator = await self._make_coordinator(
            hass, mock_config_entry, mock_async_unraid_client
        )
        refresh_calls = []

        async def _fake_refresh() -> None:
            refresh_calls.append(1)

        coordinator.async_request_refresh = _fake_refresh

        # A connect right after setup is debounced (timestamp seeded at init)
        coordinator._handle_ws_connect()
        await hass.async_block_till_done()
        assert len(refresh_calls) == 0

        # Once the debounce window has passed, a reconnect triggers one refresh
        coordinator._last_reconnect_refresh = dt_util.utcnow() - timedelta(seconds=11)
        coordinator._handle_ws_connect()
        coordinator._handle_ws_connect()
        await hass.async_block_till_done()

        assert len(refresh_calls) == 1
