# CLAUDE.md — wn-editor-extended

## Package Info
- **PyPI name**: `wn-editor-extended` (v1.0.0)
- **Import name**: `wordnet_editor`
- **Repo**: `git@github.com:Salah-Sal/wn-editor-extended.git`

## Development Setup
```bash
cd /Users/salahmac/projects/wordnet-editor
python3 -m venv .venv
source .venv/bin/activate
pip install -e ".[dev]"
```

Always activate the venv before running commands:
```bash
source /Users/salahmac/projects/wordnet-editor/.venv/bin/activate
```

## Running Tests
```bash
source .venv/bin/activate
pytest
```

## Database Tracking
- `data/*.db` files are tracked via **Git LFS** (`.gitattributes`)
- `*.db` is in `.gitignore` but `!data/*.db` exempts the data directory
- `data/awn4.xml` — source AWN4 wordnet (tracked normally)
- `data/awn4_experiment.db` — AWN4 + experimental edits (tracked via LFS)
- Run `git lfs install` after cloning to pull LFS files

## Git Conventions
- Never add `Co-Authored-By` lines to commit messages
- Remote: `git@github.com:Salah-Sal/wn-editor-extended.git`
- `legacy` branch preserves the old wn-editor-extended implementation
- `main` branch is the v1.0.0 rewrite (this codebase)
