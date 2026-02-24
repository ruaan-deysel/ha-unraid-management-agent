# Claude Code Instructions

This repository uses a shared AI agent instruction system. **All instructions are in [`AGENTS.md`](AGENTS.md).**

Read `AGENTS.md` completely before starting any work. It contains:

- Project overview and integration identifiers
- Code style, validation commands, and quality expectations
- Home Assistant patterns (config flow, coordinator, entities, services)
- Error recovery strategy and breaking change policy
- Workflow rules (scope management, translations, documentation)
- Testing patterns with fixture architecture
- API library reference

## Quick Reference

- **Domain:** `unraid_management_agent`
- **Title:** Unraid Management Agent
- **Class prefix:** `Unraid`
- **Main code:** `custom_components/unraid_management_agent/`
- **Lint:** `scripts/lint` (ruff format + ruff check --fix)
- **Test:** `pytest tests/ -v --timeout=30`
- **Run HA:** `./scripts/develop`

## Copilot Prompts

Guided workflow prompts are available in `.github/prompts/*.prompt.md` for common tasks:

- `Add New Sensor.prompt.md` -- Add sensor entities with descriptions
- `Add Entity Platform.prompt.md` -- Add new entity platforms
- `Debug Coordinator Issue.prompt.md` -- Diagnose coordinator problems
- `Review Integration.prompt.md` -- Comprehensive quality review
- `Add Action.prompt.md` -- Add service actions
- `Add Config Option.prompt.md` -- Add config flow options
- `Create Implementation Plan.prompt.md` -- Plan multi-phase features
- `Update Translations.prompt.md` -- Update translation strings
