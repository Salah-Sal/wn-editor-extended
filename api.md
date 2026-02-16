# Public API Specification

**Library**: `wordnet-editor`
**Version**: 1.0
**Date**: 2026-02-16

This document defines every public method of the `wordnet-editor` library. A developer can implement any method from this spec alone (plus `models.md` for types).

---

## 3.1 — WordnetEditor Class

The main entry point. One instance manages one editor database.

### `WordnetEditor(db_path: str | Path = ":memory:")`

**Description**: Open or create an editor database.

**Parameters**:
- `db_path` — Path to the SQLite database file. Use `":memory:"` for in-memory databases. If the file doesn't exist, it is created with the full schema.

**Returns**: A `WordnetEditor` instance.

**Raises**:
- `DatabaseError` — If the database exists but has an incompatible schema version.

**Example**:
```python
editor = WordnetEditor("my_wordnet.db")
editor = WordnetEditor()  # in-memory
```

### `WordnetEditor.from_wn(lexicon: str, db_path: str | Path = ":memory:") -> WordnetEditor`

**Description**: Create an editor database pre-populated with data from the `wn` library's database.

**Parameters**:
- `lexicon` — Lexicon specifier string (e.g., `"ewn:2024"`, `"omw-en31:1.4"`). Must match a lexicon in `wn`'s database.
- `db_path` — Path for the editor database.

**Returns**: A new `WordnetEditor` instance with the imported data.

**Raises**:
- `EntityNotFoundError` — If the lexicon specifier doesn't match any lexicon in `wn`.
- `ImportError` — If the import fails.

**Pre-conditions**: The specified lexicon must be installed in `wn` (via `wn.download()` or `wn.add()`).

**Post-conditions**: The editor database contains all entities from the specified lexicon. `edit_history` contains CREATE records for each imported entity.

**Example**:
```python
import wn
wn.download("ewn:2024")
editor = WordnetEditor.from_wn("ewn:2024", "ewn_edit.db")
```

### `WordnetEditor.from_lmf(source: str | Path, db_path: str | Path = ":memory:") -> WordnetEditor`

**Description**: Create an editor database pre-populated from a WN-LMF XML file.

**Parameters**:
- `source` — Path to a WN-LMF XML file.
- `db_path` — Path for the editor database.

**Returns**: A new `WordnetEditor` instance with the imported data.

**Raises**:
- `FileNotFoundError` — If the source file doesn't exist.
- `ImportError` — If the XML is malformed or fails validation.

**Example**:
```python
editor = WordnetEditor.from_lmf("wordnet.xml", "edit.db")
```

### `close()`

**Description**: Close the database connection. The editor instance is unusable after this call.

### Context Manager Support

```python
with WordnetEditor("my.db") as editor:
    editor.create_synset(...)
# connection automatically closed
```

---

## 3.2 — Lexicon Management

### `create_lexicon(id: str, label: str, language: str, email: str, license: str, version: str, *, url: str | None = None, citation: str | None = None, logo: str | None = None, metadata: dict | None = None) -> LexiconModel`

**Description**: Create a new lexicon in the editor database.

**Parameters**:
- `id` — Unique lexicon identifier (e.g., "awn"). Must be unique within database.
- `label` — Human-readable name (e.g., "Arabic WordNet v4").
- `language` — BCP-47 language code (e.g., "ar").
- `email` — Contact email.
- `license` — License URL.
- `version` — Version string (e.g., "4.0").

**Returns**: The created `LexiconModel`.

**Raises**:
- `DuplicateEntityError` — If a lexicon with same `(id, version)` already exists.

### `update_lexicon(lexicon_id: str, *, label: str | None = None, email: str | None = None, license: str | None = None, url: str | None = ..., citation: str | None = ..., logo: str | None = ..., metadata: dict | None = ...) -> LexiconModel`

**Description**: Update fields on an existing lexicon. Only specified fields are changed.

**Parameters**: All keyword-only. Sentinel default `...` means "don't change". Pass `None` explicitly to clear a nullable field.

**Returns**: The updated `LexiconModel`.

**Raises**:
- `EntityNotFoundError` — If the lexicon doesn't exist.

### `get_lexicon(lexicon_id: str) -> LexiconModel`

**Description**: Retrieve a lexicon by ID.

**Raises**: `EntityNotFoundError` if not found.

### `list_lexicons() -> list[LexiconModel]`

**Description**: List all lexicons in the editor database.

---

## 3.3 — Synset Operations

### `create_synset(lexicon_id: str, pos: str, definition: str, *, id: str | None = None, ili: str | None = None, ili_definition: str | None = None, lexicalized: bool = True, metadata: dict | None = None) -> SynsetModel`

**Description**: Create a new synset with one definition.

**Parameters**:
- `lexicon_id` — Owning lexicon ID.
- `pos` — Part of speech (from `PartOfSpeech` enum values).
- `definition` — Initial definition text.
- `id` — Optional explicit ID. If omitted, auto-generated per RULE-ID-001.
- `ili` — ILI identifier. `"in"` for new ILI proposal, `"iNNNNN"` for existing mapping, `None` for unmapped.
- `ili_definition` — Required when `ili="in"`. Definition for the proposed ILI (≥20 chars).
- `lexicalized` — Whether this synset has senses. Default True.
- `metadata` — Dublin Core metadata dict.

**Returns**: The created `SynsetModel`.

**Raises**:
- `EntityNotFoundError` — If `lexicon_id` doesn't exist.
- `DuplicateEntityError` — If explicit `id` already exists.
- `ValidationError` — If `pos` is not a valid POS value, or `ili="in"` without `ili_definition`, or `ili_definition` < 20 chars.

**Post-conditions**: Synset exists in DB. Definition exists in `definitions` table. If `ili="in"`, proposed ILI exists in `proposed_ilis`. Edit history records created.

**Example**:
```python
ss = editor.create_synset("awn", "n", "A large wild feline")
```

### `update_synset(synset_id: str, *, pos: str | None = None, ili: str | None = ..., metadata: dict | None = ...) -> SynsetModel`

**Description**: Update fields on an existing synset.

**Raises**: `EntityNotFoundError` if not found. `ValidationError` for invalid POS.

### `delete_synset(synset_id: str, cascade: bool = False)`

**Description**: Delete a synset. See RULE-DEL-001 and RULE-DEL-002.

**Raises**: `EntityNotFoundError` if not found. `RelationError` if `cascade=False` and senses reference it.

### `get_synset(synset_id: str) -> SynsetModel`

**Description**: Retrieve a synset by ID.

**Raises**: `EntityNotFoundError` if not found.

### `find_synsets(*, lexicon_id: str | None = None, pos: str | None = None, ili: str | None = None, definition_contains: str | None = None) -> list[SynsetModel]`

**Description**: Search for synsets matching criteria. All parameters are AND-combined.

**Parameters**:
- `definition_contains` — Substring search in definition text (case-insensitive).

**Returns**: List of matching `SynsetModel` objects. Empty list if no matches.

### `merge_synsets(source_id: str, target_id: str) -> SynsetModel`

**Description**: Merge source synset into target. See RULE-MERGE-001 through RULE-MERGE-007.

**Returns**: The updated target `SynsetModel` (source is deleted).

**Raises**:
- `EntityNotFoundError` — If either synset doesn't exist.
- `ConflictError` — If both synsets have ILI mappings.

### `split_synset(synset_id: str, sense_groups: list[list[str]]) -> list[SynsetModel]`

**Description**: Split a synset into multiple synsets by reassigning senses. See RULE-SPLIT-001 through RULE-SPLIT-006.

**Parameters**:
- `sense_groups` — List of sense ID lists. First group stays with original synset. Each subsequent group gets a new synset.

**Returns**: List of all resulting `SynsetModel` objects (original + new ones).

**Raises**:
- `EntityNotFoundError` — If synset or any sense ID doesn't exist.
- `ValidationError` — If sense groups don't partition the synset's senses exactly.

---

## 3.4 — Lexical Entry Operations

### `create_entry(lexicon_id: str, lemma: str, pos: str, *, id: str | None = None, forms: list[str] | None = None, metadata: dict | None = None) -> EntryModel`

**Description**: Create a new lexical entry (word).

**Parameters**:
- `lexicon_id` — Owning lexicon ID.
- `lemma` — The base word form.
- `pos` — Part of speech.
- `id` — Optional explicit ID. If omitted, auto-generated per RULE-ID-002.
- `forms` — Optional list of additional forms (e.g., plural, conjugations). Stored with rank 1, 2, ...

**Returns**: The created `EntryModel`.

**Raises**:
- `EntityNotFoundError` — If `lexicon_id` doesn't exist.
- `DuplicateEntityError` — If explicit `id` already exists.

**Post-conditions**: Entry exists in DB. Lemma stored as form with rank=0. Additional forms stored with rank 1+.

**Example**:
```python
entry = editor.create_entry("awn", "قطة", "n", forms=["قطط"])
```

### `update_entry(entry_id: str, *, pos: str | None = None, metadata: dict | None = ...) -> EntryModel`

**Description**: Update fields on an existing entry.

### `delete_entry(entry_id: str, cascade: bool = False)`

**Description**: Delete an entry. See RULE-DEL-003 and RULE-DEL-004.

### `get_entry(entry_id: str) -> EntryModel`

**Description**: Retrieve an entry by ID.

### `find_entries(*, lexicon_id: str | None = None, lemma: str | None = None, pos: str | None = None) -> list[EntryModel]`

**Description**: Search for entries matching criteria.

### `add_form(entry_id: str, written_form: str, *, id: str | None = None, script: str | None = None, tags: list[tuple[str, str]] | None = None)`

**Description**: Add an additional form to an entry.

**Parameters**:
- `tags` — List of `(tag, category)` tuples.

**Raises**: `EntityNotFoundError` if entry doesn't exist. `DuplicateEntityError` if form already exists for this entry.

### `remove_form(entry_id: str, written_form: str)`

**Description**: Remove a form from an entry. Cannot remove the lemma (rank=0).

**Raises**: `EntityNotFoundError` if entry or form doesn't exist. `ValidationError` if attempting to remove the lemma.

---

## 3.5 — Sense Operations

### `add_sense(entry_id: str, synset_id: str, *, id: str | None = None, lexicalized: bool = True, adjposition: str | None = None, metadata: dict | None = None) -> SenseModel`

**Description**: Create a sense linking an entry to a synset.

**Parameters**:
- `entry_id` — The lexical entry this sense belongs to.
- `synset_id` — The synset this sense references.
- `id` — Optional explicit sense ID. Auto-generated per RULE-ID-003 if omitted.
- `adjposition` — Adjective position ("a", "ip", "p"). Only for adjectives.

**Returns**: The created `SenseModel`.

**Raises**:
- `EntityNotFoundError` — If entry or synset doesn't exist.
- `DuplicateEntityError` — If sense with same ID exists, or if entry already has a sense referencing this synset.

**Post-conditions**: Sense exists. If synset was unlexicalized, it's now lexicalized (RULE-EMPTY-002).

### `remove_sense(sense_id: str)`

**Description**: Delete a sense. See RULE-DEL-005.

**Raises**: `EntityNotFoundError` if not found.

### `move_sense(sense_id: str, target_synset_id: str) -> SenseModel`

**Description**: Move a sense to a different synset. See RULE-MOVE-001 through RULE-MOVE-004.

**Returns**: The updated `SenseModel`.

### `reorder_senses(entry_id: str, sense_id_order: list[str])`

**Description**: Reorder senses within an entry by setting `entry_rank`.

**Parameters**:
- `sense_id_order` — List of sense IDs in desired order. Must contain exactly the sense IDs belonging to this entry.

**Raises**: `ValidationError` if the list doesn't match the entry's senses exactly.

### `get_sense(sense_id: str) -> SenseModel`

**Description**: Retrieve a sense by ID.

---

## 3.6 — Definition and Example Operations

### `add_definition(synset_id: str, text: str, *, language: str | None = None, source_sense: str | None = None, metadata: dict | None = None)`

**Description**: Add a definition to a synset.

### `update_definition(synset_id: str, definition_index: int, text: str)`

**Description**: Update the text of a specific definition.

**Parameters**:
- `definition_index` — 0-based index into the synset's definitions (ordered by insertion).

**Raises**: `IndexError` if index out of range.

### `remove_definition(synset_id: str, definition_index: int)`

**Description**: Remove a definition from a synset.

**Raises**: `IndexError` if index out of range.

### `add_synset_example(synset_id: str, text: str, *, language: str | None = None, metadata: dict | None = None)`

**Description**: Add an example to a synset.

### `remove_synset_example(synset_id: str, example_index: int)`

**Description**: Remove an example from a synset.

### `add_sense_example(sense_id: str, text: str, *, language: str | None = None, metadata: dict | None = None)`

**Description**: Add an example to a sense.

### `remove_sense_example(sense_id: str, example_index: int)`

**Description**: Remove an example from a sense.

### `get_definitions(synset_id: str) -> list[DefinitionModel]`

**Description**: Get all definitions for a synset.

### `get_synset_examples(synset_id: str) -> list[ExampleModel]`

**Description**: Get all examples for a synset.

### `get_sense_examples(sense_id: str) -> list[ExampleModel]`

**Description**: Get all examples for a sense.

---

## 3.7 — Relation Operations

### `add_synset_relation(source_id: str, relation_type: str, target_id: str, *, auto_inverse: bool = True, metadata: dict | None = None)`

**Description**: Add a relation between two synsets. See RULE-REL-001 through RULE-REL-010.

**Parameters**:
- `source_id` — Source synset ID.
- `relation_type` — Relation type string (e.g., "hypernym"). Must be in `SYNSET_RELATIONS`.
- `target_id` — Target synset ID.
- `auto_inverse` — If True (default), automatically create the inverse relation.
- `metadata` — Dublin Core metadata. For `relation_type="other"`, use `{"type": "custom_name"}` to specify the custom relation via `dc:type`.

**Raises**:
- `EntityNotFoundError` — If source or target doesn't exist.
- `ValidationError` — If `relation_type` is invalid, or self-loop (source == target).

**Post-conditions**:
- Forward relation exists in `synset_relations`.
- If `auto_inverse=True` and the relation has a defined inverse: inverse relation also exists.
- If the inverse already existed: no duplicate created (idempotent).

**Example**:
```python
editor.add_synset_relation("awn-00001-n", "hypernym", "awn-00002-n")
# Also creates: hyponym(awn-00002-n → awn-00001-n)
```

### `remove_synset_relation(source_id: str, relation_type: str, target_id: str, *, auto_inverse: bool = True)`

**Description**: Remove a relation between two synsets. See RULE-REL-003.

### `add_sense_relation(source_id: str, relation_type: str, target_id: str, *, auto_inverse: bool = True, metadata: dict | None = None)`

**Description**: Add a relation between two senses. Same semantics as synset relations but validates against `SENSE_RELATIONS`.

### `remove_sense_relation(source_id: str, relation_type: str, target_id: str, *, auto_inverse: bool = True)`

**Description**: Remove a relation between two senses.

### `add_sense_synset_relation(source_sense_id: str, relation_type: str, target_synset_id: str, *, metadata: dict | None = None)`

**Description**: Add a relation from a sense to a synset. No auto-inverse (sense-synset relations are unidirectional). Validates against `SENSE_SYNSET_RELATIONS`.

### `remove_sense_synset_relation(source_sense_id: str, relation_type: str, target_synset_id: str)`

**Description**: Remove a sense-to-synset relation.

### `get_synset_relations(synset_id: str, *, relation_type: str | None = None) -> list[RelationModel]`

**Description**: Get outgoing relations from a synset. Optionally filter by type.

### `get_sense_relations(sense_id: str, *, relation_type: str | None = None) -> list[RelationModel]`

**Description**: Get outgoing relations from a sense.

---

## 3.8 — ILI Operations

### `link_ili(synset_id: str, ili_id: str)`

**Description**: Link a synset to an existing ILI concept.

**Parameters**:
- `ili_id` — Existing ILI identifier (e.g., "i90287").

**Raises**: `EntityNotFoundError` if synset doesn't exist. `ValidationError` if synset already has an ILI mapping.

### `unlink_ili(synset_id: str)`

**Description**: Remove the ILI mapping from a synset.

### `propose_ili(synset_id: str, definition: str, *, metadata: dict | None = None)`

**Description**: Mark a synset as proposing a new ILI concept.

**Parameters**:
- `definition` — ILI definition text (must be ≥20 characters per WN-LMF spec).

**Post-conditions**: Synset's ILI status becomes `"in"`. Row inserted into `proposed_ilis`.

**Raises**: `ValidationError` if definition is < 20 characters, or synset already has an ILI mapping.

### `get_ili(synset_id: str) -> ILIModel | None`

**Description**: Get the ILI mapping for a synset, or None if unmapped.

---

## 3.9 — Metadata Operations

### `set_metadata(entity_type: str, entity_id: str, key: str, value: str | None)`

**Description**: Set a Dublin Core metadata property on an entity.

**Parameters**:
- `entity_type` — One of: "lexicon", "synset", "entry", "sense", "definition", "example", "relation".
- `key` — Metadata key (e.g., "dc:source", "dc:creator", "status", "note").
- `value` — Value to set. Pass `None` to remove the key.

**Notes**: The metadata dict is stored as JSON. This method reads the current metadata, updates the key, and writes back.

### `get_metadata(entity_type: str, entity_id: str) -> dict`

**Description**: Get all metadata for an entity.

**Returns**: Dict of metadata key-value pairs. Empty dict if no metadata.

### `set_confidence(entity_type: str, entity_id: str, score: float)`

**Description**: Set the confidence score on an entity.

**Parameters**:
- `score` — Float between 0.0 and 1.0.

**Notes**: Stored as `{"confidenceScore": score}` in the metadata JSON. See RULE-CONF-001 through RULE-CONF-003.

---

## 3.10 — Validation

### `validate(*, lexicon_id: str | None = None) -> list[ValidationResult]`

**Description**: Validate the editor database (or a specific lexicon) against all rules in the validation catalog.

**Parameters**:
- `lexicon_id` — If specified, validate only this lexicon. If None, validate all lexicons.

**Returns**: List of `ValidationResult` objects. Empty list means no issues found.

**Notes**: See `validation.md` for the complete rule catalog. This method never raises exceptions for validation failures — it reports them as results.

### `validate_synset(synset_id: str) -> list[ValidationResult]`

**Description**: Validate a specific synset.

### `validate_entry(entry_id: str) -> list[ValidationResult]`

**Description**: Validate a specific entry.

### `validate_relations(*, lexicon_id: str | None = None) -> list[ValidationResult]`

**Description**: Check all relations for missing inverses, dangling references, and invalid types.

---

## 3.11 — Import/Export

### `import_lmf(source: str | Path)`

**Description**: Add data from a WN-LMF XML file into the editor database. See RULE-IMPORT-001 through RULE-IMPORT-003.

**Raises**:
- `ImportError` — If the XML is malformed.
- `DuplicateEntityError` — If a lexicon with same `(id, version)` already exists.

### `export_lmf(destination: str | Path, *, lexicon_ids: list[str] | None = None)`

**Description**: Export the editor database to WN-LMF XML.

**Parameters**:
- `destination` — Output file path.
- `lexicon_ids` — Specific lexicons to export. If None, export all.

**Raises**: `ExportError` if validation errors (E-codes) are found.

**Post-conditions**: Valid WN-LMF 1.4 XML file at `destination`.

### `commit_to_wn(*, db_path: str | Path | None = None, lexicon_ids: list[str] | None = None)`

**Description**: Export to WN-LMF XML and import into the `wn` library's database. See RULE-EXPORT-003.

**Parameters**:
- `db_path` — Custom `wn` database path. If None, uses `wn`'s default.
- `lexicon_ids` — Specific lexicons to commit.

**Raises**: `ExportError` if validation fails.

**Notes**: If the lexicon already exists in `wn`, it is removed first (via `wn.remove()`) then re-added. The temp file is cleaned up after commit.

---

## 3.12 — Change Tracking

### `get_history(*, entity_type: str | None = None, entity_id: str | None = None, since: str | None = None, operation: str | None = None) -> list[EditRecord]`

**Description**: Query the edit history.

**Parameters**:
- `entity_type` — Filter by entity type (e.g., "synset").
- `entity_id` — Filter by specific entity ID.
- `since` — ISO 8601 timestamp. Only return records after this time.
- `operation` — Filter by operation type ("CREATE", "UPDATE", "DELETE").

**Returns**: List of `EditRecord` objects, ordered by timestamp ascending.

### `get_changes_since(timestamp: str) -> list[EditRecord]`

**Description**: Shorthand for `get_history(since=timestamp)`.

---

## 3.13 — Batch Operations

### `batch() -> BatchContext`

**Description**: Context manager for grouping multiple mutations into a single transaction. Improves performance for bulk operations and ensures atomicity.

**Returns**: A context manager.

**Example**:
```python
with editor.batch():
    for lemma, pos, defn in new_words:
        entry = editor.create_entry("awn", lemma, pos)
        ss = editor.create_synset("awn", pos, defn)
        editor.add_sense(entry.id, ss.id)
# all committed at once
```

**Notes**:
- Inside a batch, individual operations do not commit. The entire batch commits on successful exit of the `with` block.
- If an exception occurs, the entire batch rolls back.
- Nested batches are flattened (inner batch is a no-op; only the outermost batch controls commit/rollback).
- `edit_history` entries are still recorded for each individual operation within the batch.
