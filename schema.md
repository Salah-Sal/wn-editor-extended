# Database Schema Specification

**Library**: `wordnet-editor`
**Version**: 1.0
**Date**: 2026-02-16

This document defines the complete SQLite schema for the editor's independent database. A developer can produce the full DDL from this spec alone.

---

## 2.1 — Complete DDL

### PRAGMA Settings

```sql
PRAGMA foreign_keys = ON;
PRAGMA journal_mode = WAL;
```

**Rationale**: `WAL` provides better read concurrency during export operations (reads don't block writes). `foreign_keys` ensures referential integrity on every connection.

### Meta Table

```sql
CREATE TABLE meta (
    key TEXT NOT NULL,
    value TEXT,
    UNIQUE (key)
);
```

Stores schema version for compatibility checks. On initialization:
```sql
INSERT INTO meta VALUES ('schema_version', '1.0');
INSERT INTO meta VALUES ('created_at', strftime('%Y-%m-%dT%H:%M:%f', 'now'));
```

### Lookup Tables

```sql
CREATE TABLE relation_types (
    rowid INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    UNIQUE (type)
);
CREATE INDEX relation_type_index ON relation_types (type);

CREATE TABLE ili_statuses (
    rowid INTEGER PRIMARY KEY,
    status TEXT NOT NULL,
    UNIQUE (status)
);
CREATE INDEX ili_status_index ON ili_statuses (status);

CREATE TABLE lexfiles (
    rowid INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    UNIQUE (name)
);
CREATE INDEX lexfile_index ON lexfiles (name);
```

### ILI Tables

```sql
CREATE TABLE ilis (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    status_rowid INTEGER NOT NULL REFERENCES ili_statuses (rowid),
    definition TEXT,
    metadata META,
    UNIQUE (id)
);
CREATE INDEX ili_id_index ON ilis (id);

CREATE TABLE proposed_ilis (
    rowid INTEGER PRIMARY KEY,
    synset_rowid INTEGER REFERENCES synsets (rowid) ON DELETE CASCADE,
    definition TEXT,
    metadata META,
    UNIQUE (synset_rowid)
);
CREATE INDEX proposed_ili_synset_rowid_index ON proposed_ilis (synset_rowid);
```

### Lexicon Tables

```sql
CREATE TABLE lexicons (
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
CREATE INDEX lexicon_specifier_index ON lexicons (specifier);

CREATE TABLE lexicon_dependencies (
    dependent_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    provider_id TEXT NOT NULL,
    provider_version TEXT NOT NULL,
    provider_url TEXT,
    provider_rowid INTEGER REFERENCES lexicons (rowid) ON DELETE SET NULL
);
CREATE INDEX lexicon_dependent_index ON lexicon_dependencies(dependent_rowid);

CREATE TABLE lexicon_extensions (
    extension_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    base_id TEXT NOT NULL,
    base_version TEXT NOT NULL,
    base_url TEXT,
    base_rowid INTEGER REFERENCES lexicons (rowid),
    UNIQUE (extension_rowid, base_rowid)
);
CREATE INDEX lexicon_extension_index ON lexicon_extensions(extension_rowid);
```

### Lexical Entry Tables

```sql
CREATE TABLE entries (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    pos TEXT NOT NULL,
    metadata META,
    UNIQUE (id, lexicon_rowid)
);
CREATE INDEX entry_id_index ON entries (id);

CREATE TABLE entry_index (
    entry_rowid INTEGER NOT NULL REFERENCES entries (rowid) ON DELETE CASCADE,
    lemma TEXT NOT NULL,
    UNIQUE (entry_rowid)
);
CREATE INDEX entry_index_entry_index ON entry_index(entry_rowid);
CREATE INDEX entry_index_lemma_index ON entry_index(lemma);

CREATE TABLE forms (
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
CREATE INDEX form_entry_index ON forms (entry_rowid);
CREATE INDEX form_index ON forms (form);
CREATE INDEX form_norm_index ON forms (normalized_form);

CREATE TABLE pronunciations (
    form_rowid INTEGER NOT NULL REFERENCES forms (rowid) ON DELETE CASCADE,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    value TEXT,
    variety TEXT,
    notation TEXT,
    phonemic BOOLEAN CHECK( phonemic IN (0, 1) ) DEFAULT 1 NOT NULL,
    audio TEXT
);
CREATE INDEX pronunciation_form_index ON pronunciations (form_rowid);

CREATE TABLE tags (
    form_rowid INTEGER NOT NULL REFERENCES forms (rowid) ON DELETE CASCADE,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    tag TEXT,
    category TEXT
);
CREATE INDEX tag_form_index ON tags (form_rowid);
```

### Synset Tables

```sql
CREATE TABLE synsets (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    ili_rowid INTEGER REFERENCES ilis (rowid),
    pos TEXT,
    lexfile_rowid INTEGER REFERENCES lexfiles (rowid),
    metadata META,
    UNIQUE (id, lexicon_rowid)
);
CREATE INDEX synset_id_index ON synsets (id);
CREATE INDEX synset_ili_rowid_index ON synsets (ili_rowid);

CREATE TABLE unlexicalized_synsets (
    synset_rowid INTEGER NOT NULL REFERENCES synsets (rowid) ON DELETE CASCADE
);
CREATE INDEX unlexicalized_synsets_index ON unlexicalized_synsets (synset_rowid);

CREATE TABLE synset_relations (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    source_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    target_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    type_rowid INTEGER NOT NULL REFERENCES relation_types(rowid),
    metadata META,
    UNIQUE (source_rowid, target_rowid, type_rowid)
);
CREATE INDEX synset_relation_source_index ON synset_relations (source_rowid);
CREATE INDEX synset_relation_target_index ON synset_relations (target_rowid);

CREATE TABLE definitions (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    synset_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    definition TEXT,
    language TEXT,
    sense_rowid INTEGER REFERENCES senses(rowid) ON DELETE SET NULL,
    metadata META
);
CREATE INDEX definition_rowid_index ON definitions (synset_rowid);
CREATE INDEX definition_sense_index ON definitions (sense_rowid);

CREATE TABLE synset_examples (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    synset_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    example TEXT,
    language TEXT,
    metadata META
);
CREATE INDEX synset_example_rowid_index ON synset_examples(synset_rowid);
```

### Sense Tables

```sql
CREATE TABLE senses (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    entry_rowid INTEGER NOT NULL REFERENCES entries(rowid) ON DELETE CASCADE,
    entry_rank INTEGER DEFAULT 1,
    synset_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    synset_rank INTEGER DEFAULT 1,
    metadata META
);
CREATE INDEX sense_id_index ON senses(id);
CREATE INDEX sense_entry_rowid_index ON senses (entry_rowid);
CREATE INDEX sense_synset_rowid_index ON senses (synset_rowid);

CREATE TABLE unlexicalized_senses (
    sense_rowid INTEGER NOT NULL REFERENCES senses (rowid) ON DELETE CASCADE
);
CREATE INDEX unlexicalized_senses_index ON unlexicalized_senses (sense_rowid);

CREATE TABLE sense_relations (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    source_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    target_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    type_rowid INTEGER NOT NULL REFERENCES relation_types(rowid),
    metadata META,
    UNIQUE (source_rowid, target_rowid, type_rowid)
);
CREATE INDEX sense_relation_source_index ON sense_relations (source_rowid);
CREATE INDEX sense_relation_target_index ON sense_relations (target_rowid);

CREATE TABLE sense_synset_relations (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    source_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    target_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    type_rowid INTEGER NOT NULL REFERENCES relation_types(rowid),
    metadata META,
    UNIQUE (source_rowid, target_rowid, type_rowid)
);
CREATE INDEX sense_synset_relation_source_index ON sense_synset_relations (source_rowid);
CREATE INDEX sense_synset_relation_target_index ON sense_synset_relations (target_rowid);

CREATE TABLE adjpositions (
    sense_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    adjposition TEXT NOT NULL
);
CREATE INDEX adjposition_sense_index ON adjpositions (sense_rowid);

CREATE TABLE sense_examples (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    sense_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    example TEXT,
    language TEXT,
    metadata META
);
CREATE INDEX sense_example_index ON sense_examples (sense_rowid);

CREATE TABLE counts (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    sense_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    count INTEGER NOT NULL,
    metadata META
);
CREATE INDEX count_index ON counts(sense_rowid);
```

### Syntactic Behaviour Tables

```sql
CREATE TABLE syntactic_behaviours (
    rowid INTEGER PRIMARY KEY,
    id TEXT,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    frame TEXT NOT NULL,
    UNIQUE (lexicon_rowid, id),
    UNIQUE (lexicon_rowid, frame)
);
CREATE INDEX syntactic_behaviour_id_index ON syntactic_behaviours (id);

CREATE TABLE syntactic_behaviour_senses (
    syntactic_behaviour_rowid INTEGER NOT NULL REFERENCES syntactic_behaviours (rowid) ON DELETE CASCADE,
    sense_rowid INTEGER NOT NULL REFERENCES senses (rowid) ON DELETE CASCADE
);
CREATE INDEX syntactic_behaviour_sense_sb_index
    ON syntactic_behaviour_senses (syntactic_behaviour_rowid);
CREATE INDEX syntactic_behaviour_sense_sense_index
    ON syntactic_behaviour_senses (sense_rowid);
```

### Editor-Specific Table: Edit History

```sql
CREATE TABLE edit_history (
    rowid INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK( entity_type IN ('lexicon','synset','entry','sense','relation','definition','example','form','ili') ),
    entity_id TEXT NOT NULL,
    field_name TEXT,
    operation TEXT NOT NULL CHECK( operation IN ('CREATE', 'UPDATE', 'DELETE') ),
    old_value TEXT,
    new_value TEXT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);
CREATE INDEX edit_history_entity_index ON edit_history (entity_type, entity_id);
CREATE INDEX edit_history_timestamp_index ON edit_history (timestamp);
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
| status_rowid | INTEGER | NO | — | FK → ili_statuses.rowid |
| definition | TEXT | YES | — | Definition text |
| metadata | META | YES | — | JSON Dublin Core metadata |

### `proposed_ilis` table

| Column | Type | Nullable | Default | Description |
|--------|------|----------|---------|-------------|
| rowid | INTEGER | NO | auto | Primary key |
| synset_rowid | INTEGER | YES | — | FK → synsets.rowid (CASCADE) |
| definition | TEXT | YES | — | Proposed ILI definition (≥20 chars) |
| metadata | META | YES | — | JSON metadata |

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
| entity_type | TEXT | NO | — | "synset", "entry", "sense", "lexicon", "relation", "definition", "example" |
| entity_id | TEXT | NO | — | ID of the modified entity |
| field_name | TEXT | YES | — | Changed field (NULL for CREATE/DELETE) |
| operation | TEXT | NO | — | "CREATE", "UPDATE", or "DELETE" |
| old_value | TEXT | YES | — | JSON previous value (NULL for CREATE) |
| new_value | TEXT | YES | — | JSON new value (NULL for DELETE) |
| timestamp | TEXT | NO | auto | ISO 8601 timestamp via `strftime` |

---

## 2.3 — ER Diagram

```
                      ┌─────────────────┐
                      │   ili_statuses   │
                      │─────────────────│
                      │ rowid (PK)      │
                      │ status          │
                      └────────┬────────┘
                               │
┌──────────────┐       ┌───────┴────────┐       ┌──────────────────┐
│  lexfiles    │       │     ilis       │       │  proposed_ilis   │
│──────────────│       │────────────────│       │──────────────────│
│ rowid (PK)   │       │ rowid (PK)    │       │ rowid (PK)       │
│ name         │       │ id            │       │ synset_rowid (FK)│──┐
└──────┬───────┘       │ status_rowid  │       │ definition       │  │
       │               │ definition    │       └──────────────────┘  │
       │               └───────┬───────┘                             │
       │                       │                                     │
       │    ┌──────────────────┼─────────────────────────────────────┘
       │    │                  │
       ▼    ▼                  ▼
┌──────────────────────────────────────────────┐
│                  lexicons                     │
│──────────────────────────────────────────────│
│ rowid (PK), specifier, id, label, language,  │
│ email, license, version, url, citation,      │
│ logo, metadata, modified                     │
└──────┬────────────────────────┬──────────────┘
       │                        │
       ▼                        ▼
┌──────────────┐        ┌──────────────────┐
│   entries    │        │    synsets        │
│──────────────│        │──────────────────│
│ rowid (PK)   │        │ rowid (PK)       │
│ id           │        │ id               │
│ lexicon_rowid│        │ lexicon_rowid(FK)│
│ pos          │        │ ili_rowid (FK)   │
│ metadata     │        │ pos              │
└──┬───────────┘        │ lexfile_rowid(FK)│
   │                    │ metadata         │
   │                    └──┬───────────────┘
   │                       │
   ▼                       ├──── definitions
   ├──── forms             ├──── synset_examples
   │     ├── pronunciations├──── synset_relations ──→ relation_types
   │     └── tags          └──── unlexicalized_synsets
   │
   ├──── entry_index
   │
   └──── senses ──────────────→ synsets
         │
         ├──── sense_relations ──────→ relation_types
         ├──── sense_synset_relations ──→ relation_types
         ├──── sense_examples
         ├──── counts
         ├──── adjpositions
         ├──── unlexicalized_senses
         └──── syntactic_behaviour_senses ──→ syntactic_behaviours

┌──────────────────┐
│  edit_history    │  (standalone, no FK)
│──────────────────│
│ entity_type      │
│ entity_id        │
│ field_name       │
│ operation        │
│ old_value        │
│ new_value        │
│ timestamp        │
└──────────────────┘
```

---

## 2.4 — Divergences from `wn` Schema

| Change | Rationale |
|--------|-----------|
| Added `meta` table | Schema versioning for the editor's own database |
| Added `edit_history` table | Change tracking for batch editing audit trail |
| Added `PRAGMA journal_mode = WAL` | `wn` uses default (DELETE). WAL gives better read concurrency during export |
| Retained all `wn` tables and indexes exactly | Maximizes compatibility. The editor DB is structurally identical to `wn`'s DB for entity storage, making import/export a direct row-copy operation |
| `META` column type retained | Uses same `json.dumps`/`json.loads` adapter/converter pattern as `wn` |
| No `updated_at` columns added | Change tracking is handled by `edit_history` table instead, avoiding schema divergence from `wn` |

**Not changed from `wn`:**
- All CASCADE DELETE rules preserved (lexicon deletion cascades to all owned entities)
- All UNIQUE constraints preserved
- All indexes preserved
- The `relation_types` normalization pattern preserved
- The `unlexicalized_synsets`/`unlexicalized_senses` pattern preserved
- The `forms.rank` pattern (0 = lemma) preserved
- The `forms.normalized_form` optimization preserved

---

## 2.5 — Transaction Model

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

---

## 2.6 — Migration Strategy

**Approach**: Version check + recreate (matching `wn`'s pattern).

On connection:
1. Read `meta` table for `schema_version`
2. If version matches current, proceed
3. If version is older:
   - For compatible changes (additive): run ALTER TABLE / CREATE TABLE / CREATE INDEX statements
   - For incompatible changes: raise `DatabaseError` with migration instructions
4. If `meta` table doesn't exist: database is uninitialized, run full DDL

**Rationale**: The editor database is a working copy, not archival storage. If a schema migration is truly incompatible, the user can re-import from their WN-LMF XML source. This keeps migration logic simple.
