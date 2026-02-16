# Architecture Design Document

**Library**: `wordnet-editor`
**Version**: 1.0
**Date**: 2026-02-16

---

## 1.1 — System Overview

`wordnet-editor` is a pip-installable pure Python library that provides a complete programmatic API for editing WordNets. It maintains its own independent SQLite database — never mutating the `wn` library's store — and supports all CRUD operations on synsets, lexical entries, senses, definitions, examples, and relations. The library automatically maintains inverse relations, supports compound operations (merge, split, move), includes a validation engine, tracks edit history, and exports valid WN-LMF 1.4 XML that can be re-imported into `wn`. It targets single-user batch editing workflows.

---

## 1.2 — Architectural Principles

### Why an independent SQLite database

The `wn` library's database is append-only with zero UPDATE statements. It was designed for read-heavy query workloads, not editing. Mutating `wn`'s database directly would break its schema versioning, bypass its import pipeline, and risk corrupting data that other tools depend on. The editor's own database allows unconstrained UPDATE and DELETE operations while keeping `wn`'s store pristine.

### Why SQLite

SQLite provides ACID transactions (critical for compound operations like merge/split), referential integrity via foreign keys, rich indexing, and zero-configuration deployment. An ORM would add unnecessary abstraction over a schema we control completely. Flat files can't enforce referential integrity. In-memory dicts can't survive process crashes mid-edit. SQLite gives us all of these for free with no external dependencies.

### Why JSON metadata columns

Following `wn`'s established pattern (`META` type with JSON adapter/converter), metadata is stored as a JSON column on relevant tables. This avoids the combinatorial explosion of separate metadata tables for each entity type, keeps the schema compact, and metadata is rarely queried — it's read/written as a whole dict.

### Why single-file database

A single `.db` file is portable (email it, commit it, share it), simple to back up (copy one file), and requires no server configuration. This matches the single-user batch editing use case.

### Why `wn` as a runtime dependency

The `wn` library provides: (1) a tested WN-LMF XML parser (`wn.lmf.load()`), (2) a tested WN-LMF XML serializer (`wn.lmf.dump()`), (3) a validation engine (`wn.validate()`), (4) TypedDict definitions for all WN-LMF structures, and (5) a data import pipeline (`wn.add()`). Reimplementing any of these would be fragile and drift from the standard. The editor leverages all five.

### Why no custom query layer

After `commit_to_wn()`, the data lives in `wn`'s database where users can query it using `wn`'s rich API (`wn.synsets()`, `.hypernym_paths()`, `.shortest_path()`, etc.). The editor provides basic `get_*` and `find_*` methods for editing workflows, but delegates advanced querying to `wn`. This avoids reimplementing `wn`'s graph traversal algorithms.

---

## 1.3 — Component Diagram

```
┌─────────────────────────────────────────────────────────────┐
│                      wordnet-editor                          │
│                                                              │
│  ┌─────────────┐  ┌──────────────┐  ┌────────────────────┐  │
│  │  Editor API  │  │  Database    │  │  Import/Export      │  │
│  │  (editor.py) │──│  Layer       │  │  Pipeline           │  │
│  │             │  │  (db.py)     │  │  (importer.py,      │  │
│  │  Public API  │  │  Connection, │  │   exporter.py)      │  │
│  │  methods     │  │  DDL, CRUD   │  │                     │  │
│  └──────┬──────┘  └──────┬───────┘  └──────────┬──────────┘  │
│         │                │                      │             │
│  ┌──────┴──────┐  ┌──────┴───────┐  ┌──────────┴──────────┐  │
│  │  Domain     │  │  Validation  │  │  Change              │  │
│  │  Models     │  │  Engine      │  │  Tracking            │  │
│  │ (models.py) │  │(validator.py)│  │  (history.py)        │  │
│  └─────────────┘  └──────────────┘  └─────────────────────┘  │
│                                                              │
│  ┌──────────────┐  ┌──────────────┐                          │
│  │  Relations   │  │  Exceptions  │                          │
│  │(relations.py)│  │(exceptions.py│                          │
│  │  Inverse map │  │              │                          │
│  └──────────────┘  └──────────────┘                          │
└────────────┬──────────────────────────────┬──────────────────┘
             │                              │
             ▼                              ▼
      ┌─────────────┐              ┌──────────────┐
      │  editor.db  │              │  wn library  │
      │ (own SQLite)│              │ (read-only   │
      │             │              │  dependency) │
      └─────────────┘              └──────────────┘
```

### Component Responsibilities

| Component | File | Responsibility |
|-----------|------|----------------|
| Editor API | `editor.py` | The `WordnetEditor` class. All public methods. Orchestrates database, validation, history, and import/export. |
| Database Layer | `db.py` | Connection management, DDL initialization, low-level CRUD operations (INSERT, UPDATE, DELETE, SELECT). JSON adapter/converter for META columns. |
| Domain Models | `models.py` | Frozen dataclasses (`SynsetModel`, `EntryModel`, etc.), enums (`PartOfSpeech`, etc.), `ValidationResult`. |
| Relations | `relations.py` | `SYNSET_RELATION_INVERSES` and `SENSE_RELATION_INVERSES` dicts. Relation type validation. |
| Import Pipeline | `importer.py` | `import_from_lmf()` and `import_from_wn()`. Transforms `wn.lmf` TypedDicts into editor DB rows. |
| Export Pipeline | `exporter.py` | `export_to_lmf()` and `commit_to_wn()`. Transforms editor DB rows into `wn.lmf` TypedDicts. |
| Validation Engine | `validator.py` | Implements all rules from `validation.md`. Returns `list[ValidationResult]`. |
| Change Tracking | `history.py` | Records field-level changes in `edit_history` table. Provides query methods. |
| Exceptions | `exceptions.py` | Custom exception hierarchy. |

---

## 1.4 — Data Flow Diagrams

### Import Flow

```
WN-LMF XML file              wn library database
      │                              │
      ▼                              ▼
wn.lmf.load()               wn.export() → temp XML
      │                              │
      ▼                              ▼
LexicalResource dict         wn.lmf.load()
      │                              │
      └──────────┬───────────────────┘
                 ▼
         importer.py
         (iterate lexicons, entries,
          synsets, senses, relations)
                 │
                 ▼
           editor.db
         (INSERT rows into
          all entity tables)
                 │
                 ▼
         edit_history
         (CREATE records)
```

### Edit Flow

```
User calls editor.method()
         │
         ▼
    editor.py
    (validate params)
         │
         ▼
    db.py (within transaction)
    ┌─────────────────┐
    │ 1. Read current  │
    │    state         │
    │ 2. Validate      │
    │    constraints   │
    │ 3. UPDATE/INSERT/│
    │    DELETE rows   │
    │ 4. Handle auto-  │
    │    inverse       │
    │ 5. INSERT into   │
    │    edit_history   │
    └────────┬────────┘
             │ COMMIT
             ▼
        editor.db
        (state changed)
```

### Export Flow

```
    editor.db
         │
         ▼
    exporter.py
    (query all entities)
         │
         ▼
    LexicalResource TypedDict
    (construct from DB rows)
         │
         ├──────────────────────┐
         ▼                      ▼
    wn.lmf.dump()          wn.validate()
    (serialize to XML)     (check result)
         │                      │
         ▼                      │ errors? → raise ExportError
    WN-LMF XML file             │
         │                      │
         │  (commit_to_wn only) │
         ├──────────────────────┘
         ▼
    wn.remove() → wn.add()
         │
         ▼
    wn library database
    (updated)
```

---

## 1.5 — Module Structure

```
src/
└── wordnet_editor/
    ├── __init__.py          # Public API: WordnetEditor, all model classes, exceptions
    ├── editor.py            # WordnetEditor class (main entry point)
    ├── db.py                # Database connection, DDL, low-level CRUD
    ├── models.py            # Dataclasses and enums
    ├── relations.py         # Relation types, inverse mapping, validation
    ├── importer.py          # Import from XML and wn DB
    ├── exporter.py          # Export to XML and commit to wn
    ├── validator.py         # Validation engine
    ├── history.py           # Edit history recording and querying
    ├── exceptions.py        # Exception hierarchy
    └── py.typed             # PEP 561 typing marker
```

---

## 1.6 — Dependency Policy

**Runtime dependencies**:
- `wn >= 1.0.0` — WordNet library for LMF parsing, serialization, validation, and data import
- Python standard library only beyond that (sqlite3, json, pathlib, dataclasses, enum, tempfile)

**No other third-party dependencies.**

**Development dependencies** (not shipped):
- `pytest` — testing
- `mypy` — type checking
- `ruff` — linting

---

## 1.7 — Error Handling Strategy

### Exception Hierarchy

```
WordnetEditorError (base)
├── ValidationError          # Invalid data (bad POS, self-loop, invalid ID prefix)
├── EntityNotFoundError      # Entity doesn't exist in the database
├── DuplicateEntityError     # Entity with same ID already exists
├── RelationError            # Relation constraint violation (e.g., delete with references)
├── ConflictError            # Conflicting state (e.g., both synsets have ILI in merge)
├── ImportError              # Failed to import data (malformed XML, etc.)
├── ExportError              # Failed to export (validation errors in output)
└── DatabaseError            # Schema version mismatch, connection failure
```

### Principles

1. **Exceptions carry context**: Each exception includes the entity type, entity ID, and a human-readable message.
2. **No silent failures**: Every error condition raises an exception (mutations) or returns a result (validation).
3. **Transaction safety**: Exceptions from within a transaction trigger automatic rollback. The database is never left in a partially-modified state.
4. **Standard Python conventions**: `EntityNotFoundError` is not a subclass of `KeyError` — it's domain-specific. This prevents accidental catching by generic handlers.
