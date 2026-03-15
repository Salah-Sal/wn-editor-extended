# Baseline Metrics Report

**Project:** wn-editor-extended v1.0.0
**Date:** 2026-03-15
**Status:** Template — run `docs/audit/run_baseline.py` to populate actual values

---

## 1. Critical Operation Benchmarks

### 1.1 Single-Entity CRUD Operations

| Operation | Target | Measured | Notes |
|-----------|--------|----------|-------|
| `create_synset()` | < 10 ms | *(run benchmark)* | Includes: lexicon lookup, duplicate check, INSERT synset, INSERT definition, model build, history record |
| `get_synset()` | < 5 ms | *(run benchmark)* | `_build_synset_model`: 3-5 queries (synset+lexicon JOIN, ILI, proposed_ili, lexfile, unlexicalized check) |
| `update_synset(pos=...)` | < 10 ms | *(run benchmark)* | 1 read + 1 UPDATE + model rebuild + history |
| `delete_synset()` | < 50 ms | *(run benchmark)* | Single synset; cost depends on child count (senses, relations, definitions) |
| `create_entry()` | < 10 ms | *(run benchmark)* | Includes: INSERT entry + INSERT form (lemma) + INSERT entry_index + history |
| `add_sense()` | < 10 ms | *(run benchmark)* | ~14 queries total |
| `add_synset_relation()` | < 10 ms | *(run benchmark)* | 8-9 queries (includes auto-inverse) |

### 1.2 Search Operations

| Operation | Target | Measured | Result Count | Notes |
|-----------|--------|----------|-------------|-------|
| `find_synsets(pos="n")` | < 500 ms | *(run benchmark)* | *(count)* | N+1: 1 search + 5 queries per result |
| `find_synsets(lexicon="...")` | < 500 ms | *(run benchmark)* | *(count)* | Filtered by lexicon_rowid (indexed) |
| `find_synsets(definition_contains="...")` | < 2 s | *(run benchmark)* | *(count)* | **Full scan**: LIKE '%...%' on definitions |
| `find_entries(lemma="...")` | < 100 ms | *(run benchmark)* | *(count)* | Indexed via `form_index` on forms |
| `find_senses(synset_id="...")` | < 100 ms | *(run benchmark)* | *(count)* | Indexed via `sense_synset_rowid_index` |

### 1.3 Bulk Operations

| Operation | Target | Measured | Scale | Notes |
|-----------|--------|----------|-------|-------|
| Full import (`from_wn`) | < 60 s | *(run benchmark)* | *(synset count)* | Includes read from wn DB + bulk INSERT |
| Full export (`export_xml`) | < 30 s | *(run benchmark)* | *(synset count)* | Synsets batch-fetched; entries N+1 |
| `batch()` 1000 synset creates | > 500 ops/s | *(run benchmark)* | 1000 | Single transaction vs individual |
| Delete lexicon (cascade) | *(measure)* | *(run benchmark)* | *(total rows)* | Cascades across ~20 tables |

### 1.4 Batch vs Individual Comparison

| Mode | Operations | Time | Ops/sec | Speedup |
|------|-----------|------|---------|---------|
| Individual (auto-commit per op) | 100 synsets | *(measure)* | *(calc)* | 1.0x |
| `batch()` (single transaction) | 100 synsets | *(measure)* | *(calc)* | *(calc)* |

---

## 2. EXPLAIN QUERY PLAN Output

### 2.1 Indexed Range Scan (Expected: efficient)

```sql
EXPLAIN QUERY PLAN
SELECT s.id FROM synsets s WHERE s.lexicon_rowid = ?;
```

Expected: `SEARCH synsets USING INDEX ...` (uses the composite UNIQUE index on `(id, lexicon_rowid)`)

```
-- Actual output:
-- (run benchmark to populate)
```

### 2.2 Full Scan — Definition Search (Expected: inefficient)

```sql
EXPLAIN QUERY PLAN
SELECT synset_rowid FROM definitions WHERE definition LIKE '%word%';
```

Expected: `SCAN definitions` (no usable index for interior `LIKE` pattern)

```
-- Actual output:
-- (run benchmark to populate)
```

### 2.3 Multi-Table JOIN — Synset Relations (Expected: efficient)

```sql
EXPLAIN QUERY PLAN
SELECT sr.rowid, sr.source_rowid, sr.target_rowid, rt.type,
       tgt.id as target_id, src.id as source_id
FROM synset_relations sr
JOIN synsets tgt ON sr.target_rowid = tgt.rowid
JOIN synsets src ON sr.source_rowid = src.rowid
JOIN relation_types rt ON sr.type_rowid = rt.rowid
WHERE sr.source_rowid = ?;
```

Expected: `SEARCH synset_relations USING INDEX synset_relation_source_index`

```
-- Actual output:
-- (run benchmark to populate)
```

### 2.4 Indexed Composite Lookup — Edit History (Expected: efficient)

```sql
EXPLAIN QUERY PLAN
SELECT rowid, * FROM edit_history
WHERE entity_type = ? AND entity_id = ?
ORDER BY timestamp ASC;
```

Expected: `SEARCH edit_history USING INDEX edit_history_entity_index`

```
-- Actual output:
-- (run benchmark to populate)
```

### 2.5 Full Scan — Unfiltered History (Expected: problematic at scale)

```sql
EXPLAIN QUERY PLAN
SELECT rowid, * FROM edit_history ORDER BY timestamp ASC;
```

Expected: `SCAN edit_history USING INDEX edit_history_timestamp_index` (index-ordered full scan)

```
-- Actual output:
-- (run benchmark to populate)
```

### 2.6 4-Table JOIN — Sense Model Build (Expected: efficient for single sense)

```sql
EXPLAIN QUERY PLAN
SELECT s.rowid, s.id, s.entry_rank, s.synset_rank, s.metadata,
       e.id as entry_id, e.pos,
       syn.id as synset_id,
       l.id as lexicon_id
FROM senses s
JOIN entries e ON s.entry_rowid = e.rowid
JOIN synsets syn ON s.synset_rowid = syn.rowid
JOIN lexicons l ON s.lexicon_rowid = l.rowid
WHERE s.id = ?;
```

Expected: `SEARCH senses USING INDEX sense_id_index`

```
-- Actual output:
-- (run benchmark to populate)
```

---

## 3. Transaction & Lock Metrics

### 3.1 WAL Checkpoint Status

```sql
PRAGMA wal_checkpoint(PASSIVE);
-- Returns: (busy, log, checkpointed)
-- busy: 0 if no writer active
-- log: total frames in WAL
-- checkpointed: frames moved back to DB
```

| Metric | Value |
|--------|-------|
| WAL frames (log) | *(run PRAGMA)* |
| Checkpointed frames | *(run PRAGMA)* |
| Busy | *(run PRAGMA)* |
| WAL file size | *(measure -wal file)* |

### 3.2 Lock Contention Test

> This test requires two concurrent connections. Not covered by `run_baseline.py` — requires a dedicated concurrency test script.

| Scenario | Expected Result | Actual Result |
|----------|----------------|---------------|
| 2 readers, 0 writers | Both succeed (WAL) | *(test)* |
| 1 reader, 1 writer | Both succeed (WAL) | *(test)* |
| 2 writers, no busy_timeout | Second writer gets `SQLITE_BUSY` immediately | *(test)* |
| 2 writers, busy_timeout=5000 | Second writer retries up to 5s | *(test)* |
| batch() + concurrent reader | Reader not blocked | *(test)* |
| batch() + concurrent writer | Writer blocked until commit | *(test)* |

---

## 4. Database File & Page Metrics

```sql
PRAGMA page_count;
PRAGMA page_size;
PRAGMA freelist_count;
PRAGMA journal_mode;
PRAGMA cache_size;
PRAGMA wal_autocheckpoint;
```

| Metric | Value | Notes |
|--------|-------|-------|
| Page size | *(from PRAGMA)* | Default: 4096 bytes |
| Total pages | *(from PRAGMA)* | |
| Free pages | *(from PRAGMA)* | Pages reclaimable via VACUUM |
| DB size (calculated) | *(pages × page_size)* | |
| DB file (actual) | *(os.path.getsize)* | May differ from calculated due to partial pages |
| WAL file size | *(os.path.getsize on .db-wal)* | |
| SHM file size | *(os.path.getsize on .db-shm)* | Shared memory for WAL |
| Journal mode | *(from PRAGMA)* | Should be `wal` |
| Cache size | *(from PRAGMA)* | Default: -2000 (2MB) |
| WAL autocheckpoint | *(from PRAGMA)* | Default: 1000 pages |

---

## 5. Slow Query Log

The library does not have built-in query logging. To capture a slow query log:

### Option A: SQLite Trace Callback (Python)

```python
import time

def trace_callback(statement):
    # Note: this is called for every SQL statement
    print(f"[SQL] {statement}")

conn.set_trace_callback(trace_callback)
```

### Option B: Timed Wrapper

```python
import time
import functools

_original_execute = conn.execute

def timed_execute(sql, params=(), threshold_ms=10):
    start = time.perf_counter()
    result = _original_execute(sql, params)
    elapsed_ms = (time.perf_counter() - start) * 1000
    if elapsed_ms > threshold_ms:
        print(f"[SLOW {elapsed_ms:.1f}ms] {sql[:100]}")
    return result

conn.execute = timed_execute
```

### Known Slow Queries

| Query | Table(s) | Estimated Cost | Reason |
|-------|----------|---------------|--------|
| `definition LIKE '%...%'` | `definitions` | O(N) full scan | No FTS index; scans all definition text |
| `SELECT rowid, * FROM edit_history` (unfiltered) | `edit_history` | O(N) | Unbounded table, no LIMIT |
| `DELETE FROM lexicons WHERE rowid = ?` (large lexicon) | All tables | O(total rows) | CASCADE across ~20 tables |
| N × `_build_synset_model()` in `find_synsets()` | 5 tables | O(5N) queries | N+1 pattern |
| Export `_build_entry` loop | 8+ tables | O(entries × senses × relations) | Cascading N+1 |

---

## 6. Integrity Check

```sql
PRAGMA integrity_check;
-- Returns 'ok' if database is not corrupted
-- Returns error messages if issues found

PRAGMA foreign_key_check;
-- Returns rows with FK violations (should be empty)
```

| Check | Result | Notes |
|-------|--------|-------|
| `PRAGMA integrity_check` | *(run)* | |
| `PRAGMA foreign_key_check` | *(run)* | Should return 0 rows |
| `PRAGMA quick_check` | *(run)* | Faster subset of integrity_check |

---

## How to Run

```bash
# Run the baseline collection script
python docs/audit/run_baseline.py path/to/your/database.db

# Or against the experiment database
python docs/audit/run_baseline.py data/awn4_experiment.db
```

The script outputs:
- Formatted markdown to stdout (pipe to file with `> baseline_results.md`)
- JSON data to `baseline_results.json` in the same directory as the DB
