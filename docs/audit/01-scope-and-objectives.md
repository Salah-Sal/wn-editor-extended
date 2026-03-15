# Audit Scope & Objectives

**Project:** wn-editor-extended v1.0.0
**Date:** 2026-03-15
**Prepared by:** DBA / Engineering Team
**Status:** Pre-Audit

---

## 1. Databases in Scope

| Database | Engine | Location | Purpose |
|----------|--------|----------|---------|
| WordNet Editor DB | SQLite 3.x (WAL mode) | User-specified path (e.g., `awn4.db`) | Primary data store for all WordNet CRUD, import, export, and audit operations |

The editor database is created by `WordnetEditor.__init__()` via `db.init_db()`, which runs the full DDL (`_DDL` in `src/wordnet_editor/db.py`) and seeds lookup tables.

## 2. Schemas in Scope

All **24 tables** defined in `db.py` lines 35-332:

### Core Entity Tables
- `lexicons` — WordNet resource containers (language, version, license)
- `entries` — Lexical entries (word + POS)
- `forms` — Written forms of entries (lemma at rank 0, variants at rank >= 1)
- `synsets` — Synonym sets representing concepts
- `senses` — Links entries to synsets (the central junction)

### Relation Tables
- `synset_relations` — Directed typed relations between synsets (hypernymy, etc.)
- `sense_relations` — Directed typed relations between senses
- `sense_synset_relations` — Directed typed relations from senses to synsets

### Annotation Tables
- `definitions` — Textual definitions for synsets
- `synset_examples` — Usage examples for synsets
- `sense_examples` — Usage examples for senses
- `counts` — Frequency counts for senses
- `pronunciations` — Pronunciation data for forms
- `tags` — Categorized tags for forms
- `adjpositions` — Adjective syntactic positions for senses

### Lookup / Normalization Tables
- `relation_types` — Normalizes relation type strings to integer rowids
- `ili_statuses` — Normalizes ILI status strings (`active`, `presupposed`, `deprecated`)
- `lexfiles` — Normalizes lexicographer file names

### Infrastructure Tables
- `meta` — Key-value store (schema version, creation timestamp)
- `ilis` — Interlingual Index entries
- `proposed_ilis` — Proposed ILI entries awaiting approval
- `entry_index` — Fast lemma lookup (denormalized from `forms`)
- `unlexicalized_synsets` — Marker table for synsets with no senses
- `unlexicalized_senses` — Marker table for unlexicalized senses

### Junction Tables
- `lexicon_dependencies` — Tracks `<Requires>` relationships between lexicons
- `lexicon_extensions` — Tracks `<Extends>` relationships
- `syntactic_behaviours` — Subcategorization frames for verbs
- `syntactic_behaviour_senses` — M:N junction between frames and senses

### Audit Table
- `edit_history` — Field-level audit log of all CREATE/UPDATE/DELETE mutations

### Design Documents in Scope

The audit also reviews the design specification documents for accuracy, internal consistency, and fidelity to the implementation:

| Document | File | Audit Focus |
|----------|------|-------------|
| Architecture | `docs/design/architecture.md` | System overview claims, design rationale accuracy, SQLite behavior assumptions |
| Schema | `docs/design/schema.md` | DDL specification accuracy, constraint completeness, migration strategy |
| Pipeline | `docs/design/pipeline.md` | Import/export pipeline specification, exception handling contracts |
| Behavior | `docs/design/behavior.md` | Behavioral rule accuracy, naming consistency with implementation |
| Validation | `docs/design/validation.md` | Rule catalog accuracy, severity counts |

> **Rationale:** Design documents are not treated as golden truth. They are artifacts subject to the same audit scrutiny as the implementation. Findings are classified by source layer — a flaw may exist in the spec, the implementation, or both.

## 3. Out of Scope

| Item | Reason |
|------|--------|
| `wn` library's internal SQLite database | Read-only source for import; managed by the external `wn` package |
| Test `:memory:` databases | Ephemeral; no persistence or production relevance |
| Legacy `wn_editor/` package | Deprecated v0.6 code; untracked, scheduled for deletion |
| `arabic-wordnet-v4/` apply_reviews.py | External consumer; no longer in active use |

## 4. Performance Targets (Multi-Pipeline Deployment)

The library will serve as the backend for **automated NLP pipelines** that create, import, edit, and export Arabic WordNets. Multiple pipelines may operate concurrently against a shared database file.

| Operation | Target | Measurement Method |
|-----------|--------|--------------------|
| Single synset CRUD (create/read/update/delete) | < 10 ms | `time.perf_counter()` around individual method calls |
| `find_synsets()` with filters (POS, lexicon) on 120K-synset DB | < 500 ms | Wall clock including model building |
| `find_synsets(definition_contains=...)` on 120K-synset DB | < 2 s | Full scan case — document as known slow path |
| Full lexicon import (100K synsets, ~150K entries) | < 60 s | `WordnetEditor.from_wn()` end-to-end |
| Full lexicon export to XML | < 30 s | `export_xml()` end-to-end |
| `batch()` throughput (1000 synset creates) | > 500 ops/s | Operations per second within a batch context |
| Concurrent readers | Unlimited | WAL mode guarantees non-blocking reads |
| Concurrent writers (graceful contention) | >= 4 pipelines | No unhandled `SQLITE_BUSY` errors; retry with backoff |
| `get_history()` with filters | < 100 ms | Indexed lookup by `(entity_type, entity_id)` |
| Database vacuum / integrity check | < 30 s | `PRAGMA integrity_check`, `VACUUM` |

### Latency SLA Summary

- **P95 single-operation latency**: < 50 ms (excluding import/export bulk operations)
- **Import throughput**: > 2,000 synsets/second sustained
- **Export throughput**: > 5,000 synsets/second sustained

## 5. Business Objectives

1. **Multi-pipeline WordNet construction**: Multiple NLP agents simultaneously build and enrich Arabic WordNet entries, each operating on different synset ranges or lexicons
2. **Data integrity under concurrency**: No silent data loss, no orphaned entities, no duplicate IDs when pipelines race on overlapping entities
3. **Auditability**: Complete change history with timestamps for every mutation, queryable for pipeline provenance tracking
4. **Portability**: Single-file SQLite database that can be copied, backed up, or shared across environments without server infrastructure
5. **Import/export fidelity**: Round-trip WordNet data through WN-LMF 1.4 XML without data loss

> **Design Gap Notice:** The current architecture was designed for single-user, single-process operation (see Pain Point #9). Objectives 1 and 2 above **cannot be met by the current design** — not through configuration changes (PRAGMAs, indexes) alone, but because the library lacks fundamental capabilities: workspace isolation (branching), cross-database merge/diff, and conflict resolution. Remediation requires architectural changes to the library, not just performance tuning.

## 6. Known Pain Points (Pre-Audit)

These issues have been identified through codebase analysis and are expected to be confirmed/quantified during the audit:

| # | Pain Point | Severity | Source |
|---|-----------|----------|--------|
| 1 | **Zero concurrency protection** — no `busy_timeout`, no `BEGIN IMMEDIATE`, no thread safety, no `SQLITE_BUSY` handling | CRITICAL | `db.py` line 335-346, `editor.py` line 128 |
| 2 | **Pervasive N+1 query patterns** — `find_synsets()` issues 5N+1 queries; export entry pipeline cascades to millions | HIGH | `editor.py` `_build_synset_model`, `exporter.py` `_build_entry` |
| 3 | **`senses.id` missing UNIQUE constraint** — uniqueness enforced only at app level | HIGH | `db.py` DDL vs `entries` table which has `UNIQUE(id, lexicon_rowid)` |
| 4 | **Unbounded `edit_history`** — no rotation, no partition, no LIMIT on queries | MEDIUM | `db.py` line 320-331, `history.py` `query_history` |
| 5 | **Bare `conn.commit()` in importer** — `_apply_overrides()` commits outside transaction wrapper | MEDIUM | `importer.py` line 1098 |
| 6 | **Full-text search via LIKE** — `definition_contains` filter uses `LIKE '%...%'` with no FTS index | MEDIUM | `editor.py` `find_synsets` |
| 7 | **ID generation race conditions** — `MAX(CAST(...))` pattern not safe under concurrent writers | HIGH | `editor.py` `_generate_synset_id`, `_generate_entry_id` |
| 8 | **Cascade deletion cost** — deleting a lexicon triggers cascades across ~20 tables | LOW | `db.py` DDL, all ON DELETE CASCADE FKs |
| 9 | **No workspace isolation or branching** — the architecture cannot support multiple pipelines independently editing the same base WordNet. No branching, no cross-database merge, no diff/reconciliation. Shared-DB fails due to mutual interference; separate-DB-per-pipeline has no merge path. This is a **design-level gap**, not a missing configuration. | CRITICAL | `editor.py` `from_wn`, `merge_synsets`; `importer.py` `_apply_overrides` |
| 10 | **Design document inaccuracies** — specs contain incorrect claims (SQLite locking behavior), omit critical constraints (`senses` UNIQUE), and internally contradict each other (exception catch lists between `architecture.md` and `pipeline.md`). Design docs cannot be trusted as a reference without independent verification against the implementation. | HIGH | `architecture.md`:11, `schema.md` SCHEMA-024, `pipeline.md` §6.2 vs `architecture.md` §1.8 |
| 11 | **Requirements scope contradiction** — the design onboarding document defines single-user scope ("Targets single-user batch editing, no concurrency, no collaborative features"), while Section 5 business objectives require multi-pipeline concurrent access. The library was designed to a scope that contradicts its deployment requirements. | CRITICAL | `docs/research/Architect onboarding.md`:17 vs Section 5 objectives above |

## 7. Audit Deliverables

Upon completion of the schema review + performance audit, the following deliverables are expected:

1. **Audit Report** — Findings organized by category (normalization, integrity, indexing, concurrency, performance), each with severity, evidence, and recommendation
2. **Remediation Plan** — Prioritized action items with effort estimates, grouped into:
   - P0 (Must-fix before multi-pipeline deployment): Concurrency, UNIQUE constraints, ID generation
   - P1 (Should-fix): N+1 patterns, FTS, history rotation
   - P2 (Nice-to-have): Redundant indexes, timestamp type, migration framework
3. **Updated Baseline Metrics** — Re-run of `run_baseline.py` after P0 remediation to measure improvement
4. **Concurrency Test Suite** — New test file(s) exercising multi-writer, multi-reader, and contention scenarios
