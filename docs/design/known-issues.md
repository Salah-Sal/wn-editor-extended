# Known Issues & Technical Debt

Validated against the source code on 2026-02-26. Each item includes the
affected location, severity, and context so it can be addressed independently.

Items are ordered by severity (high → low).

---

## 1. ~~Entity ID Lookups Assume Global Uniqueness~~ ✅ Fixed

**Severity:** High — latent bug in multi-lexicon use, the library's intended
use case.

**Status:** Fixed (2026-02-27). See `tests/test_lexicon_versioning.py` (26
tests).

**Original problem:** The DB schema defines composite uniqueness (`UNIQUE(id,
lexicon_rowid)`) allowing same-ID entities across lexicons, but every lookup
helper in `db.py` queried by bare `id` alone. When two versions of a lexicon
coexisted, mutations hit all versions and reads returned arbitrary rows.

**Fix — three-layer defence:**

1. **Layer 1 — Prevention:** `create_lexicon()` and `import_lmf()` now reject
   a same-ID different-version lexicon while one already exists. Users must
   delete the old version first. This prevents the dangerous state from ever
   occurring.

2. **Layer 2 — Hardened SQL:** Six mutation methods (`update_lexicon`,
   `delete_lexicon`, `update_synset`, `delete_synset`, `update_entry`,
   `delete_entry`) changed from `WHERE id = ?` to `WHERE rowid = ?`, targeting
   the exact row returned by the initial lookup. Defensive even with Layer 1.

3. **Layer 3 — Specifier support:** All lexicon-accepting APIs now accept the
   `"id:version"` specifier format (e.g., `"awn:1.0"`) in addition to bare
   IDs. `get_lexicon_rowid`/`get_lexicon_row` in `db.py` try specifier first,
   then fall back to bare ID. The validator's `_lex_filter` and the exporter
   resolve via the same helper, eliminating ambiguous subqueries.

4. **Layer 4 — Model enhancement:** `LexiconModel.specifier` property returns
   `"id:version"` for programmatic use.

**Files changed:** `editor.py`, `db.py`, `importer.py`, `validator.py`,
`exporter.py`, `models.py`.

**Design decision:** Full simultaneous multi-version coexistence was rejected
because it would require threading lexicon context through every entity-level
API — a v2.0 architectural change. The "one version at a time" approach is
complete for the intended AWN workflow.

---

## 2. Metadata Type Adapter Is Unreliable

**Severity:** High — systemic fragility across the whole codebase.

**Description:** `db.py:17-28` registers a `META` SQLite type adapter/converter
and `db.py:340` enables `PARSE_DECLTYPES`. This should auto-deserialise
metadata columns into dicts. But automatic conversion doesn't reliably fire
across all query shapes (JOINs, subqueries, aliased columns), so the codebase
contains **~24 manual fallback guards**:

```python
meta = row["metadata"]
if isinstance(meta, str):
    meta = json.loads(meta)
```

These appear across:
- `editor.py` — 12 occurrences
- `exporter.py` — ~11 occurrences
- `validator.py` — 1 occurrence

The adapter gives a false sense of safety. Miss one guard and you get a raw JSON
string where a dict is expected.

**Fix approach:** Either (a) remove the adapter and always deserialise
explicitly via a helper function (making the contract clear), or (b) ensure all
queries that return metadata columns use `PARSE_DECLTYPES`-compatible column
declarations and remove the manual guards. Option (a) is simpler and more
reliable.

---

## 3. Inconsistent History Tracking Formats

**Severity:** Medium — affects audit trail reliability and any future undo/replay
logic.

**Description:** Most `record_update` callers pass raw values directly, and
`history.py` applies `json.dumps()` uniformly. Four locations deviate from this
pattern:

| Location | Problem |
|---|---|
| `editor.py:488-491` — `update_synset` (metadata) | Wraps values in `str()` before passing to `record_update`, which then applies `json.dumps()` again. Produces doubly-encoded strings (e.g. `"\"{'x': 1}\""`) that are neither valid JSON nor consistent with other fields. |
| `editor.py:2578-2580` — `unlink_ili` | Records `str(row["ili_rowid"])` — an opaque internal integer rowid — as `old_value`. Compare with `link_ili`, which records the actual ILI identifier string. The same logical field stores fundamentally different value types depending on direction. |
| `editor.py:1485-1488` — `move_sense` | Records `str(source_synset_rowid)` and `str(target_synset_rowid)` — internal rowids — rather than human-readable synset IDs. Inconsistent with every other UPDATE record. |
| `editor.py:847-851` — `update_entry` (metadata) | Silently **omits** `record_update` entirely. A metadata change on an entry produces no history record at all. |

**Fix approach:** Align all four sites with the standard pattern: pass raw values
directly and let `record_update` handle serialisation. For `unlink_ili` and
`move_sense`, resolve the IDs from rowids before recording. For `update_entry`,
add the missing `record_update` call.

---

## 4. `auto_inverse` Metadata Loss

**Severity:** Medium — silently drops metadata on inverse relations with no way
to correct it without remove + re-add.

**Description:** In `add_synset_relation` (`editor.py:2120-2134`), the forward
relation correctly stores the caller-supplied metadata via
`json.dumps(metadata)`. The auto-inverse INSERT hardcodes `NULL` directly in the
SQL:

```sql
INSERT OR IGNORE INTO synset_relations
  (..., metadata) VALUES (?, ?, ?, ?, NULL)
```

The same pattern exists in `add_sense_relation` (`editor.py:2262-2269`).

There is no `update_relation` method, so the only workaround is to remove and
re-add the inverse relation manually — which also triggers the auto-inverse
logic again.

**Fix approach:** Pass the same `metadata` value to the inverse INSERT. Consider
whether an `update_relation_metadata` method should also be added.

---

## 5. `suppress(IntegrityError)` Swallows All Integrity Errors

**Severity:** Medium — silently hides real data integrity problems.

**Description:** Four locations use `contextlib.suppress(sqlite3.IntegrityError)`
to silently skip duplicate relation inserts:

| Location | Context |
|---|---|
| `editor.py:2105` | `add_synset_relation` — primary insert |
| `editor.py:2241` | `add_sense_relation` — primary insert |
| `editor.py:2369` | `add_sense_synset_relation` — primary insert |
| `editor.py:3097` | `split_synset` — copy outgoing relations |

The intent is to skip duplicates (the relation tables have
`UNIQUE (source_rowid, target_rowid, type_rowid)`). But `IntegrityError` also
fires for FK violations (e.g. invalid `type_rowid`), NOT NULL violations, and
CHECK constraint failures. A legitimate data integrity problem would be silently
swallowed.

**Fix approach:** Replace `suppress(IntegrityError)` with a targeted catch that
inspects the error message for "UNIQUE constraint failed", or check for
existence before inserting. Example:

```python
try:
    self._conn.execute(...)
except sqlite3.IntegrityError as e:
    if "UNIQUE constraint failed" not in str(e):
        raise
```

---

## 6. `senses` Table Lacks a UNIQUE Constraint

**Severity:** Medium — duplicate prevention relies entirely on application logic.

**Description:** `synsets` and `entries` both enforce
`UNIQUE (id, lexicon_rowid)` at the schema level (`db.py:188`, `db.py:133`).
The `senses` table (`db.py:231-240`) has **no UNIQUE constraint at all** — only
an index on `id`:

```sql
CREATE TABLE IF NOT EXISTS senses (
    ...
    id TEXT NOT NULL,
    ...
);  -- NO UNIQUE constraint
CREATE INDEX IF NOT EXISTS sense_id_index ON senses(id);
```

Duplicate prevention happens only at the application layer
(`create_synset`/`add_sense`). If anything bypasses the API (imports, raw SQL, a
bug), phantom duplicate senses can appear. The validator's VAL-ENT-002 checks for
duplicate senses but only reports them as a WARNING, not an ERROR.

**Fix approach:** Add `UNIQUE (id, lexicon_rowid)` to the `senses` table DDL,
matching the pattern used by `synsets` and `entries`. This requires a schema
migration for existing databases.

---

## 7. Export Validation Is a No-Op

**Severity:** Medium — false safety guarantee with wasted I/O.

**Description:** `exporter.py:615-619` (`_validate_export`) is a placeholder:

```python
def _validate_export(resource: dict) -> None:
    for _lex in resource.get("lexicons", []):
        pass
```

But `export_to_lmf` re-parses the entire exported XML via `wn.lmf.load()` just
to feed the result into this no-op. Every export pays the cost of a full XML
re-parse for zero validation benefit.

`ExportError` is defined in `exceptions.py`, exported from `__init__.py`, and
referenced in docstrings under `Raises:` — but is **never raised anywhere** in
the codebase (zero occurrences of `raise ExportError`).

**Fix approach:** Either (a) implement real validation (call `wn.validate()` on
the loaded resource per RULE-EXPORT-002 in `behavior.md:353`), or (b) remove the
re-parse and the no-op function to eliminate the wasted I/O cost. Prefer (a).

---

## 8. Cascade Deletion Loses History

**Severity:** Medium — undermines the "field-level change tracking" feature.

**Description:** When `delete_synset(id, cascade=True)` runs:

**What IS recorded:**
- One `DELETE / synset / {id}` with `old_value = {"pos": "<pos>"}` (POS only)
- One `DELETE / sense / {sense_id}` per sense with `old_value = None`

**What is silently lost (no history):**
- All definitions (text, language, source_sense, metadata)
- All synset examples
- All synset relations (both directions, including cleaned-up inverses)
- All sense relations (both directions)
- All sense examples, counts, adjpositions
- The synset's ILI linkage, lexfile, and metadata
- Each sense's entry linkage, synset linkage, rank, and metadata
- Syntactic behaviour linkages

SQLite `ON DELETE CASCADE` handles the actual deletion at the DB level,
bypassing all Python history recording. A rollback or audit from history alone
is impossible for a cascade delete.

**Fix approach:** Before issuing the cascade DELETE, snapshot the full entity
tree (definitions, examples, relations, sense data) into the history record's
`old_value`. Alternatively, record individual DELETE entries for each child
entity before the cascade fires.

---

## 9. N+1 Query Problem in `find_*` Methods

**Severity:** Medium — performance cliff on real-world datasets.

**Description:** All finder methods first query for IDs, then call a model
builder per row:

| Method pair | Queries per result | For 10,000 results |
|---|---|---|
| `find_synsets` → `_build_synset_model` | 3–5 | 30,000–50,000 |
| `find_entries` → `_build_entry_model` | 3 | 30,000 |
| `find_senses` → `_build_sense_model` | 3 | 30,000 |

The exporter already solved this with pre-fetched maps (`definitions_map`,
`relations_map`, etc.) making ~5 bulk queries total regardless of dataset size.
The editor's public API uses the same database but didn't get the same
optimisation.

**Fix approach:** Add bulk model-building methods that pre-fetch related data in
batch queries (similar to the exporter's `_build_lexicon_synsets` pattern), and
use them from `find_*`. Alternatively, build models lazily so queries only fire
when attributes are accessed.

---

## 10. Proposed ILI Workflow Trap

**Severity:** Medium — undocumented state machine blocks the natural workflow.

**Description:** If a synset has a proposed ILI (via `create_synset(ili="in")`
or `propose_ili()`), calling `link_ili()` to assign the real ILI raises:

```
ValidationError("Synset already has a proposed ILI")
```

The user must call `unlink_ili()` first, then `link_ili()`. But this required
sequence is **completely undocumented** — neither `api-reference.md` nor
`design/api.md` mentions it. The docstrings say "already has an ILI" (not
"already has a *proposed* ILI"), and `unlink_ili` is described as "remove the ILI
mapping" without mentioning it also handles proposals.

**Fix approach:** Either (a) make `link_ili` automatically replace a proposed
ILI (delete from `proposed_ilis`, then link), or (b) document the required
`unlink_ili()` → `link_ili()` sequence in the API reference and docstrings.
Prefer (a).

---

## 11. Private `wn` API Dependencies

**Severity:** Low-Medium — two call sites, one without fallback.

**Description:** Two places reach into `wn`'s private internals:

| Location | Usage | Fallback? |
|---|---|---|
| `importer.py:65` | `from wn._db import connect` — fast bulk import | Yes — falls back to XML path (~14x slower) |
| `exporter.py:48-49` | `wn.config._dbpath` — redirect wn's active DB | **No** — `commit_to_wn` raises `AttributeError` with no recovery |

The importer case is well-mitigated (deferred import, try/except, documented in
`DEVELOPER_LOG.md`). The exporter case has no guard: no `getattr` default, no
`hasattr` check, no try/except.

**Fix approach:** For the exporter, add a try/except or `hasattr` guard with a
meaningful error message. For the importer, add `warnings.warn()` in the except
branch so users know when the fast path fails. Long-term, lobby for a public API
in `wn` for direct database access.

---

## 12. Synset Definition Enforcement Paradox

**Severity:** Low — API asymmetry, not data corruption.

**Description:** `create_synset` (`editor.py:346-357`) requires `definition` as
a mandatory positional argument. However, `remove_definition`
(`editor.py:1763-1798`) has no minimum-count check — calling it on a synset with
a single definition leaves the synset with zero definitions.

**Context:** Some workflows legitimately need to replace a definition
(remove + add), so a hard block on last-definition removal could be disruptive.
But the asymmetry is unexpected and undocumented.

**Fix approach:** Either (a) add a guard in `remove_definition` that raises if
it would remove the last definition, or (b) make `definition` optional in
`create_synset` for consistency, or (c) document the asymmetry explicitly as
intentional and add a validator rule for synsets with zero definitions.

---

## 13. ID Generation Race Condition (Theoretical)

**Severity:** Low — single-user tool with UNIQUE constraint backstop.

**Description:** `_generate_synset_id` (`editor.py:670-681`) uses a MAX+1
pattern: `SELECT MAX(CAST(substr(id,...) AS INTEGER))`, then `+1`.
`_generate_entry_id` (`editor.py:1199-1239`) uses a gap-filling pattern (collect
existing numeric suffixes, find lowest available >= 2). Both run inside
`@_modifies_db` transactions, but these use `BEGIN DEFERRED` — the read lock
isn't upgraded to a write lock until the INSERT, so two concurrent connections
could read the same MAX and generate the same ID.

**Mitigation already in place:** `UNIQUE (id, lexicon_rowid)` constraints on
both `synsets` and `entries` tables will raise `IntegrityError` on collision
rather than silently corrupt data. However, callers do not retry on collision.

**Context:** The library is documented for single-user batch editing. This is a
valid theoretical concern but unlikely in practice.

**Fix approach (if needed):** Use `BEGIN IMMEDIATE` instead of `BEGIN DEFERRED`
for mutation methods, or add retry logic around `IntegrityError` for ID
generation.

---

## 14. f-String SQL Column Interpolation

**Severity:** Low — currently safe, but a maintenance hazard.

**Description:** `update_lexicon` (`editor.py:269`) interpolates column names
into SQL via f-string:

```python
self._conn.execute(
    f"UPDATE lexicons SET {field} = ? WHERE id = ?",
    (val, lexicon_id),
)
```

The `field` values come from an internal hard-coded dict (lines 245-259), never
from user input. However, this pattern appears in ~15+ locations across
`editor.py`, `exporter.py`, `validator.py`, `importer.py`, and `history.py`. All
currently use internal constants, but a future contributor could extend one
without understanding the constraint.

**Fix approach (if needed):** Use a whitelist assertion
(`assert field in ALLOWED_FIELDS`) before interpolation, or restructure to avoid
interpolation entirely (e.g. separate UPDATE statements per field).

---

## 15. `split_synset` Incoming Relations Not Rewired

**Severity:** Low — intentional conservative design, documented in
`behavior.md:207` (RULE-SPLIT-004).

**Description:** `split_synset` (`editor.py:3070-3104`) copies all outgoing
relations from the original synset to new fragments. Incoming relations (other
synsets pointing TO the original) are left untouched — they continue to point
only at the original synset. New fragments start with zero incoming relations.

**Design rationale (from RULE-SPLIT-004):** "Relations TO the original synset
remain pointing to the original only. This is the conservative approach — the
user must explicitly redirect relations." The decision of which fragment should
inherit which incoming relation is semantically ambiguous and best left to the
user.

**Improvement (optional):** Consider adding an optional `redirect_incoming`
parameter or a post-split helper that lists incoming relations the user may want
to rewire.

---

## 16. Lemma Normalization Quirks

**Severity:** Low — deterministic and consistent, but potentially surprising.

**Description:** `_generate_entry_id` (`editor.py:1199-1239`) normalises lemma
text using `_NORMALIZATION_REGEX = re.compile(r"[^\w\-]", flags=re.UNICODE)` at
`editor.py:55`. The pipeline is: lowercase, replace spaces with `_`, strip
anything not matching `[\w\-]`.

This means similar surface forms produce different IDs:

| Input | Normalised ID fragment |
|---|---|
| `"can't"` | `cant` (apostrophe stripped) |
| `"can-t"` | `can-t` (hyphen kept) |
| `"can t"` | `can_t` (space becomes underscore) |

**Context:** This is a deterministic scheme and the IDs are only used internally.
For non-Latin scripts, Python 3's Unicode-aware `\w` handles diacritics and
multi-script lemmas correctly. The main risk is unexpected collisions where
stripping punctuation makes two distinct lemmas identical (e.g. `can't` and
`cant` both map to `cant`).

**Fix approach (if needed):** Consider transliterating or encoding punctuation
rather than stripping it (e.g. apostrophe → `_apos_`), or document the
normalisation rules for users who supply custom IDs.

---

## 17. `also` Relation Not Treated as Symmetric

**Severity:** Low — intentional per the GWA spec interpretation, documented in
`behavior.md:119-120` (RULE-REL-006).

**Description:** `"also"` is absent from `SYNSET_RELATION_INVERSES` in
`relations.py`. When `add_synset_relation(A, "also", B)` is called, no inverse
`also(B, A)` is created.

**Design rationale (from RULE-REL-006):** "Only the forward relation is
inserted. No inverse is created. No error is raised." The `wn` library's own
`constants.py` (credited at line 5 of `relations.py`) treats `also` as directed
with no defined inverse.

**Note:** Some WordNet implementations treat `also` as symmetric. If this
library needs to support those conventions, `also` should be added to the
symmetric section of `SYNSET_RELATION_INVERSES` (alongside `antonym`,
`similar`, etc.).

---

## 18. `entry_index` Table Duplicates Lemma Data

**Severity:** Low — defensible performance trade-off, but a sync hazard.

**Description:** `db.py:135-139` defines a 1:1 `entry_index` table that mirrors
the rank-0 form from the `forms` table:

```sql
CREATE TABLE IF NOT EXISTS entry_index (
    entry_rowid INTEGER NOT NULL REFERENCES entries(rowid) ON DELETE CASCADE,
    lemma TEXT NOT NULL,
    UNIQUE (entry_rowid)
);
```

Lemma text now lives in two places: `forms.form` (where `rank = 0`) and
`entry_index.lemma`. The editor keeps them in sync — `editor.py:787` inserts
into both on creation, `editor.py:1156` updates both in `update_lemma`. But if
any code path misses one location, they silently diverge.

**Context:** The table exists for performance — it enables fast lemma lookups
(`WHERE lemma = ?`) without JOINing through `forms WHERE rank = 0`. In a large
WordNet (~120K entries), this avoids a conditional JOIN on every
`find_entries(lemma=...)` call. A VIEW would be cleaner but slower since SQLite
cannot index a VIEW.

**Fix approach (if needed):** Accept the duplication but add a validator rule
that checks `entry_index.lemma` matches `forms.form WHERE rank = 0` for every
entry. Alternatively, use a generated column or trigger to keep them
automatically in sync.

---

## 19. Legacy `wn_editor/` Directory Contains Only `.pyc` Artifacts

**Severity:** Low — cleanup item, no functional impact.

**Description:** The `wn_editor/` directory at the repo root contains only
compiled `.pyc` bytecode files with no corresponding source:

```
wn_editor/__pycache__/changelog.cpython-312.pyc
wn_editor/__pycache__/editor.cpython-312.pyc
wn_editor/__pycache__/__init__.cpython-312.pyc
wn_editor/batch/__pycache__/executor.cpython-312.pyc
wn_editor/batch/__pycache__/parser.cpython-312.pyc
wn_editor/batch/__pycache__/schema.cpython-312.pyc
wn_editor/batch/__pycache__/validator.cpython-312.pyc
```

These are artifacts from the pre-v1.0 rewrite (source lives on the `legacy`
branch). They are not importable by the current package and serve no purpose.
Additionally, `tests/__pycache__/` contains ~28 stale `.pyc` files referencing
deleted test modules.

**Fix approach:** Delete the `wn_editor/` directory and the stale
`tests/__pycache__/` files. Add `__pycache__/` to `.gitignore` if not already
present.
