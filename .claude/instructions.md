# Claude AI Instructions - Unraid Management Agent

This repository uses a shared AI agent instruction system. **All instructions are in [`AGENTS.md`](../AGENTS.md).**

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
- **Lint:** `script/lint` (ruff format + ruff check --fix)
- **Test:** `pytest tests/ -v --timeout=30`
- **Run HA:** `./script/develop`

## Critical Policies

- **NEVER** generate unsolicited documentation, validation, or summary files
- **ALWAYS** run `script/lint` after making code changes
- **ALWAYS** validate code meets quality standards before considering work complete
- Fix all linting errors and warnings before finishing
- Do NOT create or modify tests unless explicitly requested
