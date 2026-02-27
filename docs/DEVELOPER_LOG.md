# wn-editor-extended Developer Log

## Session 1: wn 1.0.0 Compatibility Audit (2026-02-16)

### Objective

Audit `wn-editor-extended` v0.7.0 for compatibility with `wn` 1.0.0 (released 2026-02-01). The package currently depends on `wn >= 0.9.1` and was developed/tested against `wn` 0.14.0.

### Environment

| Component | Version |
|---|---|
| wn-editor-extended | 0.7.0 (local), 0.6.1 (PyPI) |
| wn (installed) | 0.14.0 |
| wn (latest) | 1.0.0 |
| Python | 3.12.11 |

### Methodology

1. Downloaded `wn-1.0.0-py3-none-any.whl` and extracted `schema.sql`, `_db.py`, `__init__.py`, `ili.py`
2. Compared schema column-by-column against wn 0.14.0
3. Grepped `wn-editor-extended` source for all potentially affected APIs
4. Classified each finding by severity

---

### Summary of Findings

**Verdict: NOT compatible with wn 1.0.0. Upgrade will require significant changes.**

| Severity | Count | Description |
|---|---|---|
| CRITICAL | 7 | Will crash immediately on use |
| HIGH | 3 | Changelog/rollback system broken |
| MEDIUM | 1 | Test assertion failures |
| LOW | 1 | Behavioral change in normalization |
| SAFE | 4 | No impact |

---

### CRITICAL Issues (Will Crash)

#### C1: `INSERT INTO synsets` — Wrong Column Count

**File:** `editor.py:907`
```python
INSERT INTO synsets VALUES (null,?,?,null,null,1,null,?)
# 8 values: rowid, id, lexicon_rowid, ili_rowid, pos, lexicalized, lexfile_rowid, metadata
```

**Problem:** wn 1.0.0 removed the `lexicalized` column from `synsets`. Table now has 7 columns, but INSERT provides 8 values.

**wn 0.14.0 schema:** `rowid, id, lexicon_rowid, ili_rowid, pos, lexicalized, lexfile_rowid, metadata`
**wn 1.0.0 schema:** `rowid, id, lexicon_rowid, ili_rowid, pos, lexfile_rowid, metadata`

**Fix:** Change to `INSERT INTO synsets VALUES (null,?,?,null,null,null,?)` (7 values, drop the `1` for lexicalized).

#### C2: `INSERT INTO senses` — Wrong Column Count

**File:** `editor.py:1420`
```python
INSERT INTO senses VALUES(null,?,?,?,null,?,null,1,null)
# 9 values: rowid, id, lexicon_rowid, entry_rowid, entry_rank, synset_rowid, synset_rank, lexicalized, metadata
```

**Problem:** wn 1.0.0 removed `lexicalized` from `senses`. Table now has 8 columns, INSERT provides 9 values.

**wn 0.14.0 schema:** `rowid, id, lexicon_rowid, entry_rowid, entry_rank, synset_rowid, synset_rank, lexicalized, metadata`
**wn 1.0.0 schema:** `rowid, id, lexicon_rowid, entry_rowid, entry_rank, synset_rowid, synset_rank, metadata`

**Fix:** Change to `INSERT INTO senses VALUES(null,?,?,?,null,?,null,null)` (8 values, drop the `1` for lexicalized).

#### C3: `INSERT INTO lexicons` — Wrong Column Count

**File:** `editor.py:525`
```python
INSERT INTO lexicons VALUES (null,?,?,?,?,?,?,?,?,?,?,0)
# 12 values for the old 12-column table
```

**Problem:** wn 1.0.0 added a `specifier` column (position 2, after rowid). Table now has 13 columns.

**wn 0.14.0 schema:** `rowid, id, label, language, email, license, version, url, citation, logo, metadata, modified`
**wn 1.0.0 schema:** `rowid, specifier, id, label, language, email, license, version, url, citation, logo, metadata, modified`

**Fix:** Add specifier value (format: `{id}:{version}`). Change to 13 values and compute `specifier = f"{lex_id}:{version}"`.

#### C4: `INSERT INTO pronunciations` — Wrong Column Count

**File:** `editor.py:1973`
```python
INSERT INTO pronunciations VALUES (?,?,?,?,?,?)
# 6 values: form_rowid, value, variety, notation, phonemic, audio
```

**Problem:** wn 1.0.0 added `lexicon_rowid` column (position 2). Table now has 7 columns.

**wn 0.14.0 schema:** `form_rowid, value, variety, notation, phonemic, audio`
**wn 1.0.0 schema:** `form_rowid, lexicon_rowid, value, variety, notation, phonemic, audio`

**Fix:** Add `lexicon_rowid` parameter and change to 7 values.

#### C5: `INSERT INTO tags` — Wrong Column Count

**File:** `editor.py:2014`
```python
INSERT INTO tags VALUES (?,?,?)
# 3 values: form_rowid, tag, category
```

**Problem:** wn 1.0.0 added `lexicon_rowid` column (position 2). Table now has 4 columns.

**wn 0.14.0 schema:** `form_rowid, tag, category`
**wn 1.0.0 schema:** `form_rowid, lexicon_rowid, tag, category`

**Fix:** Add `lexicon_rowid` parameter and change to 4 values.

#### C6: `wn.ILI` Type No Longer Exported

**Files:** `editor.py:692, 703, 707, 795, 1066, 1078`
```python
def __init__(self, ili: wn.ILI):       # line 692
if isinstance(ili, wn.ILI):            # line 707
def as_ili(self) -> wn.ILI:            # line 795
def set_ili(self, ili: int | wn.ILI):  # line 1066
```

**Problem:** In wn 0.14.0, `wn.ILI` is a Protocol class exported in `__all__`. In wn 1.0.0, `ILI` is NOT exported from `wn.__init__` — it lives only in `wn.ili.ILI` (a frozen dataclass, not a Protocol).

**Fix:** Import from the new location: `from wn.ili import ILI` or use `wn.ili.ILI`. The `isinstance()` check and type annotations need updating.

#### C7: `wn.ili()` Function Replaced by Module

**Files:** `editor.py:807`, `batch/executor.py:502`
```python
return wn.ili(res[0][0])    # editor.py:807
ili = wn.ili(id=ili_id)     # batch/executor.py:502
```

**Problem:** In wn 0.14.0, `wn.ili` is a callable function (`wn.ili(id="i12345")` returns an ILI object). In wn 1.0.0, `wn.ili` is the **module** `wn/ili.py`. Calling `wn.ili(...)` raises `TypeError: 'module' object is not callable`.

**New API:** `wn.ili.get("i12345")` returns `ILI | None`.

**Fix:** Replace `wn.ili(id=...)` with `wn.ili.get(...)`.

---

### HIGH Issues (Changelog/Rollback Broken)

#### H1: `TABLE_COLUMNS["synsets"]` Includes Removed `lexicalized`

**File:** `changelog.py:509`
```python
"synsets": ["id", "lexicon_rowid", "ili_rowid", "pos", "lexicalized", "metadata"],
```

**Problem:** The `lexicalized` column no longer exists in wn 1.0.0. The rollback system uses these column lists to construct INSERT/UPDATE queries for undoing changes. With a wrong column list, rollback operations will produce invalid SQL.

**Fix:** Remove `"lexicalized"` from synsets columns. The new column list should be `["id", "lexicon_rowid", "ili_rowid", "pos", "lexfile_rowid", "metadata"]`.

**Note:** This column list was ALREADY inaccurate for wn 0.14.0 — the 0.14.0 schema has `lexfile_rowid` which is missing from the list. This is a pre-existing bug.

#### H2: `TABLE_COLUMNS["senses"]` Includes Removed Columns

**File:** `changelog.py:510`
```python
"senses": ["id", "lexicon_rowid", "entry_rowid", "synset_rowid", "sense_key", "lexicalized", "metadata"],
```

**Problem:** Multiple issues:
- `sense_key` does not exist in wn 0.14.0 OR 1.0.0 (pre-existing bug)
- `lexicalized` removed in wn 1.0.0
- `entry_rank` and `synset_rank` are missing (pre-existing bug)

**Fix:** Update to `["id", "lexicon_rowid", "entry_rowid", "entry_rank", "synset_rowid", "synset_rank", "metadata"]`.

#### H3: `TABLE_COLUMNS` for pronunciations and tags Missing `lexicon_rowid`

**File:** `changelog.py:523-524`
```python
"pronunciations": ["form_rowid", "value", "variety", "notation", "phonemic", "audio"],
"tags": ["form_rowid", "tag", "category"],
```

**Problem:** wn 1.0.0 added `lexicon_rowid` to both tables. Rollback queries will fail.

**Fix:** Add `"lexicon_rowid"` after `"form_rowid"` in both lists.

---

### MEDIUM Issues (Test Failures)

#### M1: Test Asserts `ILI` Object String Representation

**File:** `tests/test_batch.py:632`
```python
assert str(dog.ili) == "ILI('i46360')"
```

**Problem:** In wn 0.14.0, `Synset.ili` returns an `ILI` object whose `str()` is `"ILI('i46360')"`. In wn 1.0.0, `Synset.ili` returns a plain string `"i46360"`, so `str(dog.ili)` would be just `"i46360"`.

**Fix:** Change assertion to `assert dog.ili == "i46360"` or make version-conditional.

---

### LOW Issues (Behavioral Changes)

#### L1: Form Normalizer Changed from `lower()` to `casefold()`

**Impact:** The `normalized_form` column in `forms` is populated using the normalizer. `casefold()` is more aggressive than `lower()` — e.g., German `"ß".casefold()` returns `"ss"` while `"ß".lower()` returns `"ß"`. This could affect search results for certain characters but is unlikely to cause crashes.

**Affected code:** `FormEditor._create()` at `editor.py:1892` inserts forms but does NOT explicitly normalize (sets `normalized_form` to `null`). The `wn` library handles normalization on import/search, so this is low-risk.

---

### SAFE (No Impact)

| API Change | Status | Notes |
|---|---|---|
| `Synset.relation_map()` removed | Not used | No references in wn-editor-extended |
| `Sense.relation_map()` removed | Not used | No references in wn-editor-extended |
| `wn.web` module removed | Not used | No references in wn-editor-extended |
| `relations(data=True)` returns new types | Not used | No `data=True` calls found |
| `wn._db.connect` function | Still exists | Same interface, still works |

---

### Architecture Risk: Deep Coupling to `wn._db`

The editor relies heavily on `wn._db.connect` (a private API) — **83 direct `connect()` calls** across `editor.py` and `changelog.py`. While `connect()` still exists in wn 1.0.0, key observations:

1. **Schema hash validation:** wn 1.0.0 added `_check_schema_compatibility()` which compares a hash of the database schema against `COMPATIBLE_SCHEMA_HASHES`. If wn-editor-extended's SQL modifications change the schema structure, this check could reject the database on subsequent connections.

2. **No public write API:** The `wn` library still provides no public API for writing to the database, so direct SQL via `_db.connect` remains the only option. This is an inherent fragility.

3. **INSERT with positional VALUES:** 5 of the 7 critical issues stem from using `INSERT INTO table VALUES (...)` without explicit column names. Using `INSERT INTO table (col1, col2, ...) VALUES (?, ?, ...)` would be more resilient to column additions (though not removals).

---

### Full Schema Diff: wn 0.14.0 vs wn 1.0.0

#### Changed Tables

| Table | Change | Details |
|---|---|---|
| `lexicons` | +1 column | Added `specifier TEXT NOT NULL` (position 2) + `UNIQUE (specifier)` constraint |
| `synsets` | -1 column | Removed `lexicalized BOOLEAN` |
| `senses` | -1 column | Removed `lexicalized BOOLEAN` |
| `pronunciations` | +1 column | Added `lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid)` (position 2) |
| `tags` | +1 column | Added `lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid)` (position 2) |

#### New Tables

| Table | Purpose |
|---|---|
| `entry_index` | Maps `entry_rowid` to `lemma` text (replaces implicit lookup) |
| `unlexicalized_synsets` | Contains `synset_rowid` for synsets that are not lexicalized (replaces boolean column) |
| `unlexicalized_senses` | Contains `sense_rowid` for senses that are not lexicalized (replaces boolean column) |

#### Unchanged Tables (17 total)

`ilis`, `proposed_ilis`, `entries`, `forms`, `synset_relations`, `sense_relations`, `sense_synset_relations`, `definitions`, `synset_examples`, `sense_examples`, `adjpositions`, `counts`, `syntactic_behaviours`, `syntactic_behaviour_senses`, `relation_types`, `ili_statuses`, `lexfiles`, `lexicon_dependencies`, `lexicon_extensions`

---

### Recommended Upgrade Path

#### Option A: Version-Conditional Code (Minimal Disruption)

Detect wn version at runtime and branch:
```python
import wn
WN_VERSION = tuple(int(x) for x in wn.__version__.split(".")[:2])

if WN_VERSION >= (1, 0):
    from wn.ili import ILI
    # Use new schema column counts
else:
    ILI = wn.ILI
    # Use old schema column counts
```

**Pros:** Supports both wn 0.14.0 and 1.0.0 simultaneously.
**Cons:** Doubles maintenance burden, complex branching in SQL queries.

#### Option B: Hard Upgrade to wn 1.0.0 Only (Recommended)

Update `pyproject.toml` dependency to `wn >= 1.0.0` and fix all 11 issues:

1. Fix all 5 INSERT statements for new column counts
2. Replace `wn.ILI` with `from wn.ili import ILI`
3. Replace `wn.ili(id=...)` with `wn.ili.get(...)`
4. Fix TABLE_COLUMNS in changelog.py (also fixes pre-existing bugs)
5. Fix test assertion for `Synset.ili` string representation
6. Use explicit column names in INSERT statements for future resilience

**Pros:** Clean break, fixes pre-existing changelog bugs, future-proof INSERT statements.
**Cons:** Drops support for wn < 1.0.0. Users must rebuild their WordNet databases.

#### Option C: Defer (Current State)

Keep `wn >= 0.9.1, < 1.0.0` in pyproject.toml to explicitly block the incompatible version.

**Pros:** Zero effort, no risk of breakage.
**Cons:** Misses new wn 1.0.0 features (`wn.lemmas()`, WN-LMF 1.4, `reset_database()`).

---

### Pre-Existing Bugs Discovered

During this audit, two pre-existing bugs in `changelog.py` TABLE_COLUMNS were discovered:

1. **synsets columns missing `lexfile_rowid`:** The 0.14.0 schema has this column but TABLE_COLUMNS omits it.
2. **senses columns have phantom `sense_key`:** TABLE_COLUMNS lists `sense_key` which doesn't exist in wn 0.14.0. The actual columns `entry_rank` and `synset_rank` are missing.

These bugs mean the changelog rollback system is **already partially broken** against wn 0.14.0 for synset and sense operations.

---

### Files Examined

| File | Lines | Purpose |
|---|---|---|
| `wn_editor/editor.py` | ~2033 | Core editor — 83 `connect()` calls, 5 broken INSERTs, 6 ILI references |
| `wn_editor/changelog.py` | ~600 | Change tracking — 3 broken TABLE_COLUMNS entries |
| `wn_editor/batch/executor.py` | ~520 | Batch execution — 1 broken `wn.ili()` call |
| `tests/test_batch.py` | ~650 | Tests — 1 broken assertion |
| `wn 1.0.0 schema.sql` | ~230 | New database schema |
| `wn 0.14.0 schema.sql` | ~200 | Current database schema |
| `wn 1.0.0 __init__.py` | ~75 | New public API (ILI removed) |
| `wn 1.0.0 ili.py` | ~280 | New ILI module (`get()`, `ILI` dataclass) |
| `wn 1.0.0 _db.py` | ~150 | Database connection (still compatible) |

---

## Session 2: Lexicon Version Disambiguation Fix (2026-02-27)

### Objective

Fix Known Issue #1 from `docs/design/known-issues.md` — silent data corruption when two versions of the same lexicon coexist in the database. The DB schema allows `UNIQUE(id, version)` on lexicons and `UNIQUE(id, lexicon_rowid)` on synsets/entries, but the entire public API resolved lexicons and entities by bare `id` alone (`WHERE id = ?`). With two versions loaded, mutations hit all versions, reads returned arbitrary rows, and the user received no warning.

### Problem Analysis

Three categories of affected code paths (line numbers are pre-fix):

#### Lexicon-level — every method using `get_lexicon_rowid`/`get_lexicon_row`

| Location | Pattern | Effect |
|---|---|---|
| `db.py:446-450` | `SELECT rowid FROM lexicons WHERE id = ?` + `fetchone()` | Returns arbitrary version |
| `editor.py:270,276` | `UPDATE lexicons SET ... WHERE id = ?` | Updates ALL versions |
| `editor.py:322` | `DELETE FROM lexicons WHERE id = ?` | Deletes ALL versions |
| `editor.py:589,935,1570` | `s.lexicon_rowid = (SELECT rowid FROM lexicons WHERE id = ?)` | Subquery returns arbitrary version |
| `validator.py:187` | Same subquery in `_lex_filter` | Validates wrong version |
| `exporter.py:60-63,90-95` | `WHERE id IN (...)` | Exports/removes wrong versions |

#### Entity-level — every method using `get_synset_rowid`/`get_entry_rowid`/`get_sense_rowid`

| Location | Pattern | Effect |
|---|---|---|
| `editor.py:483,493` | `UPDATE synsets SET ... WHERE id = ?` | Updates entity in ALL lexicons |
| `editor.py:545` | `DELETE FROM synsets WHERE id = ?` | Deletes from ALL lexicons |
| `editor.py:843,849` | `UPDATE entries SET ... WHERE id = ?` | Same pattern for entries |
| `editor.py:894` | `DELETE FROM entries WHERE id = ?` | Same for entry deletion |
| `editor.py:617` | `WHERE s.id = ?` + `fetchone()` | Returns arbitrary version's entity |
| `db.py:465-513` | All `get_*_rowid` helpers | `fetchone()` on bare `id` |

#### Import path — creates the collision

| Location | Pattern | Effect |
|---|---|---|
| `importer.py:507` | `WHERE id = ? AND version = ?` | Only blocks exact version match |
| `importer.py:679` | `executemany INSERT` with v2.0's `lexicon_rowid` | Creates duplicate entity IDs across versions |

The `UNIQUE(id, lexicon_rowid)` constraint allows this — it's composite, not global. After import, synset/entry/sense tables have duplicate IDs scoped to different lexicon versions, but the API has no way to distinguish them.

---

### Solution — Four-Layer Defence

#### Layer 1: Prevention — block same-ID different-version at the gate

`create_lexicon()` and `_import_lexicon()` now check for any existing lexicon with the same `id` before proceeding. If found, they raise `DuplicateEntityError` with a message directing the user to delete the old version first.

| Method | File | Lines (post-fix) |
|---|---|---|
| `create_lexicon` | `editor.py` | 187–197 |
| `_import_lexicon` | `importer.py` | 510–522 |

This prevents the dangerous multi-version state from ever occurring. Users must explicitly delete v1.0 before creating or importing v2.0 with the same ID.

#### Layer 2: Hardened SQL — mutations target exact `rowid`

Six mutation methods changed from `WHERE id = ?` to `WHERE rowid = ?`, using the `rowid` already obtained from the initial existence check. This is a defensive fix — even though Layer 1 prevents simultaneous versions, the SQL is now correct regardless.

| Method | File | Lines (post-fix) | Change |
|---|---|---|---|
| `update_lexicon` | `editor.py` | 284, 290 | `WHERE rowid = ?` using `lex_rowid = row["rowid"]` |
| `delete_lexicon` | `editor.py` | 337 | `DELETE FROM lexicons WHERE rowid = ?` |
| `update_synset` | `editor.py` | 508, 518 | Both POS and metadata UPDATEs use `synset_rowid` |
| `delete_synset` | `editor.py` | 570 | `DELETE FROM synsets WHERE rowid = ?` |
| `update_entry` | `editor.py` | 876, 882 | Both UPDATEs use `entry_rowid` |
| `delete_entry` | `editor.py` | 928 | `DELETE FROM entries WHERE rowid = ?` |

#### Layer 3: Specifier support — `"id:version"` accepted everywhere

All lexicon-accepting APIs now accept the specifier format (`"awn:1.0"`) in addition to bare IDs (`"awn"`). Resolution logic: try `WHERE specifier = ?` first, fall back to `WHERE id = ?`.

| Component | File | Lines (post-fix) | Change |
|---|---|---|---|
| `get_lexicon_rowid` | `db.py` | 444–464 | Specifier-first, bare-ID fallback |
| `get_lexicon_row` | `db.py` | 467–484 | Same pattern |
| `_lex_filter` | `validator.py` | 183–201 | Resolves via `get_lexicon_rowid`, eliminates ambiguous subquery (21 call sites updated) |
| `_resolve_lexicon_rowid` | `exporter.py` | 80–85 | New helper using deferred import |
| `_build_resource` | `exporter.py` | 89+ | Resolves each `lexicon_id` to rowid, queries `WHERE rowid IN (...)` |
| `commit_to_wn` | `exporter.py` | 110+ | Resolves to rowid, then `SELECT id, version FROM lexicons WHERE rowid = ?` |
| `create_synset`, `create_entry` | `editor.py` | various | Resolve canonical bare ID for prefix generation |
| `find_synsets`, `find_entries`, `find_senses` | `editor.py` | various | Replace subquery with `get_lexicon_rowid` + `WHERE lexicon_rowid = ?` |

#### Layer 4: Model enhancement — `LexiconModel.specifier` property

| Component | File | Lines |
|---|---|---|
| `specifier` property | `models.py` | 222–225 |

Returns `f"{self.id}:{self.version}"` (e.g., `"awn:1.0"`). Works on frozen slotted dataclasses because `@property` is a class-level descriptor.

---

### Design Decision: Why Prevent Rather Than Support Multi-Version

An external reviewer raised 6 critique points against the original plan which proposed supporting simultaneous multi-version coexistence. After validating each point against source:

| Critique | Verdict | Implication |
|---|---|---|
| Entity-level `WHERE id = ?` unaddressed | TRUE | `update_synset`, `delete_synset`, etc. would still corrupt |
| Keeping both old and new lookup functions | TRUE | Removed old functions instead of adding new ones |
| History format change is breaking | TRUE | Dropped history changes entirely |
| Import path not considered | TRUE | Added guard to `_import_lexicon` |
| `_all_lexicon_ids` hand-waved | TRUE | Concrete return type specified |
| No migration path | PARTIAL | No schema migration needed (specifier column already exists) |

**Conclusion:** Full multi-version support requires threading lexicon context through every entity-level API method — a v2.0 architectural change, not a bug fix. The "one version at a time" approach is complete for the intended AWN workflow.

---

### Files Changed

| File | Insertions | Deletions | Purpose |
|---|---|---|---|
| `src/wordnet_editor/editor.py` | +94 | -37 | Layers 1, 2, 3 |
| `src/wordnet_editor/db.py` | +25 | -5 | Layer 3: specifier-aware lookups |
| `src/wordnet_editor/validator.py` | +35 | -23 | Layer 3: `_lex_filter` + 21 call sites |
| `src/wordnet_editor/exporter.py` | +27 | -10 | Layer 3: rowid-based resolution |
| `src/wordnet_editor/importer.py` | +11 | -4 | Layer 1: import guard |
| `src/wordnet_editor/models.py` | +5 | -0 | Layer 4: specifier property |
| `tests/test_lexicon_versioning.py` | +281 | -0 | New test file (26 tests) |
| `docs/design/known-issues.md` | +526 | -0 | Issue #1 marked as fixed |
| **Total** | **+999** | **-84** | |

---

### Test Results

```
tests/test_lexicon_versioning.py (26 tests):
  TestLayer1Prevention          — 5 tests (block, allow different ID, same-version, create-after-delete, import)
  TestLayer2RowidMutations      — 6 tests (update/delete synset, entry, lexicon)
  TestLayer3SpecifierSupport    — 11 tests (get, create, find, update, delete, validate with specifier)
  TestLayer4SpecifierProperty   — 2 tests (property value, list_lexicons)
  TestBackwardsCompatibility    — 2 tests (full CRUD cycle with bare IDs)

Full suite: 153 passed, 0 failed (26 new + 127 existing)
```

---

### Commit

`86d9afb` — Fix lexicon version disambiguation (Known Issue #1)
