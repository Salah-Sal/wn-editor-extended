import pytest

class TestDuplicateILI:
    """Tests for VAL-SYN-002: ILI used by multiple synsets."""

    def test_duplicate_ili_detected(self, editor_with_lexicon):
        """Verify that multiple synsets linking to the same ILI triggers a warning."""
        ed = editor_with_lexicon

        # Create two synsets
        ss1 = ed.create_synset("test", "n", "First synset definition")
        ss2 = ed.create_synset("test", "n", "Second synset definition")

        # Link both to the same ILI
        ili_id = "i12345"
        ed.link_ili(ss1.id, ili_id)
        ed.link_ili(ss2.id, ili_id)

        # Run validation
        results = ed.validate()

        # Check for VAL-SYN-002 warning
        val_syn_002_results = [r for r in results if r.rule_id == "VAL-SYN-002"]
        assert len(val_syn_002_results) > 0, "Expected VAL-SYN-002 warning not found"

        # Verify details of the finding
        finding = val_syn_002_results[0]
        assert finding.severity == "WARNING"
        assert finding.entity_type == "synset"
        assert finding.entity_id == ili_id
        assert "used by 2 synsets" in finding.message
