"""Tests for synset CRUD, merge, and split operations."""

import pytest

from wordnet_editor import (
    ConflictError,
    DuplicateEntityError,
    EntityNotFoundError,
    RelationError,
    ValidationError,
)


class TestCreateSynset:
    """TP-SYN-001 through TP-SYN-005."""

    def test_create_with_valid_data(self, editor_with_lexicon):
        """TP-SYN-001."""
        ss = editor_with_lexicon.create_synset("test", "n", "A large feline")
        assert ss.pos == "n"
        assert ss.id.startswith("test-")
        assert ss.lexicon_id == "test"

    def test_create_with_explicit_id(self, editor_with_lexicon):
        """TP-SYN-002."""
        ss = editor_with_lexicon.create_synset(
            "test", "n", "Test", id="test-custom-n"
        )
        assert ss.id == "test-custom-n"

    def test_create_with_invalid_pos(self, editor_with_lexicon):
        """TP-SYN-003."""
        with pytest.raises(ValidationError):
            editor_with_lexicon.create_synset("test", "z", "Test")

    def test_create_with_ili_proposal(self, editor_with_lexicon):
        """TP-SYN-004."""
        ss = editor_with_lexicon.create_synset(
            "test", "n", "Test",
            ili="in",
            ili_definition="A concept at least twenty chars",
        )
        assert ss.ili == "in"

    def test_create_with_short_ili_definition(self, editor_with_lexicon):
        """TP-SYN-005."""
        with pytest.raises(ValidationError):
            editor_with_lexicon.create_synset(
                "test", "n", "Test",
                ili="in", ili_definition="short",
            )


class TestDeleteSynset:
    """TP-SYN-006, TP-SYN-007."""

    def test_delete_without_cascade_has_senses(self, editor_with_data):
        """TP-SYN-006."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        with pytest.raises(RelationError):
            ed.delete_synset(ss1.id)

    def test_delete_with_cascade(self, editor_with_data):
        """TP-SYN-007."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_synset_relation(ss1.id, "hypernym", ss2.id)
        ed.delete_synset(ss1.id, cascade=True)
        with pytest.raises(EntityNotFoundError):
            ed.get_synset(ss1.id)
        # Inverse relation should also be gone
        rels = ed.get_synset_relations(ss2.id)
        assert not any(r.relation_type == "hyponym" for r in rels)


class TestFindSynsets:
    """TP-SYN-008."""

    def test_find_by_definition(self, editor_with_data):
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        results = ed.find_synsets(definition_contains="feline")
        assert len(results) == 1
        assert results[0].id == ss1.id


class TestUpdateSynset:
    """TP-SYN-009."""

    def test_update_pos(self, editor_with_data):
        ed, ss1, *_ = editor_with_data
        updated = ed.update_synset(ss1.id, pos="v")
        assert updated.pos == "v"
        # History should have been recorded
        hist = ed.get_history(entity_type="synset", entity_id=ss1.id)
        assert any(h.operation == "UPDATE" and h.field_name == "pos" for h in hist)


class TestMergeSynsets:
    """TP-MERGE-001 through TP-MERGE-005."""

    def test_merge_transfers_senses(self, editor_with_lexicon):
        """TP-MERGE-001."""
        ed = editor_with_lexicon
        ss_a = ed.create_synset("test", "n", "Concept A")
        ss_b = ed.create_synset("test", "n", "Concept B")
        e1 = ed.create_entry("test", "word1", "n")
        e2 = ed.create_entry("test", "word2", "n")
        e3 = ed.create_entry("test", "word3", "n")
        s1 = ed.add_sense(e1.id, ss_a.id)
        s2 = ed.add_sense(e2.id, ss_a.id)
        s3 = ed.add_sense(e3.id, ss_b.id)

        result = ed.merge_synsets(ss_a.id, ss_b.id)
        senses = ed.find_senses(synset_id=ss_b.id)
        assert len(senses) == 3

        with pytest.raises(EntityNotFoundError):
            ed.get_synset(ss_a.id)

    def test_merge_transfers_relations(self, editor_with_lexicon):
        """TP-MERGE-002."""
        ed = editor_with_lexicon
        ss_a = ed.create_synset("test", "n", "A")
        ss_b = ed.create_synset("test", "n", "B")
        ss_c = ed.create_synset("test", "n", "C")
        ed.add_synset_relation(ss_a.id, "hypernym", ss_c.id)

        ed.merge_synsets(ss_a.id, ss_b.id)
        rels = ed.get_synset_relations(ss_b.id)
        assert any(
            r.relation_type == "hypernym" and r.target_id == ss_c.id
            for r in rels
        )

    def test_merge_deduplicates_relations(self, editor_with_lexicon):
        """TP-MERGE-003."""
        ed = editor_with_lexicon
        ss_a = ed.create_synset("test", "n", "A")
        ss_b = ed.create_synset("test", "n", "B")
        ss_c = ed.create_synset("test", "n", "C")
        ed.add_synset_relation(ss_a.id, "hypernym", ss_c.id)
        ed.add_synset_relation(ss_b.id, "hypernym", ss_c.id)

        ed.merge_synsets(ss_a.id, ss_b.id)
        rels = ed.get_synset_relations(ss_b.id, relation_type="hypernym")
        assert len(rels) == 1

    def test_merge_conflicting_ili(self, editor_with_lexicon):
        """TP-MERGE-004."""
        ed = editor_with_lexicon
        ss_a = ed.create_synset("test", "n", "A")
        ss_b = ed.create_synset("test", "n", "B")
        ed.link_ili(ss_a.id, "i100")
        ed.link_ili(ss_b.id, "i200")

        with pytest.raises(ConflictError):
            ed.merge_synsets(ss_a.id, ss_b.id)

    def test_merge_transfers_ili(self, editor_with_lexicon):
        """TP-MERGE-005."""
        ed = editor_with_lexicon
        ss_a = ed.create_synset("test", "n", "A")
        ss_b = ed.create_synset("test", "n", "B")
        ed.link_ili(ss_a.id, "i100")

        ed.merge_synsets(ss_a.id, ss_b.id)
        ili = ed.get_ili(ss_b.id)
        assert ili is not None
        assert ili.id == "i100"


class TestSplitSynset:
    """TP-SPLIT-001, TP-SPLIT-002."""

    def test_split_into_two(self, editor_with_lexicon):
        """TP-SPLIT-001."""
        ed = editor_with_lexicon
        ss = ed.create_synset("test", "n", "Original")
        e1 = ed.create_entry("test", "w1", "n")
        e2 = ed.create_entry("test", "w2", "n")
        e3 = ed.create_entry("test", "w3", "n")
        s1 = ed.add_sense(e1.id, ss.id)
        s2 = ed.add_sense(e2.id, ss.id)
        s3 = ed.add_sense(e3.id, ss.id)

        # Add a relation to test copying
        ss2 = ed.create_synset("test", "n", "Other")
        ed.add_synset_relation(ss.id, "hypernym", ss2.id)

        results = ed.split_synset(ss.id, [[s1.id], [s2.id, s3.id]])
        assert len(results) == 2

        # Original keeps s1
        orig_senses = ed.find_senses(synset_id=results[0].id)
        assert len(orig_senses) == 1
        assert orig_senses[0].id == s1.id

        # New synset has s2, s3
        new_senses = ed.find_senses(synset_id=results[1].id)
        assert len(new_senses) == 2

        # Relations copied to new synset
        new_rels = ed.get_synset_relations(results[1].id)
        assert any(r.relation_type == "hypernym" for r in new_rels)

    def test_split_invalid_groups(self, editor_with_lexicon):
        """TP-SPLIT-002."""
        ed = editor_with_lexicon
        ss = ed.create_synset("test", "n", "Test")
        e1 = ed.create_entry("test", "w1", "n")
        e2 = ed.create_entry("test", "w2", "n")
        s1 = ed.add_sense(e1.id, ss.id)
        s2 = ed.add_sense(e2.id, ss.id)

        with pytest.raises(ValidationError):
            ed.split_synset(ss.id, [[s1.id]])  # s2 missing
