# Project Structure & Packaging Specification

**Library**: `wordnet-editor`
**Version**: 1.0
**Date**: 2026-02-16

---

## 8.1 — Directory Layout

```
wordnet-editor/
├── pyproject.toml
├── LICENSE
├── src/
│   └── wordnet_editor/
│       ├── __init__.py          # Public API exports
│       ├── editor.py            # WordnetEditor class
│       ├── db.py                # Database layer
│       ├── models.py            # Domain dataclasses and enums
│       ├── relations.py         # Relation types, inverse mapping
│       ├── importer.py          # Import pipeline
│       ├── exporter.py          # Export pipeline
│       ├── validator.py         # Validation engine
│       ├── history.py           # Change tracking
│       ├── exceptions.py        # Custom exception hierarchy
│       └── py.typed             # PEP 561 typing marker
├── tests/
│   ├── conftest.py              # Shared fixtures
│   ├── test_editor.py           # WordnetEditor init, from_wn, from_lmf, context manager
│   ├── test_lexicons.py         # Lexicon CRUD
│   ├── test_synsets.py          # Synset CRUD, merge, split
│   ├── test_entries.py          # Entry CRUD, forms
│   ├── test_senses.py           # Sense add/remove/move/reorder
│   ├── test_definitions.py      # Definition and example CRUD
│   ├── test_relations.py        # Relation CRUD, auto-inverse, symmetric
│   ├── test_ili.py              # ILI link/unlink/propose
│   ├── test_import_export.py    # Import/export round-trip
│   ├── test_validation.py       # All validation rules
│   ├── test_history.py          # Edit history recording and querying
│   ├── test_batch.py            # Batch context manager
│   └── fixtures/
│       ├── minimal.xml          # Minimal valid WN-LMF file (1 lexicon, 1 entry, 1 synset)
│       ├── two_lexicons.xml     # Two lexicons with cross-references
│       ├── extension.xml        # Lexicon extension example
│       └── full_features.xml    # All WN-LMF features exercised
└── resources/                   # Reference docs (not shipped in package)
    ├── example WN-LMF XML file.xml
    ├── GWA relation documentation.md
    ├── Open English WordNet FORMAT.md
    └── WN-LMF 1.4 schema specification.md
```

---

## 8.2 — `pyproject.toml` Specification

```toml
[build-system]
requires = ["hatchling"]
build-backend = "hatchling.build"

[project]
name = "wordnet-editor"
version = "0.1.0"
description = "A pure Python editing library for WordNets"
readme = "README.md"
requires-python = ">=3.10"
license = { text = "MIT" }
keywords = ["wordnet", "linguistics", "nlp", "editor", "lexicon"]
authors = [
    { name = "Author Name", email = "author@example.com" }
]
classifiers = [
    "Development Status :: 3 - Alpha",
    "Intended Audience :: Developers",
    "Intended Audience :: Science/Research",
    "License :: OSI Approved :: MIT License",
    "Programming Language :: Python :: 3",
    "Programming Language :: Python :: 3.10",
    "Programming Language :: Python :: 3.11",
    "Programming Language :: Python :: 3.12",
    "Programming Language :: Python :: 3.13",
    "Topic :: Scientific/Engineering :: Information Analysis",
    "Topic :: Text Processing :: Linguistic",
    "Typing :: Typed",
]
dependencies = [
    "wn>=1.0.0",
]

[project.optional-dependencies]
dev = [
    "pytest>=7.0",
    "mypy>=1.0",
    "ruff>=0.1",
]

[tool.hatch.build.targets.wheel]
packages = ["src/wordnet_editor"]

[tool.ruff]
target-version = "py310"
line-length = 88

[tool.ruff.lint]
select = ["E", "F", "I", "UP", "B", "SIM"]

[tool.mypy]
python_version = "3.10"
strict = true

[tool.pytest.ini_options]
testpaths = ["tests"]
```

---

## 8.3 — Public API Surface

`__init__.py` exports:

### Classes
```python
from wordnet_editor.editor import WordnetEditor
```

### Models (from `models.py`)
```python
from wordnet_editor.models import (
    LexiconModel,
    SynsetModel,
    EntryModel,
    SenseModel,
    FormModel,
    PronunciationModel,
    TagModel,
    DefinitionModel,
    ExampleModel,
    RelationModel,
    ILIModel,
    ProposedILIModel,
    CountModel,
    SyntacticBehaviourModel,
    EditRecord,
    ValidationResult,
)
```

### Enums (from `models.py`)
```python
from wordnet_editor.models import (
    PartOfSpeech,
    AdjPosition,
    SynsetRelationType,
    SenseRelationType,
    SenseSynsetRelationType,
    EditOperation,
    ValidationSeverity,
)
```

### Exceptions (from `exceptions.py`)
```python
from wordnet_editor.exceptions import (
    WordnetEditorError,
    ValidationError,
    EntityNotFoundError,
    DuplicateEntityError,
    RelationError,
    ConflictError,
    DataImportError,
    ExportError,
    DatabaseError,
)
```

### Constants (from `relations.py`)
```python
from wordnet_editor.relations import (
    SYNSET_RELATION_INVERSES,
    SENSE_RELATION_INVERSES,
)
```

### `__all__` definition

```python
__all__ = [
    "WordnetEditor",
    # Models
    "LexiconModel", "SynsetModel", "EntryModel", "SenseModel",
    "FormModel", "PronunciationModel", "TagModel",
    "DefinitionModel", "ExampleModel", "RelationModel",
    "ILIModel", "ProposedILIModel", "CountModel",
    "SyntacticBehaviourModel", "EditRecord", "ValidationResult",
    # Enums
    "PartOfSpeech", "AdjPosition",
    "SynsetRelationType", "SenseRelationType", "SenseSynsetRelationType",
    "EditOperation", "ValidationSeverity",
    # Exceptions
    "WordnetEditorError", "ValidationError", "EntityNotFoundError",
    "DuplicateEntityError", "RelationError", "ConflictError",
    "DataImportError", "ExportError", "DatabaseError",
    # Constants
    "SYNSET_RELATION_INVERSES", "SENSE_RELATION_INVERSES",
]
```
