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
- **Batch change requests** - Submit bulk modifications via YAML files
- **Change tracking and rollback** - Track all modifications and undo them
- **CLI tools** - Command-line interface for batch operations
- **Full compatibility** with the `wn` package

### Enhancements over original wn-editor

- `SynsetEditor.set_pos()` - Set part of speech on synsets
- `SynsetEditor.add_word(word, pos=None)` - Add words with optional POS
- **Batch change request system** - Submit bulk changes via YAML with validation
- **Change tracking system** - Record all database modifications with session-based grouping
- **Per-change rollback** - Undo individual changes or entire sessions
- **`wn-batch` CLI** - Command-line tool for batch operations
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

## Batch Change Requests

Submit bulk modifications via YAML files with validation and rollback support:

### YAML Format

```yaml
# changes.yaml
lexicon: ewn
session:
  name: "Add new terms"
  description: "Adding blockchain terminology"

changes:
  - operation: create_synset
    words:
      - word: blockchain
        pos: n
    definition: "A decentralized digital ledger technology"
    examples:
      - "Bitcoin uses blockchain technology"

  - operation: add_word
    synset: ewn-06590210-n
    word: cryptocurrency

  - operation: add_relation
    source: ewn-NEW-SYNSET-n
    target: ewn-06590210-n
    type: hypernym
```

### Python API

```python
from wn_editor.batch import (
    load_change_request,
    validate_change_request,
    execute_change_request,
)

# Load from YAML file
request = load_change_request("changes.yaml")

# Validate before execution
validation = validate_change_request(request)
if not validation.is_valid:
    for error in validation.errors:
        print(f"Error: {error.message}")

# Execute with change tracking
result = execute_change_request(request)
print(f"Applied {result.success_count}/{result.total_count} changes")

# Or dry run first
result = execute_change_request(request, dry_run=True)
```

### CLI Tool

```bash
# Validate a change request
wn-batch validate changes.yaml

# Apply changes (with confirmation)
wn-batch apply changes.yaml

# Apply without confirmation
wn-batch apply changes.yaml --yes

# Dry run (preview without applying)
wn-batch apply changes.yaml --dry-run

# View history
wn-batch history

# Rollback a session
wn-batch rollback <session_id>
```

### Supported Operations

| Operation | Description |
|-----------|-------------|
| `create_synset` | Create new synset with words and definition |
| `add_word` | Add word to existing synset |
| `delete_word` | Remove word from synset |
| `add_definition` | Add definition to synset |
| `modify_definition` | Change existing definition |
| `delete_definition` | Remove definition |
| `add_example` | Add usage example |
| `delete_example` | Remove example |
| `set_pos` | Set part of speech |
| `add_relation` | Create relation between synsets |
| `delete_relation` | Remove relation |
| `set_ili` | Link synset to Interlingual Index |
| `delete_ili` | Remove ILI link |

See [docs/batch-change-request-spec.md](docs/batch-change-request-spec.md) for full documentation.

## Change Tracking and Rollback

Track all database modifications and undo them if needed:

```python
from wn_editor import (
    enable_tracking,
    disable_tracking,
    tracking_session,
    rollback_session,
    rollback_change,
    get_session_history,
    get_changes,
)
from wn_editor.changelog import pre_change_hook, post_change_hook
from wn_editor.editor import set_changelog_hooks, LexiconEditor

# Enable change tracking (stores in ~/.wn_changelog.db by default)
enable_tracking()
set_changelog_hooks(pre_change_hook, post_change_hook)

# Use sessions to group related changes
with tracking_session("Add new domain terms") as session:
    lex = LexiconEditor('ewn')
    synset = lex.create_synset()
    synset.add_word('blockchain', pos='n')
    synset.add_definition('A decentralized digital ledger')

# View session history
for session in get_session_history(limit=10):
    print(f"{session.name}: {session.change_count} changes")

# View changes in a session
changes = get_changes(session_id=session.id)
for change in changes:
    print(f"  {change.operation} on {change.target_table}")

# Rollback an entire session
rollback_session(session.id)

# Or rollback a specific change
rollback_change(change_id=123)

# Disable tracking when done
disable_tracking()
```

### Tracking Features

- **Session-based grouping**: Group related changes together
- **Per-change rollback**: Undo individual INSERT, UPDATE, or DELETE operations
- **Session rollback**: Undo all changes in a session (in reverse order)
- **Change history**: Query and filter change history
- **Separate storage**: Changelog stored in `~/.wn_changelog.db`, not in the WordNet database

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

### Change Tracking Functions

```python
# Enable/disable tracking
enable_tracking(db_path: Path = None)  # Default: ~/.wn_changelog.db
disable_tracking()
is_tracking_enabled() -> bool

# Session management
start_session(name: str, description: str = None) -> Session
end_session(session_id: int)
tracking_session(name: str, description: str = None)  # Context manager

# Query history
get_session_history(limit: int = 100, include_rolled_back: bool = False) -> List[Session]
get_changes(session_id: int = None, target_table: str = None, ...) -> List[Change]
get_change_by_id(change_id: int) -> Change

# Rollback operations
can_rollback(change_id: int) -> Tuple[bool, str]
rollback_change(change_id: int) -> bool
rollback_session(session_id: int) -> int  # Returns count of rolled back changes

# Maintenance
prune_history(days: int = 30) -> int  # Delete old changes
```

## Requirements

- Python 3.9+
- wn >= 0.9.1
- PyYAML >= 6.0

## Acknowledgments

- Original [wn-editor](https://github.com/Hypercookie/wn-editor) by Jannes Müller
- [wn](https://github.com/goodmami/wn) package by Michael Wayne Goodman

## License

MIT License - See [LICENSE](LICENSE) for details.
