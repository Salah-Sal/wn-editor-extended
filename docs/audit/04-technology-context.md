# Technology Context Document

**Project:** wn-editor-extended v1.0.0
**Date:** 2026-03-15

---

## 1. Database Engine

| Property | Value |
|----------|-------|
| Engine | SQLite 3.x |
| Access method | Python `sqlite3` standard library module (C extension) |
| Server process | None — SQLite is an embedded, serverless database |
| File format | Single file (`.db`) + WAL journal (`.db-wal`) + shared memory (`.db-shm`) |
| Max DB size | 281 TB (theoretical); practical limit depends on filesystem |
| Concurrency model | Single-writer, multiple-reader (WAL mode) |

### Runtime Version Detection

```python
import sqlite3
print(sqlite3.sqlite_version)       # e.g., "3.45.1"
print(sqlite3.sqlite_version_info)   # e.g., (3, 45, 1)
print(sqlite3.version)               # Python module version
```

---

## 2. Python Environment

| Property | Value | Source |
|----------|-------|--------|
| Minimum Python | ≥ 3.10 | `pyproject.toml` `requires-python` |
| Tested versions | 3.10, 3.11, 3.12, 3.13 | `pyproject.toml` classifiers |
| Build backend | `hatchling` | `pyproject.toml` `[build-system]` |
| Package name | `wn-editor-extended` | `pyproject.toml` `[project]` |
| Version | `1.0.0` | `pyproject.toml` |
| License | MIT | `pyproject.toml` |

### Runtime Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `wn` | ≥ 1.0.0 | Source WordNet library (provides lexicons to import, has its own SQLite DB) |

### Dev Dependencies

| Package | Version | Purpose |
|---------|---------|---------|
| `pytest` | ≥ 7.0 | Test framework |
| `mypy` | ≥ 1.0 | Static type checking |
| `ruff` | ≥ 0.1 | Linting and formatting |

---

## 3. PRAGMA Configuration

### Explicitly Set (in `db.connect()`, `src/wordnet_editor/db.py` lines 335-346)

| PRAGMA | Value | When Set | Purpose |
|--------|-------|----------|---------|
| `foreign_keys` | `ON` | Every connection | Enforces referential integrity (46 FK constraints) |
| `journal_mode` | `WAL` | File-based DBs only | Write-Ahead Logging: concurrent reads, non-blocking writes |

### Not Set (SQLite Defaults Apply)

| PRAGMA | Default Value | Impact on Multi-Pipeline Use |
|--------|--------------|------------------------------|
| **`busy_timeout`** | **0 ms** | **CRITICAL GAP** — any lock contention immediately raises `SQLITE_BUSY` (`sqlite3.OperationalError: database is locked`). No retry, no backoff. |
| `cache_size` | -2000 (2 MB) | May be insufficient for large import operations. Each connection gets its own cache. |
| `synchronous` | NORMAL (in WAL) | Acceptable for most use cases. `FULL` would add durability at performance cost. |
| `wal_autocheckpoint` | 1000 pages (~4 MB) | Automatic checkpointing after 1000 pages of WAL accumulation. May be too frequent under heavy write load. |
| `temp_store` | 0 (FILE) | Temp tables/indexes stored on disk. `MEMORY` would speed up complex sorts. |
| `mmap_size` | 0 (disabled) | Memory-mapped I/O disabled. Enabling could improve read performance for large DBs. |
| `page_size` | 4096 bytes | Standard. 8192 or 16384 could improve performance for metadata-heavy workloads. |
| `locking_mode` | NORMAL | Each transaction acquires/releases locks. `EXCLUSIVE` would block all other connections. |

### Test-Only PRAGMA Overrides

In `tests/test_validation.py` (lines 88, 107, 215, 227, 311, 315):

```python
ed._conn.execute("PRAGMA foreign_keys = OFF")   # Temporary — allows FK-violating test data
ed._conn.execute("PRAGMA foreign_keys = ON")     # Restored immediately after
```

These overrides exist only in test fixtures to insert intentionally invalid data for validation testing.

---

## 4. Connection Management

### Connection Lifecycle

```
WordnetEditor.__init__(db_path)
    └── db.connect(db_path)
            ├── sqlite3.connect(db_path, detect_types=PARSE_DECLTYPES|PARSE_COLNAMES)
            ├── PRAGMA foreign_keys = ON
            ├── PRAGMA journal_mode = WAL  (if file-based)
            └── conn.row_factory = sqlite3.Row
    └── db.check_schema_version(conn)
    └── db.init_db(conn)
            └── conn.executescript(_DDL)    ← implicit COMMIT
            └── INSERT OR IGNORE meta rows
            └── INSERT OR IGNORE ili_statuses seed data
    └── self._conn = conn

    ... (use connection for all operations) ...

WordnetEditor.close()  /  WordnetEditor.__exit__()
    └── self._conn.close()
```

### Connection Properties

| Property | Value | Notes |
|----------|-------|-------|
| Pooling | **None** | One `sqlite3.Connection` per `WordnetEditor` instance |
| Thread safety | **Not safe** | `check_same_thread` not set (Python default: True for C builds) |
| Row factory | `sqlite3.Row` | All results accessible by column name |
| Type detection | `PARSE_DECLTYPES \| PARSE_COLNAMES` | Enables META type auto-conversion |
| Autocommit | Disabled (Python sqlite3 default) | Transactions managed by `_modifies_db` decorator and `batch()` |

### Connection Sharing Pattern

```
Pipeline A:  editor_a = WordnetEditor("shared.db")  ←── own connection
Pipeline B:  editor_b = WordnetEditor("shared.db")  ←── own connection
Pipeline C:  editor_c = WordnetEditor("shared.db")  ←── own connection
```

Each pipeline **must** create its own `WordnetEditor` instance. The connection is stored as `self._conn` and is never shared. The `db.connect()` function is not exported in the public API (`__init__.py`), so callers cannot easily create additional connections with the correct PRAGMA settings.

---

## 5. Transaction Model

### Default: Auto-Commit Per Mutation

Every method decorated with `@_modifies_db` (defined in `editor.py` lines 58-68) wraps the call in `with self._conn:`, which:

1. Issues an implicit `BEGIN` (deferred) before the first write statement
2. Calls `COMMIT` on successful return
3. Calls `ROLLBACK` on any exception

```python
@_modifies_db
def create_synset(self, ...):
    # This entire method body runs in a single transaction
    ...
```

### Batch: Grouped Transaction

The `batch()` context manager (`editor.py` lines 117-141) groups multiple mutations:

```python
with editor.batch():
    editor.create_synset(...)    # same transaction
    editor.add_sense(...)        # same transaction
    editor.add_synset_relation(...)  # same transaction
# COMMIT happens here (or ROLLBACK on exception)
```

**Implementation details:**
- Issues an explicit `BEGIN` (not `BEGIN IMMEDIATE` or `BEGIN EXCLUSIVE`)
- Supports nesting via `_batch_depth` counter; only outermost issues COMMIT/ROLLBACK
- No savepoints — inner batches are transparent
- Catches `BaseException` (including `KeyboardInterrupt`) for rollback

### Transaction Type: DEFERRED (Default)

All transactions use SQLite's default `DEFERRED` type:

- **Read phase**: No lock acquired. Reads can proceed concurrently.
- **First write**: Acquires a `RESERVED` lock (blocks other writers, allows readers).
- **Commit**: Promotes to `EXCLUSIVE` lock briefly, then releases.

**Concurrency risk**: Two concurrent deferred transactions can both enter the read phase, then one fails with `SQLITE_BUSY` when it tries to write. `BEGIN IMMEDIATE` would acquire the write lock upfront, eliminating this race.

### Design Document Discrepancy: SQLite Locking Claim

> **[SPEC] Finding D2:** `architecture.md` line 11 states: *"If two processes open the same `editor.db`, SQLite's file-level locking ensures writes are serialized (the second writer blocks until the first commits)."*
>
> This is **incorrect**. Without `PRAGMA busy_timeout` (which is NOT set — see Section 3 above), SQLite does NOT block the second writer. Instead, the second writer receives an immediate `SQLITE_BUSY` error (`sqlite3.OperationalError: database is locked`). Blocking behavior only occurs when `busy_timeout` is set to a non-zero value, causing SQLite to retry internally for up to that many milliseconds before raising the error.
>
> The design document gives false confidence about the library's concurrent safety. A developer reading the spec would reasonably assume that multi-process access "just works" — but the implementation will crash on the first write contention.

### Known Transaction Anomaly

`importer.py` line 1098 — `_apply_overrides()` calls `conn.commit()` directly:

```python
conn.execute(f"UPDATE lexicons SET {set_clauses} WHERE rowid = ?", params)
conn.commit()  # ← bare commit, bypasses with conn: wrapper
```

This can prematurely commit a partially-imported lexicon if called within a `with conn:` block.

Additionally, `db.init_db()` uses `conn.executescript(_DDL)` which issues an **implicit COMMIT** before running the DDL. If `init_db()` is called inside an active transaction, that transaction is silently committed.

---

## 6. SQL Access Pattern

### Raw SQL (No ORM)

The library uses raw SQL throughout — no ORM, no query builder, no abstraction layer.

| Method | Usage | Files |
|--------|-------|-------|
| `conn.execute(sql, params)` | All single-row operations | `editor.py`, `db.py`, `history.py`, `validator.py`, `importer.py`, `exporter.py` |
| `conn.executemany(sql, params_list)` | Bulk inserts during import | `importer.py` (synsets, proposed_ilis, unlexicalized_synsets) |
| `conn.executescript(sql_string)` | DDL application | `db.py` `init_db()` (once, at DB creation) |

### Parameterization

All queries use `?` placeholder parameterization — **no string interpolation of user values**. However, several methods use f-string interpolation for **column names** and **table names**:

| Location | Pattern | Risk |
|----------|---------|------|
| `editor.update_lexicon()` | `f"UPDATE lexicons SET {field} = ?"` | Low — `field` sourced from internal dict keys |
| `importer._apply_overrides()` | `f"UPDATE lexicons SET {set_clauses} WHERE rowid = ?"` | Low — keys from controlled override dict |
| `validator.py` (multiple) | `f"SELECT ... FROM {table} WHERE ..."` | Low — `table` from hardcoded list |
| `editor._resolve_entity_table()` | `f"SELECT ... FROM {table} WHERE id = ?"` | Low — fixed mapping dict |
| `history.query_history()` | `f"SELECT ... WHERE {where}"` | Low — `where` built from field name list |

All dynamic identifiers are sourced from code-internal dictionaries, not from user input. However, any future refactor that passes user-supplied field names into these paths would introduce SQL injection.

---

## 7. Custom Type System

### META Column Type

Defined in `db.py` lines 17-28:

```python
def _adapt_metadata(obj: dict) -> str:
    """dict → JSON string (for INSERT/UPDATE)"""
    return json.dumps(obj)

def _convert_metadata(data: bytes) -> dict | None:
    """JSON bytes → dict (for SELECT results)"""
    if data is None or data == b"":
        return None
    return json.loads(data)

sqlite3.register_adapter(dict, _adapt_metadata)
sqlite3.register_converter("META", _convert_metadata)
```

**Behavior:**
- Any Python `dict` passed as a SQL parameter is automatically serialized to JSON
- Any column declared with type `META` in the schema is automatically deserialized to `dict` on read
- Activation requires `detect_types=PARSE_DECLTYPES | PARSE_COLNAMES` on the connection

**13 columns** use this type (all named `metadata`): `ilis`, `proposed_ilis`, `lexicons`, `entries`, `synsets`, `synset_relations`, `definitions`, `synset_examples`, `senses`, `sense_relations`, `sense_synset_relations`, `sense_examples`, `counts`.

**Caveat:** `edit_history.old_value` and `edit_history.new_value` store JSON as `TEXT` (not `META`), so they are NOT auto-converted. Code in `history.py` uses `json.dumps()` explicitly for writes, and callers must `json.loads()` manually for reads.

**External tool impact:** Tools like `sqlite3` CLI, DB Browser for SQLite, or DBeaver will see `META` columns as raw JSON text strings. The type name `META` is a custom alias that only the Python adapter/converter system understands.

---

## 8. Deployment Model

```
┌─────────────────────────────────────────────────────┐
│  NLP Pipeline Process                                │
│                                                      │
│  import wn                                           │
│  from wordnet_editor import WordnetEditor            │
│                                                      │
│  wn.download("oewn:2024")    ← downloads to wn's DB │
│  editor = WordnetEditor.from_wn("oewn:2024", "x.db")│
│                                                      │
│  with editor.batch():                                │
│      editor.create_synset(...)                       │
│      editor.add_sense(...)                           │
│                                                      │
│  editor.export_xml("output.xml")                     │
│  editor.close()                                      │
└───────────┬─────────────────────────────────────────┘
            │
            ▼
┌──────────────────────┐
│  x.db  (SQLite file) │  ← single file, portable, no server
│  x.db-wal            │  ← WAL journal (concurrent reads)
│  x.db-shm            │  ← shared memory map
└──────────────────────┘
```

**Deployment characteristics:**
- **Zero infrastructure**: No database server, no connection strings, no network
- **Portable**: Single file + WAL files, can be `scp`'d or committed to Git LFS
- **Embedded**: Library is imported as a Python package (`pip install wn-editor-extended`)
- **No authentication**: SQLite has no built-in access control; file permissions are the only barrier
- **No encryption**: Data stored in plaintext (SQLite Encryption Extension not used)

---

## 9. External Dependency: `wn` Library

The `wn` package (≥ 1.0.0) serves as the **source data provider** for import operations:

| Aspect | Detail |
|--------|--------|
| Role | Provides WordNet lexicons (OEWN, etc.) via `wn.download()` and `wn.lexicons()` |
| Own database | `~/.local/share/wn/wn.db` (or platform-specific XDG path) |
| Import pathway | `WordnetEditor.from_wn()` reads from wn's SQLite DB via bulk SQL (`wn._db` private API) or XML export fallback |
| Coupling level | **Tight** (bulk path) — reads directly from wn's internal schema. **Loose** (XML path) — uses wn's public export API |
| Version sensitivity | The bulk import path uses wn's private `_db` module and undocumented table structure. A wn library update could break this path silently. |

---

## 10. Recommended Configuration Changes for Multi-Pipeline

These are not yet implemented — they represent the audit's expected recommendations:

| PRAGMA | Current | Recommended | Rationale |
|--------|---------|-------------|-----------|
| `busy_timeout` | 0 | 5000-30000 ms | Retry on contention instead of immediate failure |
| `journal_mode` | WAL | WAL (keep) | Required for concurrent reads |
| `cache_size` | -2000 (2MB) | -8000 (8MB) | Larger cache for import/export bulk operations |
| `synchronous` | NORMAL | NORMAL (keep) | Good balance of durability and performance |
| `wal_autocheckpoint` | 1000 | 5000-10000 | Reduce checkpoint frequency under heavy write load |
| Transaction type | DEFERRED | IMMEDIATE | Acquire write lock upfront to avoid TOCTOU races |
| `mmap_size` | 0 | 268435456 (256MB) | Memory-mapped reads for large databases |
