# Database Schema Specification

**Library**: `wordnet-editor`
**Version**: 2.0
**Date**: 2026-03-15

This document defines the complete SQLite schema for the editor's independent database. A developer can produce the full DDL from this spec alone.

---

## 2.1 — Complete DDL

### Connection PRAGMAs

Set on every connection by `db.connect()` (not part of the DDL string):

```python
conn.execute("PRAGMA foreign_keys = ON")
conn.execute("PRAGMA busy_timeout = 5000")
conn.execute("PRAGMA journal_mode = WAL")   # file-backed databases only
```

### DDL (verbatim from `db.py` `_DDL`)

```sql
-- Meta table
CREATE TABLE IF NOT EXISTS meta (
    key TEXT NOT NULL,
    value TEXT,
    UNIQUE (key)
);

-- Lookup tables
CREATE TABLE IF NOT EXISTS relation_types (
    rowid INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    UNIQUE (type)
);

CREATE TABLE IF NOT EXISTS lexfiles (
    rowid INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    UNIQUE (name)
);

-- ILI table
CREATE TABLE IF NOT EXISTS ilis (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    status TEXT NOT NULL DEFAULT 'presupposed'
        CHECK( status IN ('active', 'presupposed', 'deprecated') ),
    definition TEXT,
    metadata META,
    UNIQUE (id)
);

-- Lexicon tables
CREATE TABLE IF NOT EXISTS lexicons (
    rowid INTEGER PRIMARY KEY,
    specifier TEXT NOT NULL,
    id TEXT NOT NULL,
    label TEXT NOT NULL,
    language TEXT NOT NULL,
    email TEXT NOT NULL,
    license TEXT NOT NULL,
    version TEXT NOT NULL,
    url TEXT,
    citation TEXT,
    logo TEXT,
    metadata META,
    modified BOOLEAN CHECK( modified IN (0, 1) ) DEFAULT 0 NOT NULL,
    UNIQUE (id, version),
    UNIQUE (specifier)
);
CREATE INDEX IF NOT EXISTS lexicon_specifier_index ON lexicons (specifier);

CREATE TABLE IF NOT EXISTS lexicon_dependencies (
    dependent_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    provider_id TEXT NOT NULL,
    provider_version TEXT NOT NULL,
    provider_url TEXT,
    provider_rowid INTEGER REFERENCES lexicons (rowid) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS lexicon_dependent_index ON lexicon_dependencies(dependent_rowid);

CREATE TABLE IF NOT EXISTS lexicon_extensions (
    extension_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    base_id TEXT NOT NULL,
    base_version TEXT NOT NULL,
    base_url TEXT,
    base_rowid INTEGER REFERENCES lexicons (rowid),
    UNIQUE (extension_rowid, base_rowid)
);
CREATE INDEX IF NOT EXISTS lexicon_extension_index ON lexicon_extensions(extension_rowid);

-- Entry tables
CREATE TABLE IF NOT EXISTS entries (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    pos TEXT NOT NULL,
    lemma TEXT NOT NULL DEFAULT '',
    metadata META,
    UNIQUE (id, lexicon_rowid)
);
CREATE INDEX IF NOT EXISTS entry_id_index ON entries (id);
CREATE INDEX IF NOT EXISTS entry_lemma_index ON entries (lemma);

CREATE TABLE IF NOT EXISTS forms (
    rowid INTEGER PRIMARY KEY,
    id TEXT,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    entry_rowid INTEGER NOT NULL REFERENCES entries(rowid) ON DELETE CASCADE,
    form TEXT NOT NULL,
    normalized_form TEXT,
    script TEXT,
    rank INTEGER DEFAULT 1,
    UNIQUE (entry_rowid, form, script)
);
CREATE INDEX IF NOT EXISTS form_entry_index ON forms (entry_rowid);
CREATE INDEX IF NOT EXISTS form_index ON forms (form);
CREATE INDEX IF NOT EXISTS form_norm_index ON forms (normalized_form);

CREATE TABLE IF NOT EXISTS pronunciations (
    form_rowid INTEGER NOT NULL REFERENCES forms (rowid) ON DELETE CASCADE,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    value TEXT,
    variety TEXT,
    notation TEXT,
    phonemic BOOLEAN CHECK( phonemic IN (0, 1) ) DEFAULT 1 NOT NULL,
    audio TEXT
);
CREATE INDEX IF NOT EXISTS pronunciation_form_index ON pronunciations (form_rowid);

CREATE TABLE IF NOT EXISTS tags (
    form_rowid INTEGER NOT NULL REFERENCES forms (rowid) ON DELETE CASCADE,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    tag TEXT,
    category TEXT
);
CREATE INDEX IF NOT EXISTS tag_form_index ON tags (form_rowid);

-- Synset tables
CREATE TABLE IF NOT EXISTS synsets (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    ili_rowid INTEGER REFERENCES ilis (rowid),
    pos TEXT,
    lexfile_rowid INTEGER REFERENCES lexfiles (rowid),
    lexicalized BOOLEAN NOT NULL DEFAULT 1,
    proposed_ili_definition TEXT,
    proposed_ili_metadata META,
    metadata META,
    UNIQUE (id, lexicon_rowid)
);
CREATE INDEX IF NOT EXISTS synset_id_index ON synsets (id);
CREATE INDEX IF NOT EXISTS synset_ili_rowid_index ON synsets (ili_rowid);

CREATE TABLE IF NOT EXISTS synset_relations (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    source_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    target_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    type_rowid INTEGER NOT NULL REFERENCES relation_types(rowid),
    metadata META,
    UNIQUE (source_rowid, target_rowid, type_rowid)
);
CREATE INDEX IF NOT EXISTS synset_relation_source_index ON synset_relations (source_rowid);
CREATE INDEX IF NOT EXISTS synset_relation_target_index ON synset_relations (target_rowid);

CREATE TABLE IF NOT EXISTS definitions (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    synset_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    definition TEXT,
    language TEXT,
    sense_rowid INTEGER REFERENCES senses(rowid) ON DELETE SET NULL,
    metadata META
);
CREATE INDEX IF NOT EXISTS definition_rowid_index ON definitions (synset_rowid);
CREATE INDEX IF NOT EXISTS definition_sense_index ON definitions (sense_rowid);

CREATE TABLE IF NOT EXISTS synset_examples (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    synset_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    example TEXT,
    language TEXT,
    metadata META
);
CREATE INDEX IF NOT EXISTS synset_example_rowid_index ON synset_examples(synset_rowid);

-- Sense tables
CREATE TABLE IF NOT EXISTS senses (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    entry_rowid INTEGER NOT NULL REFERENCES entries(rowid) ON DELETE CASCADE,
    entry_rank INTEGER DEFAULT 1,
    synset_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    synset_rank INTEGER DEFAULT 1,
    lexicalized BOOLEAN NOT NULL DEFAULT 1,
    adjposition TEXT,
    metadata META,
    UNIQUE (id, lexicon_rowid)
);
CREATE INDEX IF NOT EXISTS sense_id_index ON senses(id);
CREATE INDEX IF NOT EXISTS sense_entry_rowid_index ON senses (entry_rowid);
CREATE INDEX IF NOT EXISTS sense_synset_rowid_index ON senses (synset_rowid);

CREATE TABLE IF NOT EXISTS sense_relations (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    source_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    target_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    type_rowid INTEGER NOT NULL REFERENCES relation_types(rowid),
    metadata META,
    UNIQUE (source_rowid, target_rowid, type_rowid)
);
CREATE INDEX IF NOT EXISTS sense_relation_source_index ON sense_relations (source_rowid);
CREATE INDEX IF NOT EXISTS sense_relation_target_index ON sense_relations (target_rowid);

CREATE TABLE IF NOT EXISTS sense_synset_relations (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    source_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    target_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    type_rowid INTEGER NOT NULL REFERENCES relation_types(rowid),
    metadata META,
    UNIQUE (source_rowid, target_rowid, type_rowid)
);
CREATE INDEX IF NOT EXISTS sense_synset_relation_source_index ON sense_synset_relations (source_rowid);
CREATE INDEX IF NOT EXISTS sense_synset_relation_target_index ON sense_synset_relations (target_rowid);

CREATE TABLE IF NOT EXISTS sense_examples (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    sense_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    example TEXT,
    language TEXT,
    metadata META
);
CREATE INDEX IF NOT EXISTS sense_example_index ON sense_examples (sense_rowid);

CREATE TABLE IF NOT EXISTS counts (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    sense_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    count INTEGER NOT NULL,
    metadata META
);
CREATE INDEX IF NOT EXISTS count_index ON counts(sense_rowid);

-- Syntactic behaviour tables
CREATE TABLE IF NOT EXISTS syntactic_behaviours (
    rowid INTEGER PRIMARY KEY,
    id TEXT,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    frame TEXT NOT NULL,
    UNIQUE (lexicon_rowid, id),
    UNIQUE (lexicon_rowid, frame)
);
CREATE INDEX IF NOT EXISTS syntactic_behaviour_id_index ON syntactic_behaviours (id);

CREATE TABLE IF NOT EXISTS syntactic_behaviour_senses (
    syntactic_behaviour_rowid INTEGER NOT NULL REFERENCES syntactic_behaviours (rowid) ON DELETE CASCADE,
    sense_rowid INTEGER NOT NULL REFERENCES senses (rowid) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS syntactic_behaviour_sense_sb_index
    ON syntactic_behaviour_senses (syntactic_behaviour_rowid);
CREATE INDEX IF NOT EXISTS syntactic_behaviour_sense_sense_index
    ON syntactic_behaviour_senses (sense_rowid);

-- Edit history
CREATE TABLE IF NOT EXISTS edit_history (
    rowid INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK( entity_type IN ('lexicon','synset','entry','sense','relation','definition','example','form','ili') ),
    entity_id TEXT NOT NULL,
    field_name TEXT,
    operation TEXT NOT NULL CHECK( operation IN ('CREATE', 'UPDATE', 'DELETE') ),
    old_value TEXT,
    new_value TEXT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now')),
    session_id TEXT
);
CREATE INDEX IF NOT EXISTS edit_history_entity_index ON edit_history (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS edit_history_timestamp_index ON edit_history (timestamp);
```

---

## 2.2 — Column Reference

### `meta` table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| key | TEXT | NO | — | Setting name |
| value | TEXT | YES | — | Setting value |

### `ilis` table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| rowid | INTEGER | NO | auto | Primary key |
| id | TEXT | NO | — | ILI identifier (e.g., "i90287") |
| status | TEXT | NO | 'presupposed' | Status: 'active', 'presupposed', or 'deprecated' (CHECK constraint) |
| definition | TEXT | YES | — | Definition text |
| metadata | META | YES | — | JSON Dublin Core metadata |

### `lexicons` table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| rowid | INTEGER | NO | auto | Primary key |
| specifier | TEXT | NO | — | `{id}:{version}` format |
| id | TEXT | NO | — | Lexicon ID (e.g., "ewn") |
| label | TEXT | NO | — | Human-readable name |
| language | TEXT | NO | — | BCP-47 language tag |
| email | TEXT | NO | — | Contact email |
| license | TEXT | NO | — | License URL |
| version | TEXT | NO | — | Version string |
| url | TEXT | YES | — | Project URL |
| citation | TEXT | YES | — | Citation text |
| logo | TEXT | YES | — | Logo URL |
| metadata | META | YES | — | JSON Dublin Core metadata |
| modified | BOOLEAN | NO | 0 | Whether lexicon has been modified |

### `entries` table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| rowid | INTEGER | NO | auto | Primary key |
| id | TEXT | NO | — | Entry ID (e.g., "ewn-cat-n") |
| lexicon_rowid | INTEGER | NO | — | FK → lexicons.rowid (CASCADE) |
| pos | TEXT | NO | — | Part of speech |
| lemma | TEXT | NO | '' | Denormalized lemma for fast lookup (replaces former `entry_index` table) |
| metadata | META | YES | — | JSON Dublin Core metadata |

### `forms` table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| rowid | INTEGER | NO | auto | Primary key |
| id | TEXT | YES | — | Optional form ID |
| lexicon_rowid | INTEGER | NO | — | FK → lexicons.rowid (CASCADE) |
| entry_rowid | INTEGER | NO | — | FK → entries.rowid (CASCADE) |
| form | TEXT | NO | — | Written form text |
| normalized_form | TEXT | YES | — | Case-folded form (only when different from `form`) |
| script | TEXT | YES | — | Script code |
| rank | INTEGER | YES | 1 | 0 = lemma, 1+ = additional forms |

### `synsets` table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| rowid | INTEGER | NO | auto | Primary key |
| id | TEXT | NO | — | Synset ID (e.g., "ewn-10161911-n") |
| lexicon_rowid | INTEGER | NO | — | FK → lexicons.rowid (CASCADE) |
| ili_rowid | INTEGER | YES | — | FK → ilis.rowid |
| pos | TEXT | YES | — | Part of speech |
| lexfile_rowid | INTEGER | YES | — | FK → lexfiles.rowid |
| lexicalized | BOOLEAN | NO | 1 | 0 = synset has no senses (replaces former `unlexicalized_synsets` table) |
| proposed_ili_definition | TEXT | YES | — | Proposed ILI definition text, ≥20 chars (replaces former `proposed_ilis` table) |
| proposed_ili_metadata | META | YES | — | JSON metadata for proposed ILI |
| metadata | META | YES | — | JSON Dublin Core metadata |

### `senses` table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| rowid | INTEGER | NO | auto | Primary key |
| id | TEXT | NO | — | Sense ID |
| lexicon_rowid | INTEGER | NO | — | FK → lexicons.rowid (CASCADE) |
| entry_rowid | INTEGER | NO | — | FK → entries.rowid (CASCADE) |
| entry_rank | INTEGER | YES | 1 | Rank within entry |
| synset_rowid | INTEGER | NO | — | FK → synsets.rowid (CASCADE) |
| synset_rank | INTEGER | YES | 1 | Rank within synset |
| lexicalized | BOOLEAN | NO | 1 | 0 = sense is unlexicalized (replaces former `unlexicalized_senses` table) |
| adjposition | TEXT | YES | — | Adjective position: 'predicative', 'attributive', 'postpositive' (replaces former `adjpositions` table) |
| metadata | META | YES | — | JSON Dublin Core metadata |

### `synset_relations` table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| rowid | INTEGER | NO | auto | Primary key |
| lexicon_rowid | INTEGER | NO | — | FK → lexicons.rowid (CASCADE) |
| source_rowid | INTEGER | NO | — | FK → synsets.rowid (CASCADE) |
| target_rowid | INTEGER | NO | — | FK → synsets.rowid (CASCADE) |
| type_rowid | INTEGER | NO | — | FK → relation_types.rowid |
| metadata | META | YES | — | JSON metadata |

### `sense_relations` table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| rowid | INTEGER | NO | auto | Primary key |
| lexicon_rowid | INTEGER | NO | — | FK → lexicons.rowid (CASCADE) |
| source_rowid | INTEGER | NO | — | FK → senses.rowid (CASCADE) |
| target_rowid | INTEGER | NO | — | FK → senses.rowid (CASCADE) |
| type_rowid | INTEGER | NO | — | FK → relation_types.rowid |
| metadata | META | YES | — | JSON metadata |

### `definitions` table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| rowid | INTEGER | NO | auto | Primary key |
| lexicon_rowid | INTEGER | NO | — | FK → lexicons.rowid (CASCADE) |
| synset_rowid | INTEGER | NO | — | FK → synsets.rowid (CASCADE) |
| definition | TEXT | YES | — | Definition text |
| language | TEXT | YES | — | BCP-47 language tag |
| sense_rowid | INTEGER | YES | — | FK → senses.rowid (SET NULL) |
| metadata | META | YES | — | JSON metadata |

### `edit_history` table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| rowid | INTEGER | NO | auto | Primary key |
| entity_type | TEXT | NO | — | "synset", "entry", "sense", "lexicon", "relation", "definition", "example", "form", "ili" |
| entity_id | TEXT | NO | — | ID of the modified entity |
| field_name | TEXT | YES | — | Changed field (NULL for CREATE/DELETE) |
| operation | TEXT | NO | — | "CREATE", "UPDATE", or "DELETE" |
| old_value | TEXT | YES | — | JSON previous value (NULL for CREATE) |
| new_value | TEXT | YES | — | JSON new value (NULL for DELETE) |
| timestamp | TEXT | NO | auto | ISO 8601 timestamp via `strftime` |
| session_id | TEXT | YES | — | Groups related edits into a logical session (enables future rollback-to-session) |

---

## 2.3 — ER Diagram

```
┌──────────────┐       ┌───────────────────┐
│  lexfiles    │       │       ilis        │
│──────────────│       │───────────────────│
│ rowid (PK)   │       │ rowid (PK)        │
│ name         │       │ id                │
└──────┬───────┘       │ status (CHECK)    │
       │               │ definition        │
       │               │ metadata          │
       │               └────────┬──────────┘
       │                        │
       │    ┌───────────────────┘
       │    │
       ▼    ▼
┌──────────────────────────────────────────────────┐
│                    lexicons                       │
│──────────────────────────────────────────────────│
│ rowid (PK), specifier, id, label, language,      │
│ email, license, version, url, citation,          │
│ logo, metadata, modified                         │
└──────┬────────────────────────┬──────────────────┘
       │                        │
       ▼                        ▼
┌────────────────┐       ┌──────────────────────────────┐
│   entries      │       │         synsets               │
│────────────────│       │──────────────────────────────│
│ rowid (PK)     │       │ rowid (PK)                   │
│ id             │       │ id                           │
│ lexicon_rowid  │       │ lexicon_rowid (FK)           │
│ pos            │       │ ili_rowid (FK → ilis)        │
│ lemma          │       │ pos                          │
│ metadata       │       │ lexfile_rowid (FK)           │
└──┬─────────────┘       │ lexicalized                  │
   │                     │ proposed_ili_definition       │
   │                     │ proposed_ili_metadata         │
   │                     │ metadata                     │
   │                     └──┬───────────────────────────┘
   │                        │
   ▼                        ├──── definitions
   ├──── forms              ├──── synset_examples
   │     ├── pronunciations ├──── synset_relations ──→ relation_types
   │     └── tags           │
   │                        │
   └──── senses ────────────┘
         │  (+ lexicalized, adjposition)
         │
         ├──── sense_relations ──────→ relation_types
         ├──── sense_synset_relations ──→ relation_types
         ├──── sense_examples
         ├──── counts
         └──── syntactic_behaviour_senses ──→ syntactic_behaviours

┌─────────────────────┐
│   edit_history      │  (standalone, no FK)
│─────────────────────│
│ entity_type         │
│ entity_id           │
│ field_name          │
│ operation           │
│ old_value           │
│ new_value           │
│ timestamp           │
│ session_id          │
└─────────────────────┘
```

---

## 2.4 — Divergences from `wn` Schema

### Tables eliminated (v2.0 schema simplification)

| Removed table | Replacement | Rationale |
|---------------|-------------|-----------|
| `ili_statuses` | `ilis.status TEXT` with CHECK constraint | The `wn` schema uses a lookup table for 3 status values ('active', 'presupposed', 'deprecated'). A CHECK-constrained text column is simpler, eliminates a JOIN, and the value set is fixed by the WN-LMF specification |
| `proposed_ilis` | `synsets.proposed_ili_definition` + `synsets.proposed_ili_metadata` | A proposed ILI is a 1:1 annotation on a synset (a proposal for the synset to receive an ILI). Inlining avoids a separate table and JOIN. The ILI does not yet exist, so data belongs on the synset, not the `ilis` table |
| `unlexicalized_synsets` | `synsets.lexicalized BOOLEAN DEFAULT 1` | The `wn` schema stores unlexicalized synsets in a satellite table. A boolean column on `synsets` is simpler and avoids a LEFT JOIN or NOT EXISTS subquery |
| `unlexicalized_senses` | `senses.lexicalized BOOLEAN DEFAULT 1` | Same rationale as `unlexicalized_synsets` |
| `adjpositions` | `senses.adjposition TEXT` | The `wn` schema uses a 1:1 satellite table. Inlining eliminates a JOIN and simplifies sense construction |
| `entry_index` | `entries.lemma TEXT DEFAULT ''` | The `wn` schema stores a denormalized lemma in a separate 1:1 table. Inlining keeps the same fast-lookup benefit with one fewer table |

### Tables and columns added

| Addition | Rationale |
|----------|-----------|
| `meta` table | Schema versioning for the editor's own database |
| `edit_history` table | Change tracking for batch editing audit trail |
| `edit_history.session_id` | Groups related edits into a logical session, enabling future `rollback_to(session)` semantics |
| `entries.lemma` | Denormalized lemma for fast entry lookup (replaces `entry_index` table) |
| `synsets.lexicalized` | Boolean flag replacing `unlexicalized_synsets` satellite table |
| `synsets.proposed_ili_definition` | Proposed ILI definition replacing `proposed_ilis` satellite table |
| `synsets.proposed_ili_metadata` | Proposed ILI metadata replacing `proposed_ilis` satellite table |
| `senses.lexicalized` | Boolean flag replacing `unlexicalized_senses` satellite table |
| `senses.adjposition` | Adjective position replacing `adjpositions` satellite table |

### PRAGMA changes

| PRAGMA | `wn` default | Editor setting | Rationale |
|--------|-------------|----------------|-----------|
| `journal_mode` | DELETE | WAL | Better read concurrency during export |
| `foreign_keys` | OFF | ON | Enforces referential integrity on every connection |
| `busy_timeout` | 0 | 5000 | A second writer waits up to 5 seconds before raising `SQLITE_BUSY`, supporting brief contention between processes sharing a database file |

### Constraints added (v2.0)

| Constraint | Rationale |
|------------|-----------|
| `UNIQUE (id, lexicon_rowid)` on `senses` | Prevents duplicate sense IDs within the same lexicon |
| `CHECK(status IN (...))` on `ilis.status` | Enforces valid ILI status values at the database level |

**Unchanged from `wn`:**
- All CASCADE DELETE rules preserved (lexicon deletion cascades to all owned entities)
- All original UNIQUE constraints preserved
- All original indexes preserved
- The `relation_types` normalization pattern preserved
- The `forms.rank` pattern (0 = lemma) preserved
- The `forms.normalized_form` optimization preserved
- The `META` column type retained (same `json.dumps`/`json.loads` adapter/converter pattern as `wn`)

---

## 2.5 — Transaction Model

### Connection setup

Every connection sets `PRAGMA busy_timeout = 5000`. This means that if two processes open the same database file, the second writer waits up to 5 seconds for the first to finish its transaction. Without this setting, SQLite would immediately raise `SQLITE_BUSY` on contention. The 5-second window covers typical brief write transactions (single-entity edits, relation changes) without introducing indefinite blocking.

### Single-operation transactions

Every public API method that mutates data executes within a single SQLite transaction:

```python
with self._conn:  # implicit BEGIN / COMMIT
    # all mutations here
    # edit_history INSERT(s) here
```

If any step fails (validation, constraint violation), the entire transaction rolls back. The caller sees an exception; the database is unchanged.

### Compound operation transactions

Compound operations (`merge_synsets`, `split_synset`, `move_sense`) are atomic:

```python
with self._conn:
    # Step 1: validate preconditions
    # Step 2: perform all sub-mutations
    # Step 3: record all edit_history entries
    # All-or-nothing: if step 2 fails mid-way, everything rolls back
```

### Batch context manager

The `batch()` context manager defers individual transactions into one:

```python
with editor.batch():
    editor.create_synset(...)   # no individual commit
    editor.add_sense(...)       # no individual commit
    editor.add_synset_relation(...)  # no individual commit
# all committed here as single transaction
```

Implementation: `batch()` sets a flag that suppresses per-method commits. The context manager `__exit__` commits (or rolls back on exception).

### Edit history within transactions

`edit_history` rows are inserted within the same transaction as the mutation they describe. This guarantees that:
- If the mutation succeeds, the history record exists
- If the mutation fails, no orphaned history record is created

The optional `session_id` column allows grouping related edits (e.g., all changes made during an interactive session or a batch script run).

---

## 2.6 — Migration Strategy

**Approach**: Version check + schema migration.

On connection:
1. Read `meta` table for `schema_version`
2. If version matches current (`2.0`), proceed
3. If version is older: raise `DatabaseError` with migration instructions
4. If `meta` table doesn't exist: database is uninitialized, run full DDL

**Migration tool**: `tools/migrate_v1_to_v2.py` handles v1.0 → v2.0 migration:
- Creates a `.v1-backup.db` backup file before any changes
- Adds inline columns to `synsets`, `senses`, `entries` via ALTER TABLE
- Backfills data from satellite tables into inline columns
- Rebuilds `ilis` table via create-copy-rename to enforce CHECK constraint
- Adds UNIQUE index on `senses(id, lexicon_rowid)`
- Drops eliminated satellite tables
- Runs post-migration verification checks
- Updates `schema_version` to `2.0`

**Rationale**: The editor database is a working copy, not archival storage. If a schema migration fails, the user can restore from the backup or re-import from their WN-LMF XML source.
