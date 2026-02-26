"""Test VAL-SYN-007: Duplicate definitions across synsets."""

import pytest

class TestDuplicateDefinitions:
    """VAL-SYN-007."""

    def test_duplicate_definitions(self, editor_with_lexicon):
        """Test that duplicate definitions are detected."""
        ed = editor_with_lexicon
        definition = "A generic definition used by multiple synsets."

        # Create two synsets with the same definition
        # Note: editor_with_lexicon creates a lexicon with id="test"
        ss1 = ed.create_synset("test", "n", definition)
        ss2 = ed.create_synset("test", "n", definition)

        results = ed.validate()

        # Check for the specific rule ID
        errors = [r for r in results if r.rule_id == "VAL-SYN-007"]
        assert len(errors) == 1
        assert errors[0].entity_type == "synset"
        assert errors[0].severity == "WARNING"
        assert "duplicated across 2 synsets" in errors[0].message
        assert errors[0].details["definition"] == definition

    def test_no_duplicate_definitions(self, editor_with_lexicon):
        """Test that distinct definitions do not trigger the warning."""
        ed = editor_with_lexicon

        ed.create_synset("test", "n", "Definition A")
        ed.create_synset("test", "n", "Definition B")

        results = ed.validate()

        errors = [r for r in results if r.rule_id == "VAL-SYN-007"]
        assert len(errors) == 0

    def test_duplicate_definitions_filtered(self, editor):
        """Test that duplicate definitions are detected per lexicon filter."""
        ed = editor

        # Create two lexicons
        ed.create_lexicon("lex1", "Lexicon 1", "en", "t@t.com", "http://l.org", "1.0")
        ed.create_lexicon("lex2", "Lexicon 2", "en", "t@t.com", "http://l.org", "1.0")

        definition = "Shared definition"

        # Two synsets in lex1 with duplicate definitions
        # NOTE: create_synset does NOT accept lexicon_id as a kwarg, it's a positional arg.
        ed.create_synset("lex1", "n", definition)
        ed.create_synset("lex1", "n", definition)

        results_lex1 = ed.validate(lexicon_id="lex1")
        errors_lex1 = [r for r in results_lex1 if r.rule_id == "VAL-SYN-007"]
        assert len(errors_lex1) == 1
        assert "duplicated across 2 synsets" in errors_lex1[0].message

        # If we add another duplicate in lex2
        ed.create_synset("lex2", "n", definition)

        # If we validate all, we should see it duplicated across 3 synsets
        # Because the rule queries across ALL definitions if lexicon_id is None
        results_all = ed.validate()
        errors_all = [r for r in results_all if r.rule_id == "VAL-SYN-007"]
        assert len(errors_all) == 1
        assert "duplicated across 3 synsets" in errors_all[0].message

        # If we validate only lex2, there is only 1 occurrence in lex2.
        # However, the rule implementation uses GROUP BY definition HAVING cnt > 1
        # AND applies the lexicon filter to the WHERE clause.
        # So for lex2, it will find "Shared definition" in lex2, count=1.
        # HAVING cnt > 1 will be False. So no error for lex2.

        results_lex2 = ed.validate(lexicon_id="lex2")
        errors_lex2 = [r for r in results_lex2 if r.rule_id == "VAL-SYN-007"]
        assert len(errors_lex2) == 0
