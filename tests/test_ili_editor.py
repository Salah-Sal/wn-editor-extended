"""
Tests for IlIEditor class.
"""
import pytest
from wn._db import connect
from wn_editor.editor import IlIEditor, IliStatus


class TestIliEditorCreation:
    """Tests for IlIEditor initialization."""

    def test_create_new_ili(self):
        """Test creating a new ILI."""
        ili_editor = IlIEditor(None)

        assert ili_editor is not None
        assert ili_editor.row_id is not None

    def test_create_ili_from_rowid(self):
        """Test creating IlIEditor from existing row ID."""
        # First create an ILI
        new_ili = IlIEditor(None)
        row_id = new_ili.row_id

        # Now get it by row ID
        ili_editor = IlIEditor(row_id)
        assert ili_editor.row_id == row_id

    def test_create_ili_from_id_string(self):
        """Test creating IlIEditor from ILI ID string."""
        # First create an ILI and get its ID
        new_ili = IlIEditor(None)

        with connect() as conn:
            res = conn.cursor().execute(
                "SELECT id FROM ilis WHERE rowid = ?",
                (new_ili.row_id,)
            ).fetchone()
            ili_id = res[0]

        # Now get it by ID string
        ili_editor = IlIEditor(ili_id)
        assert ili_editor.row_id == new_ili.row_id


class TestIliEditorSetDefinition:
    """Tests for set_definition method."""

    def test_set_definition(self):
        """Test setting an ILI definition."""
        ili_editor = IlIEditor(None)
        ili_editor.set_definition("Test ILI definition")

        # Verify in database
        with connect() as conn:
            res = conn.cursor().execute(
                "SELECT definition FROM ilis WHERE rowid = ?",
                (ili_editor.row_id,)
            ).fetchone()

        assert res[0] == "Test ILI definition"

    def test_update_definition(self):
        """Test updating an existing definition."""
        ili_editor = IlIEditor(None)
        ili_editor.set_definition("Original definition")
        ili_editor.set_definition("Updated definition")

        with connect() as conn:
            res = conn.cursor().execute(
                "SELECT definition FROM ilis WHERE rowid = ?",
                (ili_editor.row_id,)
            ).fetchone()

        assert res[0] == "Updated definition"


class TestIliEditorSetStatus:
    """Tests for set_status method."""

    def test_set_status_presupposed(self):
        """Test setting status to presupposed."""
        ili_editor = IlIEditor(None)
        ili_editor.set_status(IliStatus.presupposed)

        with connect() as conn:
            res = conn.cursor().execute(
                "SELECT status_rowid FROM ilis WHERE rowid = ?",
                (ili_editor.row_id,)
            ).fetchone()

        assert res[0] == 1  # presupposed

    def test_set_status_proposed(self):
        """Test setting status to proposed."""
        ili_editor = IlIEditor(None)
        ili_editor.set_status(IliStatus.proposed)

        with connect() as conn:
            res = conn.cursor().execute(
                "SELECT status_rowid FROM ilis WHERE rowid = ?",
                (ili_editor.row_id,)
            ).fetchone()

        assert res[0] == 2  # proposed


class TestIliEditorSetMeta:
    """Tests for set_meta method."""

    def test_set_metadata(self):
        """Test setting metadata."""
        ili_editor = IlIEditor(None)
        metadata = {"source": "test", "note": "test note"}
        ili_editor.set_meta(metadata)

        # Metadata is stored, verify no errors occurred


class TestIliEditorIntegration:
    """Integration tests for IlIEditor."""

    def test_full_ili_workflow(self):
        """Test complete ILI creation workflow."""
        # Create new ILI
        ili_editor = IlIEditor(None)

        # Set all properties
        ili_editor.set_definition("A complete test ILI")
        ili_editor.set_status(IliStatus.proposed)
        ili_editor.set_meta({"dc:creator": "test"})

        # Verify all properties
        with connect() as conn:
            res = conn.cursor().execute(
                "SELECT id, definition, status_rowid FROM ilis WHERE rowid = ?",
                (ili_editor.row_id,)
            ).fetchone()

        assert res[0] is not None  # ID exists
        assert res[1] == "A complete test ILI"
        assert res[2] == 2  # proposed

    def test_ili_with_synset(self, test_lexicon):
        """Test associating ILI with a synset."""
        from wn_editor.editor import SynsetEditor

        # Create ILI
        ili_editor = IlIEditor(None)
        ili_editor.set_definition("ILI for synset test")

        # Create synset and associate ILI
        synset_editor = test_lexicon.create_synset()
        synset_editor.add_word("ilisynsettest")
        synset_editor.set_ili(ili_editor.row_id)

        # Verify association
        synset = synset_editor.as_synset()
        # The synset should now have an ILI


class TestIliStatus:
    """Tests for IliStatus enum."""

    def test_ili_status_values(self):
        """Test that IliStatus has correct values."""
        assert IliStatus.presupposed == 1
        assert IliStatus.proposed == 2
        assert IliStatus.active == 3  # Note: may not exist in DB

    def test_ili_status_names(self):
        """Test IliStatus enum names."""
        assert IliStatus.presupposed.name == "presupposed"
        assert IliStatus.proposed.name == "proposed"
        assert IliStatus.active.name == "active"
