"""WebSocket client for Unraid Management Agent."""

from __future__ import annotations

import asyncio
import json
import logging
from collections.abc import Callable
from typing import Any

import aiohttp

from .const import (
    API_WEBSOCKET,
    EVENT_ARRAY_STATUS_UPDATE,
    EVENT_CONTAINER_LIST_UPDATE,
    EVENT_DISK_LIST_UPDATE,
    EVENT_GPU_UPDATE,
    EVENT_NETWORK_LIST_UPDATE,
    EVENT_SHARE_LIST_UPDATE,
    EVENT_SYSTEM_UPDATE,
    EVENT_UPS_STATUS_UPDATE,
    EVENT_VM_LIST_UPDATE,
    WEBSOCKET_MAX_RETRIES,
    WEBSOCKET_RECONNECT_DELAY,
)

_LOGGER = logging.getLogger(__name__)


def identify_event_type(data: Any) -> str:
    """
    Identify event type from data structure.

    Events don't have a 'type' field, so we inspect the data structure.
    List-based events (disks, containers, VMs, network, shares) are identified
    by checking the first element in the array.
    """
    # Handle arrays - check first element for list-based events
    is_list = isinstance(data, list)
    if is_list:
        if not data:
            # Empty list - could be any list-based event, ignore silently
            return "empty_list"
        # Check first element to identify list type
        first_item = data[0]
        if not isinstance(first_item, dict):
            return "unknown"

        # Disk list (array of disks)
        if (
            "device" in first_item
            and "status" in first_item
            and "filesystem" in first_item
        ):
            return EVENT_DISK_LIST_UPDATE

        # Container list (array of containers)
        if (
            "image" in first_item
            and "ports" in first_item
            and ("id" in first_item or "container_id" in first_item)
        ):
            return EVENT_CONTAINER_LIST_UPDATE

        # VM list (array of VMs)
        if "state" in first_item and "cpu_count" in first_item:
            return EVENT_VM_LIST_UPDATE

        # Network interface list (array of interfaces)
        if "mac_address" in first_item and "bytes_received" in first_item:
            return EVENT_NETWORK_LIST_UPDATE

        # Share list (array of shares)
        if (
            "name" in first_item
            and "path" in first_item
            and "total_bytes" in first_item
        ):
            return EVENT_SHARE_LIST_UPDATE

        # GPU list (array of GPUs)
        if (
            "available" in first_item
            and "driver_version" in first_item
            and "utilization_gpu_percent" in first_item
        ):
            return EVENT_GPU_UPDATE

        return "unknown"

    # Must be a dict to identify single-object events
    if not isinstance(data, dict):
        return "unknown"

    # System update
    if "hostname" in data and "cpu_usage_percent" in data:
        return EVENT_SYSTEM_UPDATE

    # Array status
    if "state" in data and "parity_check_status" in data and "num_disks" in data:
        return EVENT_ARRAY_STATUS_UPDATE

    # UPS status
    if "connected" in data and "battery_charge_percent" in data:
        return EVENT_UPS_STATUS_UPDATE

    return "unknown"


class UnraidWebSocketClient:
    """WebSocket client for real-time updates from Unraid Management Agent."""

    def __init__(
        self,
        host: str,
        port: int,
        session: aiohttp.ClientSession,
        callback: Callable[[str, Any], None],
    ) -> None:
        """Initialize the WebSocket client."""
        self.host = host
        self.port = port
        self.session = session
        self.callback = callback
        self.ws_url = f"ws://{host}:{port}{API_WEBSOCKET}"

        self._ws: aiohttp.ClientWebSocketResponse | None = None
        self._connected = False
        self._reconnect_count = 0
        self._stop_requested = False

    @property
    def is_connected(self) -> bool:
        """Return True if WebSocket is connected."""
        return self._connected and self._ws is not None and not self._ws.closed

    async def connect(self) -> None:
        """Connect to the WebSocket."""
        if self._stop_requested:
            return

        try:
            _LOGGER.info("Connecting to WebSocket: %s", self.ws_url)
            self._ws = await self.session.ws_connect(
                self.ws_url,
                heartbeat=30,
                timeout=aiohttp.ClientTimeout(total=10),
            )
            self._connected = True
            self._reconnect_count = 0
            _LOGGER.info("WebSocket connected successfully")
        except Exception as err:
            _LOGGER.error("Failed to connect to WebSocket: %s", err)
            self._connected = False
            raise

    async def disconnect(self) -> None:
        """Disconnect from the WebSocket."""
        self._stop_requested = True
        self._connected = False

        if self._ws and not self._ws.closed:
            await self._ws.close()
            _LOGGER.info("WebSocket disconnected")

    async def listen(self) -> None:
        """Listen for WebSocket messages with automatic reconnection."""
        while not self._stop_requested:
            try:
                # Connect if not connected
                if not self.is_connected:
                    await self.connect()

                # Listen for messages
                async for msg in self._ws:
                    if msg.type == aiohttp.WSMsgType.TEXT:
                        await self._handle_message(msg.data)
                    elif msg.type == aiohttp.WSMsgType.ERROR:
                        _LOGGER.error("WebSocket error: %s", self._ws.exception())
                        break
                    elif msg.type == aiohttp.WSMsgType.CLOSED:
                        _LOGGER.warning("WebSocket closed by server")
                        break

                # Connection closed, attempt reconnection
                if not self._stop_requested:
                    await self._reconnect()

            except asyncio.CancelledError:
                _LOGGER.debug("WebSocket listen task cancelled")
                break
            except Exception as err:
                _LOGGER.error("WebSocket error: %s", err)
                if not self._stop_requested:
                    await self._reconnect()

    async def _handle_message(self, data: str) -> None:
        """Handle incoming WebSocket message."""
        try:
            message = json.loads(data)

            # Extract event data
            event_data = message.get("data")
            if event_data is None:
                _LOGGER.debug("Received message without data field")
                return

            # Identify event type
            event_type = identify_event_type(event_data)

            # Handle empty lists silently (normal occurrence)
            if event_type == "empty_list":
                return

            # Log unknown events at debug level with details
            if event_type == "unknown":
                if isinstance(event_data, dict):
                    _LOGGER.debug(
                        "Received unknown event type with keys: %s",
                        list(event_data.keys()),
                    )
                elif isinstance(event_data, list) and event_data:
                    _LOGGER.debug(
                        "Received unknown list event, first item keys: %s",
                        (
                            list(event_data[0].keys())
                            if isinstance(event_data[0], dict)
                            else type(event_data[0])
                        ),
                    )
                else:
                    _LOGGER.debug("Received unknown event type: %s", type(event_data))
                return

            # Call callback with event type and data
            if self.callback:
                self.callback(event_type, event_data)

        except json.JSONDecodeError as err:
            _LOGGER.error("Failed to decode WebSocket message: %s", err)
        except Exception as err:
            _LOGGER.error("Error handling WebSocket message: %s", err)

    async def _reconnect(self) -> None:
        """Attempt to reconnect with exponential backoff."""
        self._connected = False

        if self._reconnect_count >= WEBSOCKET_MAX_RETRIES:
            _LOGGER.error(
                "Max reconnection attempts (%d) reached, giving up",
                WEBSOCKET_MAX_RETRIES,
            )
            self._stop_requested = True
            return

        # Calculate delay with exponential backoff
        delay_index = min(self._reconnect_count, len(WEBSOCKET_RECONNECT_DELAY) - 1)
        delay = WEBSOCKET_RECONNECT_DELAY[delay_index]

        _LOGGER.info(
            "Reconnecting in %d seconds (attempt %d/%d)",
            delay,
            self._reconnect_count + 1,
            WEBSOCKET_MAX_RETRIES,
        )

        await asyncio.sleep(delay)
        self._reconnect_count += 1
