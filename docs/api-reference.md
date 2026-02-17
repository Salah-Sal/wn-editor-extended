# API Reference

Complete reference for the `wordnet-editor` public API.

## WordnetEditor

The main entry point. All editing operations go through this class.

### Constructor and lifecycle

#### `WordnetEditor(db_path=":memory:")`

Open or create a WordNet editing database.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `db_path` | `str \| Path` | `":memory:"` | Path to the SQLite file, or `":memory:"` for an in-memory database. |

**Raises:** `DatabaseError` if the file exists but has an incompatible schema.

Supports the context manager protocol:

```python
with WordnetEditor("my.db") as editor:
    ...
# connection closed automatically
```

#### `close()`

Close the database connection. Called automatically when used as a context manager.

#### `batch()`

Group multiple mutations into a single atomic transaction.

```python
with editor.batch():
    editor.create_synset(...)
    editor.create_entry(...)
    editor.add_sense(...)
# all committed on success, rolled back on exception
```

Batches may be nested — only the outermost batch issues `COMMIT`/`ROLLBACK`.

---

### Lexicon management

#### `create_lexicon(id, label, language, email, license, version, *, url=None, citation=None, logo=None, metadata=None)`

Create a new lexicon.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `id` | `str` | required | Unique lexicon identifier (e.g. `"ewn"`). |
| `label` | `str` | required | Human-readable name. |
| `language` | `str` | required | BCP-47 language tag (e.g. `"en"`). |
| `email` | `str` | required | Maintainer contact email. |
| `license` | `str` | required | License URL. |
| `version` | `str` | required | Version string (e.g. `"1.0"`). |
| `url` | `str \| None` | `None` | Project URL. |
| `citation` | `str \| None` | `None` | Bibliographic citation. |
| `logo` | `str \| None` | `None` | Logo URL. |
| `metadata` | `dict \| None` | `None` | JSON-serializable metadata. |

**Returns:** `LexiconModel`

**Raises:** `DuplicateEntityError` if a lexicon with the same `id` and `version` already exists.

#### `get_lexicon(lexicon_id)`

Retrieve a lexicon by its ID.

**Returns:** `LexiconModel`

**Raises:** `EntityNotFoundError`

#### `list_lexicons()`

Return all lexicons in the database.

**Returns:** `list[LexiconModel]`

#### `update_lexicon(lexicon_id, *, label=None, email=None, license=None, url=_UNSET, citation=_UNSET, logo=_UNSET, metadata=_UNSET)`

Update mutable fields of an existing lexicon. Only explicitly passed keyword arguments are changed. Pass `None` for nullable fields to clear them.

**Returns:** `LexiconModel`

**Raises:** `EntityNotFoundError`

#### `delete_lexicon(lexicon_id)`

Delete a lexicon and all its contents (synsets, entries, senses).

**Raises:** `EntityNotFoundError`

---

### Synset operations

#### `create_synset(lexicon_id, pos, definition, *, id=None, ili=None, ili_definition=None, lexicalized=True, metadata=None)`

Create a new synset with an initial definition.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lexicon_id` | `str` | required | Parent lexicon ID. |
| `pos` | `str` | required | Part-of-speech tag (see `PartOfSpeech`). |
| `definition` | `str` | required | Initial definition text. |
| `id` | `str \| None` | `None` | Explicit synset ID, or `None` to auto-generate. |
| `ili` | `str \| None` | `None` | ILI identifier, or `"in"` to propose a new ILI entry. |
| `ili_definition` | `str \| None` | `None` | Required when `ili="in"` (min 20 chars). |
| `lexicalized` | `bool` | `True` | Whether the synset is lexicalized. |
| `metadata` | `dict \| None` | `None` | Metadata dict. |

**Returns:** `SynsetModel`

**Raises:** `ValidationError`, `EntityNotFoundError`, `DuplicateEntityError`

#### `get_synset(synset_id)`

Retrieve a synset by its ID.

**Returns:** `SynsetModel`

**Raises:** `EntityNotFoundError`

#### `find_synsets(*, lexicon_id=None, pos=None, ili=None, definition_contains=None)`

Search for synsets matching all given criteria.

| Parameter | Type | Description |
|-----------|------|-------------|
| `lexicon_id` | `str \| None` | Filter by parent lexicon. |
| `pos` | `str \| None` | Filter by part-of-speech. |
| `ili` | `str \| None` | Filter by ILI identifier. |
| `definition_contains` | `str \| None` | Substring match in definitions. |

**Returns:** `list[SynsetModel]`

#### `update_synset(synset_id, *, pos=None, metadata=_UNSET)`

Update mutable fields of a synset.

**Returns:** `SynsetModel`

**Raises:** `EntityNotFoundError`, `ValidationError`

#### `delete_synset(synset_id, cascade=False)`

Delete a synset. Pass `cascade=True` to also delete all attached senses.

**Raises:** `EntityNotFoundError`, `RelationError` (if has senses and `cascade=False`)

---

### Entry operations

#### `create_entry(lexicon_id, lemma, pos, *, id=None, forms=None, metadata=None)`

Create a new lexical entry.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `lexicon_id` | `str` | required | Parent lexicon ID. |
| `lemma` | `str` | required | The lemma (canonical written form). |
| `pos` | `str` | required | Part-of-speech tag. |
| `id` | `str \| None` | `None` | Explicit entry ID, or `None` to auto-generate. |
| `forms` | `list[str] \| None` | `None` | Additional written forms (variants, inflections). |
| `metadata` | `dict \| None` | `None` | Metadata dict. |

**Returns:** `EntryModel`

**Raises:** `ValidationError`, `EntityNotFoundError`, `DuplicateEntityError`

#### `get_entry(entry_id)`

Retrieve an entry by its ID.

**Returns:** `EntryModel`

**Raises:** `EntityNotFoundError`

#### `find_entries(*, lexicon_id=None, lemma=None, pos=None)`

Search for entries matching all given criteria.

| Parameter | Type | Description |
|-----------|------|-------------|
| `lexicon_id` | `str \| None` | Filter by parent lexicon. |
| `lemma` | `str \| None` | Filter by exact lemma match. |
| `pos` | `str \| None` | Filter by part-of-speech. |

**Returns:** `list[EntryModel]`

#### `update_entry(entry_id, *, pos=None, metadata=_UNSET)`

Update mutable fields of an entry.

**Returns:** `EntryModel`

**Raises:** `EntityNotFoundError`, `ValidationError`

#### `delete_entry(entry_id, cascade=False)`

Delete an entry. Pass `cascade=True` to also delete all attached senses.

**Raises:** `EntityNotFoundError`, `RelationError` (if has senses and `cascade=False`)

#### `update_lemma(entry_id, new_lemma)`

Change the lemma (canonical form) of an entry.

**Raises:** `EntityNotFoundError`

---

### Form operations

#### `add_form(entry_id, written_form, *, id=None, script=None, tags=None)`

Add an additional written form (variant/inflection) to an entry.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `entry_id` | `str` | required | Parent entry ID. |
| `written_form` | `str` | required | The form text. |
| `id` | `str \| None` | `None` | Explicit form ID. |
| `script` | `str \| None` | `None` | ISO 15924 script tag. |
| `tags` | `list[tuple[str, str]] \| None` | `None` | List of `(tag, category)` pairs. |

**Raises:** `EntityNotFoundError`, `DuplicateEntityError`

#### `remove_form(entry_id, written_form)`

Remove a form from an entry. The lemma form (rank 0) cannot be removed.

**Raises:** `EntityNotFoundError`, `ValidationError`

#### `get_forms(entry_id)`

Return all forms of an entry, ordered by rank. The lemma is always at rank 0.

**Returns:** `list[FormModel]`

**Raises:** `EntityNotFoundError`

---

### Sense operations

#### `add_sense(entry_id, synset_id, *, id=None, lexicalized=True, adjposition=None, metadata=None)`

Link an entry to a synset by creating a new sense.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `entry_id` | `str` | required | Parent entry ID. |
| `synset_id` | `str` | required | Target synset ID. |
| `id` | `str \| None` | `None` | Explicit sense ID, or `None` to auto-generate. |
| `lexicalized` | `bool` | `True` | Whether the sense is lexicalized. |
| `adjposition` | `str \| None` | `None` | Adjective position (`"a"`, `"ip"`, `"p"`). |
| `metadata` | `dict \| None` | `None` | Metadata dict. |

**Returns:** `SenseModel`

**Raises:** `EntityNotFoundError`, `DuplicateEntityError`, `ValidationError`

#### `remove_sense(sense_id)`

Delete a sense and its relations, examples, and counts. If the synset has no remaining senses, it becomes unlexicalized.

**Raises:** `EntityNotFoundError`

#### `get_sense(sense_id)`

Retrieve a sense by its ID.

**Returns:** `SenseModel`

**Raises:** `EntityNotFoundError`

#### `find_senses(*, entry_id=None, synset_id=None, lexicon_id=None)`

Search for senses matching all given criteria.

**Returns:** `list[SenseModel]` (ordered by entry rank)

#### `move_sense(sense_id, target_synset_id)`

Move a sense from its current synset to a different synset. The source synset becomes unlexicalized if emptied; the target becomes lexicalized if it was unlexicalized.

**Returns:** `SenseModel`

**Raises:** `EntityNotFoundError`, `DuplicateEntityError`

#### `reorder_senses(entry_id, sense_id_order)`

Set the ordering of senses within an entry.

| Parameter | Type | Description |
|-----------|------|-------------|
| `entry_id` | `str` | Entry whose senses to reorder. |
| `sense_id_order` | `list[str]` | Complete list of sense IDs in desired order. |

**Raises:** `EntityNotFoundError`, `ValidationError`

---

### Definition and example operations

#### `add_definition(synset_id, text, *, language=None, source_sense=None, metadata=None)`

Add a definition to a synset.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `synset_id` | `str` | required | Synset ID. |
| `text` | `str` | required | Definition text. |
| `language` | `str \| None` | `None` | BCP-47 language tag. |
| `source_sense` | `str \| None` | `None` | Sense ID this definition is derived from. |
| `metadata` | `dict \| None` | `None` | Metadata dict. |

**Raises:** `EntityNotFoundError`

#### `update_definition(synset_id, definition_index, text)`

Replace a definition's text by its zero-based index.

**Raises:** `EntityNotFoundError`, `IndexError`

#### `remove_definition(synset_id, definition_index)`

Remove a definition by its zero-based index.

**Raises:** `EntityNotFoundError`, `IndexError`

#### `get_definitions(synset_id)`

Return all definitions of a synset, ordered by insertion.

**Returns:** `list[DefinitionModel]`

**Raises:** `EntityNotFoundError`

#### `add_synset_example(synset_id, text, *, language=None, metadata=None)`

Add a usage example to a synset.

**Raises:** `EntityNotFoundError`

#### `remove_synset_example(synset_id, example_index)`

Remove a synset example by its zero-based index.

**Raises:** `EntityNotFoundError`, `IndexError`

#### `get_synset_examples(synset_id)`

Return all examples of a synset.

**Returns:** `list[ExampleModel]`

**Raises:** `EntityNotFoundError`

#### `add_sense_example(sense_id, text, *, language=None, metadata=None)`

Add a usage example to a sense.

**Raises:** `EntityNotFoundError`

#### `remove_sense_example(sense_id, example_index)`

Remove a sense example by its zero-based index.

**Raises:** `EntityNotFoundError`, `IndexError`

#### `get_sense_examples(sense_id)`

Return all examples of a sense.

**Returns:** `list[ExampleModel]`

**Raises:** `EntityNotFoundError`

---

### Relation operations

All relation methods that add relations silently ignore duplicates. Synset and sense relations support automatic inverse creation (controlled by the `auto_inverse` parameter, default `True`).

#### `add_synset_relation(source_id, relation_type, target_id, *, auto_inverse=True, metadata=None)`

Add a directed relation between two synsets. When `auto_inverse=True`, the corresponding inverse (e.g. `hyponym` for `hypernym`) is also created.

**Raises:** `ValidationError`, `EntityNotFoundError`

#### `remove_synset_relation(source_id, relation_type, target_id, *, auto_inverse=True)`

Remove a directed relation between two synsets. No-op if the relation doesn't exist.

#### `get_synset_relations(synset_id, *, relation_type=None)`

Return outgoing relations from a synset, optionally filtered by type.

**Returns:** `list[RelationModel]`

**Raises:** `EntityNotFoundError`

#### `add_sense_relation(source_id, relation_type, target_id, *, auto_inverse=True, metadata=None)`

Add a directed relation between two senses.

**Raises:** `ValidationError`, `EntityNotFoundError`

#### `remove_sense_relation(source_id, relation_type, target_id, *, auto_inverse=True)`

Remove a directed relation between two senses. No-op if it doesn't exist.

#### `get_sense_relations(sense_id, *, relation_type=None)`

Return outgoing relations from a sense.

**Returns:** `list[RelationModel]`

**Raises:** `EntityNotFoundError`

#### `add_sense_synset_relation(source_sense_id, relation_type, target_synset_id, *, metadata=None)`

Add a relation from a sense to a synset.

**Raises:** `ValidationError`, `EntityNotFoundError`

#### `remove_sense_synset_relation(source_sense_id, relation_type, target_synset_id)`

Remove a relation from a sense to a synset. No-op if it doesn't exist.

---

### ILI operations

#### `link_ili(synset_id, ili_id)`

Link a synset to an existing ILI entry.

**Raises:** `EntityNotFoundError`, `ValidationError` (if synset already has an ILI)

#### `unlink_ili(synset_id)`

Remove the ILI mapping (or proposed ILI) from a synset.

**Raises:** `EntityNotFoundError`

#### `propose_ili(synset_id, definition, *, metadata=None)`

Propose a new ILI entry for a synset. Definition must be at least 20 characters.

**Raises:** `EntityNotFoundError`, `ValidationError`

#### `get_ili(synset_id)`

Get the ILI mapping for a synset, or `None` if none exists.

**Returns:** `ILIModel | None`

**Raises:** `EntityNotFoundError`

---

### Metadata operations

#### `set_metadata(entity_type, entity_id, key, value)`

Set or delete a single metadata key on any entity. Pass `None` as `value` to delete the key.

| Parameter | Type | Description |
|-----------|------|-------------|
| `entity_type` | `str` | One of `"lexicon"`, `"synset"`, `"entry"`, `"sense"`. |
| `entity_id` | `str` | Entity ID. |
| `key` | `str` | Metadata key. |
| `value` | `str \| float \| None` | Value to set, or `None` to delete. |

**Raises:** `EntityNotFoundError`, `ValidationError`

#### `get_metadata(entity_type, entity_id)`

Return the full metadata dict for an entity (empty dict if none).

**Returns:** `dict`

**Raises:** `EntityNotFoundError`, `ValidationError`

#### `set_confidence(entity_type, entity_id, score)`

Convenience method to set the `confidenceScore` metadata key.

**Raises:** `EntityNotFoundError`, `ValidationError`

---

### Compound operations

#### `merge_synsets(source_id, target_id)`

Merge two synsets atomically. Moves all senses, definitions, examples, and relations from the source into the target, then deletes the source. Duplicate definitions and self-loop relations are removed. If only the source has an ILI, it transfers to the target.

**Returns:** `SynsetModel` (the updated target)

**Raises:** `EntityNotFoundError`, `ConflictError` (if both have ILI mappings)

#### `split_synset(synset_id, sense_groups)`

Split a synset into multiple synsets. The first group keeps the original synset; each subsequent group creates a new synset. Outgoing relations are copied to all new synsets.

| Parameter | Type | Description |
|-----------|------|-------------|
| `synset_id` | `str` | Synset to split. |
| `sense_groups` | `list[list[str]]` | Partition of sense IDs (at least 2 groups). |

**Returns:** `list[SynsetModel]` (original first, then new ones)

**Raises:** `EntityNotFoundError`, `ValidationError`

---

### Validation

#### `validate(*, lexicon_id=None)`

Run all 22 validation rules. Optionally restrict to one lexicon.

**Returns:** `list[ValidationResult]`

#### `validate_synset(synset_id)`

Run validation rules scoped to a single synset.

**Returns:** `list[ValidationResult]`

#### `validate_entry(entry_id)`

Run validation rules scoped to a single entry.

**Returns:** `list[ValidationResult]`

#### `validate_relations(*, lexicon_id=None)`

Run relation-specific validation rules (e.g. missing inverses).

**Returns:** `list[ValidationResult]`

---

### Change tracking

#### `get_history(*, entity_type=None, entity_id=None, since=None, operation=None)`

Query the edit history log. All parameters are optional filters.

| Parameter | Type | Description |
|-----------|------|-------------|
| `entity_type` | `str \| None` | Filter by entity type (e.g. `"synset"`). |
| `entity_id` | `str \| None` | Filter by entity ID. |
| `since` | `str \| None` | ISO-8601 timestamp; records after this time only. |
| `operation` | `str \| None` | `"CREATE"`, `"UPDATE"`, or `"DELETE"`. |

**Returns:** `list[EditRecord]`

#### `get_changes_since(timestamp)`

Shorthand for `get_history(since=timestamp)`.

**Returns:** `list[EditRecord]`

---

### Import / export

#### `WordnetEditor.from_wn(lexicon, db_path=":memory:", *, record_history=True, version=None, label=None, lexicon_id=None, email=None, license=None, url=None, citation=None)` *(classmethod)*

Create an editor pre-loaded from the `wn` library.

| Parameter | Type | Description |
|-----------|------|-------------|
| `lexicon` | `str` | Lexicon specifier (e.g. `"ewn:2024"`). |
| `db_path` | `str \| Path` | Editor database path. |
| `record_history` | `bool` | Record import in edit history. |
| `version` | `str \| None` | Override imported version. |
| `label` | `str \| None` | Override imported label. |
| `lexicon_id` | `str \| None` | Override imported lexicon ID. |
| `email` | `str \| None` | Override imported email. |
| `license` | `str \| None` | Override imported license. |
| `url` | `str \| None` | Override imported URL. |
| `citation` | `str \| None` | Override imported citation. |

**Returns:** `WordnetEditor`

**Raises:** `DataImportError`

#### `WordnetEditor.from_lmf(source, db_path=":memory:", *, record_history=True)` *(classmethod)*

Create an editor pre-loaded from a WN-LMF XML file.

**Returns:** `WordnetEditor`

**Raises:** `DataImportError`

#### `import_lmf(source)`

Import additional data from a WN-LMF XML file into this editor.

**Raises:** `DataImportError`

#### `export_lmf(destination, *, lexicon_ids=None, lmf_version="1.4")`

Export the database to a WN-LMF XML file.

| Parameter | Type | Default | Description |
|-----------|------|---------|-------------|
| `destination` | `str \| Path` | required | Output file path. |
| `lexicon_ids` | `list[str] \| None` | `None` | Export only these lexicons. |
| `lmf_version` | `str` | `"1.4"` | LMF schema version. |

**Raises:** `ExportError`

#### `commit_to_wn(*, db_path=None, lexicon_ids=None)`

Push changes back into the `wn` library's database via a temporary LMF export and `wn.add()`.

**Raises:** `ExportError`

---

## Data models

All models are frozen dataclasses (`@dataclass(frozen=True, slots=True)`).

### `LexiconModel`

A WordNet lexicon (language-specific resource container).

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier. |
| `label` | `str` | Human-readable name. |
| `language` | `str` | BCP-47 language tag. |
| `email` | `str` | Maintainer email. |
| `license` | `str` | License URL. |
| `version` | `str` | Version string. |
| `url` | `str \| None` | Project URL. |
| `citation` | `str \| None` | Bibliographic citation. |
| `logo` | `str \| None` | Logo URL. |
| `metadata` | `dict \| None` | Arbitrary metadata. |

### `SynsetModel`

A synset (set of synonymous senses sharing a concept).

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier. |
| `lexicon_id` | `str` | Parent lexicon ID. |
| `pos` | `str \| None` | Part-of-speech. |
| `ili` | `str \| None` | ILI identifier, or `"in"` for proposed. |
| `lexicalized` | `bool` | Whether the synset has at least one sense. |
| `lexfile` | `str \| None` | Lexicographer file name. |
| `metadata` | `dict \| None` | Arbitrary metadata. |

### `EntryModel`

A lexical entry (word + part of speech).

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier. |
| `lexicon_id` | `str` | Parent lexicon ID. |
| `lemma` | `str` | Canonical written form. |
| `pos` | `str` | Part-of-speech tag. |
| `index` | `str \| None` | Lemma index. |
| `metadata` | `dict \| None` | Arbitrary metadata. |

### `SenseModel`

A sense linking a lexical entry to a synset.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | Unique identifier. |
| `entry_id` | `str` | Parent entry ID. |
| `synset_id` | `str` | Target synset ID. |
| `lexicon_id` | `str` | Parent lexicon ID. |
| `entry_rank` | `int` | Order within the entry's senses. |
| `synset_rank` | `int` | Order within the synset's senses. |
| `lexicalized` | `bool` | Whether the sense is lexicalized. |
| `adjposition` | `str \| None` | Adjective position. |
| `metadata` | `dict \| None` | Arbitrary metadata. |

### `FormModel`

A written form of a lexical entry.

| Field | Type | Description |
|-------|------|-------------|
| `written_form` | `str` | The form text. |
| `id` | `str \| None` | Optional form ID. |
| `script` | `str \| None` | ISO 15924 script tag. |
| `rank` | `int` | Order (0 = lemma). |
| `pronunciations` | `tuple[PronunciationModel, ...]` | Pronunciations. |
| `tags` | `tuple[TagModel, ...]` | Categorized tags. |

### `DefinitionModel`

A definition of a synset.

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Definition text. |
| `language` | `str \| None` | BCP-47 language tag. |
| `source_sense` | `str \| None` | Sense ID it was derived from. |
| `metadata` | `dict \| None` | Arbitrary metadata. |

### `ExampleModel`

A usage example for a synset or sense.

| Field | Type | Description |
|-------|------|-------------|
| `text` | `str` | Example text. |
| `language` | `str \| None` | BCP-47 language tag. |
| `metadata` | `dict \| None` | Arbitrary metadata. |

### `RelationModel`

A typed, directed relation between two entities.

| Field | Type | Description |
|-------|------|-------------|
| `source_id` | `str` | Source entity ID. |
| `target_id` | `str` | Target entity ID. |
| `relation_type` | `str` | Relation type string. |
| `metadata` | `dict \| None` | Arbitrary metadata. |

### `ILIModel`

An Interlingual Index entry.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str` | ILI identifier (e.g. `"i12345"`). |
| `status` | `str` | Status string. |
| `definition` | `str \| None` | ILI definition. |
| `metadata` | `dict \| None` | Arbitrary metadata. |

### `EditRecord`

A single edit-history entry.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `int` | Auto-incremented record ID. |
| `entity_type` | `str` | Entity type (e.g. `"synset"`). |
| `entity_id` | `str` | Entity ID. |
| `field_name` | `str \| None` | Field that changed. |
| `operation` | `str` | `"CREATE"`, `"UPDATE"`, or `"DELETE"`. |
| `old_value` | `str \| None` | Previous value. |
| `new_value` | `str \| None` | New value. |
| `timestamp` | `str` | ISO-8601 timestamp. |

### `ValidationResult`

A single validation finding.

| Field | Type | Description |
|-------|------|-------------|
| `rule_id` | `str` | Rule identifier. |
| `severity` | `str` | `"ERROR"` or `"WARNING"`. |
| `entity_type` | `str` | Entity type. |
| `entity_id` | `str` | Entity ID. |
| `message` | `str` | Human-readable description. |
| `details` | `dict \| None` | Additional context. |

### `PronunciationModel`

A pronunciation of a written form.

| Field | Type | Description |
|-------|------|-------------|
| `value` | `str` | Pronunciation string. |
| `variety` | `str \| None` | Language variety (e.g. dialect). |
| `notation` | `str \| None` | Notation system (e.g. `"IPA"`). |
| `phonemic` | `bool` | `True` for phonemic, `False` for phonetic. |
| `audio` | `str \| None` | URL to audio file. |

### `TagModel`

A categorized tag attached to a form.

| Field | Type | Description |
|-------|------|-------------|
| `tag` | `str` | Tag value. |
| `category` | `str` | Tag category. |

### `ProposedILIModel`

A proposed new ILI entry awaiting approval.

| Field | Type | Description |
|-------|------|-------------|
| `synset_id` | `str` | ID of the synset proposing this ILI. |
| `definition` | `str` | ILI definition (min 20 characters). |
| `metadata` | `dict \| None` | Arbitrary metadata. |

### `CountModel`

A frequency count associated with a sense.

| Field | Type | Description |
|-------|------|-------------|
| `value` | `int` | Frequency count. |
| `metadata` | `dict \| None` | Arbitrary metadata. |

### `SyntacticBehaviourModel`

A subcategorization frame shared by one or more senses.

| Field | Type | Description |
|-------|------|-------------|
| `id` | `str \| None` | Optional behaviour ID. |
| `frame` | `str` | Subcategorization frame string. |
| `sense_ids` | `tuple[str, ...]` | IDs of senses sharing this frame. |

---

## Enums

### `PartOfSpeech`

Part-of-speech tags: `NOUN` (`"n"`), `VERB` (`"v"`), `ADJECTIVE` (`"a"`), `ADVERB` (`"r"`), `ADJECTIVE_SATELLITE` (`"s"`), `PHRASE` (`"t"`), `CONJUNCTION` (`"c"`), `ADPOSITION` (`"p"`), `OTHER` (`"x"`), `UNKNOWN` (`"u"`).

### `AdjPosition`

Adjective syntactic positions: `ATTRIBUTIVE` (`"a"`), `IMMEDIATE_POSTNOMINAL` (`"ip"`), `PREDICATIVE` (`"p"`).

### `SynsetRelationType`

All valid synset-to-synset relation type strings (85 values). See `SynsetRelationType` members for the complete list.

### `SenseRelationType`

All valid sense-to-sense relation type strings (48 values). See `SenseRelationType` members for the complete list.

### `SenseSynsetRelationType`

Valid sense-to-synset relation types: `OTHER`, `DOMAIN_TOPIC`, `DOMAIN_REGION`, `EXEMPLIFIES`.

### `EditOperation`

Edit history operation types: `CREATE`, `UPDATE`, `DELETE`.

### `ValidationSeverity`

Validation severity levels: `ERROR`, `WARNING`.

---

## Exceptions

All exceptions inherit from `WordnetEditorError`.

| Exception | Description |
|-----------|-------------|
| `WordnetEditorError` | Base exception for all wordnet-editor errors. |
| `ValidationError` | Invalid data (bad POS, self-loop, invalid ID prefix). |
| `EntityNotFoundError` | Entity doesn't exist in the database. |
| `DuplicateEntityError` | Entity with same ID already exists. |
| `RelationError` | Relation constraint violation. |
| `ConflictError` | Conflicting state (e.g. both synsets have ILI in merge). |
| `DataImportError` | Failed to import data. |
| `ExportError` | Failed to export (validation errors in output). |
| `DatabaseError` | Schema version mismatch or connection failure. |

---

## Constants

### `SYNSET_RELATION_INVERSES`

`dict[str, str]` mapping each synset relation type to its inverse (e.g. `"hypernym"` → `"hyponym"`). Symmetric relations map to themselves.

### `SENSE_RELATION_INVERSES`

`dict[str, str]` mapping each sense relation type to its inverse.
