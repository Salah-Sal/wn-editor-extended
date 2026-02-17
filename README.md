# wordnet-editor

A pure Python editing library for WordNets. Provides a complete programmatic API for creating, modifying, and exporting WordNet data in the [WN-LMF 1.4](https://globalwordnet.github.io/schemas/) format.

## What it does

- **Full CRUD** on synsets, lexical entries, senses, definitions, examples, and relations
- **Automatic inverse relations** — adding `hypernym` auto-creates the `hyponym` back-link
- **Compound operations** — synset merge, synset split, sense move (all atomic)
- **Validation engine** — 22 rules checking structural integrity, missing inverses, blank definitions, etc.
- **Edit history** — field-level change tracking for every mutation
- **Import/export** — reads from WN-LMF XML or the `wn` library; exports valid WN-LMF 1.4 XML re-importable via `wn.add()`
- **Own SQLite database** — never mutates the `wn` library's store

## Quick start

```python
from wordnet_editor import WordnetEditor

# Start from an existing WordNet
import wn
wn.download("ewn:2024")
editor = WordnetEditor.from_wn("ewn:2024", "my_edits.db")

# Or from a WN-LMF XML file
editor = WordnetEditor.from_lmf("wordnet.xml", "my_edits.db")

# Or start from scratch
editor = WordnetEditor("my_edits.db")
```

```python
with WordnetEditor("my_edits.db") as editor:
    # Create a lexicon
    lex = editor.create_lexicon(
        id="mylex", label="My Lexicon",
        language="en", email="me@example.com",
        license="https://creativecommons.org/licenses/by/4.0/",
        version="1.0",
    )

    # Create a synset with its definition
    ss = editor.create_synset(
        lexicon_id="mylex", pos="n",
        definition="A small domesticated carnivorous mammal",
    )

    # Create an entry with a sense
    entry = editor.create_entry(lexicon_id="mylex", lemma="cat", pos="n")
    sense = editor.add_sense(entry_id=entry.id, synset_id=ss.id)

    # Add relations (inverse auto-created)
    editor.add_synset_relation(ss.id, "hypernym", other_ss.id)

    # Validate
    results = editor.validate()

    # Export to WN-LMF XML
    editor.export_lmf("output.xml")

    # Or commit back to wn's database
    editor.commit_to_wn()
```

## Installation

### Development setup

```bash
git clone <repo-url>
cd wordnet-editor
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

### Run tests

```bash
source .venv/bin/activate
pytest
```

### Requirements

- Python >= 3.10
- [`wn`](https://github.com/goodmami/wn) >= 1.0.0

No other third-party dependencies.

## Key concepts

| Concept | Description |
|---------|-------------|
| **Lexicon** | A named, versioned container for synsets and entries (one per language/project). |
| **Synset** | A set of synonymous senses representing one concept. Has definitions and examples. |
| **Entry** | A word (lemma) with a part of speech. Belongs to one lexicon. |
| **Sense** | The link between an entry and a synset — "word X in meaning Y." |
| **ILI** | Interlingual Index — a language-neutral identifier connecting equivalent synsets across WordNets. |
| **Auto-inverse relations** | Adding `hypernym(A→B)` automatically creates `hyponym(B→A)`. Works for all relation pairs that have a defined inverse. |
| **Cascade deletion** | Deleting a synset or entry with `cascade=True` removes its child senses first. Without cascade, the operation raises `RelationError`. |
| **Batch mode** | `with editor.batch():` groups multiple mutations into one atomic transaction. Nestable; only the outermost batch issues COMMIT/ROLLBACK. |

## Common workflows

### Build a WordNet from scratch

```python
with WordnetEditor("my.db") as ed:
    ed.create_lexicon(id="acme", label="ACME WordNet",
                      language="en", email="team@acme.org",
                      license="https://creativecommons.org/licenses/by/4.0/",
                      version="1.0")

    animal = ed.create_synset("acme", "n", "A living organism that feeds on organic matter")
    cat = ed.create_synset("acme", "n", "A small domesticated carnivorous mammal")
    ed.add_synset_relation(cat.id, "hypernym", animal.id)  # auto-creates hyponym

    entry = ed.create_entry("acme", "cat", "n")
    ed.add_sense(entry.id, cat.id)

    ed.export_lmf("acme.xml")
```

### Edit an existing WordNet

```python
import wn
wn.download("ewn:2024")

with WordnetEditor.from_wn("ewn:2024", "edits.db") as ed:
    # Find and update
    results = ed.find_synsets(definition_contains="feline")
    ed.add_definition(results[0].id, "A cat-like animal", language="en")

    # Check your work
    issues = ed.validate()
    for r in issues:
        print(f"[{r.severity}] {r.entity_id}: {r.message}")

    ed.export_lmf("ewn_edited.xml")
```

### Batch operations

```python
with ed.batch():
    for lemma, defn in word_list:
        ss = ed.create_synset("acme", "n", defn)
        entry = ed.create_entry("acme", lemma, "n")
        ed.add_sense(entry.id, ss.id)
# all committed atomically, or rolled back on error
```

### Merge and split synsets

```python
# Merge: move everything from ss1 into ss2, then delete ss1
merged = ed.merge_synsets(source_id=ss1.id, target_id=ss2.id)

# Split: partition senses into two new groups
groups = [[sense_a.id, sense_b.id], [sense_c.id]]
new_synsets = ed.split_synset(original.id, groups)
```

### Validation

```python
results = ed.validate()                     # full database
results = ed.validate(lexicon_id="acme")    # one lexicon
results = ed.validate_synset(ss.id)         # one synset
results = ed.validate_entry(entry.id)       # one entry
results = ed.validate_relations()           # relations only
```

## Error handling

All exceptions inherit from `WordnetEditorError`:

| Exception | When raised |
|-----------|-------------|
| `ValidationError` | Invalid data (bad POS, self-loop relation, invalid ID prefix, ILI constraint violation). |
| `EntityNotFoundError` | Requested entity doesn't exist in the database. |
| `DuplicateEntityError` | Creating an entity whose ID already exists. |
| `RelationError` | Relation constraint violation (e.g. deleting a synset that still has senses without `cascade=True`). |
| `ConflictError` | Conflicting state (e.g. merging two synsets that both have ILI mappings). |
| `DataImportError` | Failed to import data (malformed XML, missing lexicon in `wn`). |
| `ExportError` | Failed to export (validation errors in output data). |
| `DatabaseError` | Schema version mismatch or connection failure. |

## API overview

All public methods live on `WordnetEditor`. See [`docs/api-reference.md`](docs/api-reference.md) for full signatures and parameter details.

| Group | Methods |
|-------|---------|
| **Lifecycle** | `WordnetEditor(db_path)`, `close()`, `batch()`, `from_wn()`, `from_lmf()` |
| **Lexicon** | `create_lexicon`, `get_lexicon`, `list_lexicons`, `update_lexicon`, `delete_lexicon` |
| **Synset** | `create_synset`, `get_synset`, `find_synsets`, `update_synset`, `delete_synset` |
| **Entry** | `create_entry`, `get_entry`, `find_entries`, `update_entry`, `delete_entry`, `update_lemma` |
| **Form** | `add_form`, `remove_form`, `get_forms` |
| **Sense** | `add_sense`, `remove_sense`, `get_sense`, `find_senses`, `move_sense`, `reorder_senses` |
| **Definition** | `add_definition`, `update_definition`, `remove_definition`, `get_definitions` |
| **Example** | `add_synset_example`, `remove_synset_example`, `get_synset_examples`, `add_sense_example`, `remove_sense_example`, `get_sense_examples` |
| **Relation** | `add_synset_relation`, `remove_synset_relation`, `get_synset_relations`, `add_sense_relation`, `remove_sense_relation`, `get_sense_relations`, `add_sense_synset_relation`, `remove_sense_synset_relation` |
| **ILI** | `link_ili`, `unlink_ili`, `propose_ili`, `get_ili` |
| **Metadata** | `set_metadata`, `get_metadata`, `set_confidence` |
| **Compound** | `merge_synsets`, `split_synset` |
| **Validation** | `validate`, `validate_synset`, `validate_entry`, `validate_relations` |
| **History** | `get_history`, `get_changes_since` |
| **Export** | `export_lmf`, `commit_to_wn`, `import_lmf` |

## Design documents

This repository contains the complete architecture and design specifications:

| Document | Description |
|----------|-------------|
| [`models.md`](models.md) | Domain dataclasses, enums, and inverse relation map |
| [`schema.md`](schema.md) | SQLite database schema (DDL, indexes, constraints) |
| [`behavior.md`](behavior.md) | ~40 behavioral rules (deletion cascades, auto-inverse, merge/split/move) |
| [`api.md`](api.md) | Full public API — every method with signatures, parameters, and examples |
| [`pipeline.md`](pipeline.md) | Import/export pipeline (step-by-step SQL, round-trip fidelity) |
| [`validation.md`](validation.md) | 23 validation rules with severity levels |
| [`architecture.md`](architecture.md) | System overview, component diagram, data flows, design rationale |
| [`packaging.md`](packaging.md) | Directory layout, `pyproject.toml`, public API surface |
| [`testplan.md`](testplan.md) | ~65 structured test scenarios |

## Architecture

```
User code  ──▶  WordnetEditor  ──▶  editor.db (own SQLite)
                     │
                     ├── import from wn / WN-LMF XML
                     ├── edit (CRUD, merge, split, move)
                     ├── validate
                     └── export to WN-LMF XML / commit to wn
```

The editor maintains its own database — the `wn` library's store is read-only and never mutated. After editing, `export_lmf()` produces standard XML and `commit_to_wn()` pushes changes back into `wn`.

## License

MIT
