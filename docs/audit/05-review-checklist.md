# Review Checklist / Rubric

**Project:** wn-editor-extended v1.0.0
**Date:** 2026-03-15
**Auditor:** *(name)*
**Status:** Pre-populated from codebase analysis; to be validated during audit

---

## Status Legend

| Status | Meaning |
|--------|---------|
| PASS | Meets best practices; no action needed |
| NOTE | Intentional design choice; documented and justified |
| WARNING | Suboptimal but not breaking; should be addressed |
| FAIL | Does not meet requirements; must be fixed before multi-pipeline deployment |
| *(blank)* | Not yet evaluated |

## Source Layer Tags

Every finding is tagged with the layer at which the flaw originates. A single finding may have multiple tags when both the spec and implementation are independently wrong.

| Tag | Meaning | Example |
|-----|---------|---------|
| `[IMPL]` | Implementation bug — code doesn't match expected behavior | Missing `record_update()` call in `update_entry` metadata path |
| `[SPEC]` | Design specification flaw — the spec itself is wrong or incomplete | `architecture.md` claims "second writer blocks" without `busy_timeout` |
| `[SPEC→IMPL]` | Spec violation — implementation deviates from what the spec prescribes | `except Exception` vs spec's `except (ImportError, AttributeError, ...)` |
| `[SPEC⟷SPEC]` | Internal inconsistency — design documents contradict each other | `pipeline.md` and `architecture.md` disagree on fallback exception list |
| `[REQ→SPEC]` | Requirements mismatch — requirements contradict the design scope | Onboarding doc says "single-user"; business objectives say "multi-pipeline" |

> **Philosophy:** Design documents are not treated as golden truth. They are audited artifacts — a flaw in the spec is as serious as a flaw in the code, because future developers and auditors will reference the spec as the intended behavior.

---

## 1. Normalization

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 1.1 | Tables in 3NF (no transitive dependencies) | PASS | `[IMPL]` | All tables are properly normalized. Lookup tables (`relation_types`, `ili_statuses`, `lexfiles`) correctly normalize repeated string values to integer rowids. | `db.py` DDL |
| 1.2 | Intentional denormalization documented and justified | NOTE | `[IMPL]` | `entry_index` table duplicates the lemma from `forms` (rank=0) for O(1) lookup by lemma text. This avoids a JOIN on the hot path `find_entries(lemma=...)`. Justified by query frequency. | `db.py` lines 133-138 |
| 1.3 | No data duplication without justification | PASS | `[IMPL]` | No other denormalization detected. `lexicon_rowid` is carried on child tables for direct cascade and export filtering — standard FK pattern, not duplication. | |

---

## 2. Naming Conventions

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 2.1 | Consistent table naming | PASS | `[IMPL]` | All tables use lowercase `snake_case` with plural nouns (e.g., `synsets`, `entries`, `sense_relations`). Junction tables use compound names (`syntactic_behaviour_senses`). | `db.py` DDL |
| 2.2 | Consistent column naming | PASS | `[IMPL]` | FK columns follow `{entity}_rowid` pattern (e.g., `synset_rowid`, `entry_rowid`). Business keys use `id`. Metadata columns use `metadata`. | |
| 2.3 | Singular vs plural consistency | PASS | `[IMPL]` | Tables are plural, columns are singular. No exceptions. | |
| 2.4 | Reserved word conflicts | PASS | `[IMPL]` | No column names conflict with SQL reserved words. `count` in `counts` table could conflict in some dialects but is fine in SQLite. | |

---

## 3. Data Types

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 3.1 | Appropriate types for all columns | WARNING | `[IMPL]` | `edit_history.timestamp` is `TEXT` (ISO 8601 string). While this works for string comparison (`>`, `<`), an `INTEGER` (Unix epoch) would be faster for range queries and sorting. | `db.py` line 329 |
| 3.2 | BOOLEAN columns use CHECK constraints | PASS | `[IMPL]` | Both `lexicons.modified` and `pronunciations.phonemic` have `CHECK(col IN (0, 1))`. | `db.py` DDL |
| 3.3 | Custom types documented | NOTE | `[IMPL]` | `META` column type is a custom JSON adapter/converter registered globally on `sqlite3`. 13 columns use it. The type name is opaque to external tools (e.g., `sqlite3` CLI shows raw JSON strings). | `db.py` lines 17-28 |
| 3.4 | TEXT vs INTEGER for IDs | NOTE | `[IMPL]` | All business IDs (`synset.id`, `entry.id`, `sense.id`, `ili.id`) are `TEXT`. This is correct for WN-LMF 1.4 compliance where IDs are structured strings (e.g., `oewn-01234567-n`). | |
| 3.5 | Nullable columns appropriate | PASS | `[IMPL]` | Only truly optional fields are nullable (e.g., `metadata`, `url`, `citation`, `definition` text). Required fields are `NOT NULL`. | |

---

## 4. Referential Integrity

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 4.1 | FKs defined for all relationships | WARNING | `[IMPL]` | `edit_history.entity_id` has no FK to any entity table. This is **by design** — the audit trail must survive entity deletion. However, it means `entity_id` can reference non-existent entities. | `db.py` lines 320-331 |
| 4.2 | ON DELETE behavior correct for all FKs | WARNING | `[IMPL]` | `lexicon_extensions.base_rowid` has **no ON DELETE clause** (SQLite default: RESTRICT). If a base lexicon is deleted while an extension references it, the FK constraint blocks the delete. This may be intentional (prevent orphaning extensions) but is not documented. | `db.py` lines 116-123 |
| 4.3 | ON DELETE behavior: `synsets.ili_rowid` | WARNING | `[IMPL]` | FK to `ilis(rowid)` has no ON DELETE clause (RESTRICT). Deleting an ILI that is still referenced by a synset will fail. The `unlink_ili()` method NULLs this column before ILI deletion, but a direct SQL `DELETE FROM ilis` would be blocked. | `db.py` line 149 |
| 4.4 | ON DELETE behavior: `relation_types` FKs | NOTE | `[IMPL]` | All 3 relation tables reference `relation_types(rowid)` with no ON DELETE (RESTRICT). This prevents deletion of relation types that are in use — correct behavior for a normalization table. | |
| 4.5 | PRAGMA foreign_keys always enabled | PASS | `[IMPL]` | `db.connect()` sets `PRAGMA foreign_keys = ON` on every connection. However, external connections (e.g., `sqlite3` CLI) that do not set this PRAGMA will bypass FK enforcement. | `db.py` line 342 |
| 4.6 | Cascade depth risk | WARNING | `[IMPL]` | A single `DELETE FROM lexicons WHERE rowid = ?` cascades across ~20 tables (entries→forms→pronunciations, entries→senses→relations, synsets→definitions, etc.). For a large lexicon (100K+ synsets), this is a very expensive single-statement operation. | `db.py` DDL |

---

## 5. Indexing

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 5.1 | All FK columns indexed | PASS | `[IMPL]` | Every FK column has an explicit index. 41 explicit indexes total. | `db.py` DDL, doc 02 §3 |
| 5.2 | Redundant indexes identified | WARNING | `[IMPL]` | 3 lookup tables (`relation_types`, `ili_statuses`, `lexfiles`) have both a UNIQUE constraint (which creates an implicit index) and an explicit index on the same column. The explicit indexes are redundant and waste space + insert time. | `db.py` DDL |
| 5.3 | Missing UNIQUE constraint on `senses(id, lexicon_rowid)` | **FAIL** | **`[SPEC]`** | Unlike `entries` (UNIQUE(id, lexicon_rowid)) and `synsets` (UNIQUE(id, lexicon_rowid)), the `senses` table has **no UNIQUE constraint** on `(id, lexicon_rowid)`. **This is a design-level omission (D3):** `schema.md` SCHEMA-024 also omits this constraint, while SCHEMA-003 (entries) and SCHEMA-010 (synsets) include it. The implementation correctly follows the flawed spec. Application-level guard: `get_sense_rowid()`. | `db.py` line 218, `schema.md` SCHEMA-024 |
| 5.4 | Missing FTS index for definition search | WARNING | `[IMPL]` | `find_synsets(definition_contains=...)` uses `LIKE '%...%'` which triggers a full table scan on `definitions`. An FTS5 virtual table would enable efficient full-text search. | `editor.py` `find_synsets` |
| 5.5 | Missing single-column index on `entries(lexicon_rowid)` | WARNING | `[IMPL]` | `find_entries(lexicon="...")` filters by `lexicon_rowid`. The composite UNIQUE on `(id, lexicon_rowid)` has `id` first, so it cannot efficiently serve queries that filter only by `lexicon_rowid`. | |
| 5.6 | Missing single-column index on `senses(lexicon_rowid)` | WARNING | `[IMPL]` | Same issue as 5.5 for `find_senses()` filtered by lexicon. | |
| 5.7 | Missing single-column index on `synsets(lexicon_rowid)` | WARNING | `[IMPL]` | Same issue for synsets; the composite UNIQUE has `id` first. The exporter's range scan `WHERE lexicon_rowid = ?` may not use the index efficiently. | |

---

## 6. Query Efficiency

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 6.1 | N+1 query patterns | **FAIL** | `[IMPL]` | **16 identified N+1 patterns** across `editor.py`, `importer.py`, and `exporter.py`. Most critical: `find_synsets()` issues 5N+1 queries (1 search + 5 per result via `_build_synset_model`). Export entry pipeline cascades to millions of queries for large lexicons. | doc 02 §6.4 |
| 6.2 | Full table scans on large tables | WARNING | `[IMPL]` | 6 identified full scans. Most are acceptable (tiny `lexicons` table), but `edit_history` (unbounded) and `definitions` (LIKE scan) are concerning. | doc 02 §6.5 |
| 6.3 | Complex JOINs appropriate | PASS | `[IMPL]` | Multi-table JOINs (up to 4 tables in `_build_sense_model`) all use indexed lookups. No Cartesian products, no unnecessary JOINs. | |
| 6.4 | Bulk operations use `executemany` | WARNING | `[IMPL]` | Import pipeline uses `executemany` for synsets, proposed_ilis, and unlexicalized_synsets — but NOT for entries, forms, senses, or relations. Entry import is a per-row loop with individual `execute()` calls. | `importer.py` lines 686-721 |
| 6.5 | Update operations batched | WARNING | `[IMPL]` | `update_lexicon()` issues one `UPDATE` per changed field instead of batching into a single `UPDATE ... SET field1=?, field2=?`. `reorder_senses()` issues one `UPDATE` per sense instead of using a `CASE WHEN` expression. | `editor.py` |
| 6.6 | Unnecessary re-reads after writes | WARNING | `[IMPL]` | `create_synset()`, `create_entry()`, `add_sense()`, and `update_*()` methods all call a `_build_*_model()` method at the end to return the created/updated model. This re-reads the data that was just written (3-5 extra queries per call). | `editor.py` |

---

## 7. Concurrency

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 7.1 | `busy_timeout` configured | **FAIL** | `[IMPL]` `[SPEC]` | Not set. Default is 0 ms — any lock contention immediately raises `sqlite3.OperationalError: database is locked`. No retry mechanism. **(D2):** `architecture.md`:11 falsely claims "the second writer blocks until the first commits" — this requires `busy_timeout`, which is never set. The design document gives false confidence. | `db.py` line 335-346, `architecture.md`:11 |
| 7.2 | Transaction type appropriate | **FAIL** | `[IMPL]` | All transactions use `DEFERRED` (SQLite default). For write operations, this creates a TOCTOU window: the check phase (e.g., duplicate ID check) and the write phase happen in the same deferred transaction, but two concurrent writers can both pass the check before either commits. `BEGIN IMMEDIATE` would acquire the write lock upfront. | `editor.py` line 128 |
| 7.3 | Thread safety | **FAIL** | `[IMPL]` | `sqlite3.connect()` is called without `check_same_thread=False`. The default (`True`) means a connection cannot be used from a thread other than the one that created it. No `threading.Lock` or `threading.local()` patterns exist. | `db.py` line 337 |
| 7.4 | `SQLITE_BUSY` error handling | **FAIL** | `[IMPL]` | No code catches `sqlite3.OperationalError` for "database is locked" errors. The only caught exception is `sqlite3.IntegrityError` (for idempotent relation inserts). An unhandled `SQLITE_BUSY` will propagate as an uncaught exception, crashing the pipeline. | Grep across `src/wordnet_editor/` |
| 7.5 | Write lock acquisition strategy | **FAIL** | `[IMPL]` | `batch()` uses explicit `BEGIN` (deferred). Under concurrent access, this risks `SQLITE_BUSY` after the first write. `BEGIN IMMEDIATE` would be safer for write-heavy operations. | `editor.py` line 128 |
| 7.6 | ID generation under concurrency | **FAIL** | `[IMPL]` | `_generate_synset_id()` uses `SELECT MAX(CAST(...))` to find the next numeric suffix. Two concurrent writers can both read the same MAX value and generate the same ID. The subsequent INSERT will fail with `IntegrityError` (UNIQUE violation), but this error is not caught or retried. | `editor.py` `_generate_synset_id` |
| 7.7 | WAL checkpoint management | WARNING | `[IMPL]` | No explicit checkpoint management. SQLite's default `wal_autocheckpoint` (1000 pages) is used. Under sustained multi-writer load, the WAL file can grow large between checkpoints. No monitoring or alerting. | |
| 7.8 | Connection isolation | PASS | `[IMPL]` | Each `WordnetEditor` instance owns its own `sqlite3.Connection`. No connection sharing between instances. | `editor.py` `__init__` |
| 7.9 | Independent parallel editing (workspace isolation) | **FAIL** | `[REQ→SPEC]` `[SPEC]` | The stated requirement is for multiple pipelines to independently edit the same base WordNet (e.g., OEWN:2024) without interfering with each other. **The architecture does not support this.** There is no branching, forking, or workspace mechanism. Shared-DB fails due to write contention and mutual interference. Separate-DB-per-pipeline provides isolation but has **no merge path** — `merge_synsets()` works within a single DB only, and there is no cross-database diff/merge/reconciliation. The `lexicon_id` override in `from_wn()` cannot create in-DB "branches" because it doesn't rename child entity IDs **(D12)** and `from_wn()` always creates a new DB. The root cause is a **requirements scope contradiction (D7):** the library was designed for "single-user batch editing" (`Architect onboarding.md`:17) but is deployed for multi-pipeline concurrent access. | `editor.py` `from_wn`, `merge_synsets`; `importer.py` `_apply_overrides`; `Architect onboarding.md`:17 |

---

## 8. Schema Evolution

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 8.1 | Schema versioning present | PASS | `[IMPL]` | `meta` table stores `schema_version = "1.0"`. Checked at connection time by `check_schema_version()`. | `db.py` lines 11, 370-386 |
| 8.2 | Version check is robust | WARNING | `[SPEC→IMPL]` | Uses exact string equality (`!=`), not semantic versioning. Version `"1.0"` is incompatible with `"1.0.1"` or `"1.1"`. Missing `meta` table is silently ignored (`OperationalError` caught). Missing `schema_version` key returns without error. **(D6):** `schema.md` section 2.6 describes compatible migration paths (additive changes, ALTER TABLE), but the implementation only does exact version match — no migration framework exists. | `db.py` `check_schema_version`, `schema.md` §2.6 |
| 8.3 | Migration framework | WARNING | `[SPEC→IMPL]` | No migration framework exists despite the spec describing one (D6). If the schema changes (e.g., adding `UNIQUE(id, lexicon_rowid)` to `senses`), there is no automated migration path. The only option is manual `ALTER TABLE` or recreate the database. | `schema.md` §2.6 |
| 8.4 | `init_db()` is idempotent | PASS | `[IMPL]` | All DDL uses `CREATE TABLE IF NOT EXISTS` and `CREATE INDEX IF NOT EXISTS`. Seed data uses `INSERT OR IGNORE`. Safe to call on existing databases. | `db.py` `init_db` |
| 8.5 | `executescript()` implicit COMMIT | WARNING | `[IMPL]` | `init_db()` uses `conn.executescript(_DDL)` which issues an implicit COMMIT before running (D9). If called inside an active transaction, that transaction is silently committed. | `db.py` line 351 |

---

## 9. History / Audit Trail

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 9.1 | All mutations recorded | WARNING | `[IMPL]` | Almost all mutations record history via `record_create/update/delete()`. **Gap found (D11):** `update_entry()` metadata update path (lines 880-884 in `editor.py`) does not call `_hist.record_update()`. Entry metadata changes are silently untracked. `behavior.md` specifies that all mutations are tracked — this is a spec violation. | `editor.py`, `history.py`, `behavior.md` |
| 9.2 | History is queryable | PASS | `[IMPL]` | Indexed by `(entity_type, entity_id)` for entity-scoped queries and by `timestamp` for time-range queries. `query_history()` supports filters on entity_type, entity_id, operation, and since (timestamp). | `history.py` `query_history` |
| 9.3 | History table bounded | **FAIL** | `[IMPL]` | No rotation, no archiving, no partition, no TTL. `edit_history` grows unboundedly with every mutation. `query_history()` with no filters does a full table scan with no LIMIT. For a database with millions of edits over time, history queries will degrade significantly. | |
| 9.4 | User/session attribution | **FAIL** | **`[SPEC]`** | No `user_id`, `session_id`, `pipeline_id`, or `source` field in `edit_history`. In a multi-pipeline environment, there is no way to distinguish which pipeline made which change. All mutations are anonymous. **(D10):** `architecture.md` section 1.9 explicitly acknowledges this as design debt: *"Consider adding a session_id column to edit_history in a future schema migration."* The debt was accepted at design time but not scheduled for resolution before multi-pipeline deployment. | `db.py` line 320-331, `architecture.md` §1.9 |
| 9.5 | History survives entity deletion | PASS | `[IMPL]` | `edit_history` has no foreign keys to entity tables. `entity_id` is TEXT, not a FK rowid. Deleting an entity preserves its full change history. | |
| 9.6 | Timestamp reliability | PASS | `[IMPL]` | Timestamps use `strftime('%Y-%m-%dT%H:%M:%f', 'now')` — generated by SQLite (not Python), so they are consistent within a transaction and use UTC. Millisecond resolution. | `db.py` line 329 |
| 9.7 | Value serialization | PASS | `[IMPL]` | `old_value` and `new_value` are JSON-encoded via `json.dumps()`. Scalar values are properly wrapped (e.g., POS `"n"` stored as `'"n"'`). Complex values (metadata dicts) are full JSON objects. | `history.py` |

---

## 10. Security

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 10.1 | SQL injection prevention | PASS | `[IMPL]` | All queries use parameterized `?` placeholders. Dynamic table/column names are sourced from internal code dictionaries, not user input. | All source files |
| 10.2 | No sensitive data exposure | PASS | `[IMPL]` | No passwords, API keys, or PII stored in schema. `email` field in `lexicons` contains maintainer contact (public metadata). | |
| 10.3 | File permissions | NOTE | `[IMPL]` | SQLite relies on OS file permissions for access control. No built-in authentication or encryption. In a multi-pipeline environment, all pipelines with file access have full read/write/delete capability. | |

---

## 11. Data Import/Export Integrity

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 11.1 | Import is atomic | PASS | `[IMPL]` | `_import_resource()` wraps all lexicon imports in `with conn:` — a single transaction. Failure at any point rolls back the entire import. | `importer.py` line 491 |
| 11.2 | Import override anomaly | WARNING | `[IMPL]` | `_apply_overrides()` calls `conn.commit()` directly (line 1098), bypassing the transaction wrapper (D8). This can prematurely commit a partially-imported lexicon if overrides are applied within the import transaction. The spec (`pipeline.md`) is silent on transaction boundaries for overrides — this is an unguided implementation choice. | `importer.py` line 1098 |
| 11.3 | Export data loss warnings | PASS | `[IMPL]` | `_warn_data_loss()` checks for non-exportable data (lexfile assignments, counts) and issues warnings. Uses efficient `LIMIT 1` existence checks. | `exporter.py` |
| 11.4 | Round-trip fidelity | NOTE | `[IMPL]` | Not verified by automated tests. Manual comparison needed to confirm that `import → export → import` preserves all data without loss or mutation. | |
| 11.5 | Bulk import uses `executemany` | WARNING | `[IMPL]` | Only synsets, proposed_ilis, and unlexicalized_synsets use `executemany`. Entries, forms, senses, and relations use individual `execute()` calls in a loop — significantly slower for large imports. | `importer.py` |
| 11.6 | `except Exception` catch-all masks semantic errors | **FAIL** | **`[SPEC→IMPL]`** **`[SPEC⟷SPEC]`** | **(D1):** `import_from_wn()` wraps `_import_from_wn_bulk()` in `except Exception` (line 50). **The spec says narrow catch:** `architecture.md` §1.8 specifies `except (ImportError, AttributeError, sqlite3.OperationalError)`; `pipeline.md` §6.2 specifies only `(ImportError, AttributeError)` — **the two specs disagree**, and the implementation matches neither. The broad `except Exception` catches `DuplicateEntityError` — a semantic error meaning "this lexicon already exists." When `from_wn()` is called twice, the bulk path raises `DuplicateEntityError`, the catch-all swallows it, the XML fallback runs (wasting 10-30s), then raises the same error. **Severity upgraded to FAIL** because this is a spec violation with user-visible impact. | `importer.py` lines 48-51, `architecture.md` §1.8, `pipeline.md` §6.2 |

---

## 12. Spec Fidelity (Design Document Accuracy)

These findings assess the design specification documents themselves — not just the implementation's compliance with them.

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 12.1 | SQLite locking claims accurate | **FAIL** | `[SPEC]` | **(D2):** `architecture.md`:11 claims: *"If two processes open the same `editor.db`, SQLite's file-level locking ensures writes are serialized (the second writer blocks until the first commits)."* This is **factually incorrect**. Without `busy_timeout` (which is not set), the second writer gets an immediate `SQLITE_BUSY` error. The design doc creates false confidence about concurrent safety. | `architecture.md`:11, `db.py` lines 335-346 |
| 12.2 | `senses` UNIQUE specified in schema spec | **FAIL** | `[SPEC]` | **(D3):** `schema.md` SCHEMA-024 defines `senses` table WITHOUT `UNIQUE(id, lexicon_rowid)`, while SCHEMA-003 (`entries`) and SCHEMA-010 (`synsets`) both include this constraint. The implementation correctly follows the flawed spec. Fixing only the code leaves the spec as a source of future bugs. | `schema.md` SCHEMA-024 vs SCHEMA-003, SCHEMA-010 |
| 12.3 | Dual-path fallback spec consistent across docs | **FAIL** | `[SPEC⟷SPEC]` | **(D1b):** `architecture.md` §1.8 says `except (ImportError, AttributeError, sqlite3.OperationalError)`. `pipeline.md` §6.2 says only `(ImportError, AttributeError)`. Two documents, two different exception lists for the same feature. | `architecture.md` §1.8, `pipeline.md` §6.2 |
| 12.4 | Naming consistency between spec and code | **FAIL** | `[SPEC⟷SPEC]` | **(D4):** `behavior.md` references `REVERSE_RELATIONS` dict. `relations.py` uses `SYNSET_RELATION_INVERSES` and `SENSE_RELATION_INVERSES`. The spec was never updated to match the implementation naming or vice versa. | `behavior.md`, `relations.py` |
| 12.5 | Validation rule count accurate | **FAIL** | `[SPEC]` | **(D5):** `validation.md` claims 6 ERROR rules and 17 WARNING rules (23 total). Manual enumeration yields only 16 WARNING rules. The off-by-one indicates the spec was not self-validated. | `validation.md` |
| 12.6 | Migration strategy implemented as specified | **FAIL** | `[SPEC→IMPL]` | **(D6):** `schema.md` §2.6 describes compatible migration paths (additive changes, `ALTER TABLE`, etc.). `db.py` `check_schema_version()` only does exact string match (`version != SCHEMA_VERSION`). No migration framework, no semantic version comparison. The spec promised a capability the implementation does not provide. | `schema.md` §2.6, `db.py` `check_schema_version` |
| 12.7 | Entity ID re-prefixing addressed in spec | **FAIL** | `[SPEC]` | **(D12):** `pipeline.md` describes `_apply_overrides()` changing `lexicon_id` but is **silent on child entity IDs**. Entity IDs (e.g., `oewn-00001234-n`) embed the source lexicon name and are imported verbatim. After override, the lexicon ID and entity ID prefixes are mismatched — a namespace inconsistency that the spec doesn't acknowledge. | `pipeline.md`, `importer.py` lines 636-658, 1094-1098 |
| 12.8 | `edit_history` session attribution planned | WARNING | `[SPEC]` | **(D10):** `architecture.md` §1.9 explicitly acknowledges the need for a `session_id` column in `edit_history` as future work. This design debt was accepted at v1.0 but is now blocking for the multi-pipeline deployment target. | `architecture.md` §1.9 |

---

## 13. Requirements Alignment

| # | Check | Status | Layer | Finding | Source |
|---|-------|--------|-------|---------|--------|
| 13.1 | Design scope matches deployment requirements | **FAIL** | `[REQ→SPEC]` | **(D7):** `docs/research/Architect onboarding.md`:17 defines scope as: *"Targets **single-user batch editing** (no concurrency, no collaborative features)."* Business objectives (doc 01 §5) require: *"Multiple NLP agents simultaneously build and enrich Arabic WordNet entries."* These are contradictory. The library was designed to a single-user scope but is being deployed for multi-pipeline concurrent access. This mismatch is the **root cause** of all concurrency-related findings (7.1–7.9). | `Architect onboarding.md`:17, doc 01 §5 |

---

## Summary by Severity

### FAIL (Must Fix Before Multi-Pipeline Deployment)

| # | Issue | Category | Layer |
|---|-------|----------|-------|
| 5.3 | Missing UNIQUE on `senses(id, lexicon_rowid)` — **spec also omits it (D3)** | Indexing | `[SPEC]` |
| 6.1 | 16 N+1 query patterns | Query Efficiency | `[IMPL]` |
| 7.1 | No `busy_timeout` — **spec falsely claims blocking behavior (D2)** | Concurrency | `[IMPL]` `[SPEC]` |
| 7.2 | DEFERRED transactions (TOCTOU risk) | Concurrency | `[IMPL]` |
| 7.3 | No thread safety | Concurrency | `[IMPL]` |
| 7.4 | No `SQLITE_BUSY` error handling | Concurrency | `[IMPL]` |
| 7.5 | No `BEGIN IMMEDIATE` for writes | Concurrency | `[IMPL]` |
| 7.6 | ID generation race condition | Concurrency | `[IMPL]` |
| 7.9 | No workspace isolation / branching / cross-DB merge — **root cause: requirements scope contradiction (D7)** | Architecture | `[REQ→SPEC]` |
| 9.3 | Unbounded `edit_history` | Audit Trail | `[IMPL]` |
| 9.4 | No user/session attribution — **acknowledged design debt (D10)** | Audit Trail | `[SPEC]` |
| 11.6 | `except Exception` catch-all — **spec says narrow catch (D1), specs disagree (D1b)** | Import Error Handling | `[SPEC→IMPL]` `[SPEC⟷SPEC]` |
| 12.1 | SQLite locking claim factually incorrect (D2) | Spec Fidelity | `[SPEC]` |
| 12.2 | `senses` UNIQUE omitted from spec (D3) | Spec Fidelity | `[SPEC]` |
| 12.3 | Dual-path specs contradict each other (D1b) | Spec Fidelity | `[SPEC⟷SPEC]` |
| 12.4 | Spec naming doesn't match code (D4) | Spec Fidelity | `[SPEC⟷SPEC]` |
| 12.5 | Validation rule count wrong (D5) | Spec Fidelity | `[SPEC]` |
| 12.6 | Migration strategy spec not implemented (D6) | Spec Fidelity | `[SPEC→IMPL]` |
| 12.7 | Entity ID re-prefixing not addressed in spec (D12) | Spec Fidelity | `[SPEC]` |
| 13.1 | Requirements scope contradiction — single-user design vs multi-pipeline deployment (D7) | Requirements | `[REQ→SPEC]` |

### WARNING (Should Fix)

| # | Issue | Category | Layer |
|---|-------|----------|-------|
| 3.1 | `timestamp` as TEXT instead of INTEGER | Data Types | `[IMPL]` |
| 4.1 | `edit_history.entity_id` has no FK | Referential Integrity | `[IMPL]` |
| 4.2 | `lexicon_extensions.base_rowid` RESTRICT behavior | Referential Integrity | `[IMPL]` |
| 4.6 | Cascade deletion cost for large lexicons | Referential Integrity | `[IMPL]` |
| 5.2 | 3 redundant indexes on lookup tables | Indexing | `[IMPL]` |
| 5.4 | Missing FTS5 for definition search | Indexing | `[IMPL]` |
| 5.5-5.7 | Missing single-column `lexicon_rowid` indexes | Indexing | `[IMPL]` |
| 6.2 | Full table scans on `edit_history` and `definitions` | Query Efficiency | `[IMPL]` |
| 6.4 | Entry import not using `executemany` | Query Efficiency | `[IMPL]` |
| 6.5 | Multiple UPDATEs instead of batched | Query Efficiency | `[IMPL]` |
| 6.6 | Unnecessary re-reads after writes | Query Efficiency | `[IMPL]` |
| 7.7 | No WAL checkpoint management | Concurrency | `[IMPL]` |
| 8.2 | Exact string version matching — **spec describes migrations (D6)** | Schema Evolution | `[SPEC→IMPL]` |
| 8.3 | No migration framework — **spec describes one (D6)** | Schema Evolution | `[SPEC→IMPL]` |
| 8.5 | `executescript()` implicit COMMIT (D9) | Schema Evolution | `[IMPL]` |
| 9.1 | Missing history for entry metadata updates (D11) | Audit Trail | `[IMPL]` |
| 11.2 | Bare `conn.commit()` in `_apply_overrides` (D8) | Import Integrity | `[IMPL]` |
| 11.5 | Entry import not bulk-optimized | Import Performance | `[IMPL]` |
| 12.8 | `edit_history` session attribution planned but unscheduled (D10) | Spec Fidelity | `[SPEC]` |

### Summary by Source Layer

| Layer | FAIL | WARNING | Total |
|-------|------|---------|-------|
| `[IMPL]` — Implementation bug | 8 | 15 | 23 |
| `[SPEC]` — Design spec flaw | 7 | 1 | 8 |
| `[SPEC→IMPL]` — Spec violation | 3 | 2 | 5 |
| `[SPEC⟷SPEC]` — Internal inconsistency | 3 | 0 | 3 |
| `[REQ→SPEC]` — Requirements mismatch | 2 | 0 | 2 |

> **Note:** Some findings carry multiple tags (e.g., 7.1 is both `[IMPL]` and `[SPEC]`), so totals exceed the distinct finding count.
