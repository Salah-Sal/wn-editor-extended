# wn-editor-extended

A pure Python editing library for WordNets. Provides full CRUD operations, automatic inverse relations, compound operations, validation, edit history, and WN-LMF 1.4 import/export.

## Project Info

- **PyPI name**: `wn-editor-extended` (v1.0.0)
- **Import name**: `wordnet_editor`
- **Python version**: 3.10
- **Main class**: `WordnetEditor`
- **Schema version**: 2.0

## Architecture

This is a pure Python library project — no web frontend or backend server.

### Source Layout

- `src/wordnet_editor/` — Main library source
  - `editor.py` — Core `WordnetEditor` class with full CRUD API
  - `db.py` — SQLite database layer (schema v2.0)
  - `models.py` — Data models (Pydantic-style dataclasses)
  - `relations.py` — Synset/sense relation types and inverses
  - `validator.py` — 22-rule validation engine
  - `history.py` — Field-level edit history tracking (supports session_id)
  - `importer.py` — WN-LMF XML and `wn` library import
  - `exporter.py` — WN-LMF 1.4 XML export
  - `exceptions.py` — Custom exception hierarchy
- `tests/` — Pytest test suite (153 tests)
- `tools/` — Utility scripts
  - `migrate_v1_to_v2.py` — Database migration from schema v1.0 to v2.0
- `data/` — Sample data files
  - `awn4.xml` — Arabic WordNet 4 source XML
  - `awn4_experiment.db` — AWN4 SQLite database with experimental edits (tracked via Git LFS)
- `resources/` — Documentation and reference files

### Schema v2.0 Changes (from v1.0)

The v2.0 schema eliminates 6 anti-pattern satellite tables by inlining their data:

- `unlexicalized_synsets` table → `synsets.lexicalized` BOOLEAN column (default 1)
- `unlexicalized_senses` table → `senses.lexicalized` BOOLEAN column (default 1)
- `entry_index` table → `entries.lemma` TEXT column
- `adjpositions` table → `senses.adjposition` TEXT column (nullable)
- `proposed_ilis` table → `synsets.proposed_ili_definition` + `synsets.proposed_ili_metadata` columns
- `ili_statuses` lookup table → `ilis.status` TEXT with CHECK constraint

Additional improvements:
- `PRAGMA busy_timeout=5000` for better concurrent access
- `UNIQUE(id, lexicon_rowid)` constraint on senses
- `edit_history.session_id` column for grouping related edits

## Dependencies

- `wn>=1.0.0` — Python WordNet library (core dependency)
- `pytest`, `mypy`, `ruff` — Dev dependencies

## Workflow

The **Start application** workflow runs `python3 -m pytest tests/ -v` to demonstrate all 153 tests pass.

## Development

```bash
python3 -m pytest tests/ -v          # Run full test suite
python3 -m ruff check src/           # Lint
python3 -m mypy src/                 # Type check
python tools/migrate_v1_to_v2.py db  # Migrate v1 database to v2
```

## Data Notes

- `data/*.db` files are tracked via Git LFS (`.gitattributes`)
- The library uses its own SQLite database and never mutates the `wn` library's store
