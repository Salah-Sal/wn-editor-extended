# Behavioral Specification

**Library**: `wordnet-editor`
**Version**: 1.0
**Date**: 2026-02-16

This document defines "what happens when..." for every scenario the editor can encounter. Each rule has a unique ID. Cross-referenced by the API spec and test plan.

---

## 5.1 — Deletion Cascading Rules

### RULE-DEL-001: Delete synset with `cascade=False` (default)

**When**: `delete_synset(synset_id)` is called and senses reference this synset.
**Then**: Raise `RelationError("Synset {synset_id} has {n} senses; use cascade=True to force deletion")`.
**Rationale**: Prevents accidental data loss.

### RULE-DEL-002: Delete synset with `cascade=True`

**When**: `delete_synset(synset_id, cascade=True)` is called.
**Then** (in order within one transaction):
1. Remove all rows from `synset_relations` where `source_rowid` or `target_rowid` matches this synset
2. For each relation removed in step 1, if `auto_inverse` behavior applies, also remove the corresponding inverse relation
3. Remove all rows from `definitions` where `synset_rowid` matches
4. Remove all rows from `synset_examples` where `synset_rowid` matches
5. Remove the row from `proposed_ilis` where `synset_rowid` matches (if any)
6. Remove the row from `unlexicalized_synsets` where `synset_rowid` matches (if any)
7. For each sense referencing this synset: remove sense relations (both directions), sense examples, counts, adjpositions, unlexicalized_senses entries, syntactic_behaviour_senses entries, then the sense itself
8. Delete the synset row from `synsets`
9. Record `edit_history` entries for each deleted entity

**Note**: SQLite CASCADE DELETE handles most of this automatically. Steps 1–2 (inverse relation cleanup) require explicit handling before the CASCADE.

### RULE-DEL-003: Delete entry with `cascade=False` (default)

**When**: `delete_entry(entry_id)` is called and senses exist for this entry.
**Then**: Raise `RelationError("Entry {entry_id} has {n} senses; use cascade=True to force deletion")`.

### RULE-DEL-004: Delete entry with `cascade=True`

**When**: `delete_entry(entry_id, cascade=True)` is called.
**Then** (in order within one transaction):
1. For each sense owned by this entry: apply sense-deletion rules (RULE-DEL-005)
2. Remove all forms (CASCADE handles this)
3. Remove entry_index row (CASCADE handles this)
4. Delete the entry row
5. Record `edit_history` entries

### RULE-DEL-005: Delete sense (remove_sense)

**When**: `remove_sense(sense_id)` is called.
**Then** (in order within one transaction):
1. Remove all rows from `sense_relations` where `source_rowid` or `target_rowid` matches this sense. For each removed relation with `auto_inverse`, also remove the inverse.
2. Remove all rows from `sense_synset_relations` where `source_rowid` matches
3. Remove sense_examples, counts, adjpositions, unlexicalized_senses, syntactic_behaviour_senses rows (CASCADE handles these)
4. Delete the sense row
5. Check if the owning synset now has zero senses. If so, insert into `unlexicalized_synsets` (see RULE-EMPTY-001)
6. Record `edit_history` entries

### RULE-DEL-006: Delete relation (direct)

**When**: `remove_synset_relation(source_id, relation_type, target_id)` is called.
**Then**: Delete the matching row from `synset_relations`. If `auto_inverse=True` (default) and the relation type has an inverse in `REVERSE_RELATIONS`, also delete the inverse row.

### RULE-DEL-007: Delete lexicon

**When**: A lexicon is deleted.
**Then**: CASCADE DELETE removes all owned entries, synsets, senses, forms, relations, definitions, examples, and related data. Record a single `edit_history` entry for the lexicon deletion.

---

## 5.2 — Relation Integrity Rules

### RULE-REL-001: Adding a relation with auto_inverse=True (default)

**When**: `add_synset_relation(source_id, "hypernym", target_id)` is called.
**Then**:
1. Validate source and target exist
2. Validate no self-loop (RULE-REL-004)
3. Insert `hypernym(source → target)` into `synset_relations`
4. Look up inverse: `REVERSE_RELATIONS["hypernym"]` → `"hyponym"`
5. Insert `hyponym(target → source)` into `synset_relations`
6. Both inserts are in the same transaction
7. Record two `edit_history` entries (one per relation)

### RULE-REL-002: Idempotent inverse handling

**When**: The inverse relation already exists in the database.
**Then**: The insert of the inverse is skipped silently (no duplicate, no error). The forward relation is still inserted.

**Implementation**: Use `INSERT OR IGNORE` with a uniqueness check on `(source_rowid, target_rowid, type_rowid)`, or check existence before insert.

### RULE-REL-003: Removing a relation with auto_inverse=True

**When**: `remove_synset_relation(source_id, "hypernym", target_id)` is called.
**Then**:
1. Delete `hypernym(source → target)` from `synset_relations`
2. Look up inverse: `REVERSE_RELATIONS["hypernym"]` → `"hyponym"`
3. Delete `hyponym(target → source)` from `synset_relations` (if it exists)
4. Both deletes in same transaction

### RULE-REL-004: Self-loop prevention

**When**: `add_synset_relation(A, any_type, A)` or `add_sense_relation(A, any_type, A)` is called where source == target.
**Then**: Raise `ValidationError("Self-referential relations are not allowed: {entity_id}")`.

### RULE-REL-005: Relation type validation

**When**: A relation is added with a `relation_type` string.
**Then**: Validate that:
- For synset relations: `relation_type` is in `SYNSET_RELATIONS` (68 valid types)
- For sense relations: `relation_type` is in `SENSE_RELATIONS` (48 valid types)
- For sense-synset relations: `relation_type` is in `SENSE_SYNSET_RELATIONS` (4 valid types)
If invalid, raise `ValidationError("Invalid relation type: {relation_type}")`.

### RULE-REL-006: Relations with no defined inverse

**When**: `add_synset_relation(A, "also", B, auto_inverse=True)` is called and `"also"` is not in `REVERSE_RELATIONS`.
**Then**: Only the forward relation `also(A → B)` is inserted. No inverse is created. No error is raised. This applies to: `also`, `pertainym`, `participle`, `other`.

### RULE-REL-007: Symmetric relation storage

**When**: A symmetric relation (antonym, similar, eq_synonym, etc.) is added.
**Then**: Two rows are stored — `antonym(A → B)` and `antonym(B → A)` — because the inverse of a symmetric relation is itself. This matches `wn`'s storage pattern and WN-LMF XML output requirements.

### RULE-REL-008: Cross-lexicon relations

**When**: A relation is added between entities in different lexicons.
**Then**: The relation is allowed. The `lexicon_rowid` on the relation row is set to the lexicon of the **source** entity. The inverse relation (if created) gets the `lexicon_rowid` of the **target** entity.

### RULE-REL-009: Relation type normalization

**When**: A new relation type string is used for the first time.
**Then**: Insert it into the `relation_types` lookup table via `INSERT OR IGNORE`. Reference by `type_rowid` in the relation row.

### RULE-REL-010: auto_inverse=False bypass

**When**: Any relation method is called with `auto_inverse=False`.
**Then**: Only the explicitly specified relation is created/removed. No inverse handling occurs. Useful for bulk import where inverses are already present in the data.

---

## 5.3 — Compound Operation Rules

### Merge Synsets: `merge_synsets(source_id, target_id)`

### RULE-MERGE-001: Sense transfer

All senses from `source` are reassigned to `target` by updating `senses.synset_rowid`. Sense IDs are preserved.

### RULE-MERGE-002: Incoming relation redirect

All `synset_relations` where `target_rowid` points to `source` are updated to point to `target`. Duplicates (target already has the same relation from the same source) are removed.

### RULE-MERGE-003: Outgoing relation transfer

All `synset_relations` where `source_rowid` is `source` are updated to originate from `target`. Duplicates (target already has the same relation to the same target) are removed. Self-loops (where target == the target synset) are removed.

### RULE-MERGE-004: Definition merge

Definitions from `source` are appended to `target`'s definitions. Duplicate definition texts are skipped.

### RULE-MERGE-005: Example merge

Examples from `source` are appended to `target`'s examples.

### RULE-MERGE-006: ILI handling

| Source ILI | Target ILI | Action |
|-----------|-----------|--------|
| None | None | No action |
| None | Has ILI | No action |
| Has ILI | None | Transfer source's ILI to target |
| Has ILI | Has ILI | Raise `ConflictError("Both synsets have ILI mappings")` |

Proposed ILIs follow the same logic.

### RULE-MERGE-007: Source deletion and atomicity

After all transfers, `source` synset is deleted (it should have no remaining references). The entire merge is atomic — a single transaction. If any step fails, the database is unchanged.

---

### Split Synset: `split_synset(synset_id, sense_groups)`

### RULE-SPLIT-001: Sense group validation

`sense_groups` is a list of lists of sense IDs. Every sense currently in the synset must appear in exactly one group. If a sense is missing or duplicated, raise `ValidationError`.

### RULE-SPLIT-002: New synset creation

For each sense group (except the first), create a new synset with:
- Auto-generated ID (per RULE-ID-001)
- Same POS as original synset
- Same lexicon as original synset
- No ILI mapping (ILI stays with the original)

### RULE-SPLIT-003: Sense reassignment

Senses in the first group remain in the original synset. Senses in subsequent groups are moved to their respective new synsets.

### RULE-SPLIT-004: Relation handling

Relations FROM the original synset are **copied** to all new synsets (the user can remove unwanted copies later). Relations TO the original synset remain pointing to the original only. This is the conservative approach — the user must explicitly redirect relations.

### RULE-SPLIT-005: Definition handling

The original synset keeps its definitions. New synsets are created with no definitions. The user must add definitions to the new synsets.

### RULE-SPLIT-006: Atomicity

The entire split is atomic — single transaction.

---

### Move Sense: `move_sense(sense_id, target_synset_id)`

### RULE-MOVE-001: Duplicate check

If `target_synset_id` already has a sense from the same entry (same `entry_rowid`), raise `DuplicateEntityError("Entry already has a sense in target synset")`.

### RULE-MOVE-002: Relation preservation

Sense relations are preserved. They reference the sense, not the synset, so they follow the sense to its new home. Sense-synset relations are also preserved.

### RULE-MOVE-003: Source synset unlexicalization

After moving the sense, if the source synset has no remaining senses, insert into `unlexicalized_synsets` (do NOT delete the synset — see RULE-EMPTY-001).

### RULE-MOVE-004: Atomicity

The entire move is atomic — single transaction.

---

## 5.4 — ID Generation Rules

### RULE-ID-001: Synset ID generation

**Format**: `{lexicon_id}-{counter:08d}-{pos}`

**Counter**: Query `SELECT MAX(CAST(substr(id, len_prefix+1, 8) AS INTEGER)) FROM synsets WHERE lexicon_rowid = ?`, then increment by 1. Start at 1 if no synsets exist.

**Override**: If the user passes an explicit `id` parameter, use it instead (after validating the prefix rule).

### RULE-ID-002: Entry ID generation

**Format**: `{lexicon_id}-{normalized_lemma}-{pos}`

**Normalization**: Replace spaces with `_`, strip non-alphanumeric characters except `-` and `_`, lowercase.

**Collision handling**: If the ID already exists, append `-{n}` where `n` is the smallest integer ≥ 2 that produces a unique ID.

**Override**: If the user passes an explicit `id` parameter, use it instead.

### RULE-ID-003: Sense ID generation

**Format**: `{entry_id}-{synset_local_part}-{position:02d}`

Where `synset_local_part` is the synset ID with the lexicon prefix removed, and `position` is the 1-based position of this sense within the entry.

**Override**: If the user passes an explicit `id` parameter, use it instead.

### RULE-ID-004: ID prefix validation

All entity IDs (synset, entry, sense) MUST begin with the owning lexicon's `id` followed by `-`. If a user-provided ID violates this, raise `ValidationError("ID must start with lexicon prefix: {lexicon_id}-")`.

---

## 5.5 — Empty Synset Rules

### RULE-EMPTY-001: Synset becomes unlexicalized

**When**: A synset's last sense is removed (via `remove_sense` or `move_sense`).
**Then**: Insert the synset's rowid into `unlexicalized_synsets`. The synset is NOT deleted. Validation will issue a WARNING (VAL-SYN-002).

### RULE-EMPTY-002: Synset becomes lexicalized

**When**: A sense is added to a previously unlexicalized synset (via `add_sense`).
**Then**: Remove the synset's rowid from `unlexicalized_synsets` (if present).

---

## 5.6 — Validation Rules (Behavioral)

These rules describe validation behavior. See `validation.md` for the complete catalog.

### RULE-VAL-001: Validation is explicit

Validation is NOT run automatically on every mutation. The database relies on SQLite constraints (FK, UNIQUE, NOT NULL, CHECK) for structural integrity. Semantic validation (missing definitions, orphaned synsets, missing inverses) is run only when `validate()` is called explicitly.

### RULE-VAL-002: Validation returns results, does not raise

`validate()` returns a `list[ValidationResult]`. It does NOT raise exceptions. The caller decides how to handle errors vs. warnings.

### RULE-VAL-003: Immediate enforcement

These constraints are enforced immediately (raise exceptions on violation):
- Foreign key violations (entity must exist)
- UNIQUE constraint violations (duplicate IDs)
- NOT NULL violations (required fields)
- Self-loop prevention (RULE-REL-004)
- Relation type validation (RULE-REL-005)
- ID prefix validation (RULE-ID-004)

---

## 5.7 — Confidence Score Rules

### RULE-CONF-001: Confidence inheritance

If a sense, synset, definition, example, or relation has no explicit `confidenceScore` in its metadata, it inherits from the owning lexicon's `confidenceScore`. If the lexicon also has no explicit score, the effective score is `1.0`.

### RULE-CONF-002: No automatic confidence changes

Editing an entity does NOT automatically change its confidence score. The user must explicitly call `set_confidence()` to modify it.

### RULE-CONF-003: Export behavior

On export to WN-LMF XML, a confidence score is written to an entity's metadata only if it differs from the lexicon's default. This keeps the XML compact.

---

## 5.8 — Import Rules

### RULE-IMPORT-001: Import is additive

Importing data (from XML or `wn` DB) adds to the editor database. It does not delete or overwrite existing data. If a lexicon with the same `(id, version)` already exists, raise `DuplicateEntityError`.

### RULE-IMPORT-002: Import preserves IDs

All entity IDs from the source are preserved exactly. No ID regeneration occurs during import.

### RULE-IMPORT-003: Import records history

Import operations record `CREATE` entries in `edit_history` for each entity imported.

---

## 5.9 — Export Rules

### RULE-EXPORT-001: Export is non-destructive

Exporting does not modify the editor database.

### RULE-EXPORT-002: Export validates

After constructing the `LexicalResource` TypedDict, the export pipeline runs `wn.validate()` on the result. If errors (E-codes) are found, raise `ExportError` with the validation report. Warnings (W-codes) are included in the return value but do not block export.

### RULE-EXPORT-003: Commit safety

`commit_to_wn()` follows this order:
1. Export to temp file
2. Validate the temp file
3. Only if validation passes: `wn.remove()` then `wn.add()`
4. This prevents data loss if the export is invalid
