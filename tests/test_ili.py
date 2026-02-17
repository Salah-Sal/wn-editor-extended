"""Tests for ILI operations."""

import pytest

from wordnet_editor import ValidationError


class TestLinkILI:
    """TP-ILI-001, TP-ILI-005."""

    def test_link_ili(self, editor_with_lexicon):
        """TP-ILI-001."""
        ed = editor_with_lexicon
        ss = ed.create_synset("test", "n", "Test concept")
        ed.link_ili(ss.id, "i90287")
        ili = ed.get_ili(ss.id)
        assert ili is not None
        assert ili.id == "i90287"

    def test_link_already_mapped(self, editor_with_lexicon):
        """TP-ILI-005."""
        ed = editor_with_lexicon
        ss = ed.create_synset("test", "n", "Test concept")
        ed.link_ili(ss.id, "i90287")
        with pytest.raises(ValidationError):
            ed.link_ili(ss.id, "i99999")


class TestUnlinkILI:
    """TP-ILI-002."""

    def test_unlink_ili(self, editor_with_lexicon):
        ed = editor_with_lexicon
        ss = ed.create_synset("test", "n", "Test concept")
        ed.link_ili(ss.id, "i90287")
        ed.unlink_ili(ss.id)
        ili = ed.get_ili(ss.id)
        assert ili is None


class TestProposeILI:
    """TP-ILI-003, TP-ILI-004."""

    def test_propose_ili(self, editor_with_lexicon):
        """TP-ILI-003."""
        ed = editor_with_lexicon
        ss = ed.create_synset("test", "n", "Test concept")
        ed.propose_ili(ss.id, "A definition longer than twenty characters")
        updated = ed.get_synset(ss.id)
        assert updated.ili == "in"

    def test_propose_short_definition(self, editor_with_lexicon):
        """TP-ILI-004."""
        ed = editor_with_lexicon
        ss = ed.create_synset("test", "n", "Test concept")
        with pytest.raises(ValidationError):
            ed.propose_ili(ss.id, "short")
