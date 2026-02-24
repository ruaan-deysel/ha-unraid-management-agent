---
agent: "agent"
tools: ["search/codebase", "edit"]
description: "Create Architectural Decision Record for important design choices"
---

# Create Architectural Decision Record (ADR)

Your goal is to document an important architectural or design decision for this Home Assistant integration.

If not provided, ask for:

- What decision needs to be documented
- Context: Why is this decision being made
- Options considered
- Chosen approach and rationale

## ADR Structure

Create a new ADR in `docs/adr/NNNN-title-of-decision.md`:

```markdown
# ADR-NNNN: [Title of Decision]

**Status:** Proposed | Accepted | Deprecated | Superseded by ADR-XXXX

**Date:** YYYY-MM-DD

## Context and Problem Statement

[Describe the context and background. What is the issue we're trying to address?]

**Key considerations:**

- [Consideration 1]
- [Consideration 2]
- [Consideration 3]

## Decision Drivers

- [Driver 1: e.g., "Must support HA Core 2024.1+"]
- [Driver 2: e.g., "Minimize API calls"]
- [Driver 3: e.g., "Maintain backward compatibility"]

## Considered Options

### Option 1: [Title]

**Description:** [What is this approach]

**Pros:**

- [Advantage 1]
- [Advantage 2]

**Cons:**

- [Disadvantage 1]
- [Disadvantage 2]

### Option 2: [Title]

[Same structure as Option 1]

## Decision Outcome

**Chosen option:** Option X - [Title]

**Rationale:**
[Explain why this option was selected over the others]

**Consequences:**

- **Positive:** [What we gain]
- **Negative:** [What we give up and how we'll mitigate]

## Implementation Notes

**Files affected:**

- `custom_components/unraid_management_agent/[file1.py]`
- `custom_components/unraid_management_agent/[file2.py]`

**Breaking changes:** [Yes/No - if yes, explain migration path]

## Links and References

- [Home Assistant Documentation: Relevant Topic](https://developers.home-assistant.io/...)
- [Related GitHub Issue: #XXX](link)
```

## Common ADR Topics for This Integration

### Data Management

- Coordinator polling vs WebSocket push updates
- Data delegation to uma-api library vs local computation
- State update frequency and caching

### Entity Design

- Entity platform choices (sensor vs binary_sensor)
- Unique ID generation and stability
- Attribute structure for complex data

### API Integration

- uma-api library boundary decisions
- Error handling and retry strategy
- WebSocket reconnection behavior

### Architecture

- Single device per config entry
- Service registration in `async_setup()` vs `async_setup_entry()`
- Repair flow design decisions

## Process

1. **Number the ADR:** Check existing ADRs in `docs/adr/`, use next sequential number
2. **Write the ADR:** Focus on the "why" not just the "what"
3. **Review with developer:** Present for feedback, adjust as needed
4. **Reference in code:** Add comment references in relevant files

## Integration Context

- **Domain:** `unraid_management_agent`
- **Class prefix:** `Unraid`
- **API library:** `uma-api`
- **Agent docs:** Reference [#file:AGENTS.md]

## Output

After creating the ADR:

1. Ask if content needs adjustment
2. Suggest relevant code locations for implementation
3. Ask: "Should I proceed with implementing this decision?"
