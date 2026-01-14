# GitHub Copilot Instructions - Unraid Management Agent

## Project Context
This is a Home Assistant custom integration for monitoring and controlling Unraid servers. The integration provides system monitoring, array management, container control, and VM management through Home Assistant.

## Critical Rules

### 📋 Documentation Policy
- **NEVER** generate validation documents, summary documents, or reference documents unless explicitly requested
- **NEVER** create unsolicited README files or markdown documentation
- Only create documentation when specifically asked
- Do not summarize actions in files unless explicitly requested

## Home Assistant Integration Standards

### Required Components
- **Config Flow** (`config_flow.py`): UI-based configuration
- **Data Coordinator** (`__init__.py`): Centralized data management
- **Entity Platforms**: sensor, binary_sensor, switch, button
- **API Client** (`api_client.py`): REST API communication
- **WebSocket Client** (`websocket_client.py`): Real-time updates

### Entity Best Practices
- Use proper device classes (temperature, power, battery, duration)
- Use proper state classes (measurement, total, total_increasing)
- Use Material Design Icons (MDI)
- Include extra attributes with context
- Group all entities under a single device
- Follow Home Assistant naming conventions

### Configuration Files
- Maintain correct `manifest.json` structure
- Keep `strings.json` organized with translations
- Format `services.yaml` properly
- Update version numbers in manifest.json

## Python Code Standards

### Code Quality
- Follow PEP 8 and Python best practices
- Use type hints throughout
- Implement proper async/await patterns
- Handle errors specifically (no bare except)
- Use logging module for debug/error messages

### Async/Await
- Use async functions for all I/O operations
- Handle asyncio tasks and coroutines properly
- Implement timeout handling for network requests
- Use aiohttp for HTTP requests

## Code Quality Validation

### ✅ MANDATORY: After Every Change
1. Run `scripts/lint` to validate code quality
2. Fix all linting errors and warnings
3. Check Home Assistant logs for errors
4. Verify entity creation and updates work
5. Test control operations (switches, buttons)

### Linting Script
The `scripts/lint` script runs:
- `ruff format .` - Code formatting
- `ruff check . --fix` - Linting with automatic fixes

## Development Workflow

### Setup and Development
- Initial setup: `scripts/setup` (install dependencies)
- Development mode: `scripts/develop` (start Home Assistant in debug)
- Code quality: `scripts/lint` (check and fix code)

### After Making Changes
- **ALWAYS** run `scripts/lint`
- **ALWAYS** check logs at `config/home-assistant.log`
- Monitor Home Assistant instance for runtime errors
- Verify all entity types are created correctly
- Test WebSocket reconnection if modified

### Testing
- Verify changes don't break existing functionality
- Test entity creation and updates
- Check all entity types are created
- Verify control operations work
- Monitor logs for integration errors
- Test WebSocket behavior if modified

## Project Structure
```
custom_components/unraid_management_agent/
├── __init__.py              # Integration setup & coordinator
├── api_client.py            # REST API client
├── binary_sensor.py         # Binary sensor platform
├── button.py                # Button platform
├── config_flow.py           # Configuration flow
├── const.py                 # Constants
├── manifest.json            # Integration metadata
├── repairs.py               # Repair flows
├── sensor.py                # Sensor platform
├── services.yaml            # Service definitions
├── strings.json             # Translations
├── switch.py                # Switch platform
├── websocket_client.py      # WebSocket client
└── translations/            # Translation files
```

## Key Implementation Details
- Uses data coordinator pattern for centralized data management
- WebSocket provides real-time updates with REST polling fallback
- All entities grouped under single device
- Dynamic entity creation based on available resources
- UI-based configuration (no YAML required)

## References
- Home Assistant Integration Development: https://developers.home-assistant.io/docs/creating_integration_manifest/
- Home Assistant Developer Docs: https://developers.home-assistant.io/
