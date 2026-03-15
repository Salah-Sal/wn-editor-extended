# Stakeholder Interview Notes

**Project:** wn-editor-extended v1.0.0
**Date:** 2026-03-15
**Method:** Codebase analysis and commit history review (in lieu of developer interviews)
**Stakeholders:** Library author/maintainer (commit history), NLP pipeline developers (stated use case)

---

## 1. What Operations Feel Slow?

### 1.1 Import Pipeline

**Symptom:** Importing a large WordNet (e.g., OEWN with 120K+ synsets) takes longer than expected.

**Root cause (from code analysis):**
- **Reading from source DB** (`_build_resource_from_wn_db`): Cascading N+1 — for each synset, issues ~8-15 individual queries to fetch ILIs, proposed ILIs, lexfiles, definitions, examples, relations, unlexicalized status, and members. For each entry, ~10-20 queries for forms, pronunciations, tags, senses, sense relations, etc. A 120K-synset, 150K-entry import easily reaches **1 million+ read queries** from the source `wn` database.
- **Writing to editor DB** (`_import_lexicon`): Partially optimized — synsets use `executemany` (bulk), but entries, forms, senses, and relations use individual `execute()` calls in a loop. Entry import is the bottleneck.
- **History recording**: When `record_history=True` (default), each imported entity generates an INSERT into `edit_history`. For a full import this adds ~300K+ additional writes. Setting `record_history=False` skips this overhead.

**Evidence:** The commit history shows a dedicated "Performance" PR phase (PRs #1-#8, Feb 19, 2026) where import optimization was a focus. The synset bulk insert was added then, but entry bulk insert was not completed.

### 1.2 Export Pipeline

**Symptom:** Exporting a large lexicon to XML takes longer than expected.

**Root cause:**
- **Synset export** is well-optimized: Uses 7 batch pre-fetch queries grouped by `lexicon_rowid`, then builds synset models from in-memory data with no additional DB queries. This is the correct pattern.
- **Entry export** is the bottleneck: `_build_entry()` issues per-entry queries for forms, per-form queries for pronunciations and tags, per-entry queries for senses, and per-sense queries for synset lookup, relations (with N+1 target ID lookups), examples, counts, adjpositions, unlexicalized status, and subcategorization frames. For a lexicon with 150K entries averaging 2 senses each, this is **hundreds of thousands of queries**.
- The asymmetry between the batch-optimized synset path and the N+1 entry path suggests the synset optimization was completed but the entry optimization is still TODO.

**Evidence:** The exporter code contains an explicit comment: `# Pre-fetch synset data to avoid N+1 queries` in the synset path, but no equivalent comment or pattern in the entry path.

### 1.3 Definition Search

**Symptom:** `find_synsets(definition_contains="...")` is slow on large databases.

**Root cause:** Uses `definition LIKE '%...%'` which triggers a full table scan on `definitions`. No FTS (Full-Text Search) index exists. This is the slowest possible pattern for text search in SQLite.

**Mitigation available:** SQLite FTS5 virtual table would provide near-instant full-text search. Alternatively, applications could build an in-memory index at startup.

---

## 2. Data Integrity Issues Encountered

### 2.1 Sense ID Uniqueness Gap

**Issue:** The `senses` table lacks a `UNIQUE(id, lexicon_rowid)` constraint, unlike `entries` and `synsets` which both have this constraint.

**Impact:** A direct SQL INSERT bypassing the Python API can create duplicate sense IDs within a lexicon. The application-level guard (`get_sense_rowid()` check before insert) works for single-writer scenarios but is vulnerable to concurrent writers (TOCTOU race).

**Discovery method:** Schema comparison across the three main entity tables.

### 2.2 Transaction Atomicity Breach

**Issue:** `_apply_overrides()` in `importer.py` (line 1098) calls `conn.commit()` directly, bypassing the outer `with conn:` transaction wrapper.

**Impact:** If `_apply_overrides()` is called after a partial import (within the `with conn:` block at line 491), the bare `conn.commit()` will commit whatever has been imported so far. If the subsequent import steps fail, the database will contain a partially-imported lexicon — violating the atomicity guarantee.

**Discovery method:** Tracing all `conn.commit()` and `conn.rollback()` calls outside `with conn:` wrappers.

### 2.3 Implicit COMMIT in `init_db()`

**Issue:** `conn.executescript(_DDL)` in `init_db()` (line 351) issues an implicit COMMIT before running the DDL, per SQLite documentation.

**Impact:** If `init_db()` is called inside an active transaction (unlikely in normal usage but possible in edge cases), that transaction is silently committed. This is a latent bug rather than an active issue.

### 2.4 `except Exception` Catch-All Masks Semantic Errors in Import

**Issue:** `import_from_wn()` (`importer.py` lines 48-51) wraps `_import_from_wn_bulk()` in a bare `except Exception` to fall back to the XML path when the bulk mechanism fails. However, this also catches `DuplicateEntityError` — a semantic error indicating the lexicon already exists in the target database.

**Impact:** When a user calls `WordnetEditor.from_wn("ewn:2024", "my_edits.db")` twice on the same file:
1. The bulk path reads from wn's DB, then hits the duplicate check → raises `DuplicateEntityError`
2. The `except Exception` swallows it and triggers the XML fallback
3. The XML path exports the entire lexicon to a temp file, parses it, then hits the *same* duplicate check → raises `DuplicateEntityError` again
4. This time it propagates to the caller

The user gets the correct error, but only after an unnecessary full XML export/parse cycle. For a large WordNet, this can waste 10-30 seconds before failing. The fix: narrow the `except` clause or re-raise known semantic errors before falling through.

### 2.5 Missing History for Entry Metadata Updates

**Issue:** `update_entry()` metadata update path (lines 880-884 in `editor.py`) does not call `_hist.record_update()`. Entry metadata changes are silently untracked while all other update paths properly record history.

**Impact:** Audit trail is incomplete for entry metadata mutations. A pipeline that updates entry metadata will have no record of the change in `edit_history`.

### 2.6 Design Document Inaccuracies `[SPEC]` `[SPEC⟷SPEC]`

The following issues were discovered in the design specification documents themselves — not just the implementation:

**D2: Incorrect SQLite locking claim** `[SPEC]`

`architecture.md` line 11 states: *"If two processes open the same `editor.db`, SQLite's file-level locking ensures writes are serialized (the second writer blocks until the first commits)."*

This is factually wrong. Without `busy_timeout` (which the implementation does not set — confirmed in `db.py` lines 335-346), the second writer receives an immediate `SQLITE_BUSY` error. There is no blocking. The design document gives false confidence about concurrent safety to any developer reading it.

**D3: Missing UNIQUE constraint in spec** `[SPEC]`

`schema.md` (SCHEMA-024) defines the `senses` table WITHOUT `UNIQUE(id, lexicon_rowid)`, while `entries` (SCHEMA-003) and `synsets` (SCHEMA-010) both include this constraint. The implementation correctly follows the spec — but the spec is wrong. This is a design-level omission: the implementer built exactly what was specified, and what was specified was incomplete.

**D1: Exception handling inconsistency between specs** `[SPEC⟷SPEC]`

- `architecture.md` section 1.8 specifies the dual-path import fallback catches `except (ImportError, AttributeError, sqlite3.OperationalError)`
- `pipeline.md` section 6.2 says only `ImportError` and `AttributeError`
- Implementation (`importer.py` lines 48-51) uses `except Exception` — matching neither spec

Three documents, three different exception lists. The implementation's `except Exception` is the broadest, masking semantic errors like `DuplicateEntityError`.

**D4: Naming mismatch (spec ↔ code)** `[SPEC⟷SPEC]`

`behavior.md` references a `REVERSE_RELATIONS` dict. The actual code in `relations.py` uses `SYNSET_RELATION_INVERSES` and `SENSE_RELATION_INVERSES`. The spec was never updated to match the implementation naming.

**D5: Validation rule count error** `[SPEC]`

`validation.md` claims 6 ERROR rules and 17 WARNING rules (23 total). Manual enumeration yields only 16 WARNING rules. The off-by-one indicates the spec was not validated against itself.

**D6: Migration strategy never implemented** `[SPEC→IMPL]`

`schema.md` section 2.6 describes compatible migration paths (additive changes, `ALTER TABLE`, etc.). The implementation's `check_schema_version()` only does exact string equality (`version != SCHEMA_VERSION` → raise error). There is no migration framework, no semantic version comparison, and no incremental migration path — despite the spec describing one.

**D12: Entity ID re-prefixing gap** `[SPEC]`

`pipeline.md` describes `_apply_overrides()` changing the `lexicon_id`, but the spec doesn't address what happens to child entity IDs (synsets, entries, senses) which are prefixed with the original lexicon ID (e.g., `oewn-00001234-n`). The implementation imports entity IDs verbatim and only updates `lexicons.id`, creating a mismatch between the lexicon namespace and its children's ID prefixes.

---

## 3. Planned Features That Stress the Schema

### 3.1 Multi-Pipeline Concurrent Access (Primary Deployment Target)

**Description:** Multiple NLP pipelines will simultaneously:
- Import base WordNets from different sources
- Create new synsets and entries for Arabic WordNet construction
- Add/modify relations between synsets
- Run validation checks
- Export results to WN-LMF 1.4 XML

**Schema stress points:**
- **Write contention**: All pipelines writing to the same SQLite file. No `busy_timeout`, no `BEGIN IMMEDIATE`, no retry logic.
- **ID generation collision**: `_generate_synset_id()` and `_generate_entry_id()` use read-then-increment patterns (MAX query) that are not safe under concurrency.
- **History table explosion**: Each pipeline generates history records. With 4 pipelines × thousands of mutations each, `edit_history` grows rapidly with no rotation.
- **WAL file growth**: Sustained multi-writer load can cause the WAL file to grow large between autocheckpoints.

### 3.2 Large-Scale Arabic WordNet Construction

**Description:** Building a comprehensive Arabic WordNet with potentially 100K+ synsets, requiring:
- Bulk creation of entries with Arabic lemmas
- Rich relation networks (hypernymy, antonymy, etc.)
- Integration with existing ILI entries
- Iterative refinement by multiple review cycles

**Schema stress points:**
- **Import performance**: Entry-level N+1 in the import pipeline
- **Export performance**: Entry/sense cascading N+1 in the export pipeline
- **Cascade deletion risk**: If an entire lexicon needs to be re-imported, `delete_lexicon` cascades across ~20 tables
- **UTF-8 handling**: Arabic text in `forms.form`, `definitions.definition`, etc. — SQLite handles UTF-8 natively, but `normalized_form` (casefolded) may need special handling for Arabic script

### 3.3 Automated Review/Merge Pipelines

**Description:** Pipelines that:
- Run `validate()` across the full lexicon
- Compare synsets across lexicons
- Merge duplicate or overlapping synsets via `merge_synsets()`
- Split over-general synsets via `split_synset()`

**Schema stress points:**
- **`merge_synsets`** is a complex multi-step operation touching ~8 tables. Under concurrent access, a merge could conflict with another pipeline creating senses for the same synset.
- **`validate()` does full table scans** for several rules (VAL-SYN-007 duplicate definitions, VAL-REL-003 duplicate relations). On a large database, validation itself can be slow.
- **Validation results are not persisted**: `validate()` returns a list of `ValidationResult` objects but does not store them. Re-running validation re-scans the entire database.

### 3.4 Independent Parallel Editing of the Same Base WordNet (Architectural Gap)

**Description:** The primary deployment scenario requires multiple pipelines to independently edit the same base WordNet (e.g., OEWN:2024) without interfering with each other's work. For example:
- Pipeline A: enriches synset definitions
- Pipeline B: adds new Arabic entries and senses
- Pipeline C: restructures relation hierarchies

Each pipeline needs an isolated workspace where its edits don't affect others until explicitly merged.

**Current design does not support this.** The gap is architectural — not a missing PRAGMA or index, but a missing capability:

**Approach 1 — Shared DB file: fundamentally broken.**
- SQLite's single-writer model means only one pipeline can write at a time.
- Even with `busy_timeout` and `BEGIN IMMEDIATE` fixes, all pipelines mutate the same rows. Pipeline A's definition edits are immediately visible to (and can conflict with) Pipeline C's relation restructuring.
- No isolation between workspaces: there is no concept of "my changes" vs "your changes."
- ID generation via `MAX(CAST(...))` creates collision risk even with serialized access if the delay between read and write spans a context switch.

**Approach 2 — Separate DB files per pipeline: works for isolation, no merge path.**
- Each pipeline calls `WordnetEditor.from_wn("oewn:2024", "pipeline_X.db")` to get an independent copy.
- Full isolation — no contention, no ID collisions, no interference.
- **Critical gap**: There is no mechanism to merge results back. `merge_synsets()` merges two synsets *within* the same database. There is no cross-database diff, merge, or reconciliation feature.
- After all pipelines finish, you have N divergent database files with no built-in way to combine them.

**Approach 3 — Same DB, override `lexicon_id` to create "branches": broken.** `[SPEC]` (D12)
- `from_wn()` accepts a `lexicon_id` override, but:
  - `from_wn()` always creates a *new* `WordnetEditor` (new DB file), so you can't add multiple "branches" to the same DB.
  - `_apply_overrides()` only updates the `lexicons.id` column — it does **not** rename child entity IDs (`synsets.id`, `entries.id`, `senses.id`), which are prefixed with the original lexicon ID (e.g., `oewn-00001234-n`). This creates a mismatch between the lexicon ID and its children's ID prefixes. **The design spec (`pipeline.md`) does not address this gap** — it describes `_apply_overrides()` changing the lexicon ID but is silent on child entity IDs.
  - Entity CRUD methods resolve lexicons by bare `id` — two lexicons with different IDs in the same DB would have separate namespaces, but relations between them are not supported by the import pipeline.

**What would be needed:**
- A **workspace/branching mechanism**: either separate DB files with a merge tool, or in-DB "branches" (e.g., via a `workspace_id` column or a shadow-table pattern).
- A **diff/merge capability**: compare two versions of a lexicon and reconcile additions, modifications, and deletions — with conflict detection for overlapping edits.
- A **conflict resolution strategy**: when two pipelines modify the same synset, which edit wins? Options: last-writer-wins, manual review, or pipeline-priority ordering.

**Impact:** This is the most significant gap between the stated requirements (multi-pipeline independent editing) and the current design (single-user, single-process, single-copy).

---

## 4. Design Assumptions Identified

### 4.1 Single-User, Single-Process Usage

The library was designed for single-user, single-process operation:
- No connection pooling
- No busy timeout
- No thread safety mechanisms
- No concurrent write handling
- No lock management

**Evidence:** Zero imports of `threading`, `multiprocessing`, or `concurrent.futures` across the entire codebase. No concurrency tests in the test suite. The `_modifies_db` decorator assumes exclusive access.

### 4.2 SQLite for Zero-Deployment Overhead

SQLite was chosen specifically to avoid database server infrastructure:
- Single-file database, portable
- No connection strings, no authentication
- Built into Python's standard library
- Suitable for embedding in a library (`pip install`)

**Trade-off:** This choice inherently limits concurrent write throughput to SQLite's single-writer model. For truly high-concurrency workloads, PostgreSQL or another client-server database would be more appropriate — but that would violate the zero-deployment goal.

### 4.3 WAL Mode Enabled But Not Tuned

WAL mode was correctly enabled for concurrent read support, but no additional tuning was applied:
- Default `wal_autocheckpoint` (1000 pages)
- Default `cache_size` (2MB)
- No `busy_timeout`
- No `synchronous` override
- No `mmap_size` for memory-mapped reads

**Evidence:** `db.connect()` sets exactly two PRAGMAs: `foreign_keys = ON` and `journal_mode = WAL`. All others use SQLite defaults.

### 4.5 Spec-to-Implementation Drift

Multiple design specifications are not faithfully implemented or contain incorrect assumptions about infrastructure behavior. This drift suggests the design documents were:
1. Written aspirationally (describing intent, not verified behavior)
2. Not validated against the implementation after coding was complete
3. Not cross-checked for internal consistency between documents

**Evidence of drift (7 confirmed divergences):**
- `architecture.md` claims SQLite blocking behavior that requires `busy_timeout` — which is never set (D2)
- `architecture.md` and `pipeline.md` specify different exception catch lists for the dual-path import — implementation matches neither (D1)
- `schema.md` describes a migration framework — implementation only does exact version match (D6)
- `schema.md` omits `UNIQUE(id, lexicon_rowid)` on senses — a constraint present on the two sibling tables (D3)
- `behavior.md` references `REVERSE_RELATIONS` — code uses `SYNSET_RELATION_INVERSES` (D4)
- `validation.md` miscounts its own rules — claims 17 WARNINGs, only 16 exist (D5)
- `pipeline.md` doesn't address entity ID re-prefixing when lexicon ID is overridden (D12)

**Implication for the audit:** The design documents cannot serve as a trusted reference for "expected behavior." Every spec claim must be independently verified against the implementation before it can be used as a correctness baseline.

### 4.6 Requirements Scope Contradiction `[REQ→SPEC]`

The most fundamental gap is not in the implementation but between the requirements:

- `docs/research/Architect onboarding.md` line 17: *"Targets **single-user batch editing** (no concurrency, no collaborative features)"*
- Business Objectives (Section 5 of `01-scope-and-objectives.md`): *"Multiple NLP agents simultaneously build and enrich Arabic WordNet entries"*

The library was designed to a single-user scope but is being deployed for multi-pipeline concurrent access. This requirements contradiction is the root cause of all concurrency-related findings (Pain Points #1, #7, #9 in `01-scope-and-objectives.md`).

### 4.4 WN-LMF 1.4 Compliance as Primary Goal

The schema is a direct mapping of the WN-LMF 1.4 (Linguistic Markup Framework) XML structure:
- `lexicons` ↔ `<Lexicon>`
- `synsets` ↔ `<Synset>`
- `entries` ↔ `<LexicalEntry>`
- `senses` ↔ `<Sense>`
- `forms` ↔ `<Form>` / `<Lemma>`
- `synset_relations` ↔ `<SynsetRelation>`
- Etc.

The schema prioritizes faithful representation of the WN-LMF data model over database performance optimization. This is appropriate for the library's primary purpose (WordNet editing and interchange) but may need supplementary indexes or structures for query-heavy pipeline use.

---

## 5. ID Generation Patterns

### 5.1 Synset ID Generation

**File:** `editor.py`, `_generate_synset_id()`

**Pattern:** Counter-based via `SELECT MAX(CAST(... AS INTEGER))`:
1. Query: `SELECT MAX(CAST(SUBSTR(id, ?) AS INTEGER)) FROM synsets WHERE lexicon_rowid = ?`
2. Extract numeric suffix from the pattern `{prefix}-{number}-{pos}`
3. Increment by 1
4. Format: `{lexicon_id}-{number:08d}-{pos}`

**Concurrency risk:** Two concurrent writers both read the same MAX value, both generate the same next ID, both try to INSERT → the second one gets `IntegrityError` (UNIQUE violation), which is **not caught or retried**.

### 5.2 Entry ID Generation

**File:** `editor.py`, `_generate_entry_id()`

**Pattern:** Suffix enumeration:
1. Base: `{lexicon_id}-{lemma}-{pos}`
2. If base exists: try `{base}-01`, `{base}-02`, etc.
3. For each candidate, check `SELECT rowid FROM entries WHERE id = ?`

**Concurrency risk:** Same TOCTOU — two writers can check the same suffix, both find it available, both try to INSERT.

### 5.3 Sense ID Generation

**File:** `editor.py`, `add_sense()`

**Pattern:** Derived from entry and synset:
1. `{entry_id}-{synset_id}-{suffix}` or similar convention
2. Uniqueness checked via `get_sense_rowid()` — application-level only

**Concurrency risk:** Same TOCTOU, compounded by the missing UNIQUE constraint on `senses(id, lexicon_rowid)`.

---

## 6. Developer Workflow Notes

### 6.1 Testing Approach

- 18 test files in `tests/` covering unit, integration, and validation scenarios
- All tests use `:memory:` databases (ephemeral, single-connection)
- No concurrency tests, no stress tests, no performance benchmarks
- Test fixtures create small datasets (typically 1-5 synsets/entries)
- Coverage is good for single-user correctness but does not validate multi-pipeline behavior

### 6.2 CI/CD Status

- `.github/workflows/ci.yml` exists but has known issues:
  - References `flit` commands but build system is `hatchling`
  - Runs `ruff check wn_editor/` (legacy path) instead of `src/wordnet_editor/`
  - Includes Python 3.9 in matrix but `requires-python >= 3.10`
- These CI issues are tracked separately in the legacy code cleanup plan

### 6.3 Development History

The library underwent a ground-up rewrite:
- **Era 1 (v0.6, Jan 2026):** Monolithic `wn_editor/editor.py` (2,032 lines), "ship first" approach
- **Era 2 (v1.0, Feb 2026):** Design-first rewrite to `src/wordnet_editor/`, decomposed into 8 modules (3,395+548+1,099+... lines)
- **Gap:** 2-week gap between eras, suggesting a deliberate decision to start over

The rewrite focused on correctness, modularity, and WN-LMF compliance. Performance optimization and concurrency were deprioritized in favor of getting the API right.
