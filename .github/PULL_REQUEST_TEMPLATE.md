## Description

<!-- Provide a clear and concise description of what this PR does -->

## Type of Change

<!-- Check all that apply -->

- [ ] Bug fix (non-breaking change fixing an issue)
- [ ] New sensor or entity platform
- [ ] New feature or enhancement
- [ ] Breaking change (change that causes existing automations or setups to fail)
- [ ] Documentation update
- [ ] Code refactoring (no functional changes)
- [ ] Test additions or improvements

## Pre-Submission Governance

<!--
	REQUIRED for everyone, including AI agents and automation.
	Every box below is mandatory. If any box is left unchecked, the automated
	"PR Governance" check fails and the PR will not be reviewed or merged.
	Do not open multiple overlapping or back-to-back PRs for the same work;
	batch related changes together to avoid wasting CI runner capacity.
-->

- [ ] I built and ran the project locally and verified this change actually works (not just that it compiles)
- [ ] I ran `script/test` locally and all tests pass
- [ ] I ran `script/lint` locally and it passes
- [ ] I pasted real local verification output under **Testing Performed** below (no placeholder text)
- [ ] This PR is self-contained and is not a duplicate; I have not opened other overlapping or back-to-back PRs for the same change
- [ ] If an AI agent created or assisted with this PR, a human reviewed and verified the changes before submission

## Related Issues

<!-- Link the issue this PR resolves (Closes #123) or contributes to (Part of #123). "None" is only for maintainers with write access, for housekeeping. -->
<!-- Examples: Fixes #123, Closes https://github.com/..., Related to #456, or None (maintainers only) -->

Fixes #

## Changes Made

<!-- List the main changes in this PR -->

-
-
-

## Home Assistant Quality Scale & Standards

<!-- Check all that apply to confirm compliance with modern Home Assistant development standards -->

- [ ] Verified against the [Home Assistant Developer Docs](https://developers.home-assistant.io/) and Quality Scale (Platinum target)
- [ ] Uses `entry.runtime_data` exclusively (zero `hass.data[DOMAIN]` usage)
- [ ] All entities inherit from `UnraidBaseEntity` and set `_attr_has_entity_name = True`
- [ ] Services/actions registered in `async_setup()` with full schema validation (not `async_setup_entry()`)
- [ ] Sensor entities use `native_value` / `native_unit_of_measurement` (no deprecated properties)
- [ ] Uses `async_get_clientsession(hass)` for all HTTP/WebSocket connections
- [ ] Entities read from `coordinator.data` (no direct API/network calls in entity classes)
- [ ] Diagnostics data is properly redacted via `async_redact_data()`
- [ ] Not applicable (documentation-only or metadata change)

## Testing Performed

<!-- Check all that apply and describe what you tested -->

- [ ] Ran unit tests with coverage (`./script/test --cov` or `pytest tests/`)
- [ ] Ran linter (`./script/lint`)
- [ ] Ran type checking (`./script/type-check`)
- [ ] Ran hassfest validation (`./script/hassfest`)
- [ ] Tested live in local Home Assistant (`./script/develop`)
- [ ] Not applicable (documentation-only or metadata-only change)

### Test Results

```text
[Paste relevant test output or results]
```

## Documentation

<!-- Check all that apply -->

- [ ] Code comments added/updated
- [ ] Integration docstrings updated
- [ ] README.md updated (if needed)
- [ ] AGENTS.md / developer documentation updated (if architecture or guidelines changed)
- [ ] No documentation needed

## Breaking Changes

<!-- If this PR introduces breaking changes, describe them and provide migration instructions -->

## Checklist

<!-- Ensure you've completed all required items before submitting -->

- [ ] I have updated CHANGELOG.md under [Unreleased] with details of this change
- [ ] I verified my code against the Home Assistant Integration Quality Scale and used no deprecated APIs
- [ ] I linked the related issue in **Related Issues** (only maintainers may note "None", for housekeeping)
- [ ] I completed all required sections in this template and removed placeholder-only content
- [ ] My code follows the project's coding standards and Home Assistant patterns
- [ ] I have performed a self-review of my own code
- [ ] I have commented my code, particularly in hard-to-understand areas (if applicable)
- [ ] My changes generate no new warnings
- [ ] I have added tests that prove my fix is effective or that my feature works (if applicable)
- [ ] New and existing unit tests pass locally with my changes
- [ ] Any dependent changes have been merged and published (if applicable)
- [ ] No sensitive information (tokens, passwords, personal data) is included
