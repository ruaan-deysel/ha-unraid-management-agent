---
agent: "agent"
tools: ["search/codebase", "search", "edit"]
description: "Create structured implementation plan for new features or refactoring"
---

# Create Implementation Plan

Your goal is to create a comprehensive, phased implementation plan for a new feature, major refactoring, or architectural change in this Home Assistant integration.

If not provided, ask for:

- Feature/change description and goals
- User requirements or problem being solved
- Any constraints or dependencies
- Preferred approach (if known)

## Implementation Plan Structure

Create a markdown file in `.ai-scratch/plan-[feature-name].md` (never committed) with:

### 1. Overview

- **Goal:** What we're building and why
- **User Benefit:** How this helps users
- **Scope:** What's included and excluded
- **Constraints:** HA version requirements, uma-api dependencies

### 2. Architecture Analysis

- Current architecture relevant to this change
- Proposed architecture changes
- Impact on existing components (coordinator, entities, config flow, etc.)
- Breaking changes assessment

### 3. Implementation Phases

Break down into logical phases (typically 3-5):

**Phase 1: [Foundation/Setup]**

- File(s) to create/modify
- Key changes required
- Validation: How to test this phase works

**Phase 2: [Core Implementation]**

- File(s) to create/modify
- Key changes required
- Integration points with Phase 1
- Validation: How to test this phase works

**Phase 3: [Integration/Polish]**

- File(s) to create/modify
- Translations updates
- Final validation

### 4. Quality Checklist

- [ ] Type hints complete
- [ ] Error handling implemented
- [ ] Translations added
- [ ] Docstrings updated
- [ ] `script/lint` passes
- [ ] Manual testing completed
- [ ] Breaking changes documented (if any)

## Process

1. **Research Phase:**
   - Analyze existing code patterns
   - Check Home Assistant documentation for best practices
   - Identify all files that need changes

2. **Create Plan:**
   - Write comprehensive plan in `.ai-scratch/`
   - Get developer confirmation before implementation

3. **Implementation Phase:**
   - Work through phases sequentially
   - Run `script/lint` after each phase
   - Test functionality before moving to next phase

4. **Completion:**
   - Verify all checklist items
   - Run full validation suite
   - Suggest commit message following Conventional Commits

## Integration Context

- **Domain:** `unraid_management_agent`
- **Class prefix:** `Unraid`
- **API library:** `uma-api` (async, Pydantic models)
- **Follow patterns in `AGENTS.md`**

## Output

Present the plan and ask:

- "Does this approach make sense?"
- "Should I proceed with Phase 1?"
- "Any adjustments needed?"

Never start implementation without explicit confirmation.
