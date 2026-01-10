"""
Tests for EntryEditor and FormEditor classes.
"""
import pytest
import wn
from wn_editor.editor import EntryEditor, FormEditor


class TestEntryEditorCreation:
    """Tests for EntryEditor initialization."""

    def test_create_entry(self, test_lexicon):
        """Test creating a new entry."""
        entry = test_lexicon.create_entry()

        assert entry is not None
        assert entry.entry_id is not None

    def test_create_entry_directly(self, test_lexicon):
        """Test creating entry with exists=False."""
        entry = EntryEditor(test_lexicon.lex_rowid, exists=False)

        assert entry is not None
        assert entry.entry_id is not None

    def test_get_existing_entry(self, test_lexicon):
        """Test getting an existing entry by ID."""
        # Create an entry first
        new_entry = test_lexicon.create_entry()
        entry_id = new_entry.entry_id

        # Get it again
        existing_entry = EntryEditor(entry_id, exists=True)
        assert existing_entry.entry_id == entry_id


class TestEntryEditorMethods:
    """Tests for EntryEditor methods."""

    def test_set_pos(self, test_lexicon):
        """Test setting part of speech."""
        entry = test_lexicon.create_entry()
        entry.set_pos("n")  # noun

        # Method should return self for chaining
        result = entry.set_pos("v")
        assert result is entry

    def test_add_form(self, test_lexicon):
        """Test adding a form to entry."""
        entry = test_lexicon.create_entry()
        entry.add_form("testlemma")

        # Method should return self for chaining
        result = entry.add_form("anotherform")
        assert result is entry

    def test_add_form_with_normalized(self, test_lexicon):
        """Test adding a form with normalized form."""
        entry = test_lexicon.create_entry()
        entry.add_form("TestLemma", normalized_form="testlemma")


class TestEntryEditorDelete:
    """Tests for entry deletion."""

    def test_delete_entry(self, test_lexicon):
        """Test deleting an entry."""
        entry = test_lexicon.create_entry()
        entry_id = entry.entry_id

        entry.delete()

        # Attempting to get the deleted entry should behave differently
        # (implementation specific)


class TestFormEditorCreation:
    """Tests for FormEditor initialization."""

    def test_create_form_from_entry(self, test_lexicon):
        """Test creating a form from an entry."""
        entry = test_lexicon.create_entry()
        form = FormEditor(entry.entry_id)

        assert form is not None
        assert form.row_id is not None

    def test_create_form_via_lexicon(self, test_lexicon):
        """Test creating a form via LexiconEditor."""
        form = test_lexicon.create_form()

        assert form is not None
        assert form.row_id is not None


class TestFormEditorMethods:
    """Tests for FormEditor methods."""

    def test_set_form(self, test_lexicon):
        """Test setting the form value."""
        entry = test_lexicon.create_entry()
        form = FormEditor(entry.entry_id)
        form.set_form("myform")

        # Method should return self for chaining
        result = form.set_form("newform")
        assert result is form

    def test_set_normalized_form(self, test_lexicon):
        """Test setting the normalized form."""
        entry = test_lexicon.create_entry()
        form = FormEditor(entry.entry_id)
        form.set_form("MyForm")
        form.set_normalized_form("myform")

        result = form.set_normalized_form("normalized")
        assert result is form

    def test_add_pronunciation(self, test_lexicon):
        """Test adding a pronunciation."""
        entry = test_lexicon.create_entry()
        form = FormEditor(entry.entry_id)
        form.set_form("pronunciation")

        form.add_pronunciation(
            pronunciation="/prəˌnʌnsiˈeɪʃən/",
            notation="IPA",
            phonemic=True
        )

    def test_add_pronunciation_with_variety(self, test_lexicon):
        """Test adding a pronunciation with variety."""
        entry = test_lexicon.create_entry()
        form = FormEditor(entry.entry_id)
        form.set_form("colour")

        form.add_pronunciation(
            pronunciation="/ˈkʌlər/",
            variety="US",
            notation="IPA"
        )

    def test_add_tag(self, test_lexicon):
        """Test adding a tag to a form."""
        entry = test_lexicon.create_entry()
        form = FormEditor(entry.entry_id)
        form.set_form("tagged")

        result = form.add_tag("informal", "register")
        assert result is form

    def test_delete_tag(self, test_lexicon):
        """Test deleting a tag from a form."""
        entry = test_lexicon.create_entry()
        form = FormEditor(entry.entry_id)
        form.set_form("taggeddelete")

        form.add_tag("slang", "register")
        result = form.delete_tag("slang", "register")
        assert result is form


class TestFormEditorDelete:
    """Tests for form deletion."""

    def test_delete_form(self, test_lexicon):
        """Test deleting a form."""
        entry = test_lexicon.create_entry()
        form = FormEditor(entry.entry_id)
        form.set_form("tobedeleted")

        form.delete()


class TestFormEditorFromWnForm:
    """Tests for creating FormEditor from wn.Form."""

    def test_create_from_wn_form(self, test_lexicon):
        """Test creating FormEditor from an existing wn.Form.

        Note: In wn >= 0.9.1, word.forms() returns strings, not wn.Form objects
        with _id attributes. This test verifies that FormEditor properly rejects
        invalid input types.
        """
        # Create a synset with a word to get forms
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("formtest")

        synset = synset_editor.as_synset()
        words = synset.words()

        if words:
            forms = words[0].forms()
            if forms:
                # word.forms() returns strings in current wn versions,
                # not wn.Form objects with _id attribute.
                # FormEditor should raise TypeError for invalid input.
                with pytest.raises(TypeError):
                    FormEditor(forms[0])


class TestMethodChaining:
    """Tests for method chaining across Entry and Form editors."""

    def test_entry_form_chain(self, test_lexicon):
        """Test chaining methods on entry and forms."""
        entry = test_lexicon.create_entry()
        entry.set_pos("n").add_form("chainedform")

        # Should complete without error

    def test_form_method_chain(self, test_lexicon):
        """Test chaining multiple form methods."""
        entry = test_lexicon.create_entry()
        form = FormEditor(entry.entry_id)

        form.set_form("chained") \
            .set_normalized_form("chained") \
            .add_tag("test", "category")

        # Should complete without error
