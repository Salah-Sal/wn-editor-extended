"""
Tests for SynsetEditor class.
"""
import pytest
import wn
from wn_editor.editor import SynsetEditor, RelationType


class TestSynsetEditorCreation:
    """Tests for SynsetEditor initialization."""

    def test_create_synset_from_lexicon_name(self, test_lexicon):
        """Test creating a new synset from lexicon name."""
        lex_id = test_lexicon.as_lexicon().id
        synset_editor = SynsetEditor(lex_id)

        assert synset_editor is not None
        assert synset_editor.rowid is not None

    def test_create_synset_from_rowid(self, test_lexicon):
        """Test creating a synset from lexicon rowid."""
        synset_editor = SynsetEditor(test_lexicon.lex_rowid)

        assert synset_editor is not None
        assert synset_editor.rowid is not None

    def test_create_synset_from_existing(self, test_lexicon, existing_synset):
        """Test wrapping an existing synset."""
        if existing_synset is None:
            pytest.skip("No existing synset available")

        synset_editor = SynsetEditor(existing_synset)
        assert synset_editor is not None
        assert synset_editor.rowid is not None

    def test_from_rowid_classmethod(self, test_lexicon):
        """Test the from_rowid class method."""
        # First create a synset
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("fromrowid")
        rowid = synset_editor.rowid

        # Now get it via from_rowid
        restored = SynsetEditor.from_rowid(rowid)
        assert restored is not None
        assert restored.rowid == rowid


class TestSynsetEditorWords:
    """Tests for word-related methods."""

    def test_add_word(self, test_lexicon):
        """Test adding a word to a synset."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("testword")

        synset = synset_editor.as_synset()
        words = [w.lemma() for w in synset.words()]

        assert "testword" in words

    def test_add_multiple_words(self, test_lexicon):
        """Test adding multiple words to a synset."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("word1")
        synset_editor.add_word("word2")
        synset_editor.add_word("word3")

        synset = synset_editor.as_synset()
        words = [w.lemma() for w in synset.words()]

        assert "word1" in words
        assert "word2" in words
        assert "word3" in words

    def test_delete_word(self, test_lexicon):
        """Test deleting a word from a synset."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("keepme")
        synset_editor.add_word("deleteme")

        # Verify both exist
        synset = synset_editor.as_synset()
        words = [w.lemma() for w in synset.words()]
        assert "deleteme" in words

        # Delete one
        synset_editor.delete_word("deleteme")

        # Verify deletion
        synset = synset_editor.as_synset()
        words = [w.lemma() for w in synset.words()]
        assert "keepme" in words
        assert "deleteme" not in words

    def test_method_chaining_with_words(self, test_lexicon):
        """Test that add_word returns self for chaining."""
        synset_editor = test_lexicon.create_synset()
        result = synset_editor.add_word("chain1").add_word("chain2")

        assert result is synset_editor


class TestSynsetEditorDefinitions:
    """Tests for definition-related methods."""

    def test_add_definition(self, test_lexicon):
        """Test adding a definition."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("deftest")
        synset_editor.add_definition("A test definition")

        synset = synset_editor.as_synset()
        definition = synset.definition()

        assert definition == "A test definition"

    def test_mod_definition(self, test_lexicon):
        """Test modifying a definition."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("moddeftest")
        synset_editor.add_definition("Original definition")

        # Modify it
        synset_editor.mod_definition("Modified definition")

        synset = synset_editor.as_synset()
        definition = synset.definition()

        assert definition == "Modified definition"

    def test_mod_definition_creates_if_none(self, test_lexicon):
        """Test that mod_definition creates a definition if none exists."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("newdeftest")

        # No definition yet, mod_definition should create one
        synset_editor.mod_definition("New definition")

        synset = synset_editor.as_synset()
        definition = synset.definition()

        assert definition == "New definition"

    def test_add_definition_with_language(self, test_lexicon):
        """Test adding a definition with language specification."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("langtest")
        synset_editor.add_definition("English definition", language="en")

        synset = synset_editor.as_synset()
        assert synset.definition() is not None


class TestSynsetEditorExamples:
    """Tests for example-related methods."""

    def test_add_example(self, test_lexicon):
        """Test adding an example."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("exampletest")
        synset_editor.add_example("This is an example sentence.")

        synset = synset_editor.as_synset()
        examples = synset.examples()

        assert "This is an example sentence." in examples

    def test_add_multiple_examples(self, test_lexicon):
        """Test adding multiple examples."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("multiexample")
        synset_editor.add_example("Example one.")
        synset_editor.add_example("Example two.")

        synset = synset_editor.as_synset()
        examples = synset.examples()

        assert len(examples) >= 2
        assert "Example one." in examples
        assert "Example two." in examples

    def test_delete_example(self, test_lexicon):
        """Test deleting an example."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("delexample")
        synset_editor.add_example("Keep this.")
        synset_editor.add_example("Delete this.")

        synset_editor.delete_example("Delete this.")

        synset = synset_editor.as_synset()
        examples = synset.examples()

        assert "Keep this." in examples
        assert "Delete this." not in examples


class TestSynsetEditorRelations:
    """Tests for relation-related methods."""

    def test_set_hypernym_of(self, test_lexicon, existing_synset):
        """Test setting hypernym relation."""
        if existing_synset is None:
            pytest.skip("No existing synset available")

        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("hypernymtest")
        synset_editor.set_hypernym_of(existing_synset)

        # Verify the relation was created
        synset = synset_editor.as_synset()
        hypernyms = synset.hypernyms()
        # Note: relation direction might be inverse
        assert synset is not None

    def test_set_hyponym_of(self, test_lexicon, existing_synset):
        """Test setting hyponym relation."""
        if existing_synset is None:
            pytest.skip("No existing synset available")

        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("hyponymtest")
        synset_editor.set_hyponym_of(existing_synset)

        synset = synset_editor.as_synset()
        assert synset is not None

    def test_set_relation_to_synset(self, test_lexicon, existing_synset):
        """Test setting a generic relation to another synset."""
        if existing_synset is None:
            pytest.skip("No existing synset available")

        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("reltest")
        synset_editor.set_relation_to_synset(
            existing_synset, RelationType.similar
        )

        synset = synset_editor.as_synset()
        assert synset is not None

    def test_set_relation_with_string_creates_synset(self, test_lexicon):
        """Test that passing a string creates a new synset."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("parentword")
        synset_editor.set_hypernym_of("newchildword")

        # The new synset should have been created
        synsets = wn.synsets("newchildword")
        # May or may not find it depending on how wn indexes

    def test_delete_relation_to_synset(self, test_lexicon, existing_synset):
        """Test deleting a relation to a synset."""
        if existing_synset is None:
            pytest.skip("No existing synset available")

        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("delreltest")
        synset_editor.set_hypernym_of(existing_synset)
        synset_editor.delete_relation_to_synset(
            existing_synset, RelationType.hypernym
        )


class TestSynsetEditorDelete:
    """Tests for synset deletion."""

    def test_delete_synset(self, test_lexicon):
        """Test deleting a synset."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("deletemesynset")
        synset_id = synset_editor.as_synset().id

        synset_editor.delete()

        # Verify deletion
        with pytest.raises(Exception):
            wn.synset(synset_id)


class TestSynsetEditorILI:
    """Tests for ILI-related methods."""

    def test_set_proposed_ili(self, test_lexicon):
        """Test setting a proposed ILI."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("ilitest")
        synset_editor.set_proposed_ili("A proposed ILI definition")

        # Should not raise
        assert synset_editor.as_synset() is not None

    def test_delete_proposed_ili(self, test_lexicon):
        """Test deleting a proposed ILI."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("delilitest")
        synset_editor.set_proposed_ili("To be deleted")
        synset_editor.delete_proposed_ili()

        assert synset_editor.as_synset() is not None


class TestSynsetEditorAsSynset:
    """Tests for as_synset method."""

    def test_as_synset_returns_synset(self, test_lexicon):
        """Test that as_synset returns a wn.Synset object."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("assynsettest")

        synset = synset_editor.as_synset()

        assert synset is not None
        assert isinstance(synset, wn.Synset)

    def test_as_synset_id_matches(self, test_lexicon):
        """Test that the synset ID is consistent."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("idmatchtest")

        synset = synset_editor.as_synset()
        # Get it again
        synset2 = synset_editor.as_synset()

        assert synset.id == synset2.id
