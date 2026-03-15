# wn-editor-extended

A pure Python editing library for WordNets. Provides full CRUD operations, automatic inverse relations, compound operations, validation, edit history, and WN-LMF 1.4 import/export.

## Project Info

- **PyPI name**: `wn-editor-extended` (v1.0.0)
- **Import name**: `wordnet_editor`
- **Python version**: 3.10
- **Main class**: `WordnetEditor`

## Architecture

This is a pure Python library project — no web frontend or backend server.

### Source Layout

- `src/wordnet_editor/` — Main library source
  - `editor.py` — Core `WordnetEditor` class with full CRUD API
  - `db.py` — SQLite database layer
  - `models.py` — Data models (Pydantic-style dataclasses)
  - `relations.py` — Synset/sense relation types and inverses
  - `validator.py` — 22-rule validation engine
  - `history.py` — Field-level edit history tracking
  - `importer.py` — WN-LMF XML and `wn` library import
  - `exporter.py` — WN-LMF 1.4 XML export
  - `exceptions.py` — Custom exception hierarchy
- `tests/` — Pytest test suite (153 tests)
- `data/` — Sample data files
  - `awn4.xml` — Arabic WordNet 4 source XML
  - `awn4_experiment.db` — AWN4 SQLite database with experimental edits (tracked via Git LFS)
- `resources/` — Documentation and reference files

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
```

## Data Notes

- `data/*.db` files are tracked via Git LFS (`.gitattributes`)
- The library uses its own SQLite database and never mutates the `wn` library's store
