# Claude AI Instructions - Unraid Management Agent

## Project overview

This is a Home Assistant custom integration for monitoring and controlling Unraid servers via the Unraid Management Agent (UMA) API. The integration provides system monitoring, array management, Docker container control, and VM management through Home Assistant. See `AGENTS.md` for full project context, architecture, and conventions.

## Critical policies

### Documentation

- **NEVER** generate unsolicited documentation, validation, or summary files
- **NEVER** create markdown files proactively
- Only create documentation when the user explicitly requests it

### Code quality

- **ALWAYS** run `scripts/lint` after making code changes
- **ALWAYS** validate code meets quality standards before considering work complete
- Fix all linting errors and warnings before finishing

## Quick reference

### Integration components

- **Config flow** (`config_flow.py`): UI-based configuration with reconfigure and options flows
- **Coordinator** (`coordinator.py`): `UnraidDataUpdateCoordinator` with polling + WebSocket
- **Entity base** (`entity.py`): `UnraidBaseEntity` and `UnraidEntity` with description support
- **Platforms**: `sensor.py`, `binary_sensor.py`, `switch.py`, `button.py`
- **Services**: Registered in `__init__.py` via `async_setup`
- **Repairs** (`repairs.py`): Disk health and temperature repair issues
- **Diagnostics** (`diagnostics.py`): Redacted diagnostic data collection
- **API library**: `uma-api` (async, Pydantic models, WebSocket support)

### Key commands

```bash
scripts/lint                    # Format + lint with auto-fix
scripts/setup                   # Install dev dependencies
pytest tests/ -v --timeout=30   # Run all tests
pytest tests/ --cov=custom_components.unraid_management_agent --cov-report=term-missing  # Coverage
pre-commit run --all-files      # All pre-commit hooks
mypy custom_components/unraid_management_agent/  # Type checking
```

### Testing conventions

- Plain test functions only (no test classes)
- Use `@pytest.mark.usefixtures("mock_unraid_client_class", "mock_unraid_websocket_client_class")` for integration tests
- No inline `with patch(...)` in test files; use shared fixtures from `conftest.py`
- Mock data factories in `tests/const.py` return Pydantic model instances
- `asyncio_mode = "auto"` (no `@pytest.mark.asyncio` needed)
