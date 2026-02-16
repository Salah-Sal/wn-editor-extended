# Implementation Comparison Report

**Subject**: `wn-editor-extended` (existing implementation) vs `wordnet-editor` (our design)
**Date**: 2026-02-16

This report compares the existing `wn-editor-extended` implementation (cloned to `wn-editor-extended/`) against the 9 architecture deliverables we produced for `wordnet-editor`. The goal is to identify what the existing implementation does well, where it falls short, and what our design addresses that it does not.

---

## Executive Summary

`wn-editor-extended` is a functional 8,000-line editing framework with 6 editor classes, a YAML batch system, and hook-based change tracking. It operates **directly on `wn`'s database** and covers basic CRUD operations well. However, it has significant gaps compared to our design: no compound operations (merge/split/move), no automatic inverse relation handling, only 27 of 85+ relation types, no WN-LMF XML import/export pipeline, and no independent editor database. Our design addresses all of these gaps while maintaining compatibility with `wn`.

| Dimension | `wn-editor-extended` | `wordnet-editor` (our design) |
|-----------|---------------------|-------------------------------|
| Architecture | Direct mutation of `wn`'s DB | Independent shadow DB |
| API surface | 6 editor classes, ~96 methods | 1 `WordnetEditor` class, ~45 methods |
| Relation types | 27 (IntEnum) | 85 synset + 48 sense + 4 sense-synset |
| Auto-inverse | Not supported | Automatic with `REVERSE_RELATIONS` |
| Compound ops | None (merge/split/move) | Full support with atomicity |
| Import | YAML batch only | WN-LMF XML + `wn` DB |
| Export | None (relies on `wn`) | WN-LMF XML + `commit_to_wn()` |
| Validation | Schema/reference checks only | 23 rules (6 ERROR, 17 WARNING) |
| Change tracking | Hook-based changelog DB with rollback | Field-level `edit_history` table |
| Test coverage | 3,037 lines, ~100 tests | 60+ structured scenarios (planned) |
| Dependencies | `wn >= 0.9.1`, `PyYAML` | `wn >= 1.0.0` only |

---

## 1. Architecture

### `wn-editor-extended`: Direct DB Mutation

The existing implementation imports `wn._db.connect()` and executes raw SQL directly against `wn`'s SQLite database. Changes are immediately visible to `wn`'s query API (`wn.synsets()`, `wn.senses()`, etc.).

```python
from wn._db import connect
with connect() as conn:
    conn.execute("INSERT INTO synsets ...")
    conn.commit()
```

**Advantages:**
- Changes are instantly queryable via `wn`'s API
- No data synchronization needed
- Simpler mental model for users

**Risks:**
- Mutates `wn`'s append-only database (which has zero UPDATE statements by design)
- Bypasses `wn`'s import pipeline and schema versioning
- Risk of corrupting data that other tools depend on
- No isolation between editing and querying workflows
- Uses `wn._db` (private API) which can break between `wn` releases

### `wordnet-editor` (our design): Independent Shadow DB

Our design maintains a separate `editor.db` that replicates `wn`'s schema with editor-specific additions (`edit_history`, `meta` tables). The `wn` database is never mutated directly. Data flows back to `wn` only via `commit_to_wn()`, which exports to validated WN-LMF XML and re-imports.

**Advantages:**
- `wn`'s database stays pristine
- Full UPDATE/DELETE operations without constraint
- Can validate before committing
- Portable single-file database
- Uses only `wn`'s public API

**Trade-off:**
- Requires explicit `commit_to_wn()` step
- Query capabilities limited to basic `get_*`/`find_*` until committed
- Data exists in two places during editing

### Assessment

Our shadow DB approach is architecturally safer and aligns with `wn`'s design philosophy (append-only). The existing implementation's direct mutation approach is pragmatic but fragile. The `wn` library's maintainer has explicitly stated the database is not designed for direct mutation.

---

## 2. API Design

### `wn-editor-extended`: 6 Editor Classes

The implementation uses a multi-class approach where each entity type has its own editor:

```python
# 6 separate editor classes
lex = LexiconEditor("ewn")
synset = lex.create_synset()
synset.add_word("example").add_definition("A sample").set_pos("n")
sense = SenseEditor(wn.senses()[0])
form = FormEditor(wn.forms()[0])
ili = IlIEditor()
```

**Method chaining** is a key pattern — most methods return `self`:
```python
synset.add_word("cat").add_word("feline").add_definition("A small domesticated carnivore").set_pos("n")
```

**Total methods**: ~96 across all classes

### `wordnet-editor` (our design): Single `WordnetEditor` Class

Our design uses a single entry point with ~45 methods organized in 13 sections:

```python
editor = WordnetEditor("editor.db")
synset = editor.create_synset(lexicon_id="ewn", pos="n")
editor.add_definition(synset.id, "A sample")
editor.add_sense(entry_id, synset.id)
editor.add_synset_relation(source_id, "hypernym", target_id)
```

**No method chaining** — each method is a standalone operation that returns a model or None.

### Comparison

| Aspect | `wn-editor-extended` | `wordnet-editor` |
|--------|---------------------|-------------------|
| Entry point | 6 classes, each for one entity type | 1 class, all operations |
| Pattern | Method chaining (fluent API) | Explicit method calls |
| Entity references | `wn.Synset` objects or rowids | String IDs |
| Return values | `self` (for chaining) or `None` | Frozen dataclass models |
| Context manager | No | Yes (`with WordnetEditor(...) as e:`) |
| Batch mode | YAML batch system | `batch()` context manager |
| Factory methods | `LexiconEditor.create_new_lexicon()` | `WordnetEditor.from_wn()`, `from_lmf()` |

**Assessment**: The multi-class approach in `wn-editor-extended` is more object-oriented but requires users to manage multiple editor instances. Our single-class design is simpler and more Pythonic for batch editing workflows. The fluent API is elegant but makes error handling harder (exceptions mid-chain lose context).

---

## 3. Relation Coverage

### `wn-editor-extended`: 27 Relation Types

```python
class RelationType(IntEnum):
    also=1, antonym=2, attribute=3, causes=4, derivation=5,
    domain_region=6, domain_topic=7, entails=8, exemplifies=9,
    has_domain_region=10, has_domain_topic=11, holo_member=12,
    holo_part=13, holo_substance=14, hypernym=15, hyponym=16,
    instance_hypernym=17, instance_hyponym=18, is_exemplified_by=19,
    mero_member=20, mero_part=21, mero_substance=22, participle=23,
    pertainym=24, similar=25, is_caused_by=26, is_entailed_by=27
```

Uses `IntEnum` where values map to `relation_types` table rowids. This is **fragile** — rowids can differ between database instances.

**Missing relation types** (compared to WN-LMF 1.4 / GWA spec):
- All `co_*` relations (co_agent_instrument, co_agent_patient, etc.)
- All `involved_*` relations (involved_agent, involved_direction, etc.)
- `eq_synonym`, `ir_synonym`
- `feminine`, `masculine`, `young`, `diminutive`, `augmentative` and their `has_*` variants
- `anto_gradable`, `anto_simple`, `anto_converse`
- `metaphor`, `metonym` and their `has_*` variants
- `simple_aspect_ip/pi`, `secondary_aspect_ip/pi`
- `holonym`, `meronym` (generic versions)
- Various directional and manner relations

### `wordnet-editor` (our design): 85 + 48 + 4 Relation Types

Our design adopts the complete set from `wn/constants.py`:
- **85 synset relation types** (all from `SYNSET_RELATIONS`)
- **48 sense relation types** (all from `SENSE_RELATIONS`)
- **4 sense-synset relation types** (all from `SENSE_SYNSET_RELATIONS`)

Uses string-based types validated against frozen sets, with a complete `REVERSE_RELATIONS` inverse mapping.

### Auto-Inverse Handling

| Feature | `wn-editor-extended` | `wordnet-editor` |
|---------|---------------------|-------------------|
| Auto-inverse on add | No | Yes (default `auto_inverse=True`) |
| Auto-inverse on remove | No | Yes |
| Symmetric relations | Manual (user adds both) | Automatic (two rows stored) |
| Inverse map | Not defined | 83-entry `REVERSE_RELATIONS` dict |
| Bypass option | N/A | `auto_inverse=False` for bulk import |

**Assessment**: The existing implementation requires users to manually manage both directions of every relation. This is error-prone and leads to W404 validation warnings (missing inverse). Our design handles this automatically, matching `wn`'s own storage pattern.

---

## 4. Compound Operations

### `wn-editor-extended`: Not Supported

No merge, split, or move operations exist. Users would need to manually:
- Delete from source + add to target (move)
- Redirect all relations + transfer definitions (merge)
- Create new synsets + redistribute senses (split)

This is tedious and error-prone without atomicity guarantees.

### `wordnet-editor` (our design): Full Support

| Operation | Rules | Atomicity |
|-----------|-------|-----------|
| `merge_synsets(source, target)` | 7 rules (RULE-MERGE-001 through 007) | Single transaction |
| `split_synset(synset, sense_groups)` | 6 rules (RULE-SPLIT-001 through 006) | Single transaction |
| `move_sense(sense, target_synset)` | 4 rules (RULE-MOVE-001 through 004) | Single transaction |

Each compound operation handles edge cases: duplicate senses from same entry during merge, ILI conflict detection, unlexicalized synset marking after move, relation copying during split.

**Assessment**: Compound operations are essential for real WordNet editing workflows. Their absence in `wn-editor-extended` is its most significant functional gap.

---

## 5. Import/Export Pipeline

### `wn-editor-extended`: YAML Batch Only

**Import**: YAML batch files with 13 operation types:
```yaml
lexicon: ewn
changes:
  - operation: create_synset
    words: [{word: "blockchain", pos: "n"}]
    definition: "A decentralized ledger..."
```

**Export**: None. Relies entirely on `wn`'s own export capabilities.

**No WN-LMF XML support**: Cannot import from or export to the standard WordNet interchange format.

### `wordnet-editor` (our design): Full WN-LMF Pipeline

| Capability | Method | Pipeline |
|-----------|--------|----------|
| Import from XML | `from_lmf(source)` | `wn.lmf.load()` -> iterate -> INSERT |
| Import from `wn` DB | `from_wn(specifier)` | `wn.export()` -> temp XML -> XML import |
| Export to XML | `export_lmf(dest)` | Query DB -> `LexicalResource` TypedDict -> `wn.lmf.dump()` |
| Commit to `wn` | `commit_to_wn()` | Export -> validate -> `wn.remove()` -> `wn.add()` |

Round-trip fidelity is guaranteed for all WN-LMF 1.4 entities (45 data types preserved).

**Assessment**: WN-LMF XML is the standard interchange format for WordNets worldwide. Without import/export support, `wn-editor-extended` cannot participate in the broader WordNet ecosystem. Our design fully supports the standard.

---

## 6. Validation

### `wn-editor-extended`: Schema + Reference Checks

Validation is limited to the batch system (`batch/validator.py`, 624 lines):

1. **Schema validation**: Required fields present, operation types recognized
2. **Reference validation**: Lexicon exists, synset IDs exist, relation types valid, POS values valid
3. **Type checking**: Parameters have correct types

No semantic validation of WordNet data structures (missing definitions, orphaned synsets, missing inverses, POS mismatches, etc.).

### `wordnet-editor` (our design): 23 Validation Rules

| Category | Rules | Examples |
|----------|-------|---------|
| General | 1 ERROR | Duplicate IDs within lexicon |
| Entries/Senses | 2 WARNING, 1 ERROR | Entry with no senses, redundant senses, missing synset |
| Synsets/ILI | 7 WARNING, 1 ERROR | Empty synsets, duplicate ILI, blank definitions, ILI length |
| Relations | 3 WARNING, 2 ERROR | Missing target, invalid type, missing inverse, self-loop |
| Taxonomy | 1 WARNING | POS mismatch with hypernym |
| Editor-specific | 2 WARNING, 1 ERROR | ID prefix violation, no definitions, low confidence |

Two-tier enforcement:
- **Immediate**: FK violations, UNIQUE violations, NOT NULL, self-loops, invalid relation types, ID prefix
- **Deferred**: `validate()` returns `list[ValidationResult]` for semantic checks

**Assessment**: `wn-editor-extended` validates batch input format but not WordNet data quality. Our design validates both structural integrity (immediate) and semantic correctness (deferred), matching `wn/validate.py`'s 17 rules plus 6 editor-specific rules.

---

## 7. Change Tracking

### `wn-editor-extended`: Hook-Based Changelog

**Architecture**: Separate `~/.wn_changelog.db` SQLite database with `sessions` and `changes` tables.

**Tracking mechanism**: Decorator `@_modifies_db` on editor methods triggers pre/post hooks that capture old_data/new_data as JSON.

**Key features**:
- Session-based grouping of changes
- Per-change and per-session rollback
- 40+ tracked methods with method-to-table mappings
- Thread-local hook storage
- CLI for history/rollback (`wn-batch history`, `wn-batch rollback`)

```python
with tracking_session("Add new terms"):
    synset.add_word("example")
    synset.add_definition("A sample")
# Session automatically closed, all changes recorded
```

**Rollback logic**: INSERT->DELETE, DELETE->INSERT (restore old_data), UPDATE->restore old values.

### `wordnet-editor` (our design): Field-Level Edit History

**Architecture**: `edit_history` table in the same editor database (not separate).

```sql
CREATE TABLE edit_history (
    rowid INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL,
    entity_id TEXT NOT NULL,
    field_name TEXT,
    operation TEXT NOT NULL CHECK(operation IN ('CREATE','UPDATE','DELETE')),
    old_value TEXT,    -- JSON
    new_value TEXT,    -- JSON
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f','now'))
);
```

**Key features**:
- Field-level granularity (which field changed, not just which row)
- Co-located with entity data (single file)
- `record_history` parameter for bulk import optimization
- Query methods: `get_history()`, `get_entity_history()`
- No rollback mechanism (not in scope)

### Comparison

| Aspect | `wn-editor-extended` | `wordnet-editor` |
|--------|---------------------|-------------------|
| Storage | Separate DB (`~/.wn_changelog.db`) | Same DB (`edit_history` table) |
| Granularity | Row-level (table + rowid) | Field-level (entity + field) |
| Rollback | Yes (per-change and per-session) | No (not in scope) |
| Sessions | Yes (grouping + context manager) | No (flat history) |
| Performance toggle | `enable_tracking()`/`disable_tracking()` | `record_history=False` on import |
| Portability | Two files needed | Single file |

**Assessment**: `wn-editor-extended`'s changelog with rollback is more sophisticated and operationally useful. Our design is simpler and more portable (single file), with finer granularity (field-level). The rollback capability in the existing implementation is a genuine advantage we don't replicate. However, co-locating history with data in our design ensures the audit trail travels with the database.

---

## 8. Database Schema

### `wn-editor-extended`: Uses `wn`'s Schema As-Is

Operates on all 27 tables in `wn`'s `schema.sql` without modifications. No additional tables or columns.

### `wordnet-editor` (our design): Replicates + Extends

Replicates all 27 `wn` tables identically, plus:
- `meta` table (schema versioning)
- `edit_history` table (change tracking)
- `UNIQUE` constraints on relation tables (defense-in-depth)
- `PRAGMA journal_mode = WAL` (better read concurrency during export)

**Assessment**: Our approach preserves full compatibility while adding editor-specific capabilities. The `UNIQUE` constraints on relation tables prevent duplicate relations that `wn`'s schema allows.

---

## 9. ID Generation

### `wn-editor-extended`

| Entity | Pattern | Example |
|--------|---------|---------|
| Entry | `w{N}` | `w0`, `w1` |
| Sense | `w_{form}_{N}` | `w_test_0` |
| Synset | `{lexicon}-{N}` | `ewn-0` |
| ILI | `i{N}` | `i0` |

Simple incremental counters. No POS encoding, no prefix validation.

### `wordnet-editor` (our design)

| Entity | Pattern | Example |
|--------|---------|---------|
| Entry | `{lexicon_id}-{normalized_lemma}-{pos}` | `ewn-cat-n` |
| Sense | `{entry_id}-{synset_local_part}-{position:02d}` | `ewn-cat-n-02121620-n-01` |
| Synset | `{lexicon_id}-{counter:08d}-{pos}` | `ewn-00012345-n` |

Deterministic, human-readable IDs with lexicon prefix validation (RULE-ID-004). POS encoded at creation time (RULE-ID-005: IDs never change even if POS changes).

**Assessment**: Our IDs are more informative, follow OEWN conventions, and include prefix validation. The existing implementation's IDs are minimal and don't encode useful information.

---

## 10. Error Handling

### `wn-editor-extended`

- `AttributeError` for invalid constructor arguments
- `TypeError` for wrong input types
- Logger warnings for unsafe operations (e.g., pronunciation deletion)
- No domain-specific exception hierarchy

### `wordnet-editor` (our design)

```
WordnetEditorError (base)
  +-- ValidationError
  +-- EntityNotFoundError
  +-- DuplicateEntityError
  +-- RelationError
  +-- ConflictError
  +-- DataImportError
  +-- ExportError
  +-- DatabaseError
```

Each exception carries entity type, entity ID, and a human-readable message. Transaction safety guarantees exceptions trigger automatic rollback.

**Assessment**: Our exception hierarchy is far more specific and useful for error handling in batch workflows. The existing implementation relies on generic Python exceptions.

---

## 11. Dependencies and Packaging

| Aspect | `wn-editor-extended` | `wordnet-editor` |
|--------|---------------------|-------------------|
| Python version | >= 3.9 | >= 3.10 |
| `wn` version | >= 0.9.1 | >= 1.0.0 |
| Extra dependencies | `PyYAML >= 6.0` | None |
| Build system | flit_core | hatchling |
| Type hints | PEP 561 (py.typed) | PEP 561 (py.typed) |
| Layout | Flat `wn_editor/` | `src/wordnet_editor/` |
| Private API usage | Yes (`wn._db.connect()`) | No (public API only) |

**Assessment**: Our design has zero extra dependencies and uses only `wn`'s public API, making it more resilient to upstream changes.

---

## 12. Test Coverage

### `wn-editor-extended`: 3,037 Lines

| File | Lines | Focus |
|------|-------|-------|
| `test_batch.py` | 862 | Batch parser, validation, execution |
| `test_changelog.py` | 593 | Change tracking, rollback |
| `test_synset_editor.py` | 326 | Synset CRUD |
| `test_integration.py` | 286 | End-to-end workflows |
| `test_sense_editor.py` | 242 | Sense CRUD |
| `test_entry_form_editor.py` | 222 | Entry/form operations |
| `test_ili_editor.py` | 175 | ILI operations |
| `test_utilities.py` | 134 | Helper functions |
| `test_lexicon_editor.py` | 133 | Lexicon operations |

Tests use real EWN (English WordNet) database for ground truth validation.

### `wordnet-editor` (our design): 60+ Scenarios (Planned)

Structured test scenarios covering:
- All CRUD operations (happy path + error path)
- Relation auto-inverse mechanics
- All compound operations (merge/split/move)
- Import/export round-trip fidelity
- All 23 validation rules
- Cascade deletion behavior
- Cross-lexicon operations
- Confidence score inheritance

**Assessment**: The existing implementation has actual running tests (an advantage). Our test plan is more comprehensive in coverage but exists only as a specification. The existing tests don't cover compound operations (because they don't exist), relation auto-inverse, or validation rules beyond batch format checking.

---

## 13. What `wn-editor-extended` Does Well

1. **Method chaining**: Fluent API is elegant for interactive use
2. **Change tracking with rollback**: The session-based changelog with per-change and per-session rollback is sophisticated and operationally useful
3. **YAML batch system**: A complete batch processing pipeline with CLI, parser, validator, and executor
4. **Pronunciation and tag management**: Full CRUD on FormEditor (our API has these too, but the implementation exists)
5. **Working tests**: 3,037 lines of actual running tests against real WordNet data
6. **CLI tooling**: `wn-batch` command for validate/apply/history/rollback

---

## 14. What `wn-editor-extended` Lacks (Addressed by Our Design)

| Gap | Impact | Our Design's Solution |
|-----|--------|-----------------------|
| No independent database | Risk of corrupting `wn`'s store | Shadow DB architecture |
| No auto-inverse relations | Manual inverse management, W404 warnings | Automatic with `REVERSE_RELATIONS` |
| Only 27 of 137 relation types | Cannot represent GWA/WN-LMF 1.4 relations | Complete coverage |
| No merge/split/move | Cannot perform common WordNet editing tasks | 3 compound operations with atomicity |
| No WN-LMF XML import/export | Cannot interchange with other WordNet tools | Full import/export pipeline |
| No semantic validation | Data quality issues go undetected | 23 validation rules |
| No domain-specific exceptions | Generic errors, hard to handle | 8-class exception hierarchy |
| Uses `wn` private API | Breaks on upstream changes | Public API only |
| `PyYAML` dependency | Extra install requirement | Zero extra dependencies |
| IntEnum rowid mapping for relations | Fragile across DB instances | String-based with validation |
| No self-loop prevention | Can create nonsensical self-relations | RULE-REL-004 enforcement |
| No ID prefix validation | IDs can violate WN-LMF conventions | RULE-ID-004 enforcement |
| No cascade deletion rules | Manual cleanup required | 7 deletion rules with cascade |
| No confidence score handling | Cannot manage WN-LMF confidence metadata | RULE-CONF-001 through 003 |
| No unlexicalized synset tracking | Empty synsets not flagged | RULE-EMPTY-001/002 |

---

## 15. Recommendations

### What to Adopt from `wn-editor-extended`

1. **Rollback capability**: Consider adding session-based rollback to our design in a future version. The existing implementation's approach (storing old_data/new_data JSON snapshots) is proven and useful.

2. **YAML batch system**: While not in our v1.0 scope, a batch scripting system is valuable for automated workflows. Could be added as an extension module.

3. **CLI tooling**: A `wn-editor` CLI command would complement the programmatic API.

### What to Keep from Our Design

1. **Shadow database**: Non-negotiable for data safety
2. **Complete relation coverage**: 137 types vs 27 — essential for WN-LMF compliance
3. **Auto-inverse**: Eliminates the most common source of WordNet data errors
4. **Compound operations**: Core editing workflows that cannot be replicated manually
5. **WN-LMF pipeline**: Standard interchange is required for ecosystem participation
6. **Semantic validation**: Data quality assurance before export
7. **Single-class API**: Simpler, more discoverable than 6 separate editors

### Implementation Priority

Given that `wn-editor-extended` exists as a reference, implementation should prioritize the areas where our design diverges most:

1. **Shadow DB + schema initialization** (architecture.md, schema.md)
2. **Import/export pipeline** (pipeline.md) — this is entirely missing from the reference
3. **Compound operations** (behavior.md RULE-MERGE/SPLIT/MOVE) — also entirely missing
4. **Auto-inverse relation handling** (behavior.md RULE-REL-001 through 010)
5. **Validation engine** (validation.md) — our 23 rules vs their format-only checks
6. **Cascade deletion** (behavior.md RULE-DEL-001 through 007)

The existing implementation can serve as a useful reference for basic CRUD patterns, but the core differentiators of our design must be implemented from our specifications, not adapted from the reference.
