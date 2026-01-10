# wn-editor-extended

[![PyPI version](https://img.shields.io/pypi/v/wn-editor-extended.svg)](https://pypi.org/project/wn-editor-extended/)
[![Python versions](https://img.shields.io/pypi/pyversions/wn-editor-extended.svg)](https://pypi.org/project/wn-editor-extended/)
[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)

> An extended editor for wordnets, building on the popular [wn](https://github.com/goodmami/wn) package with additional features for synset creation and relation management.

This is an extended fork of [wn-editor](https://github.com/Hypercookie/wn-editor) by Jannes Müller, with additional features and bug fixes.

## Features

- **Edit WordNet databases** directly from Python
- **Create synsets** with words, definitions, and relations
- **Set part-of-speech** on synsets and entries
- **Manage relations** (hypernyms, hyponyms, etc.)
- **Full compatibility** with the `wn` package

### Enhancements over original wn-editor

- `SynsetEditor.set_pos()` - Set part of speech on synsets
- `SynsetEditor.add_word(word, pos=None)` - Add words with optional POS
- Fixed form creation to set `rank=0` (required for `wn.synsets()` to find new terms)
- Fixed various edge cases in ID generation

## Installation

```bash
pip install wn-editor-extended
```

## Quick Start

```python
import wn
from wn_editor.editor import LexiconEditor, SynsetEditor

# Download WordNet if needed
wn.download('ewn:2020')

# Get an editor for an installed lexicon
lex_edit = LexiconEditor('ewn')

# Create a new synset
synset_editor = lex_edit.create_synset()
synset_editor.add_word('blockchain', pos='n')
synset_editor.add_definition('A decentralized digital ledger technology')

# Get the synset object
new_synset = synset_editor.as_synset()
print(f"Created: {new_synset.id()}")

# Verify it can be found
print(wn.synsets('blockchain'))  # Should find the new synset
```

## Editing Existing Synsets

```python
import wn
from wn_editor.editor import SynsetEditor

# Get an existing synset
dog_synset = wn.synsets('dog', pos='n')[0]

# Create an editor for it
editor = SynsetEditor(dog_synset)

# Add a new word/synonym
editor.add_word('canine')

# Modify definition
editor.mod_definition('A domesticated carnivorous mammal')
```

## Setting Relations

```python
from wn_editor.editor import LexiconEditor, _set_relation_to_synset

lex_edit = LexiconEditor('ewn')

# Create a new synset
synset_editor = lex_edit.create_synset()
synset_editor.add_word('neural_ranker', pos='n')
synset_editor.add_definition('A ranking model using neural networks')

new_synset = synset_editor.as_synset()

# Set hypernym relation (15 is the database ID for hypernym)
hypernym = wn.synset('ewn-06590830-n')  # software synset
_set_relation_to_synset(new_synset, hypernym, 15)
```

## API Reference

### LexiconEditor

```python
LexiconEditor(lexicon_id: str)
    .create_synset() -> SynsetEditor
```

### SynsetEditor

```python
SynsetEditor(synset_or_rowid)
    .add_word(word: str, pos: str = None) -> SynsetEditor
    .add_definition(definition: str) -> SynsetEditor
    .mod_definition(definition: str) -> SynsetEditor
    .set_pos(pos: str) -> SynsetEditor
    .as_synset() -> wn.Synset
```

## Requirements

- Python 3.9+
- wn >= 0.9.1

## Acknowledgments

- Original [wn-editor](https://github.com/Hypercookie/wn-editor) by Jannes Müller
- [wn](https://github.com/goodmami/wn) package by Michael Wayne Goodman

## License

MIT License - See [LICENSE](LICENSE) for details.
