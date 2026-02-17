"""Tests for relation operations."""

import pytest

from wordnet_editor import ValidationError


class TestSynsetRelations:
    """TP-REL-001 through TP-REL-007, TP-REL-009, TP-REL-010, TP-REL-011."""

    def test_hypernym_creates_inverse(self, editor_with_data):
        """TP-REL-001."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_synset_relation(ss1.id, "hypernym", ss2.id)

        rels_a = ed.get_synset_relations(ss1.id)
        assert any(
            r.relation_type == "hypernym" and r.target_id == ss2.id
            for r in rels_a
        )

        rels_b = ed.get_synset_relations(ss2.id)
        assert any(
            r.relation_type == "hyponym" and r.target_id == ss1.id
            for r in rels_b
        )

    def test_no_auto_inverse(self, editor_with_data):
        """TP-REL-002."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_synset_relation(
            ss1.id, "hypernym", ss2.id, auto_inverse=False
        )

        rels_a = ed.get_synset_relations(ss1.id)
        assert any(r.relation_type == "hypernym" for r in rels_a)

        rels_b = ed.get_synset_relations(ss2.id)
        assert not any(r.relation_type == "hyponym" for r in rels_b)

    def test_remove_relation_removes_inverse(self, editor_with_data):
        """TP-REL-003."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_synset_relation(ss1.id, "hypernym", ss2.id)
        ed.remove_synset_relation(ss1.id, "hypernym", ss2.id)

        rels_a = ed.get_synset_relations(ss1.id)
        assert not any(r.relation_type == "hypernym" for r in rels_a)
        rels_b = ed.get_synset_relations(ss2.id)
        assert not any(r.relation_type == "hyponym" for r in rels_b)

    def test_self_loop_rejected(self, editor_with_data):
        """TP-REL-004."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        with pytest.raises(ValidationError):
            ed.add_synset_relation(ss1.id, "similar", ss1.id)

    def test_symmetric_stores_two_rows(self, editor_with_data):
        """TP-REL-005."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_synset_relation(ss1.id, "similar", ss2.id)

        rels_a = ed.get_synset_relations(ss1.id)
        assert any(
            r.relation_type == "similar" and r.target_id == ss2.id
            for r in rels_a
        )
        rels_b = ed.get_synset_relations(ss2.id)
        assert any(
            r.relation_type == "similar" and r.target_id == ss1.id
            for r in rels_b
        )

    def test_idempotent_inverse(self, editor_with_data):
        """TP-REL-006."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        # Manually add the inverse first
        ed.add_synset_relation(
            ss2.id, "hyponym", ss1.id, auto_inverse=False
        )
        # Now add the forward relation with auto_inverse
        ed.add_synset_relation(ss1.id, "hypernym", ss2.id)

        # Should not raise, and should not duplicate
        rels_b = ed.get_synset_relations(ss2.id, relation_type="hyponym")
        assert len(rels_b) == 1

    def test_invalid_relation_type(self, editor_with_data):
        """TP-REL-007."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        with pytest.raises(ValidationError):
            ed.add_synset_relation(ss1.id, "not_a_type", ss2.id)

    def test_relation_no_inverse(self, editor_with_data):
        """TP-REL-009: 'also' has no inverse defined in the inverse map."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_synset_relation(ss1.id, "also", ss2.id)
        rels_a = ed.get_synset_relations(ss1.id)
        assert any(r.relation_type == "also" for r in rels_a)
        # "also" is NOT in SYNSET_RELATION_INVERSES, so no inverse created
        rels_b = ed.get_synset_relations(ss2.id)
        assert not any(r.relation_type == "also" for r in rels_b)

    def test_other_relation_with_metadata(self, editor_with_data):
        """TP-REL-010."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_synset_relation(
            ss1.id, "other", ss2.id,
            metadata={"type": "custom_rel"},
        )
        rels = ed.get_synset_relations(ss1.id, relation_type="other")
        assert len(rels) == 1
        assert rels[0].metadata == {"type": "custom_rel"}

    def test_cross_lexicon_relation(self, editor):
        """TP-REL-011."""
        ed = editor
        ed.create_lexicon(
            "lex1", "Lex 1", "en", "a@b.c", "https://mit.edu", "1.0"
        )
        ed.create_lexicon(
            "lex2", "Lex 2", "ar", "a@b.c", "https://mit.edu", "1.0"
        )
        ss1 = ed.create_synset("lex1", "n", "Concept A")
        ss2 = ed.create_synset("lex2", "n", "Concept B")
        ed.add_synset_relation(ss1.id, "eq_synonym", ss2.id)

        rels = ed.get_synset_relations(ss1.id)
        assert any(r.relation_type == "eq_synonym" for r in rels)


class TestSenseRelations:
    """TP-REL-008."""

    def test_sense_relation_antonym(self, editor_with_data):
        """TP-REL-008."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_sense_relation(s1.id, "antonym", s2.id)

        rels_1 = ed.get_sense_relations(s1.id)
        assert any(
            r.relation_type == "antonym" and r.target_id == s2.id
            for r in rels_1
        )
        rels_2 = ed.get_sense_relations(s2.id)
        assert any(
            r.relation_type == "antonym" and r.target_id == s1.id
            for r in rels_2
        )
