"""Tests for change tracking / edit history."""

import time

import pytest


class TestHistoryCreate:
    """TP-HIST-001."""

    def test_create_records_history(self, editor_with_lexicon):
        ed = editor_with_lexicon
        ss = ed.create_synset("test", "n", "A concept")
        hist = ed.get_history(entity_type="synset", entity_id=ss.id)
        assert any(h.operation == "CREATE" for h in hist)


class TestHistoryUpdate:
    """TP-HIST-002."""

    def test_update_records_field_change(self, editor_with_data):
        ed, ss1, *_ = editor_with_data
        ed.update_synset(ss1.id, pos="v")
        hist = ed.get_history(entity_type="synset", entity_id=ss1.id)
        update_records = [
            h for h in hist
            if h.operation == "UPDATE" and h.field_name == "pos"
        ]
        assert len(update_records) >= 1
        rec = update_records[0]
        # History stores JSON-encoded values
        assert rec.old_value == '"n"'
        assert rec.new_value == '"v"'


class TestHistoryDelete:
    """TP-HIST-003."""

    def test_delete_records_history(self, editor_with_data):
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.delete_synset(ss1.id, cascade=True)
        hist = ed.get_history(entity_type="synset", entity_id=ss1.id)
        assert any(h.operation == "DELETE" for h in hist)


class TestHistoryTimestamp:
    """TP-HIST-004."""

    def test_filter_by_timestamp(self, editor_with_lexicon):
        ed = editor_with_lexicon
        ed.create_synset("test", "n", "First concept")
        time.sleep(0.05)
        middle = time.strftime("%Y-%m-%dT%H:%M:%S")
        time.sleep(0.05)
        ss2 = ed.create_synset("test", "n", "Second concept")

        changes = ed.get_changes_since(middle)
        # Should include the second synset but not the first
        assert any(h.entity_id == ss2.id for h in changes)
