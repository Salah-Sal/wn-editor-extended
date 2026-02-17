"""Tests for sense operations."""

import pytest

from wordnet_editor import (
    DuplicateEntityError,
    EntityNotFoundError,
    ValidationError,
)


class TestAddSense:
    """TP-SNS-001, TP-SNS-002, TP-SNS-005."""

    def test_add_sense(self, editor_with_lexicon):
        """TP-SNS-001."""
        ed = editor_with_lexicon
        ss = ed.create_synset("test", "n", "Concept")
        entry = ed.create_entry("test", "word", "n")
        sense = ed.add_sense(entry.id, ss.id)
        assert sense.entry_id == entry.id
        assert sense.synset_id == ss.id
        assert sense.id.startswith("test-")

    def test_add_duplicate_sense(self, editor_with_data):
        """TP-SNS-002."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        with pytest.raises(DuplicateEntityError):
            ed.add_sense(e1.id, ss1.id)

    def test_add_sense_makes_lexicalized(self, editor_with_lexicon):
        """TP-SNS-005."""
        ed = editor_with_lexicon
        ss = ed.create_synset(
            "test", "n", "Concept", lexicalized=False
        )
        assert not ss.lexicalized
        entry = ed.create_entry("test", "word", "n")
        ed.add_sense(entry.id, ss.id)
        ss_updated = ed.get_synset(ss.id)
        assert ss_updated.lexicalized


class TestRemoveSense:
    """TP-SNS-003."""

    def test_remove_sense(self, editor_with_data):
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.remove_sense(s1.id)
        with pytest.raises(EntityNotFoundError):
            ed.get_sense(s1.id)
        # Synset should now be unlexicalized
        ss = ed.get_synset(ss1.id)
        assert not ss.lexicalized


class TestReorderSenses:
    """TP-SNS-004."""

    def test_reorder(self, editor_with_lexicon):
        ed = editor_with_lexicon
        ss1 = ed.create_synset("test", "n", "Concept 1")
        ss2 = ed.create_synset("test", "n", "Concept 2")
        ss3 = ed.create_synset("test", "n", "Concept 3")
        entry = ed.create_entry("test", "word", "n")
        s1 = ed.add_sense(entry.id, ss1.id)
        s2 = ed.add_sense(entry.id, ss2.id)
        s3 = ed.add_sense(entry.id, ss3.id)

        ed.reorder_senses(entry.id, [s3.id, s1.id, s2.id])

        senses = ed.find_senses(entry_id=entry.id)
        assert senses[0].id == s3.id
        assert senses[0].entry_rank == 1
        assert senses[1].id == s1.id
        assert senses[1].entry_rank == 2
        assert senses[2].id == s2.id
        assert senses[2].entry_rank == 3


class TestMoveSense:
    """TP-MOVE-001, TP-MOVE-002."""

    def test_move_sense(self, editor_with_data):
        """TP-MOVE-001."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        # Add a sense relation to verify it's preserved
        ed.add_sense_relation(s1.id, "antonym", s2.id)

        moved = ed.move_sense(s1.id, ss2.id)
        assert moved.synset_id == ss2.id

        # Sense relations preserved
        rels = ed.get_sense_relations(s1.id)
        assert any(r.relation_type == "antonym" for r in rels)

        # Source synset unlexicalized
        ss = ed.get_synset(ss1.id)
        assert not ss.lexicalized

    def test_move_duplicate_check(self, editor_with_data):
        """TP-MOVE-002."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        # e1 already has s1 in ss1. Add another sense for e1 in ss2
        # Then try to move s1 to ss2 - should fail
        s_extra = ed.add_sense(e1.id, ss2.id)
        with pytest.raises(DuplicateEntityError):
            ed.move_sense(s1.id, ss2.id)
