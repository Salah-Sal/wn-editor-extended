# wordnet-editor

A pure Python editing library for WordNets. Provides a complete programmatic API for creating, modifying, and exporting WordNet data in the [WN-LMF 1.4](https://globalwordnet.github.io/schemas/) format.

## What it does

- **Full CRUD** on synsets, lexical entries, senses, definitions, examples, and relations
- **Automatic inverse relations** — adding `hypernym` auto-creates the `hyponym` back-link
- **Compound operations** — synset merge, synset split, sense move (all atomic)
- **Validation engine** — 23 rules checking structural integrity, missing inverses, blank definitions, etc.
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

    # Create a synset
    ss = editor.create_synset(lexicon_id="mylex", pos="n")
    editor.add_definition(ss.id, "A small domesticated carnivorous mammal")

    # Create an entry with a sense
    entry = editor.create_entry(lexicon_id="mylex", lemma="cat", pos="n")
    editor.add_sense(entry_id=entry.id, synset_id=ss.id)

    # Add relations (inverse auto-created)
    editor.add_synset_relation(ss.id, "hypernym", other_ss.id)

    # Merge two synsets atomically
    editor.merge_synsets(source_id=ss1.id, target_id=ss2.id)

    # Validate
    results = editor.validate()

    # Export to WN-LMF XML
    editor.export_lmf("output.xml")

    # Or commit back to wn's database
    editor.commit_to_wn()
```

## Requirements

- Python >= 3.10
- [`wn`](https://github.com/goodmami/wn) >= 1.0.0

No other third-party dependencies.

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
