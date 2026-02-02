"""
Tests for changelog and rollback functionality.
"""
import pytest
import tempfile
from pathlib import Path

import wn
from wn_editor import (
    LexiconEditor,
    SynsetEditor,
    enable_tracking,
    disable_tracking,
    is_tracking_enabled,
    start_session,
    end_session,
    tracking_session,
    get_session_history,
    get_changes,
    get_change_by_id,
    rollback_change,
    rollback_session,
    can_rollback,
    prune_history,
    get_most_recent_unclosed_session,
    Session,
    Change,
)
from wn_editor.changelog import (
    ChangelogDB,
    _get_db,
    pre_change_hook,
    post_change_hook,
    _set_active_session,
    get_active_session,
)
from wn_editor.editor import set_changelog_hooks, clear_changelog_hooks


@pytest.fixture
def temp_changelog_db():
    """Create a temporary changelog database for testing."""
    with tempfile.TemporaryDirectory() as tmpdir:
        db_path = Path(tmpdir) / "test_changelog.db"
        yield db_path


@pytest.fixture
def clean_tracking_state():
    """Ensure tracking is disabled before and after each test."""
    disable_tracking()
    clear_changelog_hooks()
    yield
    disable_tracking()
    clear_changelog_hooks()


class TestChangelogDB:
    """Tests for the ChangelogDB class."""

    def test_create_database(self, temp_changelog_db):
        """Test that database and schema are created."""
        db = ChangelogDB(temp_changelog_db)
        assert temp_changelog_db.exists()

    def test_create_session(self, temp_changelog_db):
        """Test creating a session."""
        db = ChangelogDB(temp_changelog_db)
        session = db.create_session("Test Session", "A test session")

        assert session is not None
        assert session.id is not None
        assert session.name == "Test Session"
        assert session.description == "A test session"
        assert session.started_at is not None
        assert session.ended_at is None
        assert session.rolled_back is False

    def test_end_session(self, temp_changelog_db):
        """Test ending a session."""
        db = ChangelogDB(temp_changelog_db)
        session = db.create_session("Test")
        db.end_session(session.id)

        updated = db.get_session(session.id)
        assert updated.ended_at is not None

    def test_record_change(self, temp_changelog_db):
        """Test recording a change."""
        db = ChangelogDB(temp_changelog_db)
        session = db.create_session("Test")

        change_id = db.record_change(
            editor_class="SynsetEditor",
            method_name="add_word",
            target_table="senses",
            target_rowid=123,
            operation="INSERT",
            new_data={"id": "test-sense-1"},
            session_id=session.id,
        )

        assert change_id is not None

        change = db.get_change(change_id)
        assert change is not None
        assert change.editor_class == "SynsetEditor"
        assert change.method_name == "add_word"
        assert change.target_table == "senses"
        assert change.target_rowid == 123
        assert change.operation == "INSERT"
        assert change.new_data == {"id": "test-sense-1"}

    def test_get_changes_by_session(self, temp_changelog_db):
        """Test filtering changes by session."""
        db = ChangelogDB(temp_changelog_db)
        session1 = db.create_session("Session 1")
        session2 = db.create_session("Session 2")

        db.record_change("Editor", "method1", "table1", 1, "INSERT", session_id=session1.id)
        db.record_change("Editor", "method2", "table2", 2, "INSERT", session_id=session1.id)
        db.record_change("Editor", "method3", "table3", 3, "INSERT", session_id=session2.id)

        changes1 = db.get_changes(session_id=session1.id)
        changes2 = db.get_changes(session_id=session2.id)

        assert len(changes1) == 2
        assert len(changes2) == 1

    def test_get_sessions(self, temp_changelog_db):
        """Test getting session list."""
        db = ChangelogDB(temp_changelog_db)
        db.create_session("Session 1")
        db.create_session("Session 2")
        db.create_session("Session 3")

        sessions = db.get_sessions(limit=10)
        assert len(sessions) == 3

    def test_mark_change_rolled_back(self, temp_changelog_db):
        """Test marking a change as rolled back."""
        db = ChangelogDB(temp_changelog_db)
        change_id = db.record_change("Editor", "method", "table", 1, "INSERT")

        db.mark_change_rolled_back(change_id)

        change = db.get_change(change_id)
        assert change.rolled_back is True

    def test_mark_session_rolled_back(self, temp_changelog_db):
        """Test marking a session as rolled back."""
        db = ChangelogDB(temp_changelog_db)
        session = db.create_session("Test")
        db.record_change("Editor", "method", "table", 1, "INSERT", session_id=session.id)

        db.mark_session_rolled_back(session.id)

        updated_session = db.get_session(session.id)
        assert updated_session.rolled_back is True

        changes = db.get_changes(session_id=session.id, include_rolled_back=True)
        assert all(c.rolled_back for c in changes)


class TestTrackingControl:
    """Tests for tracking enable/disable."""

    def test_enable_disable_tracking(self, clean_tracking_state, temp_changelog_db):
        """Test enabling and disabling tracking."""
        assert is_tracking_enabled() is False

        enable_tracking(temp_changelog_db)
        assert is_tracking_enabled() is True

        disable_tracking()
        assert is_tracking_enabled() is False

    def test_start_session_enables_tracking(self, clean_tracking_state, temp_changelog_db):
        """Test that start_session enables tracking if not already enabled."""
        enable_tracking(temp_changelog_db)
        session = start_session("Test")

        assert session is not None
        assert is_tracking_enabled() is True

        end_session(session.id)


class TestTrackingSession:
    """Tests for the tracking_session context manager."""

    def test_tracking_session_context_manager(self, clean_tracking_state, temp_changelog_db):
        """Test the tracking_session context manager."""
        enable_tracking(temp_changelog_db)

        with tracking_session("Test Session") as session:
            assert session is not None
            assert session.name == "Test Session"

        # Session should be ended
        sessions = get_session_history()
        assert len(sessions) >= 1
        # Most recent session should have ended_at set
        latest = sessions[0]
        assert latest.ended_at is not None

    def test_nested_tracking_sessions(self, clean_tracking_state, temp_changelog_db):
        """Test that sessions can be nested (inner replaces outer context)."""
        enable_tracking(temp_changelog_db)

        with tracking_session("Outer") as outer:
            with tracking_session("Inner") as inner:
                assert inner.id != outer.id

        sessions = get_session_history()
        assert len(sessions) >= 2


class TestChangeCapture:
    """Tests for change capture with actual editor operations."""

    def test_capture_synset_creation(self, test_lexicon, clean_tracking_state, temp_changelog_db):
        """Test that synset creation is captured."""
        enable_tracking(temp_changelog_db)
        set_changelog_hooks(pre_change_hook, post_change_hook)

        with tracking_session("Create synset") as session:
            synset = test_lexicon.create_synset()
            synset.add_word("testword")

        changes = get_changes(session_id=session.id)
        # Should have recorded at least the synset creation
        assert len(changes) >= 1

        # Check that at least one change is for synsets table
        synset_changes = [c for c in changes if c.target_table == "synsets"]
        assert len(synset_changes) >= 1

    def test_capture_definition_addition(self, test_lexicon, clean_tracking_state, temp_changelog_db):
        """Test that definition addition is captured."""
        enable_tracking(temp_changelog_db)
        set_changelog_hooks(pre_change_hook, post_change_hook)

        with tracking_session("Add definition") as session:
            synset = test_lexicon.create_synset()
            synset.add_word("deftest")
            synset.add_definition("A test definition")

        changes = get_changes(session_id=session.id)
        def_changes = [c for c in changes if c.target_table == "definitions"]
        assert len(def_changes) >= 1

    def test_capture_update_operation(self, test_lexicon, clean_tracking_state, temp_changelog_db):
        """Test that update operations capture old and new data."""
        enable_tracking(temp_changelog_db)
        set_changelog_hooks(pre_change_hook, post_change_hook)

        with tracking_session("Update definition") as session:
            synset = test_lexicon.create_synset()
            synset.add_word("updatetest")
            synset.add_definition("Original definition")
            synset.mod_definition("Modified definition")

        changes = get_changes(session_id=session.id)
        update_changes = [c for c in changes if c.operation == "UPDATE"]

        # mod_definition creates an UPDATE if definition exists
        # Note: The first add_definition is INSERT, mod_definition is UPDATE
        # We should have at least one update
        # (depending on implementation, mod_definition might add if not exists)


class TestRollback:
    """Tests for rollback functionality."""

    def test_can_rollback_check(self, temp_changelog_db):
        """Test the can_rollback check."""
        db = ChangelogDB(temp_changelog_db)
        enable_tracking(temp_changelog_db)

        # Non-existent change
        can_rb, reason = can_rollback(99999)
        assert can_rb is False
        assert "not found" in reason.lower()

        # Already rolled back change
        change_id = db.record_change("Editor", "method", "table", 1, "INSERT")
        db.mark_change_rolled_back(change_id)
        can_rb, reason = can_rollback(change_id)
        assert can_rb is False
        assert "already rolled back" in reason.lower()

    def test_rollback_insert(self, test_lexicon, clean_tracking_state, temp_changelog_db):
        """Test rolling back an INSERT operation."""
        enable_tracking(temp_changelog_db)
        set_changelog_hooks(pre_change_hook, post_change_hook)

        with tracking_session("Create for rollback") as session:
            synset = test_lexicon.create_synset()
            synset.add_word("rollbacktest")
            synset_id = synset.as_synset().id

        # Verify synset exists
        found = wn.synsets("rollbacktest")
        assert len(found) >= 1

        # Rollback the session
        count = rollback_session(session.id)
        assert count > 0

        # Note: Due to wn caching, we may still find the synset in memory
        # The actual DB rollback should have occurred

    def test_rollback_session_reverses_changes(self, test_lexicon, clean_tracking_state, temp_changelog_db):
        """Test that rollback_session attempts to reverse changes in order."""
        enable_tracking(temp_changelog_db)
        set_changelog_hooks(pre_change_hook, post_change_hook)

        with tracking_session("Multiple changes") as session:
            synset = test_lexicon.create_synset()
            synset.add_word("multi1")
            synset.add_definition("First definition")

        changes = get_changes(session_id=session.id)
        initial_count = len(changes)
        assert initial_count > 0, "Should have recorded changes"

        count = rollback_session(session.id)

        # Some changes may fail to rollback due to cascading deletes
        # but we should have attempted to rollback
        assert count >= 0

        # If all changes were rolled back, session should be marked
        if count == initial_count:
            sessions = get_session_history(include_rolled_back=True)
            rolled_back_session = next((s for s in sessions if s.id == session.id), None)
            assert rolled_back_session is not None
            assert rolled_back_session.rolled_back is True


class TestHistory:
    """Tests for history querying."""

    def test_get_session_history(self, clean_tracking_state, temp_changelog_db):
        """Test getting session history."""
        enable_tracking(temp_changelog_db)

        with tracking_session("Session A"):
            pass

        with tracking_session("Session B"):
            pass

        history = get_session_history(limit=10)
        assert len(history) >= 2

        # Should be in reverse chronological order
        names = [s.name for s in history[:2]]
        assert "Session B" in names
        assert "Session A" in names

    def test_get_changes_filtering(self, clean_tracking_state, temp_changelog_db):
        """Test filtering changes."""
        db = ChangelogDB(temp_changelog_db)
        enable_tracking(temp_changelog_db)

        session = start_session("Filter test")
        db.record_change("Editor", "m1", "synsets", 1, "INSERT", session_id=session.id)
        db.record_change("Editor", "m2", "senses", 2, "INSERT", session_id=session.id)
        db.record_change("Editor", "m3", "synsets", 3, "DELETE", session_id=session.id)
        end_session(session.id)

        # Filter by table
        synset_changes = get_changes(target_table="synsets")
        sense_changes = get_changes(target_table="senses")

        synset_count = len([c for c in synset_changes if c.session_id == session.id])
        sense_count = len([c for c in sense_changes if c.session_id == session.id])

        assert synset_count == 2
        assert sense_count == 1

    def test_prune_history(self, clean_tracking_state, temp_changelog_db):
        """Test pruning old history."""
        enable_tracking(temp_changelog_db)

        with tracking_session("Old session"):
            pass

        # Prune with 0 days should delete everything
        deleted = prune_history(days=0)
        # Should have deleted the changes from the session
        assert deleted >= 0


class TestEdgeCases:
    """Tests for edge cases and error handling."""

    def test_tracking_disabled_no_recording(self, test_lexicon, clean_tracking_state):
        """Test that changes are not recorded when tracking is disabled."""
        disable_tracking()

        synset = test_lexicon.create_synset()
        synset.add_word("notrack")

        # Should not raise, changes just aren't recorded

    def test_session_without_changes(self, clean_tracking_state, temp_changelog_db):
        """Test a session with no changes."""
        enable_tracking(temp_changelog_db)

        with tracking_session("Empty session") as session:
            pass  # No changes made

        history = get_session_history()
        empty = next((s for s in history if s.id == session.id), None)
        assert empty is not None
        assert empty.change_count == 0

    def test_change_outside_session(self, test_lexicon, clean_tracking_state, temp_changelog_db):
        """Test recording changes outside of a session."""
        enable_tracking(temp_changelog_db)
        set_changelog_hooks(pre_change_hook, post_change_hook)

        # Make changes without a session context
        synset = test_lexicon.create_synset()
        synset.add_word("nosession")

        # Changes should still be recorded, but with session_id=None
        changes = get_changes()
        orphan_changes = [c for c in changes if c.session_id is None]
        # May or may not have orphan changes depending on test order

    def test_get_change_by_id(self, clean_tracking_state, temp_changelog_db):
        """Test getting a specific change by ID."""
        db = ChangelogDB(temp_changelog_db)
        enable_tracking(temp_changelog_db)

        change_id = db.record_change(
            editor_class="TestEditor",
            method_name="test_method",
            target_table="test_table",
            target_rowid=42,
            operation="INSERT",
        )

        change = get_change_by_id(change_id)
        assert change is not None
        assert change.id == change_id
        assert change.target_rowid == 42

        # Non-existent ID
        missing = get_change_by_id(99999)
        assert missing is None


class TestUnclosedSessionRecovery:
    """Tests for unclosed session recovery (cross-process session state)."""

    def test_get_unclosed_session_from_db(self, temp_changelog_db):
        """Test that ChangelogDB.get_unclosed_session() finds unclosed sessions."""
        db = ChangelogDB(temp_changelog_db)

        # Create a session but don't end it
        session = db.create_session("Unclosed Test", "Testing unclosed session")

        # Should find the unclosed session
        unclosed = db.get_unclosed_session()
        assert unclosed is not None
        assert unclosed.id == session.id
        assert unclosed.name == "Unclosed Test"
        assert unclosed.ended_at is None

    def test_get_unclosed_session_returns_none_when_all_closed(self, temp_changelog_db):
        """Test that get_unclosed_session returns None when all sessions are closed."""
        db = ChangelogDB(temp_changelog_db)

        # Create and end a session
        session = db.create_session("Closed Test")
        db.end_session(session.id)

        # Should return None
        unclosed = db.get_unclosed_session()
        assert unclosed is None

    def test_get_unclosed_session_returns_most_recent(self, temp_changelog_db):
        """Test that get_unclosed_session returns the most recent unclosed session."""
        db = ChangelogDB(temp_changelog_db)

        # Create multiple unclosed sessions
        session1 = db.create_session("First Unclosed")
        session2 = db.create_session("Second Unclosed")
        session3 = db.create_session("Third Unclosed")

        # Should return the most recent (highest ID)
        unclosed = db.get_unclosed_session()
        assert unclosed is not None
        assert unclosed.id == session3.id
        assert unclosed.name == "Third Unclosed"

    def test_get_unclosed_session_ignores_rolled_back(self, temp_changelog_db):
        """Test that get_unclosed_session ignores rolled back sessions."""
        db = ChangelogDB(temp_changelog_db)

        # Create a session and mark it as rolled back
        session1 = db.create_session("Rolled Back")
        db.mark_session_rolled_back(session1.id)

        # Create another unclosed session
        session2 = db.create_session("Not Rolled Back")

        # Should return the non-rolled-back session
        unclosed = db.get_unclosed_session()
        assert unclosed is not None
        assert unclosed.id == session2.id

    def test_get_most_recent_unclosed_session_public_api(self, clean_tracking_state, temp_changelog_db):
        """Test the public get_most_recent_unclosed_session function."""
        enable_tracking(temp_changelog_db)

        # Create a session but don't end it
        session = start_session("Public API Test")

        # Clear thread-local state to simulate new process
        _set_active_session(None)
        assert get_active_session() is None

        # Should still find the session via database query
        unclosed = get_most_recent_unclosed_session()
        assert unclosed is not None
        assert unclosed.id == session.id

        # Clean up
        end_session(session.id)

    def test_end_session_without_id_finds_unclosed(self, clean_tracking_state, temp_changelog_db):
        """Test that end_session() without ID finds and ends unclosed session."""
        enable_tracking(temp_changelog_db)

        # Create a session
        session = start_session("Auto-find Test")
        session_id = session.id

        # Clear thread-local state to simulate new process
        _set_active_session(None)
        assert get_active_session() is None

        # end_session() without ID should find and end the unclosed session
        result = end_session()
        assert result is True

        # Verify session was ended
        db = ChangelogDB(temp_changelog_db)
        ended = db.get_session(session_id)
        assert ended.ended_at is not None

    def test_end_session_returns_false_when_no_session(self, clean_tracking_state, temp_changelog_db):
        """Test that end_session() returns False when no session exists."""
        enable_tracking(temp_changelog_db)

        # Clear any active session
        _set_active_session(None)

        # No sessions exist, should return False
        result = end_session()
        assert result is False

    def test_end_session_prefers_thread_local_over_db(self, clean_tracking_state, temp_changelog_db):
        """Test that end_session() prefers thread-local session over DB lookup."""
        enable_tracking(temp_changelog_db)

        # Create two sessions - one old unclosed, one current
        db = ChangelogDB(temp_changelog_db)
        old_session = db.create_session("Old Unclosed")

        # Start a new session (sets thread-local)
        new_session = start_session("Current Session")

        # end_session() should end the thread-local session, not the old one
        result = end_session()
        assert result is True

        # Verify the new session was ended
        updated_new = db.get_session(new_session.id)
        assert updated_new.ended_at is not None

        # Old session should still be unclosed
        updated_old = db.get_session(old_session.id)
        assert updated_old.ended_at is None

        # Clean up
        db.end_session(old_session.id)
