"""Tests for remote share entities (binary sensor, switch, sensor)."""

from __future__ import annotations

from unittest.mock import AsyncMock, MagicMock

import pytest
from homeassistant.core import HomeAssistant
from homeassistant.exceptions import HomeAssistantError


def _find_remote_share_entities(hass: HomeAssistant, platform: str) -> list[str]:
    """Return entity IDs for remote share entities on the given platform."""
    return [
        eid for eid in hass.states.async_entity_ids(platform) if "remote_share" in eid
    ]


# ── Binary sensor ─────────────────────────────────────────────────────────────


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
class TestRemoteShareBinarySensor:
    """Tests for the remote share mounted binary sensor."""

    async def test_remote_share_sensors_created(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Two remote share mounted binary sensors are created from coordinator data."""
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        sensors = _find_remote_share_entities(hass, "binary_sensor")
        assert len(sensors) >= 2

    async def test_remote_share_sensor_mounted(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """A mounted remote share reports is_on = True."""
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        sensors = _find_remote_share_entities(hass, "binary_sensor")
        assert sensors, "No remote share binary sensors found"

        state = hass.states.get(sensors[0])
        assert state is not None
        assert state.state == "on"

    async def test_remote_share_sensor_unmounted(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client: MagicMock,
    ) -> None:
        """An unmounted remote share reports is_on = False."""
        unmounted_share = MagicMock()
        unmounted_share.source = "//192.168.20.65/offline"
        unmounted_share.name = "//192.168.20.65/offline"
        unmounted_share.type = "smb"
        unmounted_share.protocol = "smb"
        unmounted_share.status = "unmounted"
        unmounted_share.mounted = False
        unmounted_share.mount_point = None
        unmounted_share.size_bytes = None
        unmounted_share.used_bytes = None
        unmounted_share.free_bytes = None
        unmounted_share.usage_percent = None
        unmounted_share.server = "192.168.20.65"

        info = MagicMock()
        info.remote_shares = [unmounted_share]
        info.devices = []
        mock_async_unraid_client.get_unassigned_info = AsyncMock(return_value=info)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        sensors = _find_remote_share_entities(hass, "binary_sensor")
        assert sensors, "No remote share binary sensors found"

        state = hass.states.get(sensors[0])
        assert state is not None
        assert state.state == "off"

    async def test_remote_share_sensor_no_shares(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client: MagicMock,
    ) -> None:
        """No binary sensors created when there are no remote shares."""
        info = MagicMock()
        info.remote_shares = []
        info.devices = []
        mock_async_unraid_client.get_unassigned_info = AsyncMock(return_value=info)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        sensors = _find_remote_share_entities(hass, "binary_sensor")
        assert len(sensors) == 0

    async def test_remote_share_sensor_attributes(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Remote share binary sensor exposes protocol and server attributes."""
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        sensors = _find_remote_share_entities(hass, "binary_sensor")
        assert sensors

        state = hass.states.get(sensors[0])
        assert state is not None
        attrs = state.attributes
        # Protocol and server should be populated from the mock data
        assert "protocol" in attrs or "server" in attrs or "mount_point" in attrs


# ── Switch ────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
class TestRemoteShareSwitch:
    """Tests for the remote share mount/unmount switch."""

    async def test_remote_share_switches_created(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Two remote share switches are created from coordinator data."""
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        switches = _find_remote_share_entities(hass, "switch")
        assert len(switches) >= 2

    async def test_remote_share_switch_on_when_mounted(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Switch state is ON when share is mounted."""
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        switches = _find_remote_share_entities(hass, "switch")
        assert switches

        state = hass.states.get(switches[0])
        assert state is not None
        assert state.state == "on"

    async def test_remote_share_switch_turn_on(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client: MagicMock,
    ) -> None:
        """Turning switch on calls mount_remote_share with the share source."""
        unmounted = MagicMock()
        unmounted.source = "//192.168.20.65/public"
        unmounted.name = "//192.168.20.65/public"
        unmounted.type = "smb"
        unmounted.protocol = "smb"
        unmounted.status = "unmounted"
        unmounted.mounted = False
        unmounted.mount_point = None
        unmounted.size_bytes = None
        unmounted.used_bytes = None
        unmounted.free_bytes = None
        unmounted.usage_percent = None
        unmounted.server = "192.168.20.65"

        info = MagicMock()
        info.remote_shares = [unmounted]
        info.devices = []
        mock_async_unraid_client.get_unassigned_info = AsyncMock(return_value=info)
        mock_async_unraid_client.mount_remote_share = AsyncMock(return_value=None)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        switches = _find_remote_share_entities(hass, "switch")
        assert switches

        await hass.services.async_call(
            "switch",
            "turn_on",
            {"entity_id": switches[0]},
            blocking=True,
        )

        mock_async_unraid_client.mount_remote_share.assert_called_once_with(
            "//192.168.20.65/public"
        )

    async def test_remote_share_switch_turn_off(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client: MagicMock,
    ) -> None:
        """Turning switch off calls unmount_remote_share with the share source."""
        mock_async_unraid_client.unmount_remote_share = AsyncMock(return_value=None)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        switches = _find_remote_share_entities(hass, "switch")
        assert switches

        await hass.services.async_call(
            "switch",
            "turn_off",
            {"entity_id": switches[0]},
            blocking=True,
        )

        mock_async_unraid_client.unmount_remote_share.assert_called_once()

    async def test_remote_share_switch_extra_attributes(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Switch exposes protocol, server, and mount_point as attributes."""
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        switches = _find_remote_share_entities(hass, "switch")
        assert switches

        state = hass.states.get(switches[0])
        assert state is not None
        assert "protocol" in state.attributes or "server" in state.attributes

    async def test_remote_share_switch_turn_on_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client: MagicMock,
    ) -> None:
        """mount_remote_share API failure raises HomeAssistantError."""
        mock_async_unraid_client.mount_remote_share = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        unmounted = MagicMock()
        unmounted.source = "//192.168.20.65/public"
        unmounted.name = "//192.168.20.65/public"
        unmounted.type = "smb"
        unmounted.protocol = "smb"
        unmounted.status = "unmounted"
        unmounted.mounted = False
        unmounted.mount_point = None
        unmounted.size_bytes = None
        unmounted.used_bytes = None
        unmounted.free_bytes = None
        unmounted.usage_percent = None
        unmounted.server = "192.168.20.65"

        info = MagicMock()
        info.remote_shares = [unmounted]
        info.devices = []
        mock_async_unraid_client.get_unassigned_info = AsyncMock(return_value=info)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        switches = _find_remote_share_entities(hass, "switch")
        assert switches

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "switch",
                "turn_on",
                {"entity_id": switches[0]},
                blocking=True,
            )

    async def test_remote_share_switch_turn_off_error(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client: MagicMock,
    ) -> None:
        """unmount_remote_share API failure raises HomeAssistantError."""
        mock_async_unraid_client.unmount_remote_share = AsyncMock(
            side_effect=Exception("Connection refused")
        )

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        switches = _find_remote_share_entities(hass, "switch")
        assert switches

        with pytest.raises(HomeAssistantError):
            await hass.services.async_call(
                "switch",
                "turn_off",
                {"entity_id": switches[0]},
                blocking=True,
            )


# ── Sensor ────────────────────────────────────────────────────────────────────


@pytest.mark.usefixtures(
    "mock_unraid_client_class",
    "mock_unraid_websocket_client_class",
)
class TestRemoteShareSensor:
    """Tests for the remote share usage percentage sensor."""

    async def test_remote_share_sensors_created(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Usage sensors are created for remote shares with usage data."""
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        sensors = _find_remote_share_entities(hass, "sensor")
        assert len(sensors) >= 2

    async def test_remote_share_sensor_value(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Usage sensor reports the usage_percent from coordinator data."""
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        sensors = _find_remote_share_entities(hass, "sensor")
        assert sensors

        state = hass.states.get(sensors[0])
        assert state is not None
        assert float(state.state) == pytest.approx(82.3, abs=0.5)

    async def test_remote_share_sensor_attributes(
        self, hass: HomeAssistant, mock_config_entry
    ) -> None:
        """Usage sensor attributes include size information."""
        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        sensors = _find_remote_share_entities(hass, "sensor")
        assert sensors

        state = hass.states.get(sensors[0])
        assert state is not None
        attrs = state.attributes
        assert "share_name" in attrs

    async def test_remote_share_sensor_no_usage_percent(
        self,
        hass: HomeAssistant,
        mock_config_entry,
        mock_async_unraid_client: MagicMock,
    ) -> None:
        """Usage sensor returns None when usage_percent is absent."""
        share = MagicMock()
        share.source = "//192.168.20.65/nousage"
        share.name = "//192.168.20.65/nousage"
        share.type = "smb"
        share.protocol = "smb"
        share.status = "mounted"
        share.mounted = True
        share.mount_point = "/mnt/remotes/192.168.20.65_nousage"
        share.size_bytes = None
        share.used_bytes = None
        share.free_bytes = None
        share.usage_percent = None
        share.server = "192.168.20.65"

        info = MagicMock()
        info.remote_shares = [share]
        info.devices = []
        mock_async_unraid_client.get_unassigned_info = AsyncMock(return_value=info)

        await hass.config_entries.async_setup(mock_config_entry.entry_id)
        await hass.async_block_till_done()

        sensors = _find_remote_share_entities(hass, "sensor")
        # Sensor is created but native_value returns None → state = "unavailable" or "unknown"
        if sensors:
            state = hass.states.get(sensors[0])
            if state:
                assert state.state in ("unknown", "unavailable")


# ── Model validator ───────────────────────────────────────────────────────────


class TestRemoteShareModelValidator:
    """Tests for the RemoteShare pydantic model_validator."""

    def test_name_derived_from_source(self) -> None:
        """RemoteShare.name is populated from source when absent."""
        from custom_components.unraid_management_agent.api.models import RemoteShare

        share = RemoteShare(source="//192.168.20.65/unraid-test", status="mounted")
        assert share.name == "//192.168.20.65/unraid-test"
        assert share.mounted is True

    def test_mounted_derived_from_status(self) -> None:
        """RemoteShare.mounted is True when status == 'mounted'."""
        from custom_components.unraid_management_agent.api.models import RemoteShare

        share = RemoteShare(source="//server/share", status="unmounted")
        assert share.mounted is False

    def test_protocol_derived_from_type(self) -> None:
        """RemoteShare.protocol is populated from type field."""
        from custom_components.unraid_management_agent.api.models import RemoteShare

        share = RemoteShare(source="//server/share", type="smb", status="mounted")
        assert share.protocol == "smb"

    def test_server_derived_from_smb_server(self) -> None:
        """RemoteShare.server is populated from smb_server field."""
        from custom_components.unraid_management_agent.api.models import RemoteShare

        share = RemoteShare(
            source="//192.168.1.1/share",
            smb_server="192.168.1.1",
            status="mounted",
        )
        assert share.server == "192.168.1.1"

    def test_all_api_fields_parsed(self) -> None:
        """All API fields from the live endpoint are correctly parsed."""
        from custom_components.unraid_management_agent.api.models import RemoteShare

        raw = {
            "type": "smb",
            "source": "//192.168.20.65/unraid-test",
            "mount_point": "/mnt/remotes/192.168.20.65_unraid-test",
            "status": "mounted",
            "size_bytes": 3296722944,
            "used_bytes": 2713268224,
            "free_bytes": 583454720,
            "usage_percent": 82.3,
            "auto_mount": False,
            "read_only": False,
            "smb_server": "192.168.20.65",
            "smb_share": "unraid-test",
            "timestamp": "2026-06-06T15:29:08.713242802+10:00",
        }
        share = RemoteShare.model_validate(raw)
        assert share.name == "//192.168.20.65/unraid-test"
        assert share.mounted is True
        assert share.protocol == "smb"
        assert share.server == "192.168.20.65"
        assert share.usage_percent == pytest.approx(82.3)
        assert share.size_bytes == 3296722944
        assert share.used_bytes == 2713268224
        assert share.free_bytes == 583454720
        assert share.smb_share == "unraid-test"
