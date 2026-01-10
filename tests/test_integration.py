"""
Integration tests for wn-editor.
These tests verify complete workflows across multiple editor classes.
"""
import pytest
import wn
from wn_editor.editor import (
    LexiconEditor,
    SynsetEditor,
    SenseEditor,
    EntryEditor,
    FormEditor,
    IlIEditor,
    RelationType,
    IliStatus,
)


class TestCompleteWordCreation:
    """Tests for creating complete word entries."""

    def test_create_word_with_all_components(self, test_lexicon):
        """Test creating a word with synset, sense, entry, and form."""
        # Create synset
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_definition("A test word for integration testing")
        synset_editor.add_example("Use the testword in a sentence.")

        # Add word (this creates entry, sense, and form internally)
        synset_editor.add_word("integrationtest")

        # Verify
        synset = synset_editor.as_synset()
        assert synset.definition() == "A test word for integration testing"
        assert "Use the testword in a sentence." in synset.examples()

        words = synset.words()
        assert len(words) >= 1

        lemmas = [w.lemma() for w in words]
        assert "integrationtest" in lemmas

    def test_create_synonym_set(self, test_lexicon):
        """Test creating a synset with multiple synonyms."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_definition("Things that are alike")

        # Add synonyms
        synset_editor.add_word("similar")
        synset_editor.add_word("alike")
        synset_editor.add_word("comparable")

        synset = synset_editor.as_synset()
        words = [w.lemma() for w in synset.words()]

        assert "similar" in words
        assert "alike" in words
        assert "comparable" in words


class TestRelationshipCreation:
    """Tests for creating relationships between synsets."""

    def test_create_hierarchy(self, test_lexicon):
        """Test creating a hypernym-hyponym hierarchy."""
        # Create parent synset
        parent = test_lexicon.create_synset()
        parent.add_word("vehicle")
        parent.add_definition("A means of transport")

        # Create child synset
        child = test_lexicon.create_synset()
        child.add_word("car")
        child.add_definition("A road vehicle with four wheels")
        child.set_hypernym_of(parent.as_synset())

        # Verify both exist
        parent_synset = parent.as_synset()
        child_synset = child.as_synset()

        assert parent_synset is not None
        assert child_synset is not None

    def test_create_part_whole_relation(self, test_lexicon):
        """Test creating holonym/meronym relationships."""
        # Create whole
        whole = test_lexicon.create_synset()
        whole.add_word("tree")
        whole.add_definition("A woody plant")

        # Create part
        part = test_lexicon.create_synset()
        part.add_word("branch")
        part.add_definition("Part of a tree")
        part.set_holonym_part_of(whole.as_synset())

        assert whole.as_synset() is not None
        assert part.as_synset() is not None


class TestMethodChaining:
    """Tests for fluent interface / method chaining."""

    def test_synset_method_chain(self, test_lexicon):
        """Test chaining multiple SynsetEditor methods."""
        synset = test_lexicon.create_synset() \
            .add_word("chainword1") \
            .add_word("chainword2") \
            .add_definition("Testing method chaining") \
            .add_example("This is chained.")

        result = synset.as_synset()
        assert result is not None
        assert result.definition() == "Testing method chaining"

    def test_form_editor_chain(self, test_lexicon):
        """Test chaining FormEditor methods."""
        entry = test_lexicon.create_entry()
        form = FormEditor(entry.entry_id)

        form.set_form("chainform") \
            .set_normalized_form("chainform") \
            .add_tag("test", "category")

        # Should complete without error


class TestModificationWorkflow:
    """Tests for modifying existing entries."""

    def test_modify_definition(self, test_lexicon):
        """Test modifying an existing definition."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("modifytest")
        synset_editor.add_definition("Original definition")

        # Modify
        synset_editor.mod_definition("New definition")

        synset = synset_editor.as_synset()
        assert synset.definition() == "New definition"

    def test_add_and_remove_example(self, test_lexicon):
        """Test adding and removing examples."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("examplemod")

        synset_editor.add_example("First example")
        synset_editor.add_example("Second example")

        synset = synset_editor.as_synset()
        assert "First example" in synset.examples()
        assert "Second example" in synset.examples()

        synset_editor.delete_example("First example")

        synset = synset_editor.as_synset()
        assert "First example" not in synset.examples()
        assert "Second example" in synset.examples()


class TestDeletionWorkflow:
    """Tests for deletion operations."""

    def test_delete_word_from_synset(self, test_lexicon):
        """Test removing a word from a synset."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("keepword")
        synset_editor.add_word("deleteword")

        # Verify both exist
        synset = synset_editor.as_synset()
        words = [w.lemma() for w in synset.words()]
        assert "keepword" in words
        assert "deleteword" in words

        # Delete one
        synset_editor.delete_word("deleteword")

        # Verify
        synset = synset_editor.as_synset()
        words = [w.lemma() for w in synset.words()]
        assert "keepword" in words
        assert "deleteword" not in words

    def test_delete_synset(self, test_lexicon):
        """Test deleting a complete synset."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("tobedeleted")
        synset_id = synset_editor.as_synset().id

        synset_editor.delete()

        # Should raise error when trying to access deleted synset
        with pytest.raises(Exception):
            wn.synset(synset_id)


class TestILIIntegration:
    """Tests for ILI integration with synsets."""

    def test_synset_with_proposed_ili(self, test_lexicon):
        """Test creating a synset with a proposed ILI."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("iliword")
        synset_editor.add_definition("Word with ILI")
        synset_editor.set_proposed_ili("Proposed interlingual definition")

        synset = synset_editor.as_synset()
        assert synset is not None

    def test_synset_with_ili_reference(self, test_lexicon):
        """Test linking a synset to an existing ILI."""
        # Create ILI
        ili_editor = IlIEditor(None)
        ili_editor.set_definition("Shared concept definition")
        ili_editor.set_status(IliStatus.proposed)

        # Create synset and link
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("sharedconcept")
        synset_editor.set_ili(ili_editor.row_id)

        synset = synset_editor.as_synset()
        assert synset is not None


class TestCrossLexiconOperations:
    """Tests for operations involving multiple lexicons."""

    def test_relation_to_external_lexicon(self, test_lexicon, existing_synset):
        """Test creating relations to synsets in other lexicons."""
        if existing_synset is None:
            pytest.skip("No existing synset available")

        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("crosslexword")
        synset_editor.add_definition("Word related to external lexicon")

        # Create relation to external synset
        synset_editor.set_hypernym_of(existing_synset)

        synset = synset_editor.as_synset()
        assert synset is not None


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_empty_synset(self, test_lexicon):
        """Test creating a synset without words."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_definition("Synset without words")

        synset = synset_editor.as_synset()
        assert synset is not None
        assert synset.definition() == "Synset without words"

    def test_synset_without_definition(self, test_lexicon):
        """Test creating a synset without definition."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("nodefword")

        synset = synset_editor.as_synset()
        words = [w.lemma() for w in synset.words()]
        assert "nodefword" in words

    def test_unicode_content(self, test_lexicon):
        """Test handling unicode characters."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("café")
        synset_editor.add_definition("A small restaurant serving coffee and light refreshments")
        synset_editor.add_example("Let's meet at the café.")

        synset = synset_editor.as_synset()
        words = [w.lemma() for w in synset.words()]
        assert "café" in words

    def test_special_characters_in_definition(self, test_lexicon):
        """Test handling special characters in definitions."""
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("specialchar")
        synset_editor.add_definition("Contains 'quotes', \"double quotes\", and other: symbols!")

        synset = synset_editor.as_synset()
        assert "quotes" in synset.definition()
