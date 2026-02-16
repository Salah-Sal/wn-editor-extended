# Test Plan

**Library**: `wordnet-editor`
**Version**: 1.0
**Date**: 2026-02-16

Structured test scenarios for every API method. Each scenario is precise enough to become a test function. Organized by feature area.

---

## Editor Initialization

### TP-INIT-001: Create editor with new database
- **Setup**: No existing database file
- **Action**: `WordnetEditor("test.db")`
- **Verify**: File exists, meta table has schema_version, all tables exist

### TP-INIT-002: Open existing database
- **Setup**: Create editor, close it
- **Action**: `WordnetEditor("test.db")` again
- **Verify**: No error, schema version matches

### TP-INIT-003: In-memory database
- **Setup**: None
- **Action**: `WordnetEditor(":memory:")`
- **Verify**: Works, tables exist, no file created

### TP-INIT-004: Context manager
- **Setup**: None
- **Action**: `with WordnetEditor() as editor: pass`
- **Verify**: Connection closed after exit

### TP-INIT-005: from_wn with valid lexicon
- **Setup**: `wn.download("ewn:2024")` (or use fixture XML via `wn.add()`)
- **Action**: `WordnetEditor.from_wn("ewn:2024")`
- **Verify**: Editor DB has lexicon, entries, synsets, senses

### TP-INIT-006: from_wn with invalid lexicon
- **Setup**: No lexicon installed
- **Action**: `WordnetEditor.from_wn("nonexistent:1.0")`
- **Verify**: Raises `EntityNotFoundError`

### TP-INIT-007: from_lmf with valid XML
- **Setup**: Valid WN-LMF XML fixture file
- **Action**: `WordnetEditor.from_lmf("fixtures/minimal.xml")`
- **Verify**: Editor DB has imported data

### TP-INIT-008: from_lmf with invalid XML
- **Setup**: Malformed XML file
- **Action**: `WordnetEditor.from_lmf("bad.xml")`
- **Verify**: Raises `DataImportError`

---

## Lexicon Management

### TP-LEX-001: Create lexicon with valid data
- **Setup**: Empty editor
- **Action**: `create_lexicon("awn", "Arabic WordNet", "ar", "a@b.c", "https://...", "4.0")`
- **Verify**: Lexicon exists, all fields match, specifier is "awn:4.0"

### TP-LEX-002: Create duplicate lexicon
- **Setup**: Lexicon "awn:4.0" exists
- **Action**: `create_lexicon("awn", ..., version="4.0")`
- **Verify**: Raises `DuplicateEntityError`

### TP-LEX-003: Update lexicon
- **Setup**: Lexicon exists
- **Action**: `update_lexicon("awn", label="New Label")`
- **Verify**: Label changed, other fields unchanged, edit_history recorded

### TP-LEX-004: Get nonexistent lexicon
- **Action**: `get_lexicon("nonexistent")`
- **Verify**: Raises `EntityNotFoundError`

### TP-LEX-005: List lexicons
- **Setup**: Two lexicons created
- **Action**: `list_lexicons()`
- **Verify**: Returns both

### TP-LEX-006: Delete lexicon cascades
- **Setup**: Lexicon with synsets, entries, senses, and relations
- **Action**: `delete_lexicon(lexicon_id)`
- **Verify**: All synsets, entries, senses, relations, definitions, and examples belonging to the lexicon are removed. Cross-lexicon relations pointing to deleted entities are also removed. Edit history records all deletions.

---

## Synset Operations

### TP-SYN-001: Create synset with valid data
- **Setup**: Editor with one lexicon "awn"
- **Action**: `create_synset("awn", "n", "A large feline")`
- **Verify**: Synset exists, has correct POS, has one definition, ID starts with "awn-"

### TP-SYN-002: Create synset with explicit ID
- **Action**: `create_synset("awn", "n", "Test", id="awn-custom-n")`
- **Verify**: Synset has ID "awn-custom-n"

### TP-SYN-003: Create synset with invalid POS
- **Action**: `create_synset("awn", "z", "Test")`
- **Verify**: Raises `ValidationError`

### TP-SYN-004: Create synset with ILI proposal
- **Action**: `create_synset("awn", "n", "Test", ili="in", ili_definition="A concept at least twenty chars")`
- **Verify**: Synset has `ili="in"`, proposed_ilis row exists

### TP-SYN-005: Create synset with short ILI definition
- **Action**: `create_synset("awn", "n", "Test", ili="in", ili_definition="short")`
- **Verify**: Raises `ValidationError`

### TP-SYN-006: Delete synset without cascade (has senses)
- **Setup**: Synset with one sense
- **Action**: `delete_synset(synset_id)`
- **Verify**: Raises `RelationError`

### TP-SYN-007: Delete synset with cascade
- **Setup**: Synset with senses and relations
- **Action**: `delete_synset(synset_id, cascade=True)`
- **Verify**: Synset gone, senses gone, relations gone, inverse relations gone

### TP-SYN-008: Find synsets by definition
- **Setup**: Synset with definition "large feline animal"
- **Action**: `find_synsets(definition_contains="feline")`
- **Verify**: Returns the synset

### TP-SYN-009: Update synset POS
- **Action**: `update_synset(synset_id, pos="v")`
- **Verify**: POS changed, edit_history recorded

---

## Merge / Split / Move

### TP-MERGE-001: Merge synsets transfers senses
- **Setup**: Synset A (senses s1, s2), synset B (sense s3)
- **Action**: `merge_synsets(A, B)`
- **Verify**: B has senses s1, s2, s3. A deleted.

### TP-MERGE-002: Merge transfers relations
- **Setup**: Synset A has hypernym→C. Synset B has hypernym→D.
- **Action**: `merge_synsets(A, B)`
- **Verify**: B has hypernym→C and hypernym→D. C has hyponym→B.

### TP-MERGE-003: Merge deduplicates relations
- **Setup**: Both A and B have hypernym→C
- **Action**: `merge_synsets(A, B)`
- **Verify**: B has only one hypernym→C (not duplicated)

### TP-MERGE-004: Merge with conflicting ILI
- **Setup**: A has ILI "i100", B has ILI "i200"
- **Action**: `merge_synsets(A, B)`
- **Verify**: Raises `ConflictError`

### TP-MERGE-005: Merge transfers ILI when target has none
- **Setup**: A has ILI "i100", B has no ILI
- **Action**: `merge_synsets(A, B)`
- **Verify**: B now has ILI "i100"

### TP-SPLIT-001: Split synset into two
- **Setup**: Synset with senses s1, s2, s3
- **Action**: `split_synset(synset_id, [[s1.id], [s2.id, s3.id]])`
- **Verify**: Original has s1. New synset has s2, s3. Relations copied to new.

### TP-SPLIT-002: Split with invalid sense group
- **Setup**: Synset with senses s1, s2
- **Action**: `split_synset(synset_id, [[s1.id]])`  (s2 missing)
- **Verify**: Raises `ValidationError`

### TP-MOVE-001: Move sense to different synset
- **Setup**: Sense s1 in synset A, synset B exists
- **Action**: `move_sense(s1.id, B.id)`
- **Verify**: s1 now in B. Sense relations preserved. A becomes unlexicalized.

### TP-MOVE-002: Move sense duplicate check
- **Setup**: Entry E has sense s1 in synset A and sense s2 in synset B
- **Action**: `move_sense(s1.id, B.id)`
- **Verify**: Raises `DuplicateEntityError`

---

## Entry Operations

### TP-ENT-001: Create entry
- **Action**: `create_entry("awn", "قطة", "n")`
- **Verify**: Entry exists, lemma form at rank 0, ID starts with "awn-"

### TP-ENT-002: Create entry with forms
- **Action**: `create_entry("awn", "cat", "n", forms=["cats"])`
- **Verify**: Lemma "cat" at rank 0, "cats" at rank 1

### TP-ENT-003: Add form to entry
- **Setup**: Entry exists
- **Action**: `add_form(entry_id, "cats", tags=[("NNS", "penn")])`
- **Verify**: Form exists with correct tag

### TP-ENT-004: Remove form
- **Setup**: Entry with form "cats"
- **Action**: `remove_form(entry_id, "cats")`
- **Verify**: Form gone

### TP-ENT-005: Remove lemma form fails
- **Action**: `remove_form(entry_id, lemma_form)`
- **Verify**: Raises `ValidationError`

### TP-ENT-006: Update entry POS
- **Setup**: Entry exists with `pos="n"`
- **Action**: `update_entry(entry_id, pos="v")`
- **Verify**: `get_entry(entry_id).pos == PartOfSpeech.v`, edit history recorded

### TP-ENT-007: Find entries by lemma
- **Setup**: Create entries with lemmas "run", "runner", "running"
- **Action**: `find_entries(lemma="run")`
- **Verify**: Returns entry with lemma "run" only

### TP-ENT-008: Delete entry without cascade
- **Setup**: Entry with senses
- **Action**: `delete_entry(entry_id)`
- **Verify**: Raises `RelationError`

### TP-ENT-009: Delete entry with cascade
- **Setup**: Entry with two senses, each having sense relations
- **Action**: `delete_entry(entry_id, cascade=True)`
- **Verify**: Entry, all its senses, all sense relations removed. Empty synsets marked unlexicalized. Edit history records all deletions.

---

## Sense Operations

### TP-SNS-001: Add sense
- **Setup**: Entry and synset exist
- **Action**: `add_sense(entry_id, synset_id)`
- **Verify**: Sense exists, links entry to synset, ID generated correctly

### TP-SNS-002: Add duplicate sense
- **Setup**: Entry already has sense for this synset
- **Action**: `add_sense(entry_id, synset_id)` again
- **Verify**: Raises `DuplicateEntityError`

### TP-SNS-003: Remove sense
- **Action**: `remove_sense(sense_id)`
- **Verify**: Sense gone, relations cleaned up

### TP-SNS-004: Reorder senses
- **Setup**: Entry with senses s1, s2, s3
- **Action**: `reorder_senses(entry_id, [s3.id, s1.id, s2.id])`
- **Verify**: entry_rank values are 1, 2, 3 matching new order

### TP-SNS-005: Add sense makes synset lexicalized
- **Setup**: Synset is unlexicalized (in unlexicalized_synsets)
- **Action**: `add_sense(entry_id, synset_id)`
- **Verify**: Synset removed from unlexicalized_synsets

---

## Relations

### TP-REL-001: Add hypernym creates inverse hyponym
- **Setup**: Two synsets A and B
- **Action**: `add_synset_relation(A.id, "hypernym", B.id)`
- **Verify**: synset_relations has hypernym(A→B) AND hyponym(B→A)

### TP-REL-002: Add with auto_inverse=False
- **Action**: `add_synset_relation(A.id, "hypernym", B.id, auto_inverse=False)`
- **Verify**: Only hypernym(A→B) exists, no hyponym(B→A)

### TP-REL-003: Remove relation removes inverse
- **Setup**: hypernym(A→B) and hyponym(B→A) exist
- **Action**: `remove_synset_relation(A.id, "hypernym", B.id)`
- **Verify**: Both gone

### TP-REL-004: Self-loop rejected
- **Action**: `add_synset_relation(A.id, "similar", A.id)`
- **Verify**: Raises `ValidationError`

### TP-REL-005: Symmetric relation stores two rows
- **Action**: `add_synset_relation(A.id, "antonym", B.id)`
- **Verify**: antonym(A→B) AND antonym(B→A) both exist

### TP-REL-006: Idempotent inverse
- **Setup**: hyponym(B→A) already exists manually
- **Action**: `add_synset_relation(A.id, "hypernym", B.id)`
- **Verify**: hypernym(A→B) added, no duplicate hyponym(B→A), no error

### TP-REL-007: Invalid relation type
- **Action**: `add_synset_relation(A.id, "not_a_type", B.id)`
- **Verify**: Raises `ValidationError`

### TP-REL-008: Sense relation
- **Setup**: Two senses s1, s2
- **Action**: `add_sense_relation(s1.id, "antonym", s2.id)`
- **Verify**: antonym(s1→s2) AND antonym(s2→s1) in sense_relations

### TP-REL-009: Relation with no inverse ("also")
- **Action**: `add_synset_relation(A.id, "also", B.id)`
- **Verify**: Only also(A→B) exists (no inverse for "also")

### TP-REL-010: "other" relation with dc:type
- **Action**: `add_synset_relation(A.id, "other", B.id, metadata={"type": "custom_rel"})`
- **Verify**: Relation exists with metadata containing dc:type

### TP-REL-011: Cross-lexicon relation
- **Setup**: Synset A in lexicon L1, synset B in lexicon L2
- **Action**: `add_synset_relation(A.id, "eq_synonym", B.id)`
- **Verify**: Relation created successfully

---

## Definitions and Examples

### TP-DEF-001: Add definition
- **Action**: `add_definition(synset_id, "A test definition")`
- **Verify**: Definition exists for synset

### TP-DEF-002: Update definition
- **Setup**: Synset has one definition
- **Action**: `update_definition(synset_id, 0, "Updated text")`
- **Verify**: Definition text changed

### TP-DEF-003: Remove definition
- **Action**: `remove_definition(synset_id, 0)`
- **Verify**: Definition gone

### TP-DEF-004: Add synset example
- **Action**: `add_synset_example(synset_id, "Example sentence")`
- **Verify**: Example exists

### TP-DEF-005: Remove synset example
- **Setup**: Synset has two examples
- **Action**: `remove_synset_example(synset_id, example_index=0)`
- **Verify**: Synset has one example remaining, edit history recorded

### TP-DEF-006: Remove sense example
- **Setup**: Sense has an example
- **Action**: `remove_sense_example(sense_id, example_index=0)`
- **Verify**: Sense has no examples, edit history recorded

### TP-DEF-007: Add sense example
- **Action**: `add_sense_example(sense_id, "Usage example")`
- **Verify**: Example exists in sense_examples table

---

## ILI Operations

### TP-ILI-001: Link ILI
- **Action**: `link_ili(synset_id, "i90287")`
- **Verify**: Synset's ili_rowid points to ILI record

### TP-ILI-002: Unlink ILI
- **Setup**: Synset linked to ILI
- **Action**: `unlink_ili(synset_id)`
- **Verify**: Synset's ili_rowid is NULL

### TP-ILI-003: Propose ILI
- **Action**: `propose_ili(synset_id, "A definition longer than twenty characters")`
- **Verify**: proposed_ilis row exists, synset marked as ili="in"

### TP-ILI-004: Propose ILI with short definition
- **Action**: `propose_ili(synset_id, "short")`
- **Verify**: Raises `ValidationError`

### TP-ILI-005: Link ILI when already mapped
- **Setup**: Synset already has ILI
- **Action**: `link_ili(synset_id, "i99999")`
- **Verify**: Raises `ValidationError`

---

## Validation

### TP-VAL-001: Validate clean database
- **Setup**: Import valid WN-LMF, no edits
- **Action**: `validate()`
- **Verify**: Empty list (no issues)

### TP-VAL-002: Missing inverse detected
- **Setup**: Add hypernym without auto_inverse
- **Action**: `validate_relations()`
- **Verify**: Returns VAL-REL-004 warning

### TP-VAL-003: Empty synset detected
- **Setup**: Create synset with no senses
- **Action**: `validate_synset(synset_id)`
- **Verify**: Returns VAL-SYN-001 warning

### TP-VAL-004: Blank definition detected
- **Setup**: Add empty definition
- **Action**: `validate()`
- **Verify**: Returns VAL-SYN-005 warning

### TP-VAL-005: ID prefix validation
- **Setup**: Manually insert synset with wrong prefix (bypass API)
- **Action**: `validate()`
- **Verify**: Returns VAL-EDT-001 error

### TP-VAL-006: Validate specific entry
- **Setup**: Entry with no senses
- **Action**: `validate_entry(entry_id)`
- **Verify**: Returns `[ValidationResult(rule_id="VAL-ENT-001", severity=WARNING)]`

### TP-VAL-007: Dangling relation target
- **Setup**: Add relation, then delete target (bypass cascade)
- **Action**: `validate()`
- **Verify**: Returns VAL-REL-001 error

---

## Import/Export

### TP-RT-001: Full round-trip (import → edit → export → reimport)
- **Setup**: Import fixture XML
- **Action**: Edit a definition, add a relation, export to new XML
- **Verify**: New XML is valid WN-LMF. Re-importing produces equivalent data.

### TP-RT-002: Export validates output
- **Setup**: Database with a dangling relation reference
- **Action**: `export_lmf("output.xml")`
- **Verify**: Raises `ExportError`

### TP-RT-003: Commit to wn
- **Setup**: Editor with valid data
- **Action**: `commit_to_wn()`
- **Verify**: Lexicon queryable via `wn.synsets()`, `wn.words()`

### TP-RT-004: Import preserves all data types
- **Setup**: XML with pronunciations, tags, syntactic behaviours, counts, metadata
- **Action**: `from_lmf("full_features.xml")` then `export_lmf("out.xml")`
- **Verify**: All data types present in output XML

### TP-RT-005: Import duplicate lexicon
- **Setup**: Lexicon already imported
- **Action**: `import_lmf("same_lexicon.xml")`
- **Verify**: Raises `DuplicateEntityError`

### TP-RT-006: Minimal-diff fidelity test
- **Setup**: Import a large WordNet (e.g., OEWN) via `from_wn("ewn:2024")`
- **Action**: Change only the version string via `update_lexicon(lexicon_id, version="2024-test")`, then `export_lmf("out.xml")`
- **Verify**: XML diff between original and exported is only the version string and specifier. All synsets, entries, senses, relations, definitions, examples, ILI mappings, pronunciations, tags, counts, lexfile names, and metadata are preserved byte-for-byte.
- **Marker**: `@pytest.mark.slow` (requires large WordNet download)

### TP-RT-007: Add/remove cycle fidelity test
- **Setup**: Import fixture XML. Record original state by exporting to `original.xml`.
- **Action**: Add a synset with senses and relations. Then delete the synset with `cascade=True`. Export to `roundtrip.xml`.
- **Verify**: `roundtrip.xml` is semantically equivalent to `original.xml` (same synsets, entries, senses, relations after normalization).

### TP-RT-008: Bulk SQL vs XML import equivalence
- **Setup**: A lexicon installed in `wn`'s database.
- **Action**: Import via bulk SQL path (`_import_from_wn_bulk`), export to `bulk.xml`. Import via XML fallback path (`_import_from_wn_xml`), export to `xml.xml`.
- **Verify**: Both XML files are semantically equivalent (same entity IDs, same relations, same definitions, same metadata). This validates that the fast path produces identical results to the reference implementation.
- **Marker**: `@pytest.mark.slow`

### TP-RT-009: Export with lmf_version="1.0" drops data
- **Setup**: Editor with synsets that have `lexfile` and senses with `count` values.
- **Action**: `export_lmf("out.xml", lmf_version="1.0")`
- **Verify**: Exported XML has no `lexfile` or `count` data. A warning was logged about data loss.

### TP-RT-010: Export with lmf_version="1.4" preserves data
- **Setup**: Same as TP-RT-009.
- **Action**: `export_lmf("out.xml", lmf_version="1.4")`
- **Verify**: Exported XML has `lexfile` and `count` data intact.

---

## Post-Commit Integration Tests

### TP-INTEG-001: Committed synsets queryable via `wn`
- **Setup**: Create synsets, entries, senses, relations. Call `commit_to_wn()`.
- **Action**: `wn.synsets(id=synset_id)`, `wn.words()`, `wn.senses()`
- **Verify**: All committed entities are queryable via `wn`'s public API.

### TP-INTEG-002: Committed relations navigable via `wn` graph methods
- **Setup**: Create hypernym chain A → B → C. Call `commit_to_wn()`.
- **Action**: Query `wn.synsets(id=A_id)[0].relations("hypernym")` and `wn.synsets(id=A_id)[0].hypernym_paths()`
- **Verify**: Relations are navigable. `hypernym_paths()` returns path `[A, B, C]`.

### TP-INTEG-003: Committed ILI mappings survive
- **Setup**: Create synset with `ili="i90287"`. Call `commit_to_wn()`.
- **Action**: `wn.synsets(id=synset_id)[0].ili`
- **Verify**: Returns `"i90287"`.

### TP-INTEG-004: Commit replaces existing lexicon cleanly
- **Setup**: `commit_to_wn()` an initial version. Modify a definition. `commit_to_wn()` again.
- **Action**: Query the modified synset via `wn`.
- **Verify**: Updated definition visible. No duplicate lexicon entries in `wn`.

### TP-INTEG-005: from_wn with metadata overrides
- **Setup**: `wn.download("ewn:2024")` (or fixture).
- **Action**: `WordnetEditor.from_wn("ewn:2024", version="2024-custom", label="My EWN")`
- **Verify**: `editor.get_lexicon(lexicon_id).version == "2024-custom"`. `editor.get_lexicon(lexicon_id).label == "My EWN"`. Original data (synsets, entries, senses) fully preserved.

---

## Change Tracking

### TP-HIST-001: Create records history
- **Action**: `create_synset(...)`
- **Verify**: `get_history(entity_type="synset")` returns CREATE record

### TP-HIST-002: Update records field-level change
- **Action**: `update_synset(synset_id, pos="v")`
- **Verify**: `get_history()` returns UPDATE record with field_name="pos", old_value="n", new_value="v"

### TP-HIST-003: Delete records history
- **Action**: `delete_synset(synset_id, cascade=True)`
- **Verify**: History has DELETE record for synset

### TP-HIST-004: Filter history by timestamp
- **Setup**: Create entity, wait, create another
- **Action**: `get_changes_since(middle_timestamp)`
- **Verify**: Only second entity's record returned

---

## Batch Operations

### TP-BATCH-001: Batch commits atomically
- **Action**: Create 100 synsets inside `batch()`
- **Verify**: All exist after batch exit

### TP-BATCH-002: Batch rollback on error
- **Action**: Inside `batch()`, create synsets, then raise exception
- **Verify**: No synsets created (all rolled back)

### TP-BATCH-003: Batch performance
- **Action**: Create 1000 entries inside vs. outside batch
- **Verify**: Batch is significantly faster (fewer transactions)

### TP-BATCH-004: Nested batch is no-op
- **Action**: `with editor.batch(): with editor.batch(): create_synset(...)`
- **Verify**: Works, commits at outermost batch exit

---

## Metadata Operations

### TP-META-001: Set and get metadata
- **Action**: `set_metadata("synset", synset_id, "dc:source", "PWN 3.1")`
- **Verify**: `get_metadata("synset", synset_id)` returns `{"dc:source": "PWN 3.1"}`

### TP-META-002: Remove metadata key
- **Action**: `set_metadata("synset", synset_id, "dc:source", None)`
- **Verify**: Key removed from metadata dict

### TP-META-003: Set confidence score
- **Action**: `set_confidence("synset", synset_id, 0.85)`
- **Verify**: Metadata contains `{"confidenceScore": 0.85}`

### TP-META-004: Confidence inheritance from lexicon
- **Setup**: Lexicon has `confidenceScore: 0.9`. Synset has no explicit confidence.
- **Action**: `export_lmf("out.xml")`
- **Verify**: Exported synset element inherits `confidenceScore="0.9"` from parent lexicon per WN-LMF spec (RULE-CONF-001).

### TP-META-005: Entity confidence overrides lexicon
- **Setup**: Lexicon has `confidenceScore: 0.9`. Synset has explicit `confidenceScore: 0.5`.
- **Action**: `export_lmf("out.xml")`
- **Verify**: Exported synset element has `confidenceScore="0.5"` (entity-level overrides lexicon-level per RULE-CONF-002).

---

## Cross-Lexicon Operations

### TP-XLEX-001: Import two lexicons
- **Setup**: Load `two_lexicons.xml` fixture containing two lexicons with cross-references
- **Action**: `from_lmf("two_lexicons.xml", "test.db")`
- **Verify**: Both lexicons imported. Cross-lexicon synset relations preserved. `find_entries(lexicon_id=...)` filters correctly.

### TP-XLEX-002: Cross-lexicon relation
- **Setup**: Two lexicons in editor
- **Action**: `add_synset_relation(synset_in_lex_A, synset_in_lex_B, "hypernym")`
- **Verify**: Relation created. Inverse `hyponym` created on the target synset in lexicon B.

### TP-XLEX-003: Import lexicon extension
- **Setup**: Load `extension.xml` fixture containing a lexicon extension
- **Action**: `from_lmf("extension.xml", "test.db")`
- **Verify**: Extension's `extends` attribute preserved. Extension entries correctly reference base lexicon synsets.
