---
agent: "agent"
tools: ["search/codebase", "edit", "search", "execute/runInTerminal", "execute/getTerminalOutput"]
description: "Comprehensive quality review of integration code and configuration"
---

# Review Integration

Your goal is to perform a comprehensive quality review of this Home Assistant integration, identifying issues and suggesting improvements.
Treat the official Quality Scale rules as mandatory review criteria:
<https://developers.home-assistant.io/docs/core/integration-quality-scale/rules>

If not provided, ask for:

- Review scope (full integration, specific component, recent changes)
- Focus areas (code quality, architecture, security, performance, user experience)
- Known issues or concerns to investigate

## Review Process

### 1. Automated Validation

Run all validation tools first:

```bash
script/lint                     # Auto-format and fix
pytest tests/ -v --timeout=30   # Run tests
mypy custom_components/unraid_management_agent/  # Type checking
```

Report any errors found. Fix critical issues before proceeding.

### 2. Architecture Review

**Coordinator Pattern:**

- [ ] Entities → Coordinator → API Client pattern followed (no layer skipping)
- [ ] All API calls go through coordinator
- [ ] Coordinator has proper error handling (individual + outer try/except)
- [ ] Update interval is 30 seconds (fixed)
- [ ] WebSocket lifecycle properly managed
- [ ] Data structure uses `UnraidData` typed dataclass

**Entity Organization:**

- [ ] Entities inherit from `UnraidBaseEntity` and platform class
- [ ] `_attr_has_entity_name = True` for all entities
- [ ] Entity names use `translation_key`
- [ ] Entity IDs are stable (won't change on restart)
- [ ] Unique IDs properly set via base entity
- [ ] Entities use coordinator data (not direct API calls)

**Config Flow:**

- [ ] User input validation is comprehensive
- [ ] Reconfigure flow exists
- [ ] Options flow exists
- [ ] No blocking I/O in flow steps

### 3. Code Quality Review

**Type Hints:**

- [ ] Full type hints on all public functions
- [ ] `from __future__ import annotations` in every file
- [ ] Proper use of `UnraidConfigEntry` type alias

**Error Handling:**

- [ ] Specific exceptions caught (not bare except)
- [ ] `UpdateFailed` used in coordinator
- [ ] `HomeAssistantError` used in services
- [ ] `ConfigEntryNotReady` for setup failures

**Async Patterns:**

- [ ] All I/O uses async
- [ ] No blocking calls
- [ ] Proper timeout handling

### 4. HA Best Practices

**Anti-Patterns to Check:**

- [ ] No `time.sleep()` (use `await asyncio.sleep()`)
- [ ] No blocking I/O in async functions
- [ ] No imports from other integrations
- [ ] No hardcoded secrets or URLs
- [ ] No I/O in `@property` methods
- [ ] No broad exception catching without re-raising

**Required Patterns:**

- [ ] Entities become unavailable when device unreachable
- [ ] Services registered in `async_setup`, NOT `async_setup_entry`
- [ ] Entity unique IDs never change
- [ ] Coordinator handles `UpdateFailed` gracefully
- [ ] Diagnostics data redacted with `async_redact_data()`

### 5. Security Review

- [ ] No credentials stored (local API, no auth)
- [ ] Sensitive data excluded from diagnostics
- [ ] No sensitive data in logs (lazy logging with `%s`)
- [ ] Uses HA's shared aiohttp session

### 6. Quality Scale Check

Review `quality_scale.yaml` against actual implementation:

- [ ] Bronze rules all satisfied
- [ ] Silver rules all satisfied
- [ ] Gold rules all satisfied
- [ ] Platinum rules all satisfied

## Review Report

Create report in `.ai-scratch/review-report.md` with:

- Executive summary
- Critical issues (with severity, location, recommendation)
- Warnings
- Improvement opportunities
- Positive findings
- Metrics (files reviewed, validation status, issue counts)

## Integration Context

- **Domain:** `unraid_management_agent`
- **Class prefix:** `Unraid`
- **Guidelines:** `AGENTS.md`
- **Quality Scale:** `quality_scale.yaml`

## After Review

1. Present findings with priorities
2. Ask: "Which issues should I address first?"
3. Offer to create implementation plan for fixes
