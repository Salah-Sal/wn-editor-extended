# Batch Change Request Feature - Specification & Implementation Plan

## Overview

This document describes the design and implementation plan for a batch change request system that allows users to submit standardized change requests in YAML format to modify WordNet databases.

## Design Decisions

| Decision | Choice | Rationale |
|----------|--------|-----------|
| Format | YAML | Human-readable, easy to edit manually |
| References | Synset IDs | Unambiguous, matches database |
| Validation | Referential | Verify targets exist before execution |
| Interface | Python API + CLI | Flexibility for scripting and interactive use |
| Error handling | Continue and report | Process all changes, report failures at end |
| Relation types | String names | User-friendly (`hypernym` vs `15`) |

---

## YAML Schema Specification

### Full Example

```yaml
# Batch change request for wn-editor-extended
# Version: 1.0

session:
  name: "Add medical terminology"
  description: "Adding disease-related terms to Arabic WordNet"

lexicon: awn3

changes:
  # ============================================
  # CREATE SYNSET - Create new synset with words
  # ============================================
  - operation: create_synset
    words:
      - word: "مرض"
        pos: n
      - word: "داء"
    definition: "حالة غير طبيعية تصيب الجسم"
    examples:
      - "يعاني المريض من مرض مزمن"
    relations:
      hypernym:
        - awn3-00024720-n
      hyponym:
        - awn3-00099999-n

  # ============================================
  # ADD WORD - Add word to existing synset
  # ============================================
  - operation: add_word
    synset: awn3-00001740-n
    word: "كائن"
    pos: n

  # ============================================
  # DELETE WORD - Remove word from synset
  # ============================================
  - operation: delete_word
    synset: awn3-00001740-n
    word: "كلمة_قديمة"

  # ============================================
  # ADD DEFINITION - Add definition to synset
  # ============================================
  - operation: add_definition
    synset: awn3-00001740-n
    definition: "تعريف إضافي للمفهوم"
    language: ar

  # ============================================
  # MODIFY DEFINITION - Change existing definition
  # ============================================
  - operation: modify_definition
    synset: awn3-00001740-n
    definition: "تعريف جديد محسن"
    index: 0  # Which definition to modify (0-based)

  # ============================================
  # DELETE DEFINITION - Remove definition
  # ============================================
  - operation: delete_definition
    synset: awn3-00001740-n
    index: 0

  # ============================================
  # ADD EXAMPLE - Add usage example
  # ============================================
  - operation: add_example
    synset: awn3-00001740-n
    example: "مثال جديد للاستخدام"
    language: ar

  # ============================================
  # DELETE EXAMPLE - Remove example
  # ============================================
  - operation: delete_example
    synset: awn3-00001740-n
    example: "مثال قديم"

  # ============================================
  # SET POS - Set part of speech
  # ============================================
  - operation: set_pos
    synset: awn3-00001740-n
    pos: n  # n=noun, v=verb, a=adjective, r=adverb

  # ============================================
  # ADD RELATION - Create relation between synsets
  # ============================================
  - operation: add_relation
    source: awn3-00001234-n
    target: awn3-00005678-n
    type: hypernym

  # ============================================
  # DELETE RELATION - Remove relation
  # ============================================
  - operation: delete_relation
    source: awn3-00001234-n
    target: awn3-00005678-n
    type: hypernym

  # ============================================
  # SET ILI - Link synset to Interlingual Index
  # ============================================
  - operation: set_ili
    synset: awn3-00001740-n
    ili: i12345

  # ============================================
  # DELETE ILI - Remove ILI link
  # ============================================
  - operation: delete_ili
    synset: awn3-00001740-n
```

### Supported Operations (Phase 1)

| Operation | Target | Required Fields | Optional Fields |
|-----------|--------|-----------------|-----------------|
| `create_synset` | new | `words`, `definition` | `pos`, `examples`, `relations` |
| `add_word` | synset | `synset`, `word` | `pos` |
| `delete_word` | synset | `synset`, `word` | |
| `add_definition` | synset | `synset`, `definition` | `language` |
| `modify_definition` | synset | `synset`, `definition` | `index`, `language` |
| `delete_definition` | synset | `synset` | `index` |
| `add_example` | synset | `synset`, `example` | `language` |
| `delete_example` | synset | `synset`, `example` | |
| `set_pos` | synset | `synset`, `pos` | |
| `add_relation` | synset | `source`, `target`, `type` | |
| `delete_relation` | synset | `source`, `target`, `type` | |
| `set_ili` | synset | `synset`, `ili` | |
| `delete_ili` | synset | `synset` | |

### Relation Types

String names mapped to database IDs (matches `wn` database `relation_types` table):

| Name | ID | Description |
|------|-----|-------------|
| `also` | 1 | See also |
| `antonym` | 2 | Opposite meaning |
| `attribute` | 3 | Attribute relation |
| `causes` | 4 | Causal relation |
| `derivation` | 5 | Derivational relation |
| `domain_region` | 6 | Domain (region) |
| `domain_topic` | 7 | Domain (topic) |
| `entails` | 8 | Entailment |
| `exemplifies` | 9 | Exemplification |
| `has_domain_region` | 10 | Has domain (region) |
| `has_domain_topic` | 11 | Has domain (topic) |
| `holo_member` | 12 | Member holonym |
| `holo_part` | 13 | Part holonym |
| `holo_substance` | 14 | Substance holonym |
| `hypernym` | 15 | More general concept |
| `hyponym` | 16 | More specific concept |
| `instance_hypernym` | 17 | Instance of |
| `instance_hyponym` | 18 | Has instance |
| `is_caused_by` | 19 | Is caused by |
| `is_entailed_by` | 20 | Is entailed by |
| `is_exemplified_by` | 21 | Is exemplified by |
| `mero_member` | 22 | Member meronym |
| `mero_part` | 23 | Part meronym |
| `mero_substance` | 24 | Substance meronym |
| `other` | 25 | Other relation |
| `participle` | 26 | Participle |
| `pertainym` | 27 | Pertains to |
| `similar` | 28 | Similar to |

### POS Codes

| Code | Meaning |
|------|---------|
| `n` | Noun |
| `v` | Verb |
| `a` | Adjective |
| `r` | Adverb |
| `s` | Adjective satellite |

---

## Python API Design

### Core Functions

```python
from wn_editor.batch import (
    # Loading
    load_change_request,

    # Validation
    validate_change_request,
    ValidationResult,
    ValidationError,

    # Execution
    execute_change_request,
    BatchResult,
    ChangeResult,

    # Data classes
    ChangeRequest,
    Change,
)
```

### Usage Examples

```python
from wn_editor.batch import (
    load_change_request,
    validate_change_request,
    execute_change_request,
)

# Load from YAML file
request = load_change_request("changes.yaml")

# Validate before execution
validation = validate_change_request(request)
if not validation.is_valid:
    for error in validation.errors:
        print(f"[{error.index}] {error.operation}: {error.message}")
    exit(1)

# Execute with change tracking
result = execute_change_request(request)

print(f"Applied {result.success_count}/{result.total_count} changes")
print(f"Session ID: {result.session_id}")

# Check individual results
for change_result in result.changes:
    status = "OK" if change_result.success else "FAILED"
    print(f"  [{status}] {change_result.operation}: {change_result.message}")

# Rollback if needed
from wn_editor import rollback_session
rollback_session(result.session_id)
```

### Dry Run Mode

```python
# Preview changes without applying them
result = execute_change_request(request, dry_run=True)

for change in result.changes:
    print(f"Would execute: {change.operation}")
    print(f"  Target: {change.target}")
```

### Data Classes

```python
@dataclass
class ChangeRequest:
    """Parsed change request from YAML."""
    session_name: Optional[str]
    session_description: Optional[str]
    lexicon: str
    changes: List[Change]
    source_file: Optional[Path]

@dataclass
class Change:
    """Single change operation."""
    operation: str
    params: Dict[str, Any]
    line_number: Optional[int]  # For error reporting

@dataclass
class ValidationResult:
    """Result of validating a change request."""
    is_valid: bool
    errors: List[ValidationError]
    warnings: List[str]

@dataclass
class ValidationError:
    """Validation error for a specific change."""
    index: int
    operation: str
    field: str
    message: str
    line_number: Optional[int]

@dataclass
class ChangeResult:
    """Result of executing a single change."""
    index: int
    operation: str
    success: bool
    message: str
    target: Optional[str]  # Synset ID or other identifier
    created_id: Optional[str]  # For create operations

@dataclass
class BatchResult:
    """Result of executing a batch change request."""
    session_id: int
    total_count: int
    success_count: int
    failure_count: int
    changes: List[ChangeResult]
    duration_seconds: float
```

---

## CLI Design

### Commands

```bash
# Validate a change request file
wn-batch validate changes.yaml

# Execute changes (with confirmation prompt)
wn-batch apply changes.yaml

# Execute without confirmation
wn-batch apply changes.yaml --yes

# Dry run (validate + show what would happen)
wn-batch apply changes.yaml --dry-run

# Override lexicon from file
wn-batch apply changes.yaml --lexicon awn3

# View execution history
wn-batch history [--limit 10]

# Rollback a session
wn-batch rollback <session_id>

# Show session details
wn-batch show <session_id>
```

### Output Examples

**Validation:**
```
$ wn-batch validate changes.yaml

Validating changes.yaml...
  Lexicon: awn3
  Changes: 15

Validation Results:
  [ERROR] Change #3 (add_relation): Synset 'awn3-99999999-n' not found
  [ERROR] Change #7 (add_word): Missing required field 'word'
  [WARN]  Change #10 (add_relation): Relation already exists (will be skipped)

Found 2 errors, 1 warning
```

**Execution:**
```
$ wn-batch apply changes.yaml

Applying changes from changes.yaml...
  Lexicon: awn3
  Session: "Add medical terminology"

  [1/15] create_synset: Created awn3-00099001-n
  [2/15] add_word to awn3-00001740-n: OK
  [3/15] add_relation: FAILED - Target synset not found
  [4/15] modify_definition: OK
  ...

Results:
  Total:    15
  Success:  13
  Failed:   2
  Session:  42

To rollback: wn-batch rollback 42
```

---

## Architecture

### Package Structure

```
wn_editor/
├── __init__.py
├── editor.py
├── changelog.py
└── batch/
    ├── __init__.py      # Public API exports
    ├── schema.py        # Dataclasses and constants
    ├── parser.py        # YAML loading and parsing
    ├── validator.py     # Schema and referential validation
    ├── executor.py      # Change execution engine
    └── cli.py           # CLI entry point
```

### Module Responsibilities

**schema.py**
- Dataclass definitions (ChangeRequest, Change, ValidationResult, etc.)
- Operation name constants
- Relation type name-to-ID mapping
- Field requirements per operation

**parser.py**
- Load YAML files
- Parse into ChangeRequest objects
- Track line numbers for error reporting
- Handle encoding (UTF-8 for Arabic)

**validator.py**
- Schema validation (required fields, types)
- Referential validation:
  - Synset IDs exist in database
  - Relation types are valid
  - Words exist (for delete operations)
- Return detailed error messages with locations

**executor.py**
- Map operations to editor methods
- Execute changes within tracking session
- Collect results (success/failure)
- Handle dry-run mode
- Continue on error, report all failures

**cli.py**
- argparse-based CLI
- Commands: validate, apply, history, rollback, show
- Colored output (optional)
- Exit codes for scripting

---

## Implementation Plan

### Phase 1: Core Module Structure (Day 1)

**Tasks:**
1. Create `wn_editor/batch/` directory
2. Implement `schema.py`:
   - All dataclasses
   - Operation constants
   - Relation type mapping
3. Implement `parser.py`:
   - YAML loading with PyYAML
   - Parse to ChangeRequest
4. Add PyYAML dependency to pyproject.toml
5. Create `__init__.py` with exports

**Deliverables:**
- `wn_editor/batch/schema.py`
- `wn_editor/batch/parser.py`
- `wn_editor/batch/__init__.py`
- Updated `pyproject.toml`

### Phase 2: Validation (Day 2)

**Tasks:**
1. Implement `validator.py`:
   - Schema validation (required fields)
   - Type validation
   - Referential validation (synset lookup)
   - Collect all errors, don't stop on first
2. Write unit tests for validation

**Deliverables:**
- `wn_editor/batch/validator.py`
- `tests/test_batch_validator.py`

### Phase 3: Executor (Day 3)

**Tasks:**
1. Implement `executor.py`:
   - Operation handlers for each operation type
   - Integration with changelog tracking
   - Dry-run mode
   - Result collection
2. Write unit tests for executor

**Deliverables:**
- `wn_editor/batch/executor.py`
- `tests/test_batch_executor.py`

### Phase 4: CLI (Day 4)

**Tasks:**
1. Implement `cli.py`:
   - validate command
   - apply command (with --dry-run, --yes)
   - history command
   - rollback command
   - show command
2. Add console_scripts entry point
3. Write CLI tests

**Deliverables:**
- `wn_editor/batch/cli.py`
- Updated `pyproject.toml` with entry point
- `tests/test_batch_cli.py`

### Phase 5: Documentation & Polish (Day 5)

**Tasks:**
1. Update README.md with batch feature docs
2. Update CHANGELOG.md
3. Create example YAML files
4. End-to-end integration tests
5. Final review and cleanup

**Deliverables:**
- Updated `README.md`
- Updated `CHANGELOG.md`
- `examples/batch_changes.yaml`
- `tests/test_batch_integration.py`

---

## Validation Details

### Schema Validation Rules

| Operation | Required Fields | Field Types |
|-----------|-----------------|-------------|
| `create_synset` | `words`, `definition` | words: list, definition: str |
| `add_word` | `synset`, `word` | synset: str, word: str |
| `delete_word` | `synset`, `word` | synset: str, word: str |
| `add_definition` | `synset`, `definition` | synset: str, definition: str |
| `modify_definition` | `synset`, `definition` | synset: str, definition: str |
| `delete_definition` | `synset` | synset: str |
| `add_example` | `synset`, `example` | synset: str, example: str |
| `delete_example` | `synset`, `example` | synset: str, example: str |
| `set_pos` | `synset`, `pos` | synset: str, pos: str |
| `add_relation` | `source`, `target`, `type` | all: str |
| `delete_relation` | `source`, `target`, `type` | all: str |
| `set_ili` | `synset`, `ili` | synset: str, ili: str |
| `delete_ili` | `synset` | synset: str |

### Referential Validation Rules

1. **Synset exists**: For all operations referencing a synset ID, verify it exists in the database
2. **Relation type valid**: For relation operations, verify type name is in RELATION_TYPES mapping
3. **POS valid**: For set_pos, verify pos is one of: n, v, a, r, s
4. **Word exists**: For delete_word, verify the word exists in the synset
5. **Definition exists**: For modify_definition/delete_definition, verify index is valid

### Error Message Format

```
[ERROR] Change #{index} ({operation}): {message}
        Field: {field}
        Line: {line_number}
```

---

## Dependencies

### New Dependencies

```toml
[project]
dependencies = [
    "wn>=0.9.1",
    "PyYAML>=6.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0.0",
    "pytest-cov>=4.0.0",
]

[project.scripts]
wn-batch = "wn_editor.batch.cli:main"
```

---

## Testing Strategy

### Unit Tests

1. **Parser tests**: Load various YAML formats, handle errors
2. **Validator tests**: Each validation rule, edge cases
3. **Executor tests**: Each operation type, error handling

### Integration Tests

1. **Full pipeline**: Load → Validate → Execute → Verify
2. **Rollback**: Execute → Rollback → Verify restoration
3. **Error recovery**: Partial execution with failures

### Test Fixtures

- Sample YAML files for testing
- Test lexicon (from existing conftest.py)
- Mock synsets for referential validation

---

## Future Enhancements (Out of Scope for Phase 1)

1. **CSV support**: Bulk operations from spreadsheets
2. **JSON format**: Alternative to YAML
3. **Sense-level operations**: Direct sense manipulation
4. **Entry-level operations**: Entry management
5. **Form-level operations**: Pronunciation, tags
6. **ILI operations**: Create/modify ILI entries
7. **Parallel execution**: Process changes concurrently
8. **Diff output**: Show what changed in detail
9. **Undo/redo**: Multiple rollback levels
10. **Import from LMF XML**: Convert standard WordNet format
