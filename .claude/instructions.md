# Claude AI Instructions - Unraid Management Agent

## Project Overview
This is a Home Assistant custom integration for monitoring and controlling Unraid servers via the Unraid Management Agent. The integration provides comprehensive system monitoring, array management, container control, and VM management through Home Assistant.

## Critical Documentation Policy

### ⚠️ NEVER Generate Unsolicited Documentation
- **NEVER** generate validation documents, summary documents, or reference documents unless explicitly requested by the user
- **NEVER** create unsolicited README files or markdown documentation
- **NEVER** create documentation files (*.md) proactively
- Only create documentation when the user specifically asks for it
- Do not summarize actions in files unless explicitly requested

## Home Assistant Integration Best Practices

### Mandatory Requirements
- Follow strict Home Assistant developer best practices for custom integrations
- Reference: https://developers.home-assistant.io/docs/creating_integration_manifest/
- Ensure proper implementation of all required components

### Integration Components
- **Config Flow** (`config_flow.py`): UI-based configuration without YAML
- **Data Coordinator** (`__init__.py`): Centralized data management and updates
- **Entity Platforms**:
  - `sensor.py`: System, array, GPU, UPS, network sensors
  - `binary_sensor.py`: Status indicators
  - `switch.py`: Container and VM control
  - `button.py`: Array and parity check control
- **API Client** (`api_client.py`): REST API communication with aiohttp
- **WebSocket Client** (`websocket_client.py`): Real-time event streaming

### Entity Implementation Standards
- Use proper device classes (temperature, power, battery, duration, etc.)
- Use proper state classes (measurement, total, total_increasing)
- Use Material Design Icons (MDI) for all entities
- Include extra attributes with contextual information
- Implement proper entity naming conventions
- Group all entities under a single device

### Manifest and Configuration
- Maintain correct `manifest.json` structure with all required fields
- Keep `strings.json` properly organized with translations
- Ensure `services.yaml` is properly formatted if services are defined
- Update version numbers appropriately in manifest.json

## Python Development Best Practices

### Code Standards
- Follow PEP 8 and Python best practices
- Use type hints appropriately throughout the codebase
- Implement proper async/await patterns for Home Assistant
- Maintain proper error handling and logging
- Use logging module for debug and error messages
- Avoid bare except clauses; catch specific exceptions

### Async/Await Patterns
- Use async functions for all I/O operations
- Properly handle asyncio tasks and coroutines
- Implement proper timeout handling for network requests
- Use aiohttp for HTTP requests (already in use)

## Code Quality and Validation

### ✅ MANDATORY: Linting and Code Quality
- **ALWAYS** run the linting script at `scripts/lint` after making code changes
- **ALWAYS** validate code meets quality standards before considering work complete
- Fix all linting errors and warnings before finishing
- The linting script runs:
  - `ruff format .` - Code formatting
  - `ruff check . --fix` - Linting with automatic fixes

### Code Review Checklist
- Verify no linting errors or warnings remain
- Check for proper type hints
- Ensure async/await patterns are correct
- Verify error handling is comprehensive
- Check logging is appropriate

## Development Workflow

### Development Environment Setup
- Use devcontainer for consistent development environment
- Initial setup: Run `scripts/setup` to install dependencies
- Development mode: Run `scripts/develop` to start Home Assistant in debug mode
- Code quality: Run `scripts/lint` to check and fix code

### After Making Changes
- **ALWAYS** run `scripts/lint` to validate code quality
- **ALWAYS** check Home Assistant logs for errors, warnings, or issues
- Monitor the Home Assistant instance for any runtime errors
- Check logs at `config/home-assistant.log` for integration-specific errors
- Verify entity creation and updates work correctly

### Testing Requirements
- Verify changes don't break existing functionality
- Test entity creation and updates
- Check that all entity types are created correctly
- Verify control operations (switches, buttons) work as expected
- Monitor logs for any integration errors or warnings
- Test WebSocket reconnection behavior if WebSocket code is modified

## Project Structure
```
ha-unraid-management-agent/
├── custom_components/unraid_management_agent/
│   ├── __init__.py              # Integration setup & coordinator
│   ├── api_client.py            # REST API client
│   ├── binary_sensor.py         # Binary sensor platform
│   ├── button.py                # Button platform
│   ├── config_flow.py           # Configuration flow
│   ├── const.py                 # Constants
│   ├── manifest.json            # Integration metadata
│   ├── repairs.py               # Repair flows
│   ├── sensor.py                # Sensor platform
│   ├── services.yaml            # Service definitions
│   ├── strings.json             # Translations
│   ├── switch.py                # Switch platform
│   ├── websocket_client.py      # WebSocket client
│   └── translations/            # Translation files
├── tests/                       # Test suite
├── scripts/
│   ├── setup                    # Install dependencies
│   ├── develop                  # Start dev environment
│   └── lint                     # Run code quality checks
├── docs/                        # Documentation
├── config/                      # Home Assistant config (dev)
├── requirements.txt             # Python dependencies
├── requirements_test.txt        # Test dependencies
├── pytest.ini                   # Pytest configuration
├── hacs.json                    # HACS metadata
└── README.md                    # Project documentation
```

## Key Implementation Details
- Uses data coordinator pattern for centralized data management
- WebSocket provides real-time updates with automatic fallback to REST polling
- All entities are grouped under a single device for better organization
- The integration supports dynamic entity creation based on available resources
- Configuration is UI-based with no YAML required for end users

## Important Notes
- Always respect the existing code structure and patterns
- Maintain consistency with Home Assistant conventions
- Test thoroughly before considering work complete
- Run linting as the final step before finishing any task
