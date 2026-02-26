"""Tests for WordnetEditor initialization and context manager."""

import os
import tempfile

from wordnet_editor import WordnetEditor


class TestInit:
    """TP-INIT-001, TP-INIT-003, TP-INIT-004."""

    def test_create_new_file_database(self):
        """TP-INIT-001: Create editor with new database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        os.unlink(path)
        try:
            editor = WordnetEditor(path)
            assert os.path.exists(path)
            # Check meta table
            row = editor._conn.execute(
                "SELECT value FROM meta WHERE key='schema_version'"
            ).fetchone()
            assert row[0] == "1.0"
            editor.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)

    def test_in_memory_database(self):
        """TP-INIT-003: In-memory database."""
        editor = WordnetEditor(":memory:")
        row = editor._conn.execute(
            "SELECT value FROM meta WHERE key='schema_version'"
        ).fetchone()
        assert row[0] == "1.0"
        editor.close()

    def test_context_manager(self):
        """TP-INIT-004: Context manager."""
        with WordnetEditor() as editor:
            assert editor is not None
        # Connection should be closed after exit

    def test_open_existing_database(self):
        """TP-INIT-002: Open existing database."""
        with tempfile.NamedTemporaryFile(suffix=".db", delete=False) as f:
            path = f.name
        os.unlink(path)
        try:
            ed1 = WordnetEditor(path)
            ed1.create_lexicon(
                "test", "Test", "en", "t@t.com",
                "https://mit.edu", "1.0",
            )
            ed1.close()

            ed2 = WordnetEditor(path)
            lexicons = ed2.list_lexicons()
            assert len(lexicons) == 1
            assert lexicons[0].id == "test"
            ed2.close()
        finally:
            if os.path.exists(path):
                os.unlink(path)
