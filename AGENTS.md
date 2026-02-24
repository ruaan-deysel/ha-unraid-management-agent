# AI Agent Instructions

This document provides guidance for AI coding agents working on this Home Assistant custom integration project.

## Project Overview

This is a Home Assistant custom integration for monitoring and controlling Unraid servers via the Unraid Management Agent (UMA) API. It is installed via HACS and runs as a custom component.

**Integration details:**

- **Domain:** `unraid_management_agent`
- **Title:** Unraid Management Agent
- **Class prefix:** `Unraid`
- **Repository:** ruaan-deysel/ha-unraid-management-agent
- **IoT class:** `local_push` (polling + WebSocket real-time updates)
- **Integration type:** `device`
- **Quality target:** Platinum on the [HA Integration Quality Scale](https://developers.home-assistant.io/docs/core/integration-quality-scale/)

**Key directories:**

- `custom_components/unraid_management_agent/` - Main integration code
- `tests/` - Unit and integration tests
- `scripts/` - Development and validation scripts

**Local development:**

**Always use the project's scripts** -- do NOT craft your own `hass`, `pip`, `pytest`, or similar commands. The scripts handle environment setup, virtual environments, and cleanup that raw commands miss. Agents that bypass scripts frequently break.

**Start Home Assistant:**

```bash
./scripts/develop
```

**Reading logs:**

- Live: Terminal where `./scripts/develop` runs
- File: `config/home-assistant.log` (most recent)

**Adjusting log levels:**

- Integration logs: `custom_components.unraid_management_agent: debug` in `config/configuration.yaml`
- You can modify log levels when debugging -- just restart HA after changes

**Context-specific instructions:**

If you're using GitHub Copilot, path-specific instructions in `.github/prompts/*.prompt.md` provide guided workflows for common tasks. This document serves as the primary reference for all agents.

**Other agent entry points:**

- **Claude Code:** See [`CLAUDE.md`](CLAUDE.md) (pointer to this file)
- **Gemini:** See [`GEMINI.md`](GEMINI.md) (pointer to this file)
- **GitHub Copilot:** See [`.github/copilot-instructions.md`](.github/copilot-instructions.md) (compact version of this file)

## Working With Developers

**For workflow basics (small changes, translations, tests, session management):** See `.github/copilot-instructions.md` for quick-reference guidance.

### When Instructions Conflict With Requests

If a developer requests something that contradicts these instructions:

1. **Clarify the intent** - Ask if they want you to deviate from the documented guidelines
2. **Confirm understanding** - Restate what you understood to avoid misinterpretation
3. **Suggest instruction updates** - If this represents a permanent change in approach, offer to update these instructions
4. **Proceed once confirmed** - Follow the developer's explicit direction after clarification

### Maintaining These Instructions

- Refine guidelines based on actual project needs
- Remove outdated rules that no longer apply
- Consolidate redundant sections to prevent bloat

**Propose updates when:**

- You notice repeated deviations from documented patterns
- Instructions become outdated or contradict actual code
- New patterns emerge that should be standardized

### Documentation vs. Instructions

**Three types of content with clear separation:**

1. **Agent Instructions** - How AI should write code (`.github/prompts/`, `AGENTS.md`)
2. **Developer Documentation** - Architecture and design decisions (`docs/`)
3. **User Documentation** - End-user guides (`README.md`)

**AI Planning:** Use `.ai-scratch/` for temporary notes (never committed)

**Rules:**

- **NEVER** create random markdown files in code directories
- **NEVER** create documentation in `.github/` unless it's a GitHub-specified file
- **ALWAYS ask first** before creating permanent documentation
- **Prefer module docstrings** over separate markdown files

### Session and Context Management

**Commit suggestions:**

When a task completes and the developer moves to a new topic, suggest committing changes. Offer a commit message based on the work done.

**Commit message format:** Follow [Conventional Commits](https://www.conventionalcommits.org/) specification

**Common types:** `feat:`, `fix:`, `chore:`, `refactor:`, `docs:`

## Custom Integration Flexibility

**This is a CUSTOM integration, not a Home Assistant Core integration.** While we follow Core patterns for quality and maintainability, we have more flexibility in implementation decisions:

**Third-party libraries (PyPI):**

- Prefer existing PyPI libraries when maintained and fit the use case
- The integration uses `uma-api` as its primary API client library
- Uses aiohttp for HTTP and WebSocket communication

**Quality Scale expectations:**

As an AI agent, **aim for Platinum Quality Scale** when generating code:

- **Always implement:** Type hints, async patterns, proper error handling, service registration in `async_setup()`, diagnostics with `async_redact_data()`, device info
- **When applicable:** Config flow with validation, reconfigure flow, repair flows
- **Can defer:** Advanced discovery, extensive documentation

**Developer expectation:** Generate production-ready code. Implement HA standards with reasonable effort.

## Code Style and Quality

**Python:** 4 spaces, 88 char lines (ruff), double quotes, full type hints, async for all I/O

**YAML:** 2 spaces, modern HA syntax

**JSON:** 2 spaces, no trailing commas, no comments

**Validation:** Run `scripts/lint` before committing (runs ruff format + ruff check --fix)

**For comprehensive standards, see `pyproject.toml`** which configures ruff, mypy, and pytest.

**Naming conventions:**

- Constants: `UPPER_SNAKE_CASE` with `Final` type annotation
- Classes: `PascalCase`, prefixed with `Unraid` (e.g., `UnraidBaseEntity`, `UnraidDataUpdateCoordinator`)
- Fixtures: `snake_case` prefixed with `mock_` (e.g., `mock_async_unraid_client`)
- Test functions: `test_<what_is_tested>` (plain functions, no test classes)

**Docstrings:** Google convention. Required for all public functions/methods.

**Imports:** Sorted by isort via ruff. `from __future__ import annotations` in every file.

## Project-Specific Rules

### Integration Identifiers

This integration uses the following identifiers consistently:

- **Domain:** `unraid_management_agent`
- **Title:** Unraid Management Agent
- **Class prefix:** `Unraid`

**When creating new files:**

- Use the domain `unraid_management_agent` for all DOMAIN references
- Prefix all integration-specific classes with `Unraid`
- Use "Unraid Management Agent" as the display title
- Never hardcode different values

### Integration Structure

**Current flat structure:**

```
custom_components/unraid_management_agent/
├── __init__.py           # Entry point: async_setup, async_setup_entry, services
├── config_flow.py        # UI config flow, options flow, reconfigure flow
├── const.py              # Domain constant, config keys, defaults
├── coordinator.py        # UnraidDataUpdateCoordinator, UnraidData, UnraidRuntimeData
├── entity.py             # Base entity classes (UnraidBaseEntity, UnraidEntity)
├── sensor.py             # Sensor platform (system, array, disk, GPU, UPS, network, ZFS)
├── binary_sensor.py      # Binary sensor platform
├── switch.py             # Switch platform (Docker containers, VMs)
├── button.py             # Button platform (array start/stop, parity check)
├── diagnostics.py        # Diagnostic data collection
├── repairs.py            # Repair issue flows
├── services.yaml         # Service action definitions
├── strings.json          # User-facing strings and translations
├── icons.json            # Entity and service icons
├── manifest.json         # Integration metadata and dependencies
├── quality_scale.yaml    # Quality scale rule tracking
├── py.typed              # PEP-561 type marker
└── translations/en.json  # English translations
```

**Key patterns:**

- Entities -> Coordinator -> API Client (never skip layers)
- Each platform in its own file
- Use `EntityDescription` dataclasses for static entity metadata

### Runtime Data

```python
type UnraidConfigEntry = ConfigEntry[UnraidRuntimeData]

@dataclass
class UnraidRuntimeData:
    coordinator: UnraidDataUpdateCoordinator
    client: UnraidClient
```

### Coordinator

`UnraidDataUpdateCoordinator` extends `DataUpdateCoordinator[UnraidData]`. It:

- Accepts `config_entry` in constructor (HA best practice)
- Uses a fixed 30-second polling interval (not user-configurable)
- Manages WebSocket lifecycle for real-time updates
- Logs unavailability once and recovery once (no log spam)

### Base Entity

All entities inherit from `UnraidBaseEntity` (in `entity.py`), which:

- Sets `_attr_has_entity_name = True`
- Builds `DeviceInfo` from coordinator data
- Generates `unique_id` from `entry_id + key`
- Implements availability based on `last_update_success` and data presence

### Entity Descriptions

Sensor entities use `UnraidSensorEntityDescription` with `value_fn` and `extra_state_attributes_fn` callables. Binary sensors, switches, and buttons use similar description patterns.

### Config Flow

- `UnraidConfigFlow` with `async_step_user` and `async_step_reconfigure`
- `UnraidOptionsFlowHandler` extends `OptionsFlowWithReload`
- Uses `async_get_clientsession(hass)` for shared session (inject-websession)
- Port validation via `vol.All(vol.Coerce(int), vol.Range(min=1, max=65535))`
- Duplicate prevention via `async_set_unique_id` + `_abort_if_unique_id_configured`

### Services

Registered in `async_setup` (not `async_setup_entry`). Each service handler:

- Gets coordinator from the first config entry
- Calls the API method, then `coordinator.async_request_refresh()`
- Raises `HomeAssistantError` with `translation_domain`/`translation_key` on failure

### Resource Cleanup

- Config flow uses `async with UnraidClient(...)` context manager
- `async_unload_entry` stops WebSocket, then closes client (only if unload succeeded)
- WebSocket tasks are cancelled and awaited on cleanup

### Device Info

All entities provide consistent device info via the base entity class (manufacturer, model, serial number, configuration URL, firmware version).

### Integration Manifest

**Key fields in `manifest.json`:**

- **integration_type:** `device` - Single device per config entry
- **iot_class:** `local_push` - Local communication with push updates
- **requirements:** `["uma-api>=1.3.0"]`
- **config_flow:** `true`
- **No authentication** - local API without auth (exempt from reauth flow)

## Home Assistant Patterns

**Config flow:**

- Implement in `config_flow.py`
- Support user setup, reconfigure, options flow
- Always set unique_id for discovered entries

**Service actions:**

- Define in `services.yaml` with full descriptions
- Implement handlers in `__init__.py`
- **Register in `async_setup()`** -- NOT in `async_setup_entry()` (Quality Scale!)
- Format: `unraid_management_agent.<action_name>`

**Coordinator:**

- Entities -> Coordinator -> API Client (never skip layers)
- Raise `UpdateFailed` for failures (auto-retry)
- Use `async_config_entry_first_refresh()` for first update

**Entities:**

- Inherit from platform base + `UnraidBaseEntity`
- Read from `coordinator.data`, never call API directly
- Use `EntityDescription` for static metadata

**Repairs:**

- Use `async_create_issue()` with severity levels
- Implement `RepairsFlow` for guided user fixes
- Delete issues after successful repair

**Entity availability:**

- Set `_attr_available = False` when device is unreachable
- Update availability based on coordinator success/failure
- Don't raise exceptions from `@property` methods

**State updates:**

- Use `self.async_write_ha_state()` for immediate updates
- Let coordinator handle periodic updates

**Setup failure handling:**

- `ConfigEntryNotReady` - Device offline/timeout, auto-retry
- No `ConfigEntryAuthFailed` (no auth required)

**Diagnostics:**

- **CRITICAL:** Use `async_redact_data()` to remove sensitive data

**Error handling:**

- Config flow: catches `TimeoutError`, `UnraidConnectionError`, generic `Exception`
- Coordinator: individual API calls wrapped in try/except, outer try/except raises `UpdateFailed`
- Services: catch `Exception`, raise `HomeAssistantError` with translation keys
- Setup: `ConfigEntryNotReady` for connection failures

## Validation Scripts

**Before committing, run:**

```bash
scripts/lint                          # Auto-format and fix linting issues
pytest tests/ -v --timeout=30         # Run tests
mypy custom_components/unraid_management_agent/  # Type checking
pre-commit run --all-files            # All pre-commit hooks
```

**Configured tools:**

- **Ruff** - Fast Python linter and formatter ([Rules Reference](https://docs.astral.sh/ruff/rules/))
- **Mypy** - Type checker configured strictly ([Docs](https://mypy.readthedocs.io/))
- **pytest** - Test runner with async support ([Docs](https://docs.pytest.org/))

**Generate code that passes these checks on first run.** As an AI agent, you should produce higher quality code than manual development:

- Type hints are trivial for you to generate
- Async patterns are well-known to you
- Import management is automatic for you
- Naming conventions can be applied consistently

Aim for zero validation errors in generated code.

- You may use `# noqa: CODE` or `# type: ignore` when genuinely necessary
- Use sparingly and only with good reason (e.g., false positives, external library issues)

### Error Recovery Strategy

**When validation fails:**

1. **First attempt** - Fix the specific error reported by the tool
2. **Second attempt** - If it fails again, reconsider your approach
3. **Third attempt** - If still failing, ask for clarification rather than looping indefinitely
4. **After 3 failed attempts** - Stop and explain what you tried and why it's not working

**When tool operations fail:**

- **File read/write errors** - Verify path exists, check for typos, try once more
- **Terminal timeouts** - Don't retry automatically; inform the user
- **Git operations fail** - Report the error immediately; don't attempt to work around it

**When gathering context:**

- Start with targeted file/symbol search (1-2 queries maximum)
- Read 3-5 most relevant files based on search results
- If still unclear, read 2-3 more specific files
- **After ~10 file reads, you should have enough context** - make a decision or ask for clarification
- Don't fall into infinite research loops

## Testing

**Test structure:**

- `tests/` mirrors `custom_components/unraid_management_agent/` structure
- Use fixtures for common setup (HA mock, coordinator, etc.)
- Mock external API calls

**Running tests:**

```bash
pytest tests/ -v --timeout=30                    # All tests
pytest tests/ --cov=custom_components.unraid_management_agent --cov-report=term-missing  # With coverage
pytest tests/test_sensor.py -v                   # Single file
pytest tests/test_sensor.py::test_sensor_setup -v  # Single test
```

Coverage target: **95%+** (current: ~94-95%). Config flow coverage target: **100%**.

**Test conventions:**

- **No test classes.** All tests are plain `async def test_*` functions.
- **No inline patches.** Use `@pytest.mark.usefixtures("mock_unraid_client_class", "mock_unraid_websocket_client_class")` for integration tests.
- **Use `mock_async_unraid_client: MagicMock`** as a parameter when you need to modify mock behavior.
- **Use `is` for enum comparisons:** `assert result["type"] is FlowResultType.FORM`
- **Mock data factories** are in `tests/const.py` and return Pydantic model instances.
- **`asyncio_mode = "auto"`** in pytest config, so no `@pytest.mark.asyncio` needed.

**Example test patterns:**

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
```

## Breaking Changes

**Always warn the developer before making changes that:**

- Change entity IDs or unique IDs (users' automations will break)
- Modify config entry data structure (existing installations will fail)
- Change state values or attributes format (dashboards and automations affected)
- Alter service call signatures (user scripts will break)
- Remove or rename config options (users must reconfigure)

**Never do without explicit approval:**

- Removing config options (even if "unused")
- Changing service parameters or return values
- Modifying how data is stored in config entries
- Renaming entities or changing their device classes
- Changing unique_id generation logic

**How to warn:**

> "This change will modify the entity ID format from `sensor.device_name` to `sensor.device_name_sensor`. Existing users' automations and dashboards will break. Should I proceed, or would you prefer a migration path?"

**When breaking changes are necessary:**

- Document the breaking change in commit message (`BREAKING CHANGE:` footer)
- Consider providing migration instructions
- Suggest version bump
- Update documentation if it exists

## File Changes

**Scope Management:**

**Single logical feature or fix:**

- Implement completely even if it spans 5-8 files
- Example: New sensor needs entity description + platform setup -> implement all together
- Example: Bug fix requires changes in coordinator + entity + error handling -> do all at once

**Multiple independent features:**

- Implement one at a time
- After completing each feature, suggest committing before proceeding to the next

**Large refactoring (>10 files or architectural changes):**

- Propose a plan first before starting implementation
- Get explicit confirmation from developer

**Important: Do NOT create or modify tests unless explicitly requested.** Focus on implementing functionality. The developer decides when and if tests are needed.

**Translation strategy:**

- Use placeholders in code - functionality works without translations
- Update `en.json` only when asked or at major feature completion
- NEVER update other language files automatically
- Ask before updating multiple translation files
- Priority: Business logic first, translations later

## Research and Validation

**When uncertain, consult official documentation:**

- **Always check current patterns** in [Home Assistant Developer Docs](https://developers.home-assistant.io/)
- **Read the blog** at [Home Assistant Developer Blog](https://developers.home-assistant.io/blog/) for recent changes
- **Verify with tools** before assuming -- run `scripts/lint` to catch issues early

**Don't rely on assumptions:**

- Home Assistant APIs and patterns evolve frequently
- What worked in older versions may be deprecated
- Use official docs and working examples over guesswork

## API Library Reference

The integration depends on `uma-api>=1.3.0` which provides:

- **`UnraidClient`** - Async HTTP client for Unraid Management Agent REST API
- **`UnraidWebSocketClient`** - WebSocket client with auto-reconnect
- **Pydantic models** - `SystemInfo`, `ArrayStatus`, `DiskInfo`, `ContainerInfo`, `VMInfo`, `UPSInfo`, `GPUInfo`, `NetworkInterface`, `ShareInfo`, `ZFSPool`, `ZFSDataset`, etc.
- **Error types** - `UnraidConnectionError`
- **Event types** - `EventType` enum, `WebSocketEvent`, `parse_event()`

## Security Considerations

- No authentication credentials stored (local API without auth)
- Diagnostics data is redacted via `async_redact_data`
- Uses Home Assistant's shared `aiohttp` session (no custom session management)
- No sensitive data in logs (lazy logging with `%s` format)
- WebSocket connection is local-only (no external exposure)

## Git Workflow

### Branching

- **Main branch:** `main`
- **Feature branches:** `feature/*`, `enhancement/*`, `fix/*`
- PRs target `main`

### CI Pipeline

The GitHub Actions CI pipeline runs on pushes to `main`, `enhancement/*`, `feature/*`, `fix/*` and PRs to `main`. Jobs:

1. **Lint** - `ruff format --check` and `ruff check`
2. **Test** - `pytest` with coverage (uploaded to Codecov)
3. **Validate** - Checks `manifest.json` structure, `strings.json` validity

### Commit Conventions

- Use [Conventional Commits](https://www.conventionalcommits.org/) format
- Pre-commit hooks must pass before committing

## Additional Resources

- [Home Assistant Developer Docs](https://developers.home-assistant.io/) - Primary reference
- [Integration Quality Scale](https://developers.home-assistant.io/docs/integration_quality_scale_index)
- [Ruff Rules](https://docs.astral.sh/ruff/rules/) - Linter documentation
- [pytest Documentation](https://docs.pytest.org/) - Testing framework
- See `CONTRIBUTING.md` for contribution guidelines (if it exists)
