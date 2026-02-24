---
applyTo: "**/*.md"
---

# Markdown Instructions

**Applies to:** All Markdown documentation files

## Formatting Standards

**Headers:**

- Use ATX-style (`#` not underlines)
- One H1 per file (usually)
- Don't skip heading levels (H1 -> H2 -> H3, not H1 -> H3)

**Code blocks:**

- Always specify language: ` ```python `, ` ```bash `, ` ```yaml `
- Use `console` or `bash` for terminal commands
- Use `text` for plain output

**Lists:**

- Unordered: Use `-` (dash)
- Ordered: Use `1.` with proper numbering
- Consistent indentation (2 spaces for nested items)

**Links:**

- Relative links for internal docs
- Absolute URLs for external references

## Common Patterns

**Inline code:** Use backticks for `filenames`, `symbols`, `commands`

**Emphasis:** Use `*italic*` for emphasis, `**bold**` for strong emphasis

**Tables:**

```markdown
| Column 1 | Column 2 |
| -------- | -------- |
| Value    | Value    |
```

## Instructions Files

**GitHub Copilot instructions (`.github/instructions/*.instructions.md`):**

- Must have frontmatter with `applyTo` glob pattern
- Keep focused and concise (~50-300 lines)
- Enforce standards, not tutorials
- Use compact examples over verbose explanations
