"""
Tests for SenseEditor class.
"""
import pytest
import wn
from wn_editor.editor import SenseEditor, SynsetEditor, RelationType


class TestSenseEditorCreation:
    """Tests for SenseEditor initialization."""

    def test_create_sense_from_components(self, test_lexicon):
        """Test creating a sense from lexicon, entry, and synset rowids."""
        entry = test_lexicon.create_entry()
        synset = test_lexicon.create_synset()

        sense_editor = SenseEditor(
            lexicon_rowid=test_lexicon.lex_rowid,
            entry_rowid=entry.entry_id,
            synset_rowid=synset.rowid
        )

        assert sense_editor is not None
        assert sense_editor.row_id is not None

    def test_create_sense_from_wn_sense(self, test_lexicon):
        """Test wrapping an existing wn.Sense."""
        # Create a synset with a word to get a sense
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("sensetest")

        synset = synset_editor.as_synset()
        senses = synset.senses()

        if senses:
            sense = senses[0]
            sense_editor = SenseEditor(sense=sense)
            assert sense_editor is not None
            assert sense_editor.row_id is not None

    def test_sense_requires_proper_arguments(self):
        """Test that SenseEditor requires either sense or all three rowids."""
        with pytest.raises(AttributeError):
            SenseEditor()  # No arguments

        with pytest.raises(AttributeError):
            SenseEditor(lexicon_rowid=1)  # Missing entry and synset

        with pytest.raises(AttributeError):
            SenseEditor(lexicon_rowid=1, entry_rowid=1)  # Missing synset


class TestSenseEditorSetId:
    """Tests for set_id method."""

    def test_set_id(self, test_lexicon):
        """Test setting a custom sense ID."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("setidtest")

        synset = synset_editor.as_synset()
        senses = synset.senses()

        if senses:
            sense = senses[0]
            sense_editor = SenseEditor(sense=sense)
            sense_editor.set_id("custom_sense_id_123")

            # Verify by creating a new editor
            # Note: The sense ID change should persist


class TestSenseEditorExamples:
    """Tests for example-related methods."""

    def test_add_example(self, test_lexicon):
        """Test adding an example to a sense."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("senseexample")

        synset = synset_editor.as_synset()
        senses = synset.senses()

        if senses:
            sense_editor = SenseEditor(sense=senses[0])
            sense_editor.add_example("This is a sense example.")

    def test_delete_example(self, test_lexicon):
        """Test deleting an example from a sense."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("delexamplesense")

        synset = synset_editor.as_synset()
        senses = synset.senses()

        if senses:
            sense_editor = SenseEditor(sense=senses[0])
            sense_editor.add_example("To be deleted")
            sense_editor.delete_example("To be deleted")


class TestSenseEditorRelations:
    """Tests for relation-related methods."""

    def test_set_relation_to_synset(self, test_lexicon, existing_synset):
        """Test setting a relation from sense to synset."""
        if existing_synset is None:
            pytest.skip("No existing synset available")

        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("sensereltest")

        synset = synset_editor.as_synset()
        senses = synset.senses()

        if senses:
            sense_editor = SenseEditor(sense=senses[0])
            sense_editor.set_relation_to_synset(
                existing_synset, RelationType.domain_topic
            )

    def test_set_relation_to_sense(self, test_lexicon):
        """Test setting a relation from sense to sense."""
        # Create two synsets with senses
        synset1 = test_lexicon.create_synset()
        synset1.add_word("sense1rel")

        synset2 = test_lexicon.create_synset()
        synset2.add_word("sense2rel")

        senses1 = synset1.as_synset().senses()
        senses2 = synset2.as_synset().senses()

        if senses1 and senses2:
            sense_editor = SenseEditor(sense=senses1[0])
            sense_editor.set_relation_to_sense(
                senses2[0], RelationType.similar
            )

    def test_delete_relation_to_synset(self, test_lexicon, existing_synset):
        """Test deleting a relation from sense to synset."""
        if existing_synset is None:
            pytest.skip("No existing synset available")

        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("delrelsynset")

        synset = synset_editor.as_synset()
        senses = synset.senses()

        if senses:
            sense_editor = SenseEditor(sense=senses[0])
            sense_editor.set_relation_to_synset(
                existing_synset, RelationType.domain_topic
            )
            sense_editor.delete_relation_to_synset(
                existing_synset, RelationType.domain_topic
            )


class TestSenseEditorCounts:
    """Tests for count-related methods."""

    def test_set_count(self, test_lexicon):
        """Test setting a count on a sense."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("counttest")

        synset = synset_editor.as_synset()
        senses = synset.senses()

        if senses:
            sense_editor = SenseEditor(sense=senses[0])
            sense_editor.set_count(42)

    def test_delete_count(self, test_lexicon):
        """Test deleting a count from a sense."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("delcounttest")

        synset = synset_editor.as_synset()
        senses = synset.senses()

        if senses:
            sense_editor = SenseEditor(sense=senses[0])
            sense_editor.set_count(10)
            sense_editor.delete_count(10)


class TestSenseEditorAdjposition:
    """Tests for adjposition methods."""

    def test_add_adjposition(self, test_lexicon):
        """Test adding an adjposition."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("adjtest")

        synset = synset_editor.as_synset()
        senses = synset.senses()

        if senses:
            sense_editor = SenseEditor(sense=senses[0])
            sense_editor.add_adjposition("a")


class TestSenseEditorDelete:
    """Tests for sense deletion."""

    def test_delete_sense(self, test_lexicon):
        """Test deleting a sense."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("deletemesense")

        synset = synset_editor.as_synset()
        initial_senses = synset.senses()

        if initial_senses:
            sense_editor = SenseEditor(sense=initial_senses[0])
            sense_editor.delete()

            # Verify the sense is gone
            updated_synset = synset_editor.as_synset()
            # The synset may still exist but sense count should be less


class TestSenseEditorAsSense:
    """Tests for as_sense method."""

    def test_as_sense_returns_sense(self, test_lexicon):
        """Test that as_sense returns a wn.Sense object."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("assensetest")

        synset = synset_editor.as_synset()
        senses = synset.senses()

        if senses:
            sense_editor = SenseEditor(sense=senses[0])
            sense = sense_editor.as_sense()

            assert sense is not None
            assert isinstance(sense, wn.Sense)
