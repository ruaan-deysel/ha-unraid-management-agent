# AI Agent Instructions

This repository contains `ha-unraid-management-agent`, a Home Assistant custom integration for monitoring and controlling Unraid servers via the Unraid Management Agent (UMA) API. It is installed via HACS and runs as a custom component under `custom_components/unraid_management_agent/`.

## Project overview

- **Type:** Home Assistant custom integration (HACS-compatible)
- **Domain:** `unraid_management_agent`
- **Language:** Python 3.13+
- **API library:** [`uma-api`](https://pypi.org/project/uma-api/) (async Pydantic-based client)
- **Quality target:** Platinum on the [HA Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)
- **IoT class:** `local_push` (polling + WebSocket real-time updates)
- **License:** MIT
- **Owner:** @ruaan-deysel

## Repository structure

```
ha-unraid-management-agent/
├── custom_components/unraid_management_agent/   # Integration source
│   ├── __init__.py           # Entry point: async_setup, async_setup_entry, services
│   ├── config_flow.py        # UI config flow, options flow, reconfigure flow
│   ├── const.py              # Domain constant, config keys, defaults
│   ├── coordinator.py        # DataUpdateCoordinator, UnraidData, UnraidRuntimeData
│   ├── entity.py             # Base entity classes (UnraidBaseEntity, UnraidEntity)
│   ├── sensor.py             # Sensor platform (system, array, disk, GPU, UPS, network, ZFS)
│   ├── binary_sensor.py      # Binary sensor platform (parity, UPS, flash, mover, updates)
│   ├── switch.py             # Switch platform (Docker containers, VMs)
│   ├── button.py             # Button platform (array start/stop, parity check)
│   ├── diagnostics.py        # Diagnostic data collection
│   ├── repairs.py            # Repair issue flows (disk health, temperatures)
│   ├── services.yaml         # Service action definitions
│   ├── strings.json          # User-facing strings and translations
│   ├── icons.json            # Entity and service icons
│   ├── manifest.json         # Integration metadata and dependencies
│   ├── quality_scale.yaml    # Quality scale rule tracking
│   ├── py.typed              # PEP-561 type marker
│   └── translations/en.json  # English translations
├── tests/                    # Test suite
│   ├── conftest.py           # Shared fixtures (mock client, coordinator, config entry)
│   ├── const.py              # Mock data factories (Pydantic model builders)
│   ├── test_init.py          # Integration setup/unload tests
│   ├── test_config_flow.py   # Config flow tests (user, reconfigure, options)
│   ├── test_coordinator.py   # Coordinator data fetching and WebSocket tests
│   ├── test_sensor.py        # Sensor entity and value function tests
│   ├── test_binary_sensor.py # Binary sensor helper and entity tests
│   ├── test_switch.py        # Switch entity and control tests
│   ├── test_button.py        # Button entity and press tests
│   ├── test_repairs.py       # Repair flow tests
│   └── test_diagnostics.py   # Diagnostic data tests
├── scripts/
│   ├── setup                 # Install development dependencies
│   ├── develop               # Start HA dev environment
│   └── lint                  # Run ruff format + ruff check --fix
├── docs/                     # Development documentation
├── pyproject.toml            # Build config, ruff, mypy, pytest settings
├── hacs.json                 # HACS repository metadata
└── .github/workflows/ci.yml  # CI pipeline (lint, test, validate)
```

## Build, lint, and test commands

### Initial setup

```bash
scripts/setup                # Install all dev dependencies
pip install -e ".[dev]"      # Alternative: install from pyproject.toml
```

### Linting and formatting

```bash
scripts/lint                          # Run ruff format + ruff check --fix
ruff format .                         # Format only
ruff check . --fix                    # Lint with auto-fix only
pre-commit run --all-files            # Run all pre-commit hooks
```

Pre-commit hooks include: ruff (format + check), codespell, mypy, yamllint, prettier, and general file checks. Direct commits to `main`/`master` are blocked by pre-commit.

### Running tests

```bash
# Run all tests
pytest tests/ -v --timeout=30

# Run tests with coverage
pytest tests/ \
  --cov=custom_components.unraid_management_agent \
  --cov-report=term-missing \
  --cov-branch

# Run a specific test file
pytest tests/test_sensor.py -v

# Run a specific test
pytest tests/test_sensor.py::test_sensor_setup -v
```

Coverage target: **95%+** (current: ~94-95%). Config flow coverage target: **100%**.

### Type checking

```bash
mypy custom_components/unraid_management_agent/
```

Mypy is configured strictly in `pyproject.toml` (disallow_untyped_defs, strict_equality, etc.) with relaxed settings for `tests/`.

## Code style and conventions

### Python standards

- **Python 3.13+** required. Use modern features: type hints, f-strings, walrus operator, pattern matching, dataclasses.
- **Formatter:** Ruff (line-length 88)
- **Linter:** Ruff with extensive rule set (see `pyproject.toml [tool.ruff.lint]`)
- **Docstrings:** Google convention. Required for all public functions/methods. File headers are short and descriptive.
- **Imports:** Sorted by isort via ruff. `from __future__ import annotations` in every file.
- **Language:** American English, sentence case.

### Naming conventions

- Constants: `UPPER_SNAKE_CASE` with `Final` type annotation
- Classes: `PascalCase`, prefixed with `Unraid` (e.g., `UnraidBaseEntity`, `UnraidDataUpdateCoordinator`)
- Fixtures: `snake_case` prefixed with `mock_` (e.g., `mock_async_unraid_client`)
- Test functions: `test_<what_is_tested>` (plain functions, no test classes)

### Key architectural patterns

This integration follows Home Assistant Core patterns targeting Platinum quality:

#### Runtime data

```python
type UnraidConfigEntry = ConfigEntry[UnraidRuntimeData]

@dataclass
class UnraidRuntimeData:
    coordinator: UnraidDataUpdateCoordinator
    client: UnraidClient
```

#### Coordinator

`UnraidDataUpdateCoordinator` extends `DataUpdateCoordinator[UnraidData]`. It:

- Accepts `config_entry` in constructor (HA best practice)
- Uses a fixed 30-second polling interval (not user-configurable)
- Manages WebSocket lifecycle for real-time updates
- Logs unavailability once and recovery once (no log spam)

#### Base entity

All entities inherit from `UnraidBaseEntity` (in `entity.py`), which:

- Sets `_attr_has_entity_name = True`
- Builds `DeviceInfo` from coordinator data
- Generates `unique_id` from `entry_id + key`
- Implements availability based on `last_update_success` and data presence

#### Entity descriptions

Sensor entities use `UnraidSensorEntityDescription` with `value_fn` and `extra_state_attributes_fn` callables. Binary sensors, switches, and buttons use similar description patterns.

#### Config flow

- `UnraidConfigFlow` with `async_step_user` and `async_step_reconfigure`
- `UnraidOptionsFlowHandler` extends `OptionsFlowWithReload`
- Uses `async_get_clientsession(hass)` for shared session (inject-websession)
- Port validation via `vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))`
- Duplicate prevention via `async_set_unique_id` + `_abort_if_unique_id_configured`

#### Services

Registered in `async_setup` (not `async_setup_entry`). Each service handler:

- Gets coordinator from the first config entry
- Calls the API method, then `coordinator.async_request_refresh()`
- Raises `HomeAssistantError` with `translation_domain`/`translation_key` on failure

#### Resource cleanup

- Config flow uses `async with UnraidClient(...)` context manager
- `async_unload_entry` stops WebSocket, then closes client (only if unload succeeded)
- WebSocket tasks are cancelled and awaited on cleanup

### Error handling

- Config flow: catches `TimeoutError`, `UnraidConnectionError`, generic `Exception`
- Coordinator `_async_update_data`: individual API calls wrapped in try/except (debug-level logging for individual failures), outer try/except raises `UpdateFailed` for total failure
- Services: catch `Exception`, raise `HomeAssistantError` with translation keys
- Setup: `ConfigEntryNotReady` for connection failures
- No authentication required (exempt from reauth flow)

## Testing patterns

### Fixture architecture

The test suite uses a layered fixture pattern:

1. **`mock_async_unraid_client`** - Creates a fully mocked `UnraidClient` instance with all API methods as `AsyncMock`
2. **`mock_websocket_client`** - Creates a mocked `UnraidWebSocketClient`
3. **`mock_unraid_client_class`** - Patches `UnraidClient` in the integration module with `new=mock_class` pattern
4. **`mock_unraid_websocket_client_class`** - Patches `UnraidWebSocketClient` similarly
5. **`mock_config_entry`** - Creates and registers a `MockConfigEntry`
6. **`mock_unraid_data`** - Creates a populated `UnraidData` instance
7. **`mock_coordinator`** - Creates a mocked coordinator with data

### Test conventions

- **No test classes.** All tests are plain `async def test_*` functions.
- **No inline patches in test files.** Use `@pytest.mark.usefixtures("mock_unraid_client_class", "mock_unraid_websocket_client_class")` for integration tests.
- **Use `mock_async_unraid_client: MagicMock`** as a parameter when you need to modify mock behavior or assert calls.
- **Use `is` for enum comparisons:** `assert result["type"] is FlowResultType.FORM`
- **Mock data factories** are in `tests/const.py` and return Pydantic model instances.
- **`asyncio_mode = "auto"`** in pytest config, so no `@pytest.mark.asyncio` needed.

### Example test patterns

```python
# Integration test using fixtures
@pytest.mark.usefixtures("mock_unraid_client_class", "mock_unraid_websocket_client_class")
async def test_switch_setup(hass: HomeAssistant, mock_config_entry) -> None:
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    assert len(hass.states.async_entity_ids("switch")) > 0

# Unit test for helper functions
def test_is_array_started_no_data():
    coordinator = MagicMock()
    coordinator.data = None
    assert _is_array_started(coordinator) is False

# Test needing to inspect API calls
@pytest.mark.usefixtures("mock_unraid_client_class", "mock_unraid_websocket_client_class")
async def test_button_press(hass, mock_config_entry, mock_async_unraid_client) -> None:
    await hass.config_entries.async_setup(mock_config_entry.entry_id)
    await hass.async_block_till_done()
    await hass.services.async_call("button", "press", {"entity_id": "button.unraid_test_start_array"}, blocking=True)
    mock_async_unraid_client.start_array.assert_called()
```

## Git workflow

### Branching

- **Main branch:** `main`
- **Feature branches:** `feature/*`, `enhancement/*`, `fix/*`
- Direct commits to `main` are blocked by pre-commit hook
- PRs target `main`

### CI pipeline

The GitHub Actions CI pipeline (`.github/workflows/ci.yml`) runs on pushes to `main`, `enhancement/*`, `feature/*`, `fix/*` and PRs to `main`. Jobs:

1. **Lint** - `ruff format --check` and `ruff check`
2. **Test** - `pytest` with coverage (uploaded to Codecov)
3. **Validate** - Checks `manifest.json` structure, `strings.json` validity, required files

### Commit conventions

- Use descriptive commit messages explaining the "why"
- Do not amend or squash commits after review has started
- Pre-commit hooks must pass before committing

## Security considerations

- No authentication credentials stored (local API without auth)
- Diagnostics data is redacted via `async_redact_data`
- Uses Home Assistant's shared `aiohttp` session (no custom session management)
- No sensitive data in logs (lazy logging with `%s` format)
- WebSocket connection is local-only (no external exposure)

## API library reference

The integration depends on `uma-api>=1.3.0` which provides:

- **`UnraidClient`** - Async HTTP client for Unraid Management Agent REST API
- **`UnraidWebSocketClient`** - WebSocket client with auto-reconnect
- **Pydantic models** - `SystemInfo`, `ArrayStatus`, `DiskInfo`, `ContainerInfo`, `VMInfo`, `UPSInfo`, `GPUInfo`, `NetworkInterface`, `ShareInfo`, `ZFSPool`, `ZFSDataset`, etc.
- **Error types** - `UnraidConnectionError`
- **Event types** - `EventType` enum, `WebSocketEvent`, `parse_event()`

## Quality scale status

See `quality_scale.yaml` for current rule-by-rule status. Key completions:

- **Bronze:** All done (config-flow, entity-unique-id, runtime-data, etc.)
- **Silver:** All done except test-coverage verification (action-exceptions, config-entry-unloading, parallel-updates, etc.)
- **Gold:** All done (devices, diagnostics, reconfiguration-flow, repair-issues, entity-translations, exception-translations, icon-translations)
- **Platinum:** All done (async-dependency, inject-websession, strict-typing)
- **Remaining todos:** Documentation items (docs-actions, docs-installation-instructions, docs-removal-instructions, etc.) and brand asset submission
