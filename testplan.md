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
- **Verify**: Raises `ImportError`

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
