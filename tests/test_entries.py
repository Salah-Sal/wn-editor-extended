"""Tests for entry CRUD and form operations."""

import pytest

from wordnet_editor import (
    DuplicateEntityError,
    EntityNotFoundError,
    RelationError,
    ValidationError,
)


class TestCreateEntry:
    """TP-ENT-001, TP-ENT-002."""

    def test_create_entry(self, editor_with_lexicon):
        """TP-ENT-001."""
        entry = editor_with_lexicon.create_entry("test", "cat", "n")
        assert entry.lemma == "cat"
        assert entry.pos == "n"
        assert entry.id.startswith("test-")
        forms = editor_with_lexicon.get_forms(entry.id)
        assert forms[0].rank == 0
        assert forms[0].written_form == "cat"

    def test_create_with_forms(self, editor_with_lexicon):
        """TP-ENT-002."""
        entry = editor_with_lexicon.create_entry(
            "test", "cat", "n", forms=["cats"]
        )
        forms = editor_with_lexicon.get_forms(entry.id)
        assert len(forms) == 2
        assert forms[0].written_form == "cat"
        assert forms[0].rank == 0
        assert forms[1].written_form == "cats"
        assert forms[1].rank == 1


class TestFormOperations:
    """TP-ENT-003, TP-ENT-004, TP-ENT-005."""

    def test_add_form_with_tags(self, editor_with_lexicon):
        """TP-ENT-003."""
        ed = editor_with_lexicon
        entry = ed.create_entry("test", "cat", "n")
        ed.add_form(entry.id, "cats", tags=[("NNS", "penn")])
        forms = ed.get_forms(entry.id)
        cats = [f for f in forms if f.written_form == "cats"][0]
        assert len(cats.tags) == 1
        assert cats.tags[0].tag == "NNS"
        assert cats.tags[0].category == "penn"

    def test_remove_form(self, editor_with_lexicon):
        """TP-ENT-004."""
        ed = editor_with_lexicon
        entry = ed.create_entry("test", "cat", "n", forms=["cats"])
        ed.remove_form(entry.id, "cats")
        forms = ed.get_forms(entry.id)
        assert len(forms) == 1
        assert forms[0].written_form == "cat"

    def test_remove_lemma_fails(self, editor_with_lexicon):
        """TP-ENT-005."""
        ed = editor_with_lexicon
        entry = ed.create_entry("test", "cat", "n")
        with pytest.raises(ValidationError):
            ed.remove_form(entry.id, "cat")


class TestUpdateEntry:
    """TP-ENT-006."""

    def test_update_pos(self, editor_with_lexicon):
        ed = editor_with_lexicon
        entry = ed.create_entry("test", "run", "n")
        updated = ed.update_entry(entry.id, pos="v")
        assert updated.pos == "v"


class TestFindEntries:
    """TP-ENT-007."""

    def test_find_by_lemma(self, editor_with_lexicon):
        ed = editor_with_lexicon
        ed.create_entry("test", "run", "n")
        ed.create_entry("test", "runner", "n")
        ed.create_entry("test", "running", "n")
        results = ed.find_entries(lemma="run")
        assert len(results) == 1
        assert results[0].lemma == "run"


class TestDeleteEntry:
    """TP-ENT-008, TP-ENT-009."""

    def test_delete_without_cascade(self, editor_with_data):
        """TP-ENT-008."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        with pytest.raises(RelationError):
            ed.delete_entry(e1.id)

    def test_delete_with_cascade(self, editor_with_data):
        """TP-ENT-009."""
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.delete_entry(e1.id, cascade=True)
        with pytest.raises(EntityNotFoundError):
            ed.get_entry(e1.id)
        # Synset should be unlexicalized now
        ss = ed.get_synset(ss1.id)
        assert not ss.lexicalized


class TestUpdateLemma:
    def test_update_lemma(self, editor_with_lexicon):
        ed = editor_with_lexicon
        entry = ed.create_entry("test", "cat", "n")
        ed.update_lemma(entry.id, "kitten")
        updated = ed.get_entry(entry.id)
        assert updated.lemma == "kitten"
        # ID should NOT change (RULE-ID-005)
        assert updated.id == entry.id
