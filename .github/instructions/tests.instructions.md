---
applyTo: "tests/**/*.py"
---

# Test Instructions

**Applies to:** `tests/` directory

## Test Structure

**Mirror integration structure:**

```text
tests/
  conftest.py             # Shared fixtures
  const.py                # Mock data factories (Pydantic models)
  test_init.py            # Integration setup/unload
  test_config_flow.py     # Config flow tests
  test_coordinator.py     # Coordinator tests
  test_sensor.py          # Sensor tests
  test_binary_sensor.py   # Binary sensor tests
  test_switch.py          # Switch tests
  test_button.py          # Button tests
  test_repairs.py         # Repair flow tests
  test_diagnostics.py     # Diagnostic tests
```

## Conventions

- **No test classes.** All tests are plain `async def test_*` functions.
- **`asyncio_mode = "auto"`** -- no `@pytest.mark.asyncio` needed.
- **No inline patches.** Use `@pytest.mark.usefixtures(...)` for integration tests.
- **Use `is` for enum comparisons:** `assert result["type"] is FlowResultType.FORM`

## Fixtures

**Layered fixture pattern (in `conftest.py`):**

1. `mock_async_unraid_client` -- Fully mocked `UnraidClient` with all API methods as `AsyncMock`
2. `mock_websocket_client` -- Mocked `UnraidWebSocketClient`
3. `mock_unraid_client_class` -- Patches `UnraidClient` in integration module
4. `mock_unraid_websocket_client_class` -- Patches `UnraidWebSocketClient`
5. `mock_config_entry` -- Creates and registers `MockConfigEntry`
6. `mock_unraid_data` -- Populated `UnraidData` instance
7. `mock_coordinator` -- Mocked coordinator with data

**Mock data factories** in `tests/const.py` mirror the vendored API models used by the integration.

## Test Patterns

**Integration test:**

```python
@pytest.mark.usefixtures("mock_unraid_client_class", "mock_unraid_websocket_client_class")
async def test_switch_setup(hass: HomeAssistant, mock_config_entry) -> None:
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("switch")) > 0
```

**Unit test:**

```python
def test_is_array_started_no_data():
    coordinator = MagicMock()
    coordinator.data = None
    assert _is_array_started(coordinator) is False
```

**Config flow test:**

```python
result = await hass.config_entries.flow.async_init(
    DOMAIN, context={"source": "user"}, data={...}
)
assert result["type"] is FlowResultType.CREATE_ENTRY
```

## Mocking

- **Mock:** The vendored API client methods and network calls
- **Don't mock:** Home Assistant internals, your own integration code
- Use `patch.object()` for success cases, `side_effect` for errors

## Coverage

- Target: **95%+** (current: ~94-95%)
- Config flow target: **100%**
- Minimum threshold: **60%** (in pyproject.toml)

## Commands

```bash
pytest tests/ -v --timeout=30                    # All tests
pytest tests/ --cov=custom_components.unraid_management_agent --cov-report=term-missing
pytest tests/test_sensor.py -v                   # Single file
pytest tests/test_sensor.py::test_sensor_setup   # Single test
```
