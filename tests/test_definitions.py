"""Tests for definition and example operations."""

import pytest

from wordnet_editor import EntityNotFoundError


class TestAddDefinition:
    """TP-DEF-001."""

    def test_add_definition(self, editor_with_data):
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_definition(ss1.id, "An alternative definition")
        defs = ed.get_definitions(ss1.id)
        assert len(defs) == 2
        assert defs[1].text == "An alternative definition"


class TestUpdateDefinition:
    """TP-DEF-002."""

    def test_update_definition(self, editor_with_data):
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.update_definition(ss1.id, 0, "Updated definition text")
        defs = ed.get_definitions(ss1.id)
        assert defs[0].text == "Updated definition text"


class TestRemoveDefinition:
    """TP-DEF-003."""

    def test_remove_definition(self, editor_with_data):
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_definition(ss1.id, "Second definition")
        ed.remove_definition(ss1.id, 0)
        defs = ed.get_definitions(ss1.id)
        assert len(defs) == 1
        assert defs[0].text == "Second definition"


class TestSynsetExamples:
    """TP-DEF-004, TP-DEF-005."""

    def test_add_synset_example(self, editor_with_data):
        """TP-DEF-004."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_synset_example(ss1.id, "Example sentence")
        examples = ed.get_synset_examples(ss1.id)
        assert len(examples) == 1
        assert examples[0].text == "Example sentence"

    def test_remove_synset_example(self, editor_with_data):
        """TP-DEF-005."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_synset_example(ss1.id, "Example 1")
        ed.add_synset_example(ss1.id, "Example 2")
        ed.remove_synset_example(ss1.id, 0)
        examples = ed.get_synset_examples(ss1.id)
        assert len(examples) == 1
        assert examples[0].text == "Example 2"


class TestSenseExamples:
    """TP-DEF-006, TP-DEF-007."""

    def test_remove_sense_example(self, editor_with_data):
        """TP-DEF-006."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_sense_example(s1.id, "Usage example")
        ed.remove_sense_example(s1.id, 0)
        examples = ed.get_sense_examples(s1.id)
        assert len(examples) == 0

    def test_add_sense_example(self, editor_with_data):
        """TP-DEF-007."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_sense_example(s1.id, "Usage example")
        examples = ed.get_sense_examples(s1.id)
        assert len(examples) == 1
        assert examples[0].text == "Usage example"
