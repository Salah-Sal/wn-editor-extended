"""Additional validation tests for redundant entries."""

import pytest

class TestSameLemmaRefSynset:
    """VAL-ENT-003: Multiple entries with same lemma referencing the same synset."""

    def test_same_lemma_references_same_synset(self, editor_with_lexicon):
        ed = editor_with_lexicon

        # 1. Create a synset
        ss1 = ed.create_synset("test", "n", "A feline animal")

        # 2. Create two entries with the same lemma
        # The editor should auto-generate unique IDs (e.g. test-cat-n and test-cat-n-2)
        e1 = ed.create_entry("test", "cat", "n")
        e2 = ed.create_entry("test", "cat", "n")

        assert e1.id != e2.id
        assert e1.lemma == "cat"
        assert e2.lemma == "cat"

        # 3. Link both entries to the same synset
        ed.add_sense(e1.id, ss1.id)
        ed.add_sense(e2.id, ss1.id)

        # 4. Validate
        results = ed.validate()

        # 5. Check for VAL-ENT-003
        val_ent_003 = [r for r in results if r.rule_id == "VAL-ENT-003"]
        assert len(val_ent_003) > 0

        # Verify message
        msg = val_ent_003[0].message
        assert "Multiple entries with lemma 'cat'" in msg
        assert "reference the same synset" in msg
