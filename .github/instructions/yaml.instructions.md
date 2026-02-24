---
applyTo: "**/*.yaml, **/*.yml"
---

# YAML Instructions

**Applies to:** All YAML files

## Formatting Standards

- **2 spaces** for indentation (never tabs)
- No trailing whitespace
- End files with a single newline
- Use lowercase for keys (except where case matters)
- Prefer `>` for multi-line strings (folded) over inline strings
- Use `|` when preserving newlines is important

## Project-Specific Rules

- Keep files focused and readable
- Use comments to separate logical sections
- Group related configuration together

## Key YAML Files

- `services.yaml` - Service action definitions (see `services_yaml.instructions.md`)
- `.github/workflows/*.yml` - CI/CD pipeline definitions
- `pyproject.toml` uses TOML, not YAML

## Home Assistant YAML Conventions

- Boolean values: `true`/`false` (lowercase)
- Use `!secret` for sensitive values in configuration
