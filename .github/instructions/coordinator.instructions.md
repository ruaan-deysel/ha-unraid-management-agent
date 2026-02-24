---
applyTo: "custom_components/unraid_management_agent/coordinator.py"
---

# Coordinator Instructions

**Applies to:** Coordinator implementation file

## Using the Coordinator

- `self.coordinator.data.system_info` (in entity properties via `value_fn`)
- **Never** fetch directly in entities: `await self.client.get_system_info()`

## Architecture

`UnraidDataUpdateCoordinator` extends `DataUpdateCoordinator[UnraidData]`:

- Fixed 30-second polling interval
- WebSocket for real-time push updates
- Individual API calls wrapped in try/except (debug-level logging for failures)
- Outer try/except raises `UpdateFailed` for total failure
- Logs unavailability once and recovery once (no log spam)

## Error Handling in `_async_update_data()`

**Exception mapping:**

- `UnraidConnectionError` -> `raise UpdateFailed("message") from err`
- `TimeoutError` and `aiohttp.ClientError` -> handled by coordinator base class
- No auth errors (local API without authentication)

## Pull vs. Push Architecture

This integration uses a **hybrid** approach:

- **Polling (Pull):** 30-second interval via `_async_update_data()`
- **Push (WebSocket):** Real-time updates via `UnraidWebSocketClient`
- Call `coordinator.async_set_updated_data(new_data)` when WebSocket events arrive

## First Refresh

**In `async_setup_entry()`:** Call `await coordinator.async_config_entry_first_refresh()`

If `_async_update_data()` raises `UpdateFailed`, coordinator raises `ConfigEntryNotReady` automatically.

## Collector Status

The coordinator tracks which collectors are enabled on the Unraid server:

```python
def is_collector_enabled(self, collector_name: str) -> bool:
    """Check if a collector is enabled."""
```

Entity platforms use this to skip creating entities for disabled collectors.

## Data Structure

```python
@dataclass
class UnraidData:
    system_info: SystemInfo | None
    array_status: ArrayStatus | None
    disks: list[DiskInfo]
    containers: list[ContainerInfo]
    vms: list[VMInfo]
    # ... etc
```

## WebSocket Lifecycle

- Started in `async_setup_entry()` after first refresh
- Event types parsed with `parse_event()` from `uma-api`
- Auto-reconnect handled by `UnraidWebSocketClient`
- Stopped in `async_unload_entry()` before client close
- Tasks cancelled and awaited on cleanup
