# Multi-Pipeline Concurrency Test Report

**Date:** 2026-03-15 10:48:09
**Python:** 3.11.13
**SQLite:** 3.51.2
**Platform:** darwin (macOS, Apple Silicon)
**busy_timeout:** 5000ms
**Transaction type:** `BEGIN IMMEDIATE` (batch), `BEGIN DEFERRED` (single mutations via `with conn:`)

---

## Summary

| # | Scenario | Result | Key Observation |
|---|----------|--------|-----------------|
| 1 | Two pipelines import SAME lexicon | 1 PASS, 1 ERROR | UNIQUE constraint correctly prevents duplicate import |
| 2 | Two pipelines import DIFFERENT lexicons | ALL PASS | WAL mode handles concurrent writes to separate lexicons |
| 3 | Writer imports while reader queries | ALL PASS | WAL snapshot isolation works — reader sees pre-import state |
| 4 | Two pipelines create 20 synsets each (ID race) | ALL PASS | No ID collision — `BEGIN IMMEDIATE` serialized the batches |
| 5 | Two pipelines create entries with overlapping lemmas | ALL PASS | Suffix dedup (`-2`) resolved overlapping IDs correctly |
| 6 | Two pipelines do full CRUD batch simultaneously | ALL PASS | Atomic batches serialized cleanly |
| 7 | Three concurrent batch writers (stress) | ALL PASS | 3-way contention resolved within <6ms per pipeline |
| 8 | Import then immediate export from another process | ALL PASS | Exporter got complete data (timing-dependent) |
| 9 | Concurrent updates to DIFFERENT synsets | ALL PASS | Non-conflicting writes serialize correctly |
| 10 | Concurrent updates to SAME synset | ALL PASS | Last-writer-wins; both updates recorded in history |

**Overall: 9 of 10 scenarios fully passed. Scenario 1's "error" is expected behavior (duplicate prevention).**

---

## Scenario 1: Two pipelines import the SAME LMF file simultaneously

> Both Pipeline A and B try to import minimal.xml (lexicon 'test-min') into the same DB at the same time. Expected: one succeeds, one gets DuplicateEntityError.

### Worker Results

| Worker | Status | Time (s) | Detail |
|--------|--------|----------|--------|
| S1-Pipeline-A | PASS | 0.1375 | Imported OK. Lexicons: ['test-min'] |
| S1-Pipeline-B | ERROR | 0.1381 | IntegrityError: UNIQUE constraint failed: lexicons.specifier |

### Post-Check

```json
{
  "lexicon_count": 1,
  "lexicon_ids": ["test-min"],
  "synset_count": 1
}
```

### Observation

**Result: EXPECTED BEHAVIOR** — The `UNIQUE` constraint on `lexicons.specifier` correctly prevented the second pipeline from creating a duplicate lexicon. Pipeline B received an `IntegrityError`, which is the correct response.

**However, the error type is wrong.** Pipeline B got a raw `sqlite3.IntegrityError` rather than the library's `DuplicateEntityError`. This means the import code path (`importer.py`) doesn't catch `IntegrityError` on the lexicon insert and wrap it in a user-friendly exception. A pipeline consuming this library would need to catch `IntegrityError` directly, which leaks the SQLite abstraction.

**Audit finding confirmed:** The error handling is functional but not ergonomic. The caller receives a low-level database exception instead of a domain-specific one.

---

## Scenario 2: Two pipelines import DIFFERENT lexicons simultaneously

> Pipeline A imports minimal.xml (test-min), Pipeline B imports full_features.xml (test-full). No ID conflicts expected. Tests WAL concurrent write capability.

### Worker Results

| Worker | Status | Time (s) | Detail |
|--------|--------|----------|--------|
| S2-Pipeline-A | PASS | 0.075 | Imported OK. Lexicons: ['test-min'] |
| S2-Pipeline-B | PASS | 0.0772 | Imported OK. Lexicons: ['test-min', 'test-full'] |

### Post-Check

```json
{
  "lexicon_count": 2,
  "lexicon_ids": ["test-min", "test-full"],
  "synset_count": 6
}
```

### Observation

**Result: CLEAN PASS** — Both imports completed successfully within ~75ms each. The `busy_timeout=5000ms` combined with `BEGIN IMMEDIATE` correctly serialized the two write transactions. Pipeline B's result shows it can see Pipeline A's lexicon after A committed, confirming WAL read-after-write visibility.

**Key insight:** Both pipelines finished in nearly identical time (~75ms), suggesting minimal contention. The second writer likely waited briefly for the first to commit, but the wait was sub-millisecond (within the 5000ms timeout). This is the happy path for multi-pipeline deployment: different lexicons, no conflicts.

**Total data: 1 synset (minimal) + 5 synsets (full_features) = 6 synsets.** All data intact.

---

## Scenario 3: One pipeline writes while another reads

> Writer imports full_features.xml while Reader queries find_synsets(). WAL mode should allow non-blocking reads. Reader may see pre-import or post-import state (snapshot isolation).

### Worker Results

| Worker | Status | Time (s) | Detail |
|--------|--------|----------|--------|
| S3-Reader | PASS | 0.0008 | Read 1 synsets |
| S3-Writer | PASS | 0.0724 | Imported OK. Lexicons: ['test-min', 'test-full'] |

### Post-Check

```json
{
  "synset_count": 6
}
```

### Observation

**Result: WAL SNAPSHOT ISOLATION CONFIRMED** — The Reader started 50ms after the Writer but completed in 0.8ms — far before the Writer finished (72ms). The Reader saw only 1 synset (the pre-seeded minimal lexicon), not the 6 synsets that existed after the Writer committed.

This demonstrates WAL mode's snapshot isolation: the Reader got a consistent snapshot of the database as it existed when the Reader's transaction began. The Writer's uncommitted changes were invisible to the Reader. This is exactly the correct behavior for multi-pipeline operation.

**Post-check shows 6 synsets** because it ran after both processes completed. The Reader's 1-synset result is a point-in-time snapshot, not stale data — it's the correct answer at the time the read executed.

---

## Scenario 4: Two pipelines create synsets concurrently (ID generation race)

> Both pipelines create 20 synsets each in the same lexicon. Tests `_generate_synset_id` MAX(CAST) race condition (PP7-A). Expected: one pipeline may get SQLITE_BUSY or IntegrityError due to ID collision.

### Worker Results

| Worker | Status | Time (s) | Detail |
|--------|--------|----------|--------|
| S4-Pipeline-B | PASS | 0.002 | Created 20 synsets |
| S4-Pipeline-A | PASS | 0.0037 | Created 20 synsets |

### Post-Check

```json
{
  "total_synsets": 41,
  "unique_ids": 41,
  "duplicate_ids": []
}
```

### Observation

**Result: PASS — but misleading.** Both pipelines created all 20 synsets with zero collisions. 41 total = 1 (seed) + 20 + 20. No duplicate IDs.

**Why no race condition?** The `BEGIN IMMEDIATE` fix (PP1-B) is the key. Because each `batch()` call now acquires the write lock immediately, the two pipelines' batches were fully serialized — Pipeline B ran its entire batch first (2.0ms), then Pipeline A ran its batch (3.7ms). The `MAX(CAST(...))` ID generator worked correctly because only one writer was active at any time.

**The race condition (PP7-A) is effectively mitigated by `BEGIN IMMEDIATE` when all synset creation happens inside a `batch()` context.** However, if synsets were created *outside* a batch (using individual `@_modifies_db` calls with `DEFERRED` transactions), the race could still occur because `_modifies_db` uses `with self._conn:` which is `DEFERRED`.

**Residual risk:** The `MAX(CAST)` pattern is safe only as long as all concurrent writes use `batch()`. Single-statement mutations via `_modifies_db` still use `DEFERRED` and could theoretically race.

---

## Scenario 5: Two pipelines create entries with overlapping lemmas

> Pipeline A creates word0-word9, Pipeline B creates word5-word14. Lemmas word5-word9 overlap — both pipelines try to create the same entry IDs. Tests `_generate_entry_id` TOCTOU race (PP7-B).

### Worker Results

| Worker | Status | Time (s) | Detail |
|--------|--------|----------|--------|
| S5-Pipeline-B | PASS | 0.0021 | Created: ['test-min-word5-n', ..., 'test-min-word9-n'] |
| S5-Pipeline-A | PASS | 0.0031 | Created: ['test-min-word0-n', ..., 'test-min-word4-n'] |

### Post-Check

```json
{
  "total_entries": 21,
  "unique_ids": 21,
  "entry_ids": [
    "test-min-cat-n",
    "test-min-word0-n", "test-min-word1-n", "test-min-word2-n",
    "test-min-word3-n", "test-min-word4-n",
    "test-min-word5-n", "test-min-word5-n-2",
    "test-min-word6-n", "test-min-word6-n-2",
    "test-min-word7-n", "test-min-word7-n-2",
    "test-min-word8-n", "test-min-word8-n-2",
    "test-min-word9-n", "test-min-word9-n-2",
    "test-min-word10-n", "test-min-word11-n",
    "test-min-word12-n", "test-min-word13-n", "test-min-word14-n"
  ]
}
```

### Observation

**Result: PASS with suffix deduplication.** All 21 entries (1 seed + 10 + 10) have unique IDs. For the 5 overlapping lemmas (word5-word9), Pipeline B got the base IDs (`test-min-word5-n`) and Pipeline A got suffixed IDs (`test-min-word5-n-2`).

**The dedup mechanism works correctly** under serialized batches. Because `BEGIN IMMEDIATE` serialized the writes, Pipeline B's batch committed first, then Pipeline A's batch saw the existing entries and generated `-2` suffixes. No collisions.

**Note:** The `-2` suffix convention is functional but creates a semantic issue for consumers. `test-min-word5-n` and `test-min-word5-n-2` are both entries for the lemma "word5" with POS "n" — they represent the *same word* created by different pipelines. Without `session_id` tracking or a merge mechanism, a consumer cannot distinguish whether these are intentional duplicates or accidental race artifacts.

**This confirms the D12 finding:** if multiple pipelines create entries for the same lemma, the system creates separate entries with suffixed IDs rather than detecting the conflict and merging or rejecting.

---

## Scenario 6: Two pipelines do full batch CRUD simultaneously

> Each pipeline creates 2 synsets, 1 entry, 1 sense, and 1 relation in a batch. Tests BEGIN IMMEDIATE contention and overall atomicity.

### Worker Results

| Worker | Status | Time (s) | Detail |
|--------|--------|----------|--------|
| S6-Pipeline-A | PASS | 0.002 | synset:test-min-00000002-n, synset:test-min-00000003-n, entry:test-min-word1a-n, sense, relation |
| S6-Pipeline-B | PASS | 0.0034 | synset:test-min-00000004-n, synset:test-min-00000005-n, entry:test-min-word2a-n, sense, relation |

### Post-Check

```json
{
  "synset_count": 5,
  "entry_count": 3
}
```

### Observation

**Result: CLEAN PASS** — Both pipelines completed full CRUD operations (create synset → create entry → add sense → add relation) atomically. The synset IDs are sequential and non-overlapping: A got `00000002-n`/`00000003-n`, B got `00000004-n`/`00000005-n`. This confirms `BEGIN IMMEDIATE` properly serialized the write-heavy batches.

**Atomicity verified:** 5 synsets (1 seed + 2 + 2) and 3 entries (1 seed + 1 + 1) are exactly correct. No partial commits, no orphaned entities.

**Timing:** Pipeline A took 2.0ms, Pipeline B took 3.4ms. The ~1.4ms difference is the write lock wait time — well within the 5000ms `busy_timeout`.

---

## Scenario 7: Three concurrent batch writers (stress test)

> Three pipelines each create synsets, entries, senses, and relations simultaneously. Tests whether busy_timeout=5000ms is sufficient for 3-way write contention.

### Worker Results

| Worker | Status | Time (s) | Detail |
|--------|--------|----------|--------|
| S7-Pipeline-A | PASS | 0.0041 | synsets 00000002-n, 00000003-n |
| S7-Pipeline-B | PASS | 0.0029 | synsets 00000004-n, 00000005-n |
| S7-Pipeline-C | PASS | 0.0037 | synsets 00000006-n, 00000007-n |

### Post-Check

```json
{
  "synset_count": 7,
  "entry_count": 4,
  "history_count": 19
}
```

### Observation

**Result: CLEAN PASS under 3-way contention.** All three pipelines completed in under 6ms each. The 5000ms `busy_timeout` is massively oversized for this workload — real contention was sub-millisecond.

**History tracking:** 19 history entries = 1 (seed synset CREATE) + 3×(2 synset CREATEs + 1 entry CREATE + 1 sense CREATE + 1 relation synset_relation + 1 inverse relation) = 1 + 3×6 = 19. All mutations were correctly audited.

**Sequential ID assignment:** A got IDs 2-3, B got 4-5, C got 6-7. The `BEGIN IMMEDIATE` lock ensured each batch saw the previous batch's commits before generating IDs.

**Scalability note:** This test used small batches (~6 operations each). Real-world pipelines creating thousands of synsets per batch would hold the write lock longer, increasing contention. The 5000ms timeout may need to increase for production workloads with large imports.

---

## Scenario 8: Import then immediate export from another process

> One process imports full_features.xml, another exports after a 100ms delay. Tests WAL snapshot isolation — exporter may get empty DB or partial/full import depending on timing.

### Worker Results

| Worker | Status | Time (s) | Detail |
|--------|--------|----------|--------|
| S8-Importer | PASS | 0.0703 | Imported OK. Lexicons: ['test-full'] |
| S8-Exporter | PASS | 0.0723 | Exported 3286 bytes |

### Post-Check

```json
{
  "export_exists": true,
  "export_size_bytes": 3286
}
```

### Observation

**Result: PASS — Exporter got complete data.** The import took ~70ms and the exporter started after a 100ms delay, so the import had already committed by the time the export began. The 3286-byte export file contains the full `test-full` lexicon.

**Timing dependency:** This scenario's success is timing-dependent. If the import took longer than 100ms (e.g., importing a 100K-synset lexicon), the exporter would have started during the import and received a WAL snapshot of the pre-import state (potentially empty). This is correct WAL behavior but could surprise callers expecting to see the import's data.

**Production implication:** Pipelines that import-then-export should use the same `WordnetEditor` instance (guaranteeing read-your-own-writes) rather than separate processes. If separate processes are needed, the exporter should verify the expected lexicon exists before exporting.

---

## Scenario 9: Concurrent updates to DIFFERENT synsets in same lexicon

> Pipeline A updates test-full-00000001-n metadata, Pipeline B updates test-full-00000002-n metadata. No logical conflict — tests write serialization.

### Worker Results

| Worker | Status | Time (s) | Detail |
|--------|--------|----------|--------|
| S9-Pipeline-B | PASS | 0.0017 | Updated test-full-00000002-n |
| S9-Pipeline-A | PASS | 0.0028 | Updated test-full-00000001-n |

### Post-Check

```json
{
  "test-full-00000001-n_metadata": {"source": "pipeline-A", "confidence": 0.9},
  "test-full-00000002-n_metadata": {"source": "pipeline-B", "confidence": 0.8}
}
```

### Observation

**Result: CLEAN PASS** — Both updates succeeded. Each synset has the correct metadata from its respective pipeline. The writes were serialized by `_modifies_db`'s `with self._conn:` (DEFERRED transactions, but since each is a single UPDATE there's no upgrade deadlock risk).

**Note:** These are single-statement mutations (not batches), so they use `DEFERRED` transactions via `_modifies_db`. For single-statement writes, DEFERRED is safe because the transaction acquires the write lock on the first (and only) statement. The deadlock risk only exists with multi-statement DEFERRED transactions.

---

## Scenario 10: Concurrent updates to the SAME synset (true write race)

> Both pipelines update metadata on test-full-00000001-n. Last writer wins. Tests whether both writes succeed (serialized by busy_timeout) or one fails. Also checks if history captures both updates.

### Worker Results

| Worker | Status | Time (s) | Detail |
|--------|--------|----------|--------|
| S10-Pipeline-A | PASS | 0.0013 | metadata={'source': 'pipeline-A', 'version': 1} |
| S10-Pipeline-B | PASS | 0.0025 | metadata={'source': 'pipeline-B', 'version': 2} |

### Post-Check

```json
{
  "final_metadata": {"source": "pipeline-B", "version": 2},
  "history_entries": 3,
  "history_detail": [
    {"op": "UPDATE", "field": "metadata", "new": "\"{'source': 'pipeline-A', 'version': 1}\""},
    {"op": "UPDATE", "field": "metadata", "new": "\"{'source': 'pipeline-B', 'version': 2}\""}
  ]
}
```

### Observation

**Result: LAST-WRITER-WINS, both writes recorded.** Both pipelines successfully updated the same synset. Pipeline A wrote first (1.3ms), Pipeline B wrote second (2.5ms). The final metadata is Pipeline B's value, which overwrote Pipeline A's.

**History is complete:** Both updates appear in `edit_history` in chronological order. The `session_id` field (D10 fix) would allow distinguishing which pipeline made which change — but we didn't pass `session_id` in this test, so both entries lack attribution.

**Concurrency semantics: NO CONFLICT DETECTION.** The library uses a simple last-writer-wins model with no optimistic locking (version column, CAS, or ETag). Pipeline B blindly overwrote Pipeline A's metadata without knowing Pipeline A had just changed it. For metadata fields this is acceptable, but for structural changes (e.g., two pipelines both trying to `merge_synsets` or `split_synset`) this could cause data corruption.

**The lack of optimistic locking is a design-level limitation** — not a bug, but a known gap for multi-pipeline deployment. The `edit_history` provides forensic traceability after the fact, but not real-time conflict prevention.

---

## Overall Conclusions

### What Works Well

1. **`busy_timeout=5000ms`** (PP1-A fix) — eliminates `SQLITE_BUSY` errors across all scenarios
2. **`BEGIN IMMEDIATE`** (PP1-B fix) — serializes batch writes, prevents DEFERRED upgrade deadlocks
3. **WAL snapshot isolation** — readers never block writers, writers never block readers
4. **`UNIQUE` constraints** — prevent duplicate lexicons (S1) and duplicate entity IDs (S4, S5)
5. **`edit_history`** — both updates recorded in S10, providing audit traceability
6. **Entry ID suffix dedup** — handles overlapping lemma creation gracefully (S5)

### What Doesn't Work / Gaps

1. **No conflict detection** — last-writer-wins on same entity with no optimistic locking (S10)
2. **Raw `IntegrityError` leaks** — S1 should raise `DuplicateEntityError`, not raw `sqlite3.IntegrityError`
3. **Duplicate entry creation** — overlapping lemmas create separate entries with `-2` suffix instead of detecting the conflict (S5, relates to D12)
4. **`_modifies_db` still uses DEFERRED** — single-statement mutations are safe for now, but multi-statement `@_modifies_db` methods could deadlock under contention (PP1-C)
5. **No `session_id` passed by default** — history entries lack pipeline attribution unless callers explicitly provide it
6. **Timing-dependent export** — S8 passed only because import finished before export started; no coordination mechanism exists

### Recommendations

| Priority | Fix | Effort |
|----------|-----|--------|
| P0 | Wrap `IntegrityError` on lexicon insert in `DuplicateEntityError` | Small |
| P0 | Add `session_id` parameter to all public mutation methods | Medium |
| P1 | Add optimistic locking (version column) for concurrent update safety | Medium |
| P1 | Change `_modifies_db` to use `BEGIN IMMEDIATE` | Small |
| P2 | Add coordination mechanism for import-then-export workflows | Design |
| P2 | Detect and merge/reject duplicate entries from different pipelines | Design |