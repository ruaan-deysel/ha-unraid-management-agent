"""WebSocket client for real-time Unraid updates."""

from __future__ import annotations

import logging
from collections.abc import Callable

from uma_api.websocket import UnraidWebSocketClient as UmaWebSocketClient

_LOGGER = logging.getLogger(__name__)


class UnraidWebSocketManager:
    """Manager for Unraid WebSocket connections with event handling."""

    def __init__(
        self,
        host: str,
        port: int,
        on_message_callback: Callable[[dict], None] | None = None,
    ) -> None:
        """
        Initialize the WebSocket manager.

        Args:
            host: Unraid server hostname/IP.
            port: Unraid server port.
            on_message_callback: Callback for raw WebSocket messages.

        """
        self.host = host
        self.port = port
        self.on_message_callback = on_message_callback
        self._ws_client: UmaWebSocketClient | None = None
        self._is_connected = False

    @property
    def is_connected(self) -> bool:
        """Return WebSocket connection state."""
        return self._is_connected and self._ws_client is not None

    async def start(self) -> None:
        """Start WebSocket connection."""
        if self._is_connected:
            _LOGGER.debug("WebSocket already connected")
            return

        try:
            self._ws_client = UmaWebSocketClient(
                host=self.host,
                port=self.port,
                on_message=self._handle_message,
                on_connect=self._on_connect,
                on_disconnect=self._on_disconnect,
                auto_reconnect=True,
                reconnect_delays=[1, 2, 5, 10, 30],
                max_retries=10,
            )

            await self._ws_client.start()
            self._is_connected = True
            _LOGGER.info("WebSocket client started successfully")

        except Exception as err:
            _LOGGER.error("Failed to start WebSocket client: %s", err)
            self._ws_client = None
            self._is_connected = False
            raise

    async def stop(self) -> None:
        """Stop WebSocket connection."""
        if self._ws_client:
            try:
                await self._ws_client.stop()
                _LOGGER.info("WebSocket client stopped")
            except Exception as err:
                _LOGGER.error("Error stopping WebSocket client: %s", err)
            finally:
                self._ws_client = None
                self._is_connected = False

    def _on_connect(self) -> None:
        """Handle WebSocket connection."""
        self._is_connected = True
        _LOGGER.info("WebSocket connected")

    def _on_disconnect(self) -> None:
        """Handle WebSocket disconnection."""
        self._is_connected = False
        _LOGGER.warning("WebSocket disconnected")

    def _handle_message(self, data: dict) -> None:
        """
        Handle incoming WebSocket message.

        Args:
            data: Raw WebSocket message data.

        """
        try:
            if self.on_message_callback:
                self.on_message_callback(data)
        except Exception as err:
            _LOGGER.debug("Error handling WebSocket message: %s", err)
