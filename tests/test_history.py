"""Tests for change tracking / edit history."""

import datetime
import time


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
        s1 = ed.create_synset("test", "n", "First concept")

        # Database uses UTC timestamps with microseconds
        time.sleep(0.1)
        # Use UTC to match database
        middle = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%S.%f")
        time.sleep(0.1)

        s2 = ed.create_synset("test", "n", "Second concept")

        changes = ed.get_changes_since(middle)

        # Should include the second synset but not the first
        assert any(h.entity_id == s2.id for h in changes)
        assert not any(h.entity_id == s1.id for h in changes)
