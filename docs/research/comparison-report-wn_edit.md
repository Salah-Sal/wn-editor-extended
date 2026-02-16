# Implementation Comparison Report: `wn_edit`

**Subject**: `wn_edit` (existing implementation) vs `wordnet-editor` (our design)
**Date**: 2026-02-16

This report compares `wn_edit` v0.3.2 (cloned to `wn_edit/`) against the 9 architecture deliverables we produced for `wordnet-editor`. This is the second comparison — see `comparison-report.md` for the `wn-editor-extended` comparison.

---

## Executive Summary

`wn_edit` is a compact, well-designed ~1,600-line editor that works **entirely with in-memory `wn.lmf` TypedDict structures**. It loads data from `wn`'s DB or XML, manipulates dicts in memory, and exports back to XML or commits via `wn.add_lexical_resource()`. This is architecturally closer to our design than `wn-editor-extended`: it doesn't mutate `wn`'s DB directly during edits, uses `wn.lmf` structures as the data model, and has solid round-trip fidelity. However, it lacks compound operations, auto-inverse relations, edit history, its own persistent database, and most of our validation rules. It's the strongest existing implementation we've found.

| Dimension | `wn_edit` | `wordnet-editor` (our design) |
|-----------|-----------|-------------------------------|
| Architecture | In-memory dicts (no persistent editor DB) | Independent SQLite shadow DB |
| API surface | 1 class, ~30 methods + 14 helpers | 1 class, ~45 methods |
| Data model | `wn.lmf` TypedDicts directly | Frozen dataclasses (query), DB rows (storage) |
| Relation types | All from `wn.constants` (68 synset, 48 sense) | Same — full coverage |
| Auto-inverse | Not supported | Automatic with `REVERSE_RELATIONS` |
| Compound ops | None (no merge/split/move) | Full support with atomicity |
| Import | From `wn` DB (bulk SQL + XML fallback), from XML | WN-LMF XML + `wn` DB |
| Export | To XML via `wn.lmf.dump()`, commit via `wn.add_lexical_resource()` | WN-LMF XML + `commit_to_wn()` |
| Validation | Delegates to `wn.validate` (optional) | 23 rules (6 ERROR, 17 WARNING) |
| Change tracking | None | Field-level `edit_history` table |
| Atomicity | None (in-memory, no transactions) | SQLite transactions for every mutation |
| ID generation | UUID-based (`{lex}-synset-{uuid8}-{pos}`) | Deterministic counter-based (`{lex}-{counter:08d}-{pos}`) |
| Storage persistence | None (must export to save) | Automatic (SQLite file) |
| Test coverage | 218+ tests, 2,129 lines | 60+ structured scenarios (planned) |
| Lines of code | ~1,600 (editor only) | ~2,400-3,300 (planned) |
| Dependencies | `wn >= 1.0.0` only | `wn >= 1.0.0` only |
| Python version | 3.10+ | 3.10+ |

---

## 1. Architecture

### `wn_edit`: In-Memory Dict Manipulation

`wn_edit` works entirely with Python dicts in memory. The `WordnetEditor` holds a `LexicalResource` TypedDict and manipulates it directly. There is no editor-specific database.

```python
# Internal data is a dict tree:
self._resource = {
    'lmf_version': '1.4',
    'lexicons': [{
        'id': 'my-wn',
        'entries': [...],   # list of entry dicts
        'synsets': [...],   # list of synset dicts
        ...
    }]
}
```

**Advantages:**
- Simple — no DB schema to manage, no SQL
- Uses `wn.lmf` structures directly — guaranteed export compatibility
- Fast for small-to-medium lexicons (all data in memory)

**Risks:**
- No persistence — a crash loses all uncommitted work
- No atomicity — partial failures leave inconsistent state
- O(n) scans for many operations (mitigated by 4 index dicts)
- Memory-bound — OEWN (~120K synsets) must fit in RAM
- No concurrent access — single process only

### `wordnet-editor` (our design): Independent SQLite DB

Our design maintains its own `editor.db` file. All mutations are SQL operations within transactions. The DB survives crashes, supports concurrent reads, and can be backed up by copying a single file.

**Key difference:** `wn_edit` is a stateless transform pipeline (load → edit → export). Our design is a stateful editing environment with persistence, history, and transactional integrity.

---

## 2. API Design

### `wn_edit`: Single Class + Helper Functions

```python
# 1 class, ~30 methods
class WordnetEditor:
    def __init__(self, lexicon_specifier=None, create_new=False, ...)
    def create_synset(self, pos, definition=None, words=None, ...)
    def get_synset(self, synset_id)
    def modify_synset(self, synset_id, definition=None, ...)
    def remove_synset(self, synset_id)
    def add_synset_relation(self, source_id, target_id, rel_type, ...)
    def create_entry(self, lemma, pos, entry_id=None, forms=None)
    def get_entry(self, entry_id)
    def find_entries(self, lemma, pos=None)
    def add_word_to_synset(self, synset_id, lemma, pos=None)
    def remove_entry(self, entry_id)
    def add_sense_relation(self, source_sense_id, target_id, rel_type, ...)
    def export(self, filepath, validate_first=False)
    def commit(self, validate_first=False)
    def validate(self)
    def stats(self)
    # + metadata setters, load_from_file, internal methods

# 14 standalone helper functions
make_lexical_resource(), make_lexicon(), make_lexical_entry(), ...
```

### `wordnet-editor` (our design): Single Class, Richer API

```python
class WordnetEditor:
    # All CRUD + compound operations + import/export + validation + history
    # ~45 methods including:
    # - merge_synsets(), split_synset(), move_sense()
    # - add_definition(), remove_definition(), update_definition()
    # - add_example(), remove_example()
    # - get_history(), undo()
    # - import_lmf(), import_from_wn()
    # - export_lmf(), commit_to_wn()
    # - validate()
    # - batch() context manager
```

### Comparison

| Aspect | `wn_edit` | Our Design |
|--------|-----------|------------|
| Class count | 1 | 1 |
| Method count | ~30 | ~45 |
| Compound ops | 0 | 3 (merge, split, move) |
| Definition CRUD | Via `modify_synset()` only | Dedicated `add/remove/update_definition()` |
| Example CRUD | Via `modify_synset()` only | Dedicated `add/remove_example()` |
| Sense management | Implicit via `add_word_to_synset()` | Explicit `add_sense()`, `remove_sense()`, `move_sense()` |
| History queries | None | `get_history()`, filterable |
| Import methods | Constructor or `load_from_file()` | `import_lmf()`, `import_from_wn()` |
| Context manager | No | Yes (`batch()` for grouped mutations) |

**Notable `wn_edit` design choices:**
- `create_synset(words=['dog', 'canine'])` — convenience for creating synset + entries in one call
- `add_word_to_synset()` — finds-or-creates entry, then links sense (smart dedup)
- `modify_synset()` supports both replace-all and append modes for definitions/examples
- Helper functions (`make_synset()`, `make_entry()`, etc.) are separate from the class — useful for testing but adds cognitive overhead

---

## 3. Data Model

### `wn_edit`: Raw `wn.lmf` TypedDicts

All data is stored as nested dicts matching `wn.lmf` TypedDict structures:

```python
synset = {
    'id': 'my-wn-synset-a1b2c3d4-n',
    'partOfSpeech': 'n',
    'ili': '',
    'definitions': [{'text': 'A domesticated animal', 'language': '', 'sourceSense': '', 'meta': None}],
    'relations': [{'target': 'other-synset-id', 'relType': 'hypernym', 'meta': None}],
    'examples': [{'text': 'The dog barked', 'language': '', 'meta': None}],
    'members': [],
    'lexicalized': True,
    'meta': None,
}
```

**Advantages:**
- Zero translation cost on export — dicts go directly to `wn.lmf.dump()`
- Guaranteed compatibility with `wn`'s TypedDict expectations
- Familiar to anyone who knows WN-LMF

**Disadvantages:**
- Mutable — callers can accidentally corrupt internal state
- camelCase keys (`writtenForm`, `partOfSpeech`, `relType`) — un-Pythonic
- No type safety at runtime (dicts don't enforce required fields)
- Relations stored as flat lists within parent entities — O(n) lookups

### `wordnet-editor` (our design): Frozen Dataclasses + DB Rows

```python
@dataclass(frozen=True)
class SynsetModel:
    id: str
    lexicon_id: str
    pos: PartOfSpeech
    ili: str | None
    definitions: list[DefinitionModel]
    examples: list[ExampleModel]
    relations: list[RelationModel]
    lexicalized: bool
    metadata: dict[str, Any] | None
```

**Key difference:** Our models are immutable query results. Storage is in normalized SQLite tables with proper foreign keys. `wn_edit` uses mutable dicts that serve as both storage and query results.

---

## 4. Relation Handling

### `wn_edit`: Manual, No Auto-Inverse

```python
# Add hypernym — only forward direction
editor.add_synset_relation(dog_id, animal_id, 'hypernym')

# To also have hyponym, must add manually:
editor.add_synset_relation(animal_id, dog_id, 'hyponym')
```

- Relations stored as flat list in source synset's `relations` field
- No automatic inverse creation
- Validation is optional (`validate=True` warns on unknown types)
- All relation types from `wn.constants` are available but not enforced
- No self-loop prevention
- No symmetric relation handling

### `wordnet-editor` (our design): Automatic Inverse with Full Coverage

```python
# Add hypernym — automatically creates hyponym(animal → dog)
editor.add_synset_relation(dog_id, 'hypernym', animal_id)
# auto_inverse=True by default
```

- Automatic inverse via `REVERSE_RELATIONS` (83 entries)
- Symmetric relations stored as two rows (RULE-REL-007)
- Self-loop prevention (RULE-REL-004)
- Idempotent inverse handling (RULE-REL-002)
- Cross-lexicon support with proper lexicon_rowid assignment (RULE-REL-008)

**Impact:** Without auto-inverse, `wn_edit` users must manually maintain relation pairs, which is error-prone and leads to validation warnings (W404: missing reverse relation).

---

## 5. Compound Operations

### `wn_edit`: Not Supported

No merge, split, or move operations. Users must:
1. Manually transfer senses between synsets
2. Manually update all relation references
3. Manually handle ILI conflicts
4. Hope they didn't miss anything

The closest is `remove_synset()` which cascades to senses and orphaned entries.

### `wordnet-editor` (our design): Full Support

| Operation | Rules | Steps |
|-----------|-------|-------|
| `merge_synsets(source, target)` | RULE-MERGE-001 through 007 | Transfer senses, redirect relations, merge definitions, handle ILI, delete source |
| `split_synset(synset, groups)` | RULE-SPLIT-001 through 006 | Validate groups, create new synsets, reassign senses, copy relations |
| `move_sense(sense, target)` | RULE-MOVE-001 through 004 | Duplicate check, preserve relations, handle unlexicalization |

All compound operations are atomic (single transaction) with full history recording.

---

## 6. Import/Export Pipeline

### `wn_edit`: Import via Constructor, Export via `wn.lmf`

**Import from `wn` DB:**
1. Bulk SQL path: `wn._db.connect()` → 20 bulk SELECT queries → assemble dicts in Python (~10s for OEWN)
2. XML fallback: `wn.export()` → temp file → `wn.lmf.load()` (~140s for OEWN)

**Import from XML:**
```python
editor = WordnetEditor.load_from_file('wordnet.xml')
# Uses wn.lmf.load() internally
```

**Export to XML:**
```python
editor.export('output.xml')
# Uses wn.lmf.dump() on internal resource dict
```

**Commit to `wn` DB:**
```python
editor.commit()
# Uses wn.add_lexical_resource() — adds directly to wn's DB
```

**Strengths:**
- Bulk SQL loading is a clever optimization (10x faster than XML roundtrip)
- Graceful fallback if `wn`'s schema changes
- `load_from_file()` classmethod is clean

**Weaknesses:**
- `commit()` doesn't remove existing lexicon first — can create duplicates
- No validation-before-commit by default (`validate_first=False`)
- No temp-file safety pattern (validate → remove → add) like our design
- Imports only single lexicon at a time

### `wordnet-editor` (our design): Full Pipeline with Safety

**Import:** `wn.lmf.load()` → iterate → INSERT into editor DB (12 ordered steps with FK resolution)

**Export:** Query editor DB → construct LexicalResource TypedDict → `wn.lmf.dump()` → validate output

**Commit to `wn`:** Export to temp → validate → `wn.remove()` → `wn.add()` (RULE-EXPORT-003: validate BEFORE remove to prevent data loss)

**Key differences:**
- Our design validates before removing existing data from `wn`
- Our design supports multiple lexicons simultaneously
- Our design records import history (optional)

---

## 7. Validation

### `wn_edit`: Delegates to `wn.validate`

```python
def validate(self):
    # Export to temp XML → wn.validate(temp) → return messages
    import wn.validate as wn_validate
    report = wn_validate.validate(temp_path)
    return messages
```

- Optional dependency (`HAS_WN_VALIDATE` flag)
- Validates the exported XML, not the in-memory state
- No editor-specific validation rules
- No severity classification (ERROR vs WARNING)

### `wordnet-editor` (our design): Two-Tier, 23 Rules

**Tier 1 — Immediate enforcement** (DB constraints):
- Foreign key violations, UNIQUE violations, NOT NULL, self-loop prevention, relation type validation, ID prefix validation

**Tier 2 — Explicit `validate()` call:**
- 23 rules across 6 categories (General, Entries/Senses, Synsets/ILI, Relations, Taxonomy, Editor-specific)
- Returns `list[ValidationResult]` with rule_id, severity, entity_type, entity_id, message
- Does NOT raise — caller decides how to handle

**Key difference:** Our design catches errors at mutation time (immediate enforcement) plus offers deep semantic validation on demand. `wn_edit` only validates at export time.

---

## 8. Change Tracking & History

### `wn_edit`: None

No edit history, no audit log, no undo/redo. Users must manually track changes via XML snapshots:

```python
editor.export('backup.xml')
# ... make changes ...
# if something goes wrong:
editor = WordnetEditor.load_from_file('backup.xml')
```

### `wordnet-editor` (our design): Field-Level History

```sql
CREATE TABLE edit_history (
    rowid INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    field_name TEXT,
    operation TEXT NOT NULL,  -- 'CREATE', 'UPDATE', 'DELETE'
    old_value TEXT,           -- JSON
    new_value TEXT,           -- JSON
    timestamp TEXT NOT NULL
);
```

- Every mutation records what changed
- Queryable: "show all changes to synset X", "show all deletes in the last hour"
- Foundation for future undo/redo

---

## 9. ID Generation

### `wn_edit`: UUID-Based

```python
def _generate_id(self, prefix, suffix=''):
    unique = uuid.uuid4().hex[:8]
    return f"{lex_id}-{prefix}-{unique}-{suffix}"
```

- Synsets: `{lex}-synset-{uuid8}-{pos}` → e.g., `oewn-synset-a1b2c3d4-n`
- Entries: `{lex}-{lemma}-{uuid8}-{pos}` → e.g., `oewn-dog-a1b2c3d4-n`
- Senses: `{entry_id}-{synset_id}` → very long, concatenated IDs

**Issues:**
- UUID-based IDs are not deterministic — running the same code twice produces different IDs
- Sense IDs can be very long (concatenation of entry + synset IDs)
- No ID prefix validation
- `synset` literal in synset IDs is unusual for WN conventions

### `wordnet-editor` (our design): Deterministic Counter-Based

- Synsets: `{lex}-{counter:08d}-{pos}` → e.g., `oewn-00000042-n` (matches OEWN convention)
- Entries: `{lex}-{normalized_lemma}-{pos}` → e.g., `oewn-dog-n`
- Senses: `{entry_id}-{synset_local}-{pos:02d}` → compact
- ID prefix validation enforced (RULE-ID-004)
- All IDs are deterministic and reproducible

---

## 10. Persistence & Crash Safety

### `wn_edit`: No Persistence

All data lives in memory. If the process crashes, all edits since the last `export()` are lost. There is no auto-save, no journal, no WAL.

### `wordnet-editor` (our design): SQLite with WAL

- Every mutation is immediately persisted to `editor.db`
- WAL journal mode for crash safety and read concurrency
- ACID transactions guarantee consistency even on power loss
- Database file can be backed up, shared, or committed to version control

---

## 11. Transaction & Atomicity

### `wn_edit`: No Transactions

Operations modify dicts in-place. A multi-step operation (e.g., remove synset → remove senses → remove orphaned entries) can fail mid-way, leaving indexes and data inconsistent.

```python
def remove_synset(self, synset_id):
    synset = self._synset_by_id.get(synset_id)
    if not synset:
        raise KeyError(f"Synset '{synset_id}' not found")
    # Step 1: Remove senses
    for entry in self._lexicon['entries']:
        entry['senses'] = [s for s in entry['senses'] if s['synset'] != synset_id]
    # Step 2: Remove orphaned entries
    # Step 3: Remove synset from list
    # Step 4: Update indexes
    # If crash between steps → inconsistent state
```

### `wordnet-editor` (our design): Transaction Per Mutation

Every public API method runs within a single SQLite transaction. Compound operations (merge, split, move) are also atomic. If any step fails, the entire transaction rolls back.

---

## 12. Error Handling

### `wn_edit`: Standard Python Exceptions

| Exception | Usage |
|-----------|-------|
| `KeyError` | Entity not found |
| `ValueError` | Invalid POS, validation failure, missing required params |
| `TypeError` | Invalid count type |
| `ImportError` | `wn` or `wn.validate` not available |
| `FileNotFoundError` | XML file doesn't exist |

No custom exception hierarchy. Errors carry basic messages but no structured context.

### `wordnet-editor` (our design): Domain-Specific Hierarchy

```
WordnetEditorError (base)
├── ValidationError
├── EntityNotFoundError
├── DuplicateEntityError
├── RelationError
├── ConflictError
├── DataImportError
├── ExportError
└── DatabaseError
```

Each exception includes entity type, entity ID, and a human-readable message. Domain-specific exceptions prevent accidental catching by generic handlers.

---

## 13. Indexing & Performance

### `wn_edit`: 4 In-Memory Indexes

```python
_synset_by_id: Dict[str, Dict]        # O(1) synset lookup
_entry_by_id: Dict[str, Dict]         # O(1) entry lookup
_sense_by_id: Dict[str, Dict]         # O(1) sense lookup
_entries_by_lemma: Dict[str, List]     # O(1) lemma → entries
```

- Indexes rebuilt after every structural change (O(n))
- All data must fit in memory
- Queries that aren't indexed (e.g., "find all relations of type X") are O(n) scans

### `wordnet-editor` (our design): SQLite Indexes

- DB-level indexes on all foreign keys and lookup columns
- Queries use SQL with index-backed WHERE clauses
- No memory limit — SQLite handles large datasets efficiently
- Compound indexes for common query patterns

---

## 14. Test Coverage Comparison

### `wn_edit`: 218+ Tests, Well-Structured

| Test File | Tests | Lines | Coverage |
|-----------|-------|-------|----------|
| `test_editor.py` | ~68 | 1,352 | All CRUD, helpers, metadata, export, round-trip |
| `test_wn_integration.py` | ~18 | 523 | Commit → query via `wn` API, ILI, relations |
| `test_roundtrip_fidelity.py` | ~4 | 254 | OEWN round-trip (slow), minimal-diff tests |
| `conftest.py` | — | 26 | Fixtures |
| **Total** | **~90** | **2,155** | — |

**Strengths:**
- Good round-trip fidelity tests (especially the OEWN slow tests)
- Bulk loader equivalence test (SQL path = XML path)
- Integration tests that verify data is queryable via `wn` API after commit
- Metadata override tests (constructor + post-load)

**Gaps:**
- No auto-inverse relation tests (because feature doesn't exist)
- No compound operation tests (merge/split/move)
- No cascade deletion depth tests
- No sense-level operation tests (only 1 complex regression test)
- No ID format/uniqueness tests
- No concurrent access tests
- No large-scale performance tests (except slow OEWN test)

### `wordnet-editor` (our design): 60+ Planned Scenarios

Our test plan covers every API method with happy-path and error-path scenarios, including compound operations, auto-inverse, cascade deletion, validation rules, and import/export fidelity.

---

## 15. Dependencies & Packaging

### `wn_edit`

```toml
[project]
name = "wn_edit"
requires-python = ">=3.10"
dependencies = ["wn>=1.0.0"]
# Build: hatchling
# Dev tools: pytest, pytest-cov, mypy, ruff
```

### `wordnet-editor` (our design)

```toml
[project]
name = "wordnet-editor"
requires-python = ">=3.10"
dependencies = ["wn>=1.0.0"]
# Build: hatchling
# Dev tools: pytest, mypy, ruff
```

**Identical dependency profile.** Both target `wn >= 1.0.0` and Python 3.10+. Both use hatchling for builds.

---

## What `wn_edit` Does Well

1. **Clean single-class API** — Same pattern we chose. Methods are intuitive and well-named.

2. **Direct `wn.lmf` TypedDict usage** — Zero translation cost for export. The helper functions (`make_synset()`, `make_entry()`, etc.) create correctly-structured dicts.

3. **Bulk SQL loading** — The `_load_from_database_bulk()` method with graceful fallback is a clever optimization that cuts OEWN load time from 140s to 10s. We should consider this pattern for our `import_from_wn()`.

4. **Round-trip fidelity** — Extensive testing ensures that data survives import → edit → export cycles. The minimal-diff approach (only version change → minimal XML diff) is rigorous.

5. **Metadata override on construction** — Loading from `wn` DB with simultaneous metadata overrides (new version, new label, etc.) is a nice UX pattern for derivative works.

6. **LMF version handling** — Proper handling of different LMF versions (1.0 vs 1.1 vs 1.4) and awareness that `wn.export(version='1.0')` drops `lexfile` and `count` data.

7. **Good test discipline** — Slow tests marked separately, local `.wn_data` isolation, cleanup fixtures for `wn` DB.

8. **Minimal codebase** — 1,600 lines for the editor is remarkably compact. Easy to understand and maintain.

---

## What `wn_edit` Lacks (Addressed by Our Design)

1. **No persistent storage** — All edits are in-memory. A crash = lost work. Our design uses SQLite for durability.

2. **No auto-inverse relations** — Users must manually add both directions. Our design handles this automatically via `REVERSE_RELATIONS`.

3. **No compound operations** — No merge, split, or move. These are essential for real wordnet editing workflows.

4. **No edit history** — No record of what changed. Our design tracks field-level changes in `edit_history`.

5. **No transaction safety** — Multi-step operations can leave inconsistent state. Our design uses SQLite transactions.

6. **No self-loop prevention** — No check for `add_synset_relation(A, A, 'hypernym')`. Our design raises `ValidationError`.

7. **No semantic validation** — Delegates entirely to `wn.validate` at export time. Our design has 23 rules across 2 tiers.

8. **No cascade deletion rules** — `remove_synset()` removes senses and orphaned entries, but no formal cascade policy. Our design has 7 deletion rules (RULE-DEL-001 through 007).

9. **UUID-based IDs** — Non-deterministic, don't follow WN conventions. Our design uses deterministic counter-based IDs matching OEWN patterns.

10. **No ID prefix validation** — No check that IDs start with lexicon prefix. Our design enforces RULE-ID-004.

11. **No safe commit pattern** — `commit()` calls `wn.add_lexical_resource()` without first removing the existing lexicon, risking duplicates. Our design validates → removes → adds (RULE-EXPORT-003).

12. **No cross-lexicon relation support** — Single-lexicon editor. Our design supports multiple lexicons with cross-lexicon relations.

13. **No unlexicalized synset tracking** — No mechanism to mark synsets that lose all senses. Our design uses `unlexicalized_synsets` table (RULE-EMPTY-001/002).

---

## Refactoring Assessment

### Could we refactor `wn_edit` into our design?

**No — the architectural gap is fundamental.**

`wn_edit` stores everything as nested dicts in memory. Our design stores everything in a normalized SQLite database. This is not a refactoring — it's a ground-up rewrite of the storage layer, which is the foundation of every other component.

What we could reuse:

| Component | Reusable? | Notes |
|-----------|-----------|-------|
| Helper functions (`make_*`) | **Partially** | Useful pattern for constructing LMF dicts in our exporter |
| Bulk SQL loading | **Yes, adapt** | The `_load_from_database_bulk()` approach is faster than our planned XML roundtrip for `import_from_wn()`. We should adapt this pattern. |
| Round-trip fidelity tests | **Yes, adapt** | Test patterns and assertions are directly applicable |
| Integration tests | **Yes, adapt** | Commit → query patterns are relevant |
| Metadata override UX | **Yes, adopt** | Constructor overrides for derivative works |
| LMF version awareness | **Yes, adopt** | Handle version differences in import/export |

### Effort Comparison

| Approach | Estimated New Code | Estimated Refactored Code | Total Effort |
|----------|-------------------|--------------------------|-------------|
| Build from scratch | ~3,000 lines | 0 | Baseline |
| Refactor `wn_edit` | ~2,800 lines (everything except helper fns) | ~200 lines (helpers) | ~Same effort |

The "refactored" code is almost entirely new because:
- Storage layer: 100% new (dict → SQLite)
- Editor methods: ~90% new (need SQL, transactions, history, auto-inverse)
- Import: ~80% new (need FK resolution, ordered inserts)
- Export: ~70% new (need DB queries → TypedDict construction)
- Validation: ~95% new (23 rules vs delegation to `wn.validate`)
- History: 100% new (doesn't exist)
- Compound ops: 100% new (don't exist)

### Recommendation

**Build from scratch. Use `wn_edit` as a reference implementation.**

Specifically:
1. **Adopt** the bulk SQL loading pattern for `import_from_wn()` — it's 14x faster
2. **Adopt** the metadata override UX pattern for constructor
3. **Adopt** the LMF version awareness in import/export
4. **Adapt** the round-trip fidelity test patterns
5. **Reference** the `make_*` helpers when building our exporter (dict construction)
6. **Reference** the `wn.add_lexical_resource()` commit pattern (though add validation-first safety)

---

## Side-by-Side: `wn_edit` vs `wn-editor-extended` vs Our Design

| Dimension | `wn_edit` | `wn-editor-extended` | Our Design |
|-----------|-----------|---------------------|------------|
| Architecture | In-memory dicts | Direct `wn` DB mutation | Independent SQLite DB |
| Storage | None (volatile) | `wn`'s DB (shared) | Own `editor.db` (independent) |
| API style | 1 class, ~30 methods | 6 classes, ~96 methods | 1 class, ~45 methods |
| Data model | `wn.lmf` TypedDicts | DB rowids + `wn._db` | Frozen dataclasses + SQL |
| Relations | Manual, all types | Manual, 27 types | Auto-inverse, all types |
| Compound ops | None | None | merge/split/move |
| Import | wn DB + XML | YAML batch | XML + wn DB |
| Export | XML + commit | None | XML + commit |
| Validation | Delegates to `wn` | Schema checks | 23 rules, 2 tiers |
| History | None | Hook-based changelog | Field-level `edit_history` |
| Atomicity | None | Transaction per SQL | Transaction per mutation |
| ID generation | UUID-based | From `wn` DB | Deterministic counter |
| Persistence | Export to save | Always (wn DB) | Always (editor.db) |
| Crash safety | None | SQLite guarantees | SQLite WAL guarantees |
| Lines of code | ~1,600 | ~8,000 | ~3,000 (planned) |
| Test lines | ~2,155 | ~3,037 | ~2,500 (planned) |
| Dependencies | `wn>=1.0.0` | `wn>=0.9.1`, `PyYAML` | `wn>=1.0.0` |

### Winner by Category

| Category | Best Implementation | Why |
|----------|-------------------|-----|
| Simplicity | `wn_edit` | 1,600 lines, clean API |
| Correctness | Our design | Transactions, constraints, validation |
| Performance (import) | `wn_edit` | Bulk SQL loading |
| Durability | Our design | SQLite persistence |
| Relation integrity | Our design | Auto-inverse, self-loop prevention |
| Round-trip fidelity | `wn_edit` (tested) | Proven with OEWN |
| Batch operations | `wn-editor-extended` | YAML batch system |
| Change tracking | `wn-editor-extended` | Hook-based with rollback |
| Compound operations | Our design | Only one with merge/split/move |
| WN-LMF compliance | `wn_edit` | Direct TypedDict usage |

---

## Conclusion

`wn_edit` is the most architecturally aligned existing implementation to our design. It validates our key decisions: single-class API, `wn.lmf` TypedDict structures, `wn >= 1.0.0` dependency, and round-trip fidelity focus. However, its in-memory approach means it can't provide the persistence, atomicity, and semantic integrity guarantees that our SQLite-based design offers.

The strongest takeaway from `wn_edit` is the **bulk SQL loading optimization** — we should adopt this pattern rather than our planned XML roundtrip for `import_from_wn()`. The second strongest takeaway is the **round-trip fidelity test suite** — we should adapt these test patterns to validate our own export pipeline.

Build from scratch. Reference both implementations. Ship something better than either.
