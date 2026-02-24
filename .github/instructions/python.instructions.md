---
applyTo: "**/*.py"
---

# Python Code Instructions

**Applies to:** All Python files in the integration

## File Structure

**File size guidelines:**

- **Target:** 200-400 lines per file
- **Maximum:** ~500 lines before refactoring

**Naming:**

- Files: `snake_case.py`
- Classes: `PascalCase` prefixed with `Unraid`
- Functions/methods: `snake_case`
- Constants: `UPPER_SNAKE_CASE`

## Type Annotations

**Required for:**

- All function parameters and return values
- Class attributes (when not obvious)

**Import rules:**

- `from __future__ import annotations` (always first import)
- `collections.abc` for abstract base classes (prefer over `typing`)
- `typing` for complex types (Any, TYPE_CHECKING, etc.)

**Avoiding circular imports:**

Use `if TYPE_CHECKING:` block for type-only imports that would cause circular dependencies.

## Async Patterns

**All I/O operations must be async** -- Network, file, database, blocking operations

**Core patterns:**

- `async def` for coroutines, `await` for async calls
- `asyncio.gather()` for concurrent operations
- `asyncio.timeout()` for timeouts (not `async_timeout`)
- Never: `time.sleep()`, synchronous HTTP libraries, blocking operations

**Running blocking code:**

- `await hass.async_add_executor_job(sync_function, arg1, arg2)`

**Callback decorator:**

- `@callback` from `homeassistant.core` -- For event loop functions without blocking
- Required for event listeners, state change callbacks
- Cannot do I/O, cannot call coroutines

## Code Style

**Conventions not enforced by Ruff:**

- Comments as complete sentences with capitalization and ending period
- Alphabetical sorting of constants/lists when order doesn't matter

## Home Assistant Requirements

**Setup Failure Handling:**

- `ConfigEntryNotReady` -- Device offline/unavailable
- Pass error message to exception (HA logs at debug level automatically)
- **Do NOT log setup failures manually** -- Avoid log spam

**Constants:**

- Prefer `homeassistant.const` over defining new ones
- Only add to integration's `const.py` if widely used internally

**Units of Measurement:**

- Always use constants from `homeassistant.const` -- Never hardcode strings

**Service Actions:**

- Format: `unraid_management_agent.<action_name>`
- Register under integration domain

## Imports

**Order (separated by blank lines):**

1. `from __future__ import annotations`
2. Standard library
3. Third-party packages
4. Home Assistant core
5. Local integration imports

**Standard HA aliases:** `vol`, `cv`, `dr`, `er`, `dt_util`

## Entity Classes

**Structure requirements:**

- Inherit from both platform entity and `UnraidBaseEntity` (order matters)
- Set `_attr_unique_id` in `__init__` (format: `{entry_id}_{key}`)
- Use coordinator data only -- Never call API directly
- Handle unavailability via `_attr_available`

## Error Handling

**Logging levels:**

- `_LOGGER.error()` -- Errors affecting functionality
- `_LOGGER.warning()` -- Recoverable issues
- `_LOGGER.info()` -- Sparingly, user-facing only
- `_LOGGER.debug()` -- Detailed troubleshooting

**Log message style:**

- No periods at end (syslog style)
- Never log credentials/tokens/API keys
- Use `%` formatting (enforced by Ruff G004)

## Validation

Run before submitting: `scripts/lint`

**Suppressing checks (use sparingly):**

- Specific suppression: `# noqa: F401 - Reason` or `# type: ignore[attr-defined] - Reason`
- **Never use blanket:** `# noqa`, `# type: ignore`
- Always include error codes and explanatory comments
