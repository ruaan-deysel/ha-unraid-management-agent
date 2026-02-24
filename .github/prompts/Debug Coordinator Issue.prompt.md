---
agent: "agent"
tools: ["search/codebase", "search", "problems", "runCommands", "runCommands/terminalLastCommand"]
description: "Diagnose and fix data update coordinator problems like stale data or unavailable entities"
---

# Debug Coordinator Issue

Your goal is to diagnose and fix issues with the data update coordinator.

## Common Issues to Check

**Data Not Updating:**

- Check coordinator update interval in `coordinator.py` (fixed 30-second polling)
- Verify `_async_update_data()` is actually fetching new data
- Look for exceptions in Home Assistant logs
- Check if `uma-api` client is returning stale data
- Verify WebSocket connection status (real-time updates)
- Check collector status -- disabled collectors won't provide data

**Entities Unavailable:**

- Check if coordinator is raising `UpdateFailed` exception
- Verify entity's `available` property logic in `entity.py`
- Look for missing keys in `UnraidData`
- Check API connection (no auth required, just network reachability)
- Verify error handling in `_async_update_data()`

**WebSocket Issues:**

- Check WebSocket client lifecycle management
- Verify event parsing with `parse_event()`
- Check auto-reconnect behavior
- Look for `UnraidConnectionError` in logs

**Performance Issues:**

- Check if data processing in coordinator is efficient
- Verify individual API calls have proper error handling (debug-level logging)
- Look for blocking I/O (should be async throughout)

## Debugging Steps

1. **Enable Debug Logging:**
   - Add/verify in `config/configuration.yaml`:
     ```yaml
     logger:
       logs:
         custom_components.unraid_management_agent: debug
     ```
   - Restart Home Assistant: `./scripts/develop`

2. **Check Logs:**
   - Look at terminal output where `./scripts/develop` is running
   - Or check `config/home-assistant.log`
   - Search for error traces and `UpdateFailed` exceptions

3. **Verify Coordinator State:**
   - Check `coordinator.last_update_success`
   - Inspect `coordinator.data` structure (it's `UnraidData`)
   - Verify `coordinator.update_interval` is 30 seconds

4. **Test API Client:**
   - Check if `UnraidClient` methods are returning data
   - Verify Pydantic model parsing is working
   - Check for `UnraidConnectionError` exceptions

## Common Fixes

**Add Error Handling:**

```python
async def _async_update_data(self) -> UnraidData:
    """Fetch data from API."""
    try:
        system_info = await self.client.get_system_info()
    except UnraidConnectionError as err:
        raise UpdateFailed(f"Connection error: {err}") from err
```

**Handle Missing Data:**

```python
value_fn=lambda data: data.system_info.cpu_usage if data.system_info else None,
```

## Related Files to Review

- `custom_components/unraid_management_agent/coordinator.py` -- Coordinator implementation
- `custom_components/unraid_management_agent/entity.py` -- Base entity availability
- `custom_components/unraid_management_agent/__init__.py` -- Setup and cleanup
- `config/home-assistant.log` -- Error traces

## Before Finishing

- Run `scripts/lint` to validate code quality
- Restart Home Assistant to test fixes
- Monitor logs for any remaining errors
- Verify entities update correctly and stay available
