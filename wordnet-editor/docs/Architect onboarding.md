# WordNet-Editor: Architect Onboarding & Instructions

**Project**: `wordnet-editor` — A pure Python editing library for WordNets  
**Your role**: System Architect — produce all design documents a developer needs to implement this library from scratch  
**Date**: February 2026

---

## 1. WHAT WE ARE BUILDING

A pip-installable pure Python library called `wordnet-editor` that gives linguists a complete programmatic API for editing WordNets. The library:

- Has its **own independent SQLite database** — it never mutates the `wn` library's database
- **Reads from `wn`** (via `wn.lmf.load()` and `wn`'s query API) but writes only to its own store
- Supports all CRUD operations a linguist needs: synsets, lexical entries, senses, definitions, examples, relations, ILI mappings
- Exports valid WN-LMF 1.4 XML that can be re-imported into `wn` via `wn.add()`
- Targets **single-user batch editing** (no concurrency, no collaborative features)
- Maintains **automatic inverse relations** (add hypernym → hyponym auto-created)
- Supports **compound operations**: synset merge, synset split, sense move
- Includes a **validation engine** and **change tracking** (edit history table)

The only runtime dependency is `wn >= 1.0.0` plus Python standard library.

---

## 2. YOUR WORKSPACE

You have this folder structure:

```
wordnet-editor/
├── wn/                          # The wn library repo (full source)
└── resources/
    ├── example WN-LMF XML file.xml
    ├── GWA relation documentation.md
    ├── Open English WordNet FORMAT.md
    └── WN-LMF 1.4 schema specification.md
```

Everything you need is either in these folders or derivable from them. You should NOT need internet access for any design work — all references are local.

---

## 3. WHAT YOU MUST READ (IN THIS ORDER)

The order matters. Each step builds context for the next. Do not skip ahead.

### Phase A: Understand the data model (do this first)

These resources define WHAT a WordNet is — the entities, relationships, and constraints that the editor must faithfully represent.

**Step A1 — Read `resources/WN-LMF 1.4 schema specification.md`**

This is the canonical data model. Read it end to end. While reading, extract:

- Every entity type (LexicalResource, Lexicon, LexicalEntry, Lemma, Form, Sense, Synset, Definition, Example, ILIDefinition, SynsetRelation, SenseRelation, SyntacticBehaviour, Count, Tag, Pronunciation)
- Every attribute on every entity (id, writtenForm, partOfSpeech, relType, target, ili, etc.)
- Cardinality constraints (which are required, which are optional, which are repeatable)
- The Dublin Core metadata namespace and which elements can carry metadata
- The confidence score model (how it cascades from lexicon to child elements)
- The ILI system: what `ili="i90287"` vs `ili="in"` vs empty means
- The `partOfSpeech` enum: n, v, a, r, s, c, p, x, u

**What to note down**: A complete entity-relationship list. This becomes the foundation for your Domain Model spec and Database Schema spec.

**Step A2 — Read `resources/GWA relation documentation.md`**

This documents every relation type the GWA recognizes. While reading, build two tables:

TABLE 1 — Synset relations:
```
| Relation         | Inverse              | Applies to POS | Description |
|------------------|----------------------|----------------|-------------|
| hypernym         | hyponym              | n, v           | ...         |
| instance_hypernym| instance_hyponym     | n              | ...         |
| ...              | ...                  | ...            | ...         |
```

TABLE 2 — Sense relations:
```
| Relation    | Inverse     | Description |
|-------------|-------------|-------------|
| antonym     | antonym     | symmetric   |
| derivation  | derivation  | symmetric   |
| ...         | ...         | ...         |
```

Pay special attention to:
- Which relations are **symmetric** (antonym, similar) — these are their own inverse
- Which relations are **asymmetric** with a named inverse (hypernym/hyponym)
- The `other` type with `dc:type` — how custom relations work
- Role relations (agent, patient, result, instrument, location, direction)
- Morphosemantic sense relations

**What to note down**: The complete inverse-relation mapping. This directly becomes the lookup table that powers automatic inverse relation maintenance — the most important behavioral feature of the editor.

**Step A3 — Read `resources/Open English WordNet FORMAT.md`**

This documents the conventions used by the most widely-used WordNet (OEWN). While reading, note:

- Synset ID format: how IDs are constructed (prefix + digits + POS suffix)
- Entry ID format and conventions
- Sense ID format and conventions
- Any OEWN-specific extensions to the base WN-LMF schema

**What to note down**: The ID generation conventions. The editor needs an ID generation strategy for new entities that is compatible with these conventions.

**Step A4 — Read `resources/example WN-LMF XML file.xml`**

Read this as a concrete instance of everything you learned in A1–A3. Trace every element back to the WN-LMF spec. Verify your understanding by confirming:

- Can you identify every entity and its attributes?
- Can you follow the sense → synset linkages?
- Can you trace the relation graph?
- Can you see how metadata is attached?

**What to note down**: Nothing new — this is a comprehension check. If anything surprises you, go back to A1.

---

### Phase B: Understand the `wn` library internals

Now you understand the data model. Next, understand how the `wn` library implements it — because the editor must interoperate with `wn`.

**Step B1 — Read `wn/wn/_db.py`**

This is the most important source file for your work. It contains:

- The complete SQLite DDL (all CREATE TABLE statements)
- All indexes
- PRAGMA settings (foreign_keys, journal_mode)
- The `meta` table and schema versioning approach
- The `_connect()` function — how connections are managed
- All INSERT functions — how data flows into the database
- The DELETE logic in the `remove()` path

While reading, build a table:

```
| Table                | Columns (name: type)           | Foreign Keys              | Indexes         | Notes                    |
|----------------------|-------------------------------|---------------------------|-----------------|--------------------------|
| meta                 | key: TEXT, value: TEXT          | —                         | —               | Schema version tracking  |
| ilis                 | rowid, ili: TEXT UNIQUE, ...   | —                         | —               | ILI entries              |
| lexicons             | rowid, id: TEXT, label, ...    | —                         | UNIQUE(id,ver)  | Wordnet packages         |
| ...                  | ...                           | ...                       | ...             | ...                      |
```

**Critical things to identify**:
- The `relation_types` table — a normalization table where relation strings are stored once and referenced by rowid. This is an elegant design. Keep it.
- The `forms` table `rank` column — rank 0 = lemma, rank > 0 = inflected forms. Keep this.
- The `normalized_form` column on `forms` — for case-insensitive lookup. Keep this.
- The `metadata` JSON column pattern — used on most tables. Keep this.
- The `lexicalized` boolean on `synsets` and `senses` — keep this.
- The absence of any UPDATE statements — the database is insert-once, delete-all. This is the core limitation the editor addresses.

**What to note down**: The complete schema with all columns, types, constraints, and indexes. This is the starting point for your editor's schema — you will replicate most of it and extend it.

**Step B2 — Read `wn/wn/lmf.py`**

This file defines:

- The TypedDict structures: `LexicalResource`, `Lexicon`, `LexicalEntry`, `Sense`, `Synset`, etc.
- The `load()` function — parses WN-LMF XML into these TypedDicts
- The `dump()` function — serializes TypedDicts back to WN-LMF XML
- The `scan()` function — lightweight metadata-only parsing

While reading, note:

- The exact TypedDict field names and types for every structure
- How `load()` handles optional fields (what defaults are used)
- How `dump()` orders elements (this must be WN-LMF compliant)
- How Dublin Core metadata is represented in the TypedDicts (the `metadata` dict)

**What to note down**: The complete TypedDict hierarchy. This feeds your domain model spec. The editor's import pipeline will call `wn.lmf.load()` and transform these dicts into database rows. The export pipeline will construct these dicts from database rows and call `wn.lmf.dump()`.

**Step B3 — Read `wn/wn/constants.py`**

This contains:

- `SYNSET_RELATIONS` — the set of valid synset relation type strings
- `SENSE_RELATIONS` — the set of valid sense relation type strings  
- `PARTS_OF_SPEECH` — the valid POS codes
- Any other constant enums

**What to note down**: All constant sets. Cross-reference with your relation tables from Step A2. Verify completeness. These constants define the editor's validation rules for relation types and POS values.

**Step B4 — Read `wn/wn/_add.py`**

This shows how `wn.add()` and `wn.add_lexical_resource()` populate the database:

- The transaction structure (BEGIN IMMEDIATE)
- The order of table population (lexicons first, then entries, forms, synsets, senses, relations)
- How rowids are resolved for foreign key references
- How ILI entries are handled (deduplication, status)
- How `relation_types` are normalized (insert-or-get pattern)

**What to note down**: The insertion order and foreign key resolution strategy. Your editor's import pipeline must follow a compatible order. Also note: this is the code path that `commit_to_wn()` will ultimately trigger — the editor exports to a `LexicalResource` dict, then calls `wn.add_lexical_resource()`.

**Step B5 — Read `wn/wn/validate.py`** (if it exists, otherwise check `wn/wn/_valid.py` or similar)

This contains the validation rules `wn` enforces. Note every rule:

- Required fields on each entity
- ID format constraints
- Referential integrity checks (does every sense reference an existing synset?)
- Relation type validity
- ILI constraints (ILIDefinition ≥ 20 chars when `ili="in"`)

**What to note down**: A numbered list of every validation rule. This becomes the seed for your Validation Rules Catalog deliverable.

**Step B6 — Read the public API surface**

Skim these files to understand the query API the editor coexists with:

- `wn/wn/__init__.py` — the public module-level functions: `words()`, `senses()`, `synsets()`, `lexicons()`, `download()`, `add()`, `remove()`, `export()`
- `wn/wn/_core.py` — the `Wordnet`, `Word`, `Sense`, `Synset`, `Form`, `Lexicon` classes and their methods

You don't need to deeply study these, but you need to know:
- What query methods exist (so the editor doesn't redundantly reimplement them)
- What the class signatures look like (so the editor's types feel consistent)
- How `wn.export()` works (so you know the existing export path)

**What to note down**: A list of all public `wn` classes and their key methods. This informs your API spec — specifically, what the editor delegates to `wn` for querying vs. what it implements itself.

---

### Phase C: Study prior art

Now you understand both the data model and the implementation. Study what others have built.

**Step C1 — Read `wn/` for the `wn_edit` extension** 

Check if `wn_edit` is included as a subpackage or extra in the `wn` repo. If not, note that it exists at `github.com/bond-lab/wn_edit` and study it from the research report. From whatever source you have, understand:

- The `WordnetEditor` class: its three initialization paths (from `wn` DB, from scratch, from XML)
- The CRUD methods: `create_synset()`, `modify_synset()`, `remove_synset()`, `create_entry()`, etc.
- The factory functions: `make_synset()`, `make_lexical_entry()`, `make_sense()`
- The export/commit mechanism
- The in-memory operation model (operates on TypedDicts, not on a database)

**What to note down**: 
- Good patterns to adopt (method naming, parameter conventions)
- Gaps to fill (no independent DB, no change tracking, no merge/split, no automatic inverses)
- API decisions you agree or disagree with

---

## 4. WHAT YOU MUST PRODUCE

After completing all reading, produce these deliverables in this order. Each document should be standalone — a developer should be able to implement from any single document without needing to read the others, though they will reference each other.

### Deliverable 1: Architecture Design Document (ADD)

**Filename**: `architecture.md`

Must contain:

**1.1 — System overview**: One paragraph stating what the library is, what it does, and what it does not do.

**1.2 — Architectural principles**: State and justify each design decision:
- Why an independent SQLite database (not mutating `wn`'s store)
- Why SQLite (not an ORM, not flat files, not in-memory dicts)
- Why JSON metadata columns (not separate metadata tables)
- Why single-file database (portability, simplicity)
- Why `wn` is a runtime dependency (leveraging its import/export/query infrastructure)
- Why no custom query layer (delegate reads to `wn` after `commit_to_wn()`)

**1.3 — Component diagram**: Show these components and their relationships:
```
┌─────────────────────────────────────────────────────┐
│                   wordnet-editor                     │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Editor   │  │ Database │  │ Import/Export      │  │
│  │ API      │──│ Layer    │  │ Pipeline           │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
│  ┌──────────┐  ┌──────────┐  ┌───────────────────┐  │
│  │ Domain   │  │Validation│  │ Change             │  │
│  │ Models   │  │ Engine   │  │ Tracking           │  │
│  └──────────┘  └──────────┘  └───────────────────┘  │
└─────────────────────────────────────────────────────┘
          │                            │
          ▼                            ▼
   ┌─────────────┐            ┌──────────────┐
   │ editor.db   │            │  wn library  │
   │ (own SQLite)│            │  (read-only) │
   └─────────────┘            └──────────────┘
```

**1.4 — Data flow diagrams**: Three flows:
1. **Import flow**: WN-LMF XML → `wn.lmf.load()` → LexicalResource dict → editor DB population → editor.db
2. **Edit flow**: User calls editor API → validation → editor.db mutation → edit_history record
3. **Export flow**: editor.db → LexicalResource dict construction → `wn.lmf.dump()` → WN-LMF XML (and optionally → `wn.add_lexical_resource()` → wn.db)

**1.5 — Module structure**:
```
wordnet_editor/
├── __init__.py          # Public API exports
├── editor.py            # WordnetEditor class
├── db.py                # Database layer (connection, DDL, CRUD)
├── models.py            # Domain dataclasses and enums
├── relations.py         # Relation types, inverse mapping
├── importer.py          # Import pipeline
├── exporter.py          # Export pipeline  
├── validator.py         # Validation engine
├── history.py           # Change tracking
├── exceptions.py        # Custom exception hierarchy
└── py.typed             # PEP 561 typing marker
```

**1.6 — Dependency policy**: Only `wn >= 1.0.0`. No other third-party dependencies. Standard library only beyond that.

**1.7 — Error handling strategy**: Define the exception hierarchy (base `WordnetEditorError`, then `ValidationError`, `EntityNotFoundError`, `DuplicateEntityError`, `RelationError`, `ImportError`, `ExportError`).

---

### Deliverable 2: Database Schema Specification

**Filename**: `schema.md`

Must contain:

**2.1 — Complete DDL**: Every CREATE TABLE statement, exactly as SQLite would execute it. Include:
- All PRAGMA statements (`foreign_keys = ON`, `journal_mode = WAL`)
- The `meta` table (schema version)
- All entity tables replicated from `wn`'s schema (with modifications noted)
- New editor-specific tables:
  - `edit_history` (operation log: entity_type, entity_id, operation, old_value_json, new_value_json, timestamp)
  - Any staging/pending tables you think are needed
- All indexes, including new ones for write patterns:
  - `synset_relations(target_rowid)` — needed for inverse relation lookup
  - `sense_relations(target_rowid)` — same
  - Any others the write patterns require

**2.2 — Column reference**: For every table, a sub-section listing:
```
| Column          | Type    | Nullable | Default | Description                           |
|-----------------|---------|----------|---------|---------------------------------------|
| rowid           | INTEGER | NO       | auto    | SQLite implicit primary key           |
| id              | TEXT    | NO       | —       | WN-LMF entity ID                     |
| lexicon_rowid   | INTEGER | NO       | —       | FK → lexicons.rowid                   |
| ...             | ...     | ...      | ...     | ...                                   |
```

**2.3 — ER diagram**: Show all tables and their foreign key relationships. ASCII art is fine.

**2.4 — Divergences from `wn` schema**: A section explicitly listing every change from `wn/_db.py`'s schema and the rationale. Examples:
- "Added index on `synset_relations(target_rowid)` — needed for efficient inverse relation lookup during `add_synset_relation()`"
- "Added `edit_history` table — provides change tracking for batch editing workflows"
- "Added `updated_at` column to entity tables — supports change detection for incremental export"

**2.5 — Transaction model**: Document how transactions work:
- Every public API method that mutates data runs in a single transaction
- Compound operations (merge, split) are atomic — all-or-nothing
- How the `edit_history` table is populated within the same transaction
- Rollback behavior on validation failure

**2.6 — Migration strategy**: How schema changes are handled. Options: version check + recreate (like `wn`), or a migration table. State which you choose and why.

---

### Deliverable 3: Public API Specification

**Filename**: `api.md`

This is the contract the developer implements against. For every public method, provide:

```
### `method_name(param1: Type, param2: Type = default) -> ReturnType`

**Description**: One-line summary.

**Parameters**:
- `param1` — what it is, constraints
- `param2` — what it is, when to use the default

**Returns**: What the return value represents.

**Raises**:
- `ValidationError` — when X
- `EntityNotFoundError` — when Y

**Pre-conditions**: What must be true before calling.
**Post-conditions**: What is guaranteed after successful return.

**Example**:
```python
editor = WordnetEditor.from_wn("oewn:2024")
ss = editor.create_synset(pos="n", definition="A large feline")
```

**Notes**: Any edge cases, behavioral details, or cross-references.
```

Organize the spec by these sections:

**3.1 — WordnetEditor class** (the main entry point):
- `__init__(db_path: str | Path)` — open or create editor database
- `from_wn(lexicon: str, db_path: ...) -> WordnetEditor` — import from `wn` database
- `from_lmf(source: str | Path, db_path: ...) -> WordnetEditor` — import from WN-LMF XML
- `close()` — close database connection
- Context manager support (`__enter__`, `__exit__`)

**3.2 — Lexicon management**:
- `create_lexicon(id, label, language, email, license, version, ...)` 
- `update_lexicon(lexicon_id, **fields)`
- `get_lexicon(lexicon_id) -> LexiconModel`
- `list_lexicons() -> list[LexiconModel]`

**3.3 — Synset operations**:
- `create_synset(lexicon_id, pos, definition, ili=None, ...) -> SynsetModel`
- `update_synset(synset_id, **fields)`
- `delete_synset(synset_id, cascade=False)`
- `get_synset(synset_id) -> SynsetModel`
- `find_synsets(lemma=None, pos=None, definition_contains=None, ...) -> list[SynsetModel]`
- `merge_synsets(source_id, target_id, strategy=...) -> SynsetModel` — compound operation
- `split_synset(synset_id, sense_groups: list[list[str]]) -> list[SynsetModel]` — compound operation

**3.4 — Lexical entry operations**:
- `create_entry(lexicon_id, lemma, pos, forms=None, ...) -> EntryModel`
- `update_entry(entry_id, **fields)`
- `delete_entry(entry_id, cascade=False)`
- `get_entry(entry_id) -> EntryModel`
- `find_entries(lemma=None, pos=None, ...) -> list[EntryModel]`
- `add_form(entry_id, written_form, tags=None, ...)`
- `remove_form(entry_id, written_form)`

**3.5 — Sense operations**:
- `add_sense(entry_id, synset_id, ...) -> SenseModel`
- `remove_sense(sense_id)`
- `move_sense(sense_id, target_synset_id)` — compound operation
- `reorder_senses(entry_id, sense_id_order: list[str])`
- `get_sense(sense_id) -> SenseModel`

**3.6 — Definition and example operations**:
- `add_definition(synset_id, text, language=None, source_sense=None)`
- `update_definition(synset_id, definition_index, text)`
- `remove_definition(synset_id, definition_index)`
- `add_synset_example(synset_id, text, language=None)`
- `remove_synset_example(synset_id, example_index)`
- `add_sense_example(sense_id, text, language=None)`
- `remove_sense_example(sense_id, example_index)`

**3.7 — Relation operations** (CRITICAL — document automatic inverse behavior):
- `add_synset_relation(source_id, relation_type, target_id, auto_inverse=True)`
- `remove_synset_relation(source_id, relation_type, target_id, auto_inverse=True)`
- `add_sense_relation(source_id, relation_type, target_id, auto_inverse=True)`
- `remove_sense_relation(source_id, relation_type, target_id, auto_inverse=True)`
- `get_synset_relations(synset_id, relation_type=None) -> list[RelationModel]`
- `get_sense_relations(sense_id, relation_type=None) -> list[RelationModel]`

For each relation method, document:
- What happens when `auto_inverse=True` (default) — the inverse relation is created/removed in the same transaction
- What happens when the inverse already exists (idempotent? error?)
- What happens with symmetric relations (antonym: only one row, or two?)

**3.8 — ILI operations**:
- `link_ili(synset_id, ili_id)`
- `unlink_ili(synset_id)`
- `propose_ili(synset_id, definition)` — sets `ili="in"` and creates ILIDefinition
- `get_ili(synset_id) -> ILIModel | None`

**3.9 — Metadata operations**:
- `set_metadata(entity_type, entity_id, key, value)` — Dublin Core metadata
- `get_metadata(entity_type, entity_id) -> dict`
- `set_confidence(entity_type, entity_id, score: float)`

**3.10 — Validation**:
- `validate() -> list[ValidationResult]` — validate entire database
- `validate_synset(synset_id) -> list[ValidationResult]`
- `validate_entry(entry_id) -> list[ValidationResult]`
- `validate_relations() -> list[ValidationResult]` — check all inverse pairs, dangling refs

**3.11 — Import/Export**:
- `import_lmf(source: str | Path)` — add data from WN-LMF XML into editor DB
- `export_lmf(destination: str | Path, lexicon_ids: list[str] = None)`
- `commit_to_wn(db_path: str | Path = None)` — export and import into `wn`'s database

**3.12 — Change tracking**:
- `get_history(entity_type=None, entity_id=None, since=None) -> list[EditRecord]`
- `get_changes_since(timestamp) -> list[EditRecord]`

**3.13 — Batch operations**:
- `batch() -> BatchContext` — context manager for grouping operations into a single transaction
- Document how nested batches work (or don't)

---

### Deliverable 4: Domain Model Specification

**Filename**: `models.md`

Must contain:

**4.1 — Every dataclass the library uses**, with all fields, types, and docstrings:
- `LexiconModel`, `SynsetModel`, `EntryModel`, `SenseModel`, `FormModel`, `DefinitionModel`, `ExampleModel`, `RelationModel`, `ILIModel`, `EditRecord`, `ValidationResult`
- State which are **immutable** (returned from queries) vs **mutable** (used for updates)

**4.2 — Enums**:
- `PartOfSpeech` — n, v, a, r, s, c, p, x, u
- `SynsetRelationType` — all GWA synset relations from your table in Step A2
- `SenseRelationType` — all GWA sense relations
- `EditOperation` — CREATE, UPDATE, DELETE
- `ValidationSeverity` — ERROR, WARNING
- `ILIStatus` — active, deprecated, presupposed, proposed
- `MergeStrategy` — for synset merge behavior options

**4.3 — The inverse relation map**: A complete bidirectional mapping:
```python
SYNSET_RELATION_INVERSES: dict[SynsetRelationType, SynsetRelationType] = {
    SynsetRelationType.HYPERNYM: SynsetRelationType.HYPONYM,
    SynsetRelationType.HYPONYM: SynsetRelationType.HYPERNYM,
    SynsetRelationType.SIMILAR: SynsetRelationType.SIMILAR,  # symmetric
    ...
}
```
This must be exhaustive. Every relation in the GWA documentation must appear.

**4.4 — Mapping to database rows**: For each model, show how it maps to/from a database row (which table, which columns).

**4.5 — Mapping to `wn` types**: For each model, show the corresponding `wn` class and how conversion works (for query delegation).

**4.6 — Mapping to WN-LMF TypedDicts**: For each model, show the corresponding `wn.lmf` TypedDict and how conversion works (for import/export).

---

### Deliverable 5: Behavioral Specification

**Filename**: `behavior.md`

Document every "what happens when..." scenario as a rule with an ID. Organize by category.

**5.1 — Deletion cascading rules**:
- RULE-DEL-001: Deleting a synset with `cascade=False` raises `RelationError` if any senses reference it
- RULE-DEL-002: Deleting a synset with `cascade=True` removes all senses, all incoming/outgoing relations, all definitions, all examples
- RULE-DEL-003: Deleting an entry with `cascade=True` removes all its senses (which triggers sense-deletion rules)
- RULE-DEL-004: Deleting a sense removes all its sense_relations (both directions if auto_inverse)
- ... (complete this list)

**5.2 — Relation integrity rules**:
- RULE-REL-001: Adding a hypernym(A→B) with auto_inverse=True also creates hyponym(B→A)
- RULE-REL-002: If the inverse already exists, the operation is idempotent (no duplicate, no error)
- RULE-REL-003: Removing a hypernym(A→B) with auto_inverse=True also removes hyponym(B→A)
- RULE-REL-004: A synset cannot have a relation to itself (no self-loops) — or CAN it? Decide and document.
- RULE-REL-005: Relation types must be from the GWA standard set, or `other` with `dc:type` metadata
- ... (complete this list)

**5.3 — Compound operation rules**:

For `merge_synsets(source_id, target_id)`:
- RULE-MERGE-001: All senses from source are reassigned to target
- RULE-MERGE-002: All relations pointing TO source are redirected to target
- RULE-MERGE-003: All relations FROM source are moved to originate from target (deduplicating if target already has the same relation)
- RULE-MERGE-004: Definitions from source are appended to target's definitions
- RULE-MERGE-005: If source has ILI mapping and target does not, the mapping transfers. If both have ILI mappings, raise `ConflictError` unless a strategy is specified
- RULE-MERGE-006: Source synset is deleted after transfer
- RULE-MERGE-007: The entire operation is atomic (single transaction)

For `split_synset(synset_id, sense_groups)`:
- RULE-SPLIT-001: Each sense group becomes a new synset
- RULE-SPLIT-002: The original synset is deleted (or kept with remaining senses if not all senses are assigned)
- RULE-SPLIT-003: Relations from the original synset are... (you must decide: copied to all new synsets? Only to the first? Ask the caller to specify?)
- RULE-SPLIT-004: ILI mapping goes to... (you must decide)

For `move_sense(sense_id, target_synset_id)`:
- RULE-MOVE-001: If target already has a sense for the same word, raise `DuplicateEntityError`
- RULE-MOVE-002: Sense relations are preserved (they reference the sense, not the synset)
- RULE-MOVE-003: If source synset becomes empty after move, it is... (auto-deleted? left empty? configurable?)

**5.4 — ID generation rules**:
- RULE-ID-001: How new synset IDs are generated (format, uniqueness guarantee)
- RULE-ID-002: How new entry IDs are generated
- RULE-ID-003: How new sense IDs are generated
- RULE-ID-004: All IDs must begin with the lexicon ID prefix (WN-LMF requirement)

**5.5 — Validation rules** (blocking vs. warning):
- RULE-VAL-001: [ERROR] Every synset must have at least one definition
- RULE-VAL-002: [WARNING] Synsets with no senses (unlexicalized) are flagged
- RULE-VAL-003: [ERROR] Every hypernym must have a corresponding hyponym inverse
- RULE-VAL-004: [ERROR] Synset IDs must begin with lexicon ID prefix
- RULE-VAL-005: [ERROR] ILI proposals require ILIDefinition ≥ 20 characters
- RULE-VAL-006: [ERROR] No dangling references in relations (target must exist)
- RULE-VAL-007: [WARNING] Senses with confidence < 0.5
- ... (enumerate ALL rules, cross-referencing `wn/validate.py` findings)

**5.6 — Confidence score inheritance**:
- RULE-CONF-001: If a sense has no explicit confidence, it inherits from the lexicon
- RULE-CONF-002: Editing an entity does NOT automatically change its confidence
- RULE-CONF-003: Confidence is exported to WN-LMF only if it differs from the lexicon default

---

### Deliverable 6: Import/Export Pipeline Specification

**Filename**: `pipeline.md`

**6.1 — Import from WN-LMF XML**:
Step-by-step transformation:
1. Call `wn.lmf.load(source)` → get `LexicalResource` dict
2. For each `Lexicon` in the resource: INSERT into `lexicons` table
3. For each `LexicalEntry`: INSERT into `entries`, then `forms` (rank 0 for lemma, rank 1+ for forms), then `tags`, then `pronunciations`
4. For each `Synset`: INSERT into `synsets`, then `synset_definitions`, then `synset_examples`
5. For each `Sense`: INSERT into `senses`, then `sense_relations`, then `sense_examples`, then `counts`
6. For each `SynsetRelation`: INSERT into `synset_relations` (with `relation_types` normalization)
7. For each ILI: INSERT into `ilis`
8. All within a single transaction

Document the foreign key resolution order (which inserts must happen before which).

**6.2 — Import from `wn` database**:
Step-by-step:
1. Call `wn.export(lexicon, temp_file)` to get WN-LMF XML
2. Follow the XML import pipeline above
(Or alternatively: query `wn`'s database directly via `wn.Wordnet` API and construct rows. Document which approach you choose and why.)

**6.3 — Export to WN-LMF XML**:
Step-by-step transformation from editor.db rows → `LexicalResource` TypedDict → XML:
1. Query all lexicons (or specified subset)
2. For each lexicon, query entries, senses, synsets, relations
3. Construct `LexicalResource` dict following `wn.lmf` TypedDict structure
4. Call `wn.lmf.dump(resource, destination)`
5. Validate the output (call `wn.validate` on the file)

**6.4 — Commit to `wn` database**:
1. Export to temporary WN-LMF XML (6.3)
2. Call `wn.remove(lexicon)` for each lexicon being committed (if it exists in `wn`)
3. Call `wn.add(temp_xml)` or `wn.add_lexical_resource(resource_dict)`
4. Clean up temp file

Document: what happens if `wn.add()` fails validation? The editor.db is unchanged, but the `wn.remove()` already happened. How to handle this? (Suggest: export + validate first, only then remove + add.)

**6.5 — Round-trip fidelity**: 
List every piece of data that must survive import → edit → export without loss:
- All synset/entry/sense IDs
- All metadata (Dublin Core)
- All confidence scores
- Relation types including `other` + `dc:type`
- Form ordering (rank)
- Pronunciation data
- Syntactic behaviours

And anything that is intentionally NOT preserved (if any).

---

### Deliverable 7: Validation Rules Catalog

**Filename**: `validation.md`

A flat table:

```
| Rule ID      | Severity | Entity    | Description                                              | Source         |
|--------------|----------|-----------|----------------------------------------------------------|----------------|
| VAL-SYN-001  | ERROR    | Synset    | Must have at least one definition                        | WN-LMF 1.4    |
| VAL-SYN-002  | WARNING  | Synset    | No associated senses (unlexicalized)                     | Editor policy  |
| VAL-REL-001  | ERROR    | Relation  | Every asymmetric relation must have its inverse present  | Editor policy  |
| VAL-REL-002  | ERROR    | Relation  | Target entity must exist in the database                 | Referential    |
| VAL-ID-001   | ERROR    | All       | ID must begin with lexicon ID prefix                     | WN-LMF 1.4    |
| VAL-ILI-001  | ERROR    | ILI       | New ILI proposals require definition ≥ 20 characters     | WN-LMF 1.4    |
| ...          | ...      | ...       | ...                                                      | ...            |
```

Group by entity type. Mark which rules come from WN-LMF spec, which from `wn/validate.py`, and which are editor-specific policies.

---

### Deliverable 8: Project Structure & Packaging Spec

**Filename**: `packaging.md`

**8.1 — Directory layout**:
```
wordnet-editor/
├── pyproject.toml
├── README.md
├── LICENSE
├── src/
│   └── wordnet_editor/
│       ├── __init__.py
│       ├── editor.py
│       ├── db.py
│       ├── models.py
│       ├── relations.py
│       ├── importer.py
│       ├── exporter.py
│       ├── validator.py
│       ├── history.py
│       ├── exceptions.py
│       └── py.typed
└── tests/
    ├── conftest.py
    ├── test_editor.py
    ├── test_synsets.py
    ├── test_entries.py
    ├── test_senses.py
    ├── test_relations.py
    ├── test_import_export.py
    ├── test_validation.py
    ├── test_merge_split.py
    └── fixtures/
        └── (test WN-LMF XML files)
```

**8.2 — `pyproject.toml` specification**: 
- Package name: `wordnet-editor`
- Import name: `wordnet_editor`
- Python requires: `>=3.10`
- Dependencies: `wn>=1.0.0`
- Build system: `hatchling` or `setuptools` (state which)
- Include `py.typed` marker

**8.3 — Public API surface**: What `__init__.py` exports.

---

### Deliverable 9: Test Plan

**Filename**: `testplan.md`

Not test code. Structured scenarios:

```
### TP-SYN-001: Create synset with valid data
- Setup: Editor with one lexicon
- Action: create_synset(lexicon_id, pos="n", definition="A test concept")
- Verify: Synset exists in DB, has correct POS, has one definition, ID starts with lexicon prefix

### TP-REL-001: Add hypernym creates inverse hyponym
- Setup: Editor with two synsets A and B
- Action: add_synset_relation(A, "hypernym", B)
- Verify: synset_relations contains hypernym(A→B) AND hyponym(B→A)

### TP-MERGE-001: Merge synsets transfers senses
- Setup: Editor with synset A (senses s1, s2) and synset B (sense s3)
- Action: merge_synsets(A, B)
- Verify: B now has senses s1, s2, s3. A no longer exists. All relations from A now point from B.

### TP-RT-001: Import-edit-export round trip
- Setup: Import example WN-LMF XML
- Action: Edit a definition, add a relation, export to new XML
- Verify: New XML passes `wn.validate`. Re-importing produces equivalent data.
```

Cover every API method with at least one happy-path and one error-path scenario.

---

## 5. HOW TO APPROACH THE WORK

**Step 1**: Complete all reading (Phases A, B, C) before writing anything. Take notes in the format suggested above.

**Step 2**: Write Deliverable 4 (Domain Models) first. The models are the vocabulary everything else uses. Getting the types right first prevents cascading rewrites.

**Step 3**: Write Deliverable 2 (Database Schema) second. The schema is the physical implementation of the models. Having the models finalized makes the DDL straightforward.

**Step 4**: Write Deliverable 5 (Behavioral Spec) third. Now that you know the models and schema, you can rigorously define what happens in every scenario.

**Step 5**: Write Deliverable 3 (API Spec) fourth. The API is shaped by the models, schema, and behavioral rules.

**Step 6**: Write Deliverables 6, 7, 1, 8, 9 in any order — these are less interdependent.

**Step 7**: Cross-check. Every entity in the WN-LMF spec (A1) must appear in the models (D4), the schema (D2), the API (D3), and the validation catalog (D7). Every relation in the GWA docs (A2) must appear in the inverse map (D4). Every validation rule from `wn/validate.py` (B5) must appear in the catalog (D7). No gaps.

---

## 6. QUALITY CRITERIA FOR YOUR DELIVERABLES

A developer should be able to:

1. **Implement any module** by reading only its corresponding deliverable + the domain model spec
2. **Write the complete DDL** from the schema spec alone (no ambiguity about types, constraints, or indexes)
3. **Implement any API method** from the API spec alone (pre/post conditions, exceptions, and examples are sufficient)
4. **Handle every edge case** by looking up the relevant rule in the behavioral spec (no undocumented scenarios)
5. **Write tests** directly from the test plan (each scenario is precise enough to become a test function)
6. **Build a valid WN-LMF export** from the pipeline spec (the transformation steps are complete and ordered)

If any of these are not possible, the deliverable has a gap. Fill it.

---

## 7. WHAT YOU ARE NOT RESPONSIBLE FOR

- Implementation code (the developer writes this)
- Performance optimization (the developer profiles and optimizes)
- CI/CD pipeline configuration  
- Documentation website or Sphinx setup
- Internal helper functions or utility code
- Specific SQL query construction (you define the schema and the operations; the developer writes the queries)

Your job is to make every design decision, document every behavior, and leave zero ambiguity. The developer's job is to translate your specs into working Python code.

---

## 8. QUESTIONS TO RESOLVE DURING DESIGN

You will encounter decisions that require judgment. Here are the ones I've identified — resolve each in the appropriate deliverable and state your reasoning:

1. **Symmetric relation storage**: For symmetric relations (antonym, similar), do you store one row or two? One row is space-efficient but requires query-time symmetry expansion. Two rows are redundant but simplify queries. Decide and document in the behavioral spec.

2. **Self-referential relations**: Can a synset have a relation to itself? (e.g., `similar(A, A)`). Probably not, but state the rule explicitly.

3. **Empty synsets after sense removal**: If a synset has its last sense removed, is it auto-deleted, left as unlexicalized, or is the removal rejected? Decide and document.

4. **ID generation for new entities**: UUID-based? Sequential with prefix? Matching OEWN convention? The choice affects export compatibility. Decide and document.

5. **Multiple lexicons in one editor database**: Can the editor hold data for multiple lexicons simultaneously (e.g., editing AWN 4.0 while referencing OEWN)? This affects schema design significantly.

6. **Cross-lexicon relations**: Can relations span lexicons (synset in lexicon A → synset in lexicon B)? WN-LMF allows this via the ILI. Document the editor's stance.

7. **History granularity**: Does `edit_history` record field-level changes (old definition text → new definition text) or entity-level (synset X was modified)? Field-level is more useful but more complex.

8. **Validation timing**: Is validation run automatically on every mutation (fail-fast), on explicit `validate()` call only (batch-friendly), or configurable? Each has tradeoffs for batch editing performance.

Document your decision for each in the relevant deliverable, with a one-sentence rationale.