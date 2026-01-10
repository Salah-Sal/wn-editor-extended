"""
Tests for LexiconEditor class.
"""
import pytest
import wn
from wn_editor.editor import LexiconEditor, SynsetEditor, SenseEditor, EntryEditor, FormEditor


class TestLexiconEditorCreation:
    """Tests for LexiconEditor initialization and creation."""

    def test_create_new_lexicon(self):
        """Test creating a new artificial lexicon."""
        import uuid
        unique_id = f"test-create-{uuid.uuid4().hex[:8]}"

        lex = LexiconEditor.create_new_lexicon(
            lex_id=unique_id,
            label="Test Creation",
            language="en",
            email="test@example.com",
            lex_license="MIT",
            version="1.0"
        )

        assert lex is not None
        assert lex.lex_rowid is not None

        # Verify it's in the database
        lexicon = lex.as_lexicon()
        assert lexicon.id == unique_id
        assert lexicon.label == "Test Creation"

        # Cleanup
        wn.remove(f"{unique_id}:1.0")

    def test_create_lexicon_with_metadata(self):
        """Test creating a lexicon with custom metadata."""
        import uuid
        unique_id = f"test-meta-{uuid.uuid4().hex[:8]}"

        metadata = {"note": "custom note", "dc:source": "test"}
        lex = LexiconEditor.create_new_lexicon(
            lex_id=unique_id,
            label="Test Metadata",
            language="en",
            email="test@example.com",
            lex_license="MIT",
            version="1.0",
            metadata=metadata
        )

        assert lex is not None
        # The artificial marker should be appended to the note
        wn.remove(f"{unique_id}:1.0")

    def test_get_lexicon_by_id(self, test_lexicon):
        """Test getting a LexiconEditor by lexicon ID."""
        lex_id = test_lexicon.as_lexicon().id
        lex = LexiconEditor(lex_id)
        assert lex.lex_rowid == test_lexicon.lex_rowid

    def test_get_lexicon_by_rowid(self, test_lexicon):
        """Test getting a LexiconEditor by row ID."""
        lex = LexiconEditor(test_lexicon.lex_rowid)
        assert lex.lex_rowid == test_lexicon.lex_rowid


class TestLexiconEditorCreateMethods:
    """Tests for LexiconEditor create methods."""

    def test_create_synset(self, test_lexicon):
        """Test creating a synset from lexicon."""
        synset_editor = test_lexicon.create_synset()

        assert synset_editor is not None
        assert isinstance(synset_editor, SynsetEditor)
        assert synset_editor.rowid is not None

    def test_create_entry(self, test_lexicon):
        """Test creating an entry from lexicon."""
        entry_editor = test_lexicon.create_entry()

        assert entry_editor is not None
        assert isinstance(entry_editor, EntryEditor)
        assert entry_editor.entry_id is not None

    def test_create_form(self, test_lexicon):
        """Test creating a form from lexicon."""
        form_editor = test_lexicon.create_form()

        assert form_editor is not None
        assert isinstance(form_editor, FormEditor)
        assert form_editor.row_id is not None

    def test_create_sense_with_synset(self, test_lexicon):
        """Test creating a sense with an existing synset."""
        synset_editor = test_lexicon.create_synset()
        synset = synset_editor.as_synset()

        sense_editor = test_lexicon.create_sense(synset=synset)

        assert sense_editor is not None
        assert isinstance(sense_editor, SenseEditor)

    def test_as_lexicon(self, test_lexicon):
        """Test getting the wn.Lexicon object."""
        lexicon = test_lexicon.as_lexicon()

        assert lexicon is not None
        assert isinstance(lexicon, wn.Lexicon)


class TestLexiconEditorSyntacticBehaviour:
    """Tests for syntactic behaviour methods."""

    def test_add_and_delete_syntactic_behaviour(self, test_lexicon):
        """Test adding and deleting syntactic behaviour."""
        # First create a sense to associate with
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("testword")

        # Add syntactic behaviour
        test_lexicon.add_syntactic_behaviour(
            syn_id="sb-test-1",
            frame="Someone %s something"
        )

        # Delete it
        test_lexicon.delete_syntactic_behaviour(
            syn_id="sb-test-1",
            frame="Someone %s something"
        )
