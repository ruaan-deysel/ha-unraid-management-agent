# Codecov Integration Setup

This document explains the Codecov integration setup for the Unraid Management Agent.

## Overview

Codecov provides:
- **Coverage Analytics**: Track code coverage over time
- **Test Analytics**: Monitor test execution and flaky tests  
- **PR Comments**: Automatic coverage reports on pull requests
- **Status Checks**: Prevent merging code that decreases coverage

## Configuration Files

### `.github/workflows/ci.yml`

The CI workflow runs on every push and pull request:

```yaml
- Tests on Python 3.12 and 3.13
- Generates coverage.xml for Codecov coverage reports
- Generates junit.xml for Codecov test analytics
- Uploads both to Codecov after test completion
```

**Key Commands:**
```bash
# Run tests with coverage and JUnit output
pytest \
  --cov \
  --cov-branch \
  --cov-report=xml \
  --cov-report=term-missing \
  --junitxml=junit.xml \
  -o junit_family=legacy \
  -v
```

### `.codecov.yml`

Configuration for Codecov behavior:

- **Coverage Target**: 60% minimum
- **Precision**: 2 decimal places
- **Comment Layout**: Shows coverage diff, flags, and file tree
- **Flags**: `unittests` flag for test categorization
- **Ignored Paths**: Tests, cache files, generated HTML

## Setup Instructions

### 1. Add Repository to Codecov

1. Visit [codecov.io](https://codecov.io/)
2. Sign in with GitHub
3. Add the `ha-unraid-management-agent` repository
4. Codecov will provide a `CODECOV_TOKEN`

### 2. Add GitHub Secret

1. Go to repository **Settings** → **Secrets and variables** → **Actions**
2. Click **New repository secret**
3. Name: `CODECOV_TOKEN`
4. Value: Paste the token from Codecov
5. Click **Add secret**

### 3. Trigger First Run

1. Push a commit or create a pull request
2. GitHub Actions will run the CI workflow
3. Coverage and test results will upload to Codecov
4. View results at: `https://codecov.io/gh/ruaan-deysel/ha-unraid-management-agent`

## Features

### Coverage Reports

**What it tracks:**
- Line coverage percentage
- Branch coverage percentage  
- Coverage by file and directory
- Coverage trends over time
- Untested code locations

**Where to view:**
- Codecov dashboard: Coverage graphs and file browser
- PR comments: Automatic coverage diff for changes
- GitHub checks: Pass/fail status on coverage threshold

### Test Analytics

**What it tracks:**
- Test execution time
- Flaky test detection
- Test failure rates
- Test trends over time

**Where to view:**
- Codecov dashboard under "Tests" tab
- PR comments: Failed test summaries
- GitHub checks: Test result status

### PR Integration

Codecov automatically comments on pull requests with:

```markdown
# Codecov Report
Coverage: 65.3% (+2.1%)

Files changed: 
- coordinator.py: 72.5% (+5.2%)
- sensor.py: 68.1% (+1.3%)

⚠️ 2 files have coverage gaps
```

## Local Development

### Run Tests with Coverage

```bash
# Full coverage report
pytest --cov --cov-report=term-missing --cov-report=html

# View HTML report
open htmlcov/index.html
```

### Check Coverage Threshold

```bash
# Will fail if coverage < 60%
pytest --cov --cov-fail-under=60
```

### Generate Both Reports

```bash
# Same as CI runs
pytest \
  --cov \
  --cov-branch \
  --cov-report=xml \
  --cov-report=term-missing \
  --junitxml=junit.xml \
  -o junit_family=legacy \
  -v
```

## Configuration Options

### Adjust Coverage Threshold

Edit `.codecov.yml`:

```yaml
coverage:
  status:
    project:
      default:
        target: 70%  # Change from 60%
```

### Ignore Additional Files

Edit `.codecov.yml`:

```yaml
ignore:
  - "tests/**"
  - "docs/**"
  - "examples/**"
```

### Customize PR Comments

Edit `.codecov.yml`:

```yaml
comment:
  layout: "reach,diff,flags,tree"  # Remove 'footer'
  behavior: once  # Comment only once per PR
```

## Badges

Add to README.md:

```markdown
[![codecov](https://codecov.io/gh/ruaan-deysel/ha-unraid-management-agent/branch/main/graph/badge.svg)](https://codecov.io/gh/ruaan-deysel/ha-unraid-management-agent)
```

## Troubleshooting

### Coverage Not Uploading

1. Check `CODECOV_TOKEN` is set in GitHub secrets
2. Verify workflow runs successfully
3. Check Codecov upload step logs in Actions
4. Ensure `coverage.xml` is generated before upload

### Test Results Not Appearing

1. Verify `junit.xml` is generated  
2. Check test-results-action step in workflow
3. Ensure pytest uses `-o junit_family=legacy`

### Coverage Percentage Incorrect

1. Check `.coveragerc` or `pyproject.toml` excludes
2. Verify source paths in coverage configuration
3. Run locally: `pytest --cov --cov-report=term-missing`

## Resources

- [Codecov Documentation](https://docs.codecov.com/)
- [pytest-cov Documentation](https://pytest-cov.readthedocs.io/)
- [GitHub Actions Documentation](https://docs.github.com/en/actions)
- [Home Assistant Testing Guide](https://developers.home-assistant.io/docs/development_testing)

## Monitoring

**Key Metrics to Watch:**
- Overall coverage trend (should stay above 60%)
- Coverage on new code (should be high for new features)
- Flaky tests (should be investigated and fixed)
- Test execution time (should stay reasonable)

**Regular Tasks:**
- Review coverage reports weekly
- Investigate coverage drops in PRs
- Fix flaky tests promptly
- Update coverage targets as codebase matures
