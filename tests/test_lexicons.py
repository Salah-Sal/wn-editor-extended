"""Tests for lexicon CRUD operations."""

import pytest

from wordnet_editor import (
    DuplicateEntityError,
    EntityNotFoundError,
    LexiconModel,
)


class TestCreateLexicon:
    """TP-LEX-001, TP-LEX-002."""

    def test_create_with_valid_data(self, editor):
        """TP-LEX-001."""
        lex = editor.create_lexicon(
            "awn", "Arabic WordNet", "ar", "a@b.c",
            "https://opensource.org/licenses/MIT", "4.0",
        )
        assert isinstance(lex, LexiconModel)
        assert lex.id == "awn"
        assert lex.label == "Arabic WordNet"
        assert lex.language == "ar"
        assert lex.version == "4.0"

    def test_create_duplicate(self, editor):
        """TP-LEX-002."""
        editor.create_lexicon(
            "awn", "Test", "ar", "a@b.c", "https://mit.edu", "4.0"
        )
        with pytest.raises(DuplicateEntityError):
            editor.create_lexicon(
                "awn", "Test2", "ar", "a@b.c", "https://mit.edu", "4.0"
            )


class TestUpdateLexicon:
    """TP-LEX-003."""

    def test_update_label(self, editor_with_lexicon):
        ed = editor_with_lexicon
        updated = ed.update_lexicon("test", label="New Label")
        assert updated.label == "New Label"
        # Other fields unchanged
        assert updated.language == "en"


class TestGetLexicon:
    """TP-LEX-004."""

    def test_get_nonexistent(self, editor):
        with pytest.raises(EntityNotFoundError):
            editor.get_lexicon("nonexistent")


class TestListLexicons:
    """TP-LEX-005."""

    def test_list_two(self, editor):
        editor.create_lexicon(
            "a", "A", "en", "a@b.c", "https://mit.edu", "1.0"
        )
        editor.create_lexicon(
            "b", "B", "en", "a@b.c", "https://mit.edu", "1.0"
        )
        lexicons = editor.list_lexicons()
        assert len(lexicons) == 2
        ids = {l.id for l in lexicons}
        assert ids == {"a", "b"}


class TestDeleteLexicon:
    """TP-LEX-006."""

    def test_delete_cascades(self, editor_with_data):
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.delete_lexicon("test")
        assert ed.list_lexicons() == []
        with pytest.raises(EntityNotFoundError):
            ed.get_synset(ss1.id)

    def test_delete_nonexistent(self, editor):
        with pytest.raises(EntityNotFoundError):
            editor.delete_lexicon("nope")
