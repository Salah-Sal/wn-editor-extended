"""Tests for metadata operations."""

import pytest


class TestSetGetMetadata:
    """TP-META-001, TP-META-002."""

    def test_set_and_get_metadata(self, editor_with_data):
        """TP-META-001."""
        ed, ss1, *_ = editor_with_data
        ed.set_metadata("synset", ss1.id, "dc:source", "PWN 3.1")
        meta = ed.get_metadata("synset", ss1.id)
        assert meta["dc:source"] == "PWN 3.1"

    def test_remove_metadata_key(self, editor_with_data):
        """TP-META-002."""
        ed, ss1, *_ = editor_with_data
        ed.set_metadata("synset", ss1.id, "dc:source", "PWN 3.1")
        ed.set_metadata("synset", ss1.id, "dc:source", None)
        meta = ed.get_metadata("synset", ss1.id)
        assert "dc:source" not in meta


class TestSetConfidence:
    """TP-META-003."""

    def test_set_confidence(self, editor_with_data):
        ed, ss1, *_ = editor_with_data
        ed.set_confidence("synset", ss1.id, 0.85)
        meta = ed.get_metadata("synset", ss1.id)
        assert meta["confidenceScore"] == 0.85
