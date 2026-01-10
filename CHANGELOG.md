# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/),
and this project adheres to [Semantic Versioning](https://semver.org/spec/v2.0.0.html).

## [0.6.1] - 2025-01-10

### Fixed
- Fixed `get_wordnet_overview()` to handle None rowid and use correct lexicon string format for `get_modified()`
- Fixed `mod_definition()` to query database directly instead of using `get_definitions()` which expects synset ID strings
- Fixed `FormEditor.__init__()` to properly validate input types with elif and raise TypeError for invalid inputs
- Fixed `add_syntactic_behaviour()` to check for None sense before calling SenseEditor
- Fixed `set_relation_to_synset()` and `delete_relation_to_synset()` source/target parameter order
- Fixed `delete_syntactic_behaviour()` missing `conn.commit()`
- Fixed `delete_pronunciation()` to include `self.row_id` in query parameters
- Fixed `create_sense()` to use keyword arguments when calling SenseEditor
- Fixed `RelationType` enum values to match the actual wn database relation_types table (all 27 values corrected)

### Added
- Comprehensive test suite with 109 tests covering all editor functionality

## [0.6.0] - 2025-01-10

### Added
- `SynsetEditor.set_pos(pos)` method to set part of speech on synsets
- `SynsetEditor.add_word(word, pos=None)` now accepts optional `pos` parameter
- POS is automatically set on both synset and entry when provided

### Fixed
- `FormEditor._create()` now sets `rank=0` instead of NULL, fixing issue where newly created terms couldn't be found by `wn.synsets()`
- Fixed `_get_valid_entity_id()` to properly handle None from max ID query
- Fixed `_get_valid_ili_id()` to properly increment ID
- Fixed `_get_all_lexicon_row_ids()` list comprehension
- Added missing `conn.commit()` in `ILIEditor._create()`

### Changed
- Package renamed to `wn-editor-extended`
- Updated Python version support to 3.9-3.12
- Relaxed `wn` dependency from `==0.9.1` to `>=0.9.1`

## [0.5.4] - Previous releases

See original [wn-editor](https://github.com/Hypercookie/wn-editor) for previous history.
