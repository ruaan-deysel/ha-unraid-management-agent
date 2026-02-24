---
applyTo: "**/*.json"
---

# JSON Instructions

**Applies to:** All JSON files

## Formatting Standards

- **2 spaces** for indentation
- No trailing commas
- No comments (JSON spec doesn't support them)
- Use double quotes for all strings
- End files with a single newline

## Validation

Use Python's json module to validate syntax:

```bash
python3 -m json.tool file.json > /dev/null
```

## Key JSON Files

- `manifest.json` - Integration metadata (see `manifest.instructions.md`)
- `strings.json` - Source translation strings (see `translations.instructions.md`)
- `translations/*.json` - Translated strings
- `icons.json` - Entity and service icons
- `hacs.json` - HACS metadata
