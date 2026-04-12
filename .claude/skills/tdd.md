---
name: tdd
description: Generate test stubs following project TDD conventions for a given module or feature
user_invocable: true
---

# TDD Scaffold

Generate test stubs for the module or feature specified by the user.

## Backend Tests (Python/pytest)

When generating backend test stubs, follow these conventions:

### File location
- Engine tests: `backend/tests/unit/engines/test_<engine>.py`
- Service tests: `backend/tests/integration/test_<service>.py`
- API/router tests: `backend/tests/api/test_<resource>.py`

### Structure
```python
"""Tests for <module description>."""

import uuid
from datetime import datetime, timezone

import pytest

# Import the module under test
# from app.<path> import <Class>


class TestClassName:
    """Tests for <ClassName>."""

    def test_<behavior_description>(self) -> None:
        """<What this test verifies>."""
        # Arrange

        # Act

        # Assert
        pass
```

### Naming rules
- Test functions: `test_<what_it_does>` — describe the behavior, not the method
- Examples: `test_bracket_with_3_options_creates_bye`, `test_score_rejects_out_of_range`, `test_activate_requires_minimum_2_options`
- Group related tests in classes: `TestBracketEngine`, `TestOptionRepository`

### Common fixtures (define in conftest.py)
- `tmp_data_dir` — tmpdir for file repository tests
- `option_repo` — OptionRepository with tmp_data_dir
- `tournament_repo` — TournamentRepository with tmp_data_dir
- `sample_options` — list of pre-created Option objects

## Frontend Tests (TypeScript/Jest)

### File location
- Component tests: alongside the component as `<component>.spec.ts`
- Service tests: alongside the service as `<service>.spec.ts`

### Structure
```typescript
import { TestBed } from '@angular/core/testing';
import { ComponentName } from './component-name.component';

describe('ComponentName', () => {
  beforeEach(async () => {
    await TestBed.configureTestingModule({
      imports: [ComponentName],
    }).compileComponents();
  });

  it('should create', () => {
    const fixture = TestBed.createComponent(ComponentName);
    expect(fixture.componentInstance).toBeTruthy();
  });

  it('should <behavior>', () => {
    // Arrange
    // Act
    // Assert
  });
});
```

## Instructions

1. Read the user's argument to determine which module/feature to scaffold tests for
2. Check the SPEC.md for the expected behavior of that module
3. Generate comprehensive test stubs covering:
   - Normal flow (happy path)
   - Edge cases (minimum inputs, boundary values)
   - Error cases (invalid input, wrong state)
   - For engines: deterministic results (same input → same output)
4. Write the test file(s) to the appropriate location
5. Run `make test-backend` or `make test-frontend` to verify the stubs compile
