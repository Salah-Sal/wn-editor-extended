"""
Change tracking and rollback functionality for wn-editor.

This module provides granular change tracking that records every database
modification, allowing users to roll back individual changes or entire sessions.
"""
from __future__ import annotations

import json
import logging
import sqlite3
import threading
from contextlib import contextmanager
from dataclasses import dataclass, field
from datetime import datetime
from pathlib import Path
from typing import Any, Callable, Dict, List, Optional, Tuple

from wn._db import connect as wn_connect

logger = logging.getLogger(__name__)

# Default changelog database location
DEFAULT_CHANGELOG_PATH = Path.home() / ".wn_changelog.db"

# Thread-local storage for active session
_local = threading.local()

# Schema version for migrations
SCHEMA_VERSION = 1

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS schema_version (
    version INTEGER PRIMARY KEY
);

CREATE TABLE IF NOT EXISTS sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name TEXT,
    description TEXT,
    started_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    ended_at TIMESTAMP,
    rolled_back INTEGER DEFAULT 0
);

CREATE TABLE IF NOT EXISTS changes (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER REFERENCES sessions(id),
    timestamp TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    editor_class TEXT NOT NULL,
    method_name TEXT NOT NULL,
    target_table TEXT NOT NULL,
    target_rowid INTEGER,
    operation TEXT NOT NULL,
    old_data TEXT,
    new_data TEXT,
    rolled_back INTEGER DEFAULT 0,
    lexicon_rowid INTEGER
);

CREATE INDEX IF NOT EXISTS idx_changes_session ON changes(session_id);
CREATE INDEX IF NOT EXISTS idx_changes_target ON changes(target_table, target_rowid);
CREATE INDEX IF NOT EXISTS idx_changes_timestamp ON changes(timestamp);
"""


@dataclass
class Change:
    """Represents a single tracked change."""
    id: int
    session_id: Optional[int]
    timestamp: datetime
    editor_class: str
    method_name: str
    target_table: str
    target_rowid: Optional[int]
    operation: str  # INSERT, UPDATE, DELETE
    old_data: Optional[Dict[str, Any]]
    new_data: Optional[Dict[str, Any]]
    rolled_back: bool
    lexicon_rowid: Optional[int]

    @classmethod
    def from_row(cls, row: sqlite3.Row) -> Change:
        """Create a Change from a database row."""
        return cls(
            id=row["id"],
            session_id=row["session_id"],
            timestamp=datetime.fromisoformat(row["timestamp"]) if row["timestamp"] else None,
            editor_class=row["editor_class"],
            method_name=row["method_name"],
            target_table=row["target_table"],
            target_rowid=row["target_rowid"],
            operation=row["operation"],
            old_data=json.loads(row["old_data"]) if row["old_data"] else None,
            new_data=json.loads(row["new_data"]) if row["new_data"] else None,
            rolled_back=bool(row["rolled_back"]),
            lexicon_rowid=row["lexicon_rowid"],
        )


@dataclass
class Session:
    """Represents a tracking session grouping related changes."""
    id: int
    name: Optional[str]
    description: Optional[str]
    started_at: datetime
    ended_at: Optional[datetime]
    rolled_back: bool
    change_count: int = 0

    @classmethod
    def from_row(cls, row: sqlite3.Row, change_count: int = 0) -> Session:
        """Create a Session from a database row."""
        return cls(
            id=row["id"],
            name=row["name"],
            description=row["description"],
            started_at=datetime.fromisoformat(row["started_at"]) if row["started_at"] else None,
            ended_at=datetime.fromisoformat(row["ended_at"]) if row["ended_at"] else None,
            rolled_back=bool(row["rolled_back"]),
            change_count=change_count,
        )


class ChangelogDB:
    """Manages the changelog database connection and operations."""

    def __init__(self, db_path: Path = None):
        self.db_path = db_path or DEFAULT_CHANGELOG_PATH
        self._ensure_schema()

    def _get_connection(self) -> sqlite3.Connection:
        """Get a database connection with row factory."""
        conn = sqlite3.connect(str(self.db_path))
        conn.row_factory = sqlite3.Row
        return conn

    def _ensure_schema(self) -> None:
        """Ensure the database schema exists."""
        with self._get_connection() as conn:
            conn.executescript(SCHEMA_SQL)
            # Check/set schema version
            cur = conn.execute("SELECT version FROM schema_version LIMIT 1")
            row = cur.fetchone()
            if row is None:
                conn.execute("INSERT INTO schema_version VALUES (?)", (SCHEMA_VERSION,))
            conn.commit()

    def create_session(self, name: str = None, description: str = None) -> Session:
        """Create a new tracking session."""
        with self._get_connection() as conn:
            cur = conn.execute(
                "INSERT INTO sessions (name, description) VALUES (?, ?)",
                (name, description)
            )
            session_id = cur.lastrowid
            conn.commit()
            cur = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            return Session.from_row(cur.fetchone())

    def end_session(self, session_id: int) -> None:
        """Mark a session as ended."""
        with self._get_connection() as conn:
            conn.execute(
                "UPDATE sessions SET ended_at = CURRENT_TIMESTAMP WHERE id = ?",
                (session_id,)
            )
            conn.commit()

    def record_change(
        self,
        editor_class: str,
        method_name: str,
        target_table: str,
        target_rowid: Optional[int],
        operation: str,
        old_data: Optional[Dict] = None,
        new_data: Optional[Dict] = None,
        lexicon_rowid: Optional[int] = None,
        session_id: Optional[int] = None,
    ) -> int:
        """Record a change to the changelog."""
        with self._get_connection() as conn:
            cur = conn.execute(
                """INSERT INTO changes
                   (session_id, editor_class, method_name, target_table,
                    target_rowid, operation, old_data, new_data, lexicon_rowid)
                   VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
                (
                    session_id,
                    editor_class,
                    method_name,
                    target_table,
                    target_rowid,
                    operation,
                    json.dumps(old_data) if old_data else None,
                    json.dumps(new_data) if new_data else None,
                    lexicon_rowid,
                )
            )
            change_id = cur.lastrowid
            conn.commit()
            return change_id

    def get_change(self, change_id: int) -> Optional[Change]:
        """Get a single change by ID."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM changes WHERE id = ?", (change_id,))
            row = cur.fetchone()
            return Change.from_row(row) if row else None

    def get_changes(
        self,
        session_id: int = None,
        target_table: str = None,
        limit: int = 100,
        include_rolled_back: bool = False,
    ) -> List[Change]:
        """Get changes with optional filters."""
        query = "SELECT * FROM changes WHERE 1=1"
        params = []

        if session_id is not None:
            query += " AND session_id = ?"
            params.append(session_id)

        if target_table is not None:
            query += " AND target_table = ?"
            params.append(target_table)

        if not include_rolled_back:
            query += " AND rolled_back = 0"

        query += " ORDER BY id DESC LIMIT ?"
        params.append(limit)

        with self._get_connection() as conn:
            cur = conn.execute(query, params)
            return [Change.from_row(row) for row in cur.fetchall()]

    def get_session(self, session_id: int) -> Optional[Session]:
        """Get a session by ID."""
        with self._get_connection() as conn:
            cur = conn.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
            row = cur.fetchone()
            if row:
                count_cur = conn.execute(
                    "SELECT COUNT(*) as cnt FROM changes WHERE session_id = ?",
                    (session_id,)
                )
                count = count_cur.fetchone()["cnt"]
                return Session.from_row(row, count)
            return None

    def get_sessions(self, limit: int = 10, include_rolled_back: bool = False) -> List[Session]:
        """Get recent sessions."""
        query = "SELECT * FROM sessions"
        if not include_rolled_back:
            query += " WHERE rolled_back = 0"
        query += " ORDER BY id DESC LIMIT ?"

        with self._get_connection() as conn:
            cur = conn.execute(query, (limit,))
            sessions = []
            for row in cur.fetchall():
                count_cur = conn.execute(
                    "SELECT COUNT(*) as cnt FROM changes WHERE session_id = ?",
                    (row["id"],)
                )
                count = count_cur.fetchone()["cnt"]
                sessions.append(Session.from_row(row, count))
            return sessions

    def get_unclosed_session(self) -> Optional[Session]:
        """Get the most recent unclosed session (ended_at IS NULL).

        This is useful for recovering session state across process invocations,
        where thread-local storage is lost but the database retains the session.

        Returns:
            The most recent session with ended_at=NULL, or None if all sessions are closed.
        """
        with self._get_connection() as conn:
            cur = conn.execute(
                """SELECT * FROM sessions
                   WHERE ended_at IS NULL AND rolled_back = 0
                   ORDER BY id DESC LIMIT 1"""
            )
            row = cur.fetchone()
            if row:
                count_cur = conn.execute(
                    "SELECT COUNT(*) as cnt FROM changes WHERE session_id = ?",
                    (row["id"],)
                )
                count = count_cur.fetchone()["cnt"]
                return Session.from_row(row, count)
            return None

    def mark_change_rolled_back(self, change_id: int) -> None:
        """Mark a change as rolled back."""
        with self._get_connection() as conn:
            conn.execute("UPDATE changes SET rolled_back = 1 WHERE id = ?", (change_id,))
            conn.commit()

    def mark_session_rolled_back(self, session_id: int) -> None:
        """Mark a session as rolled back."""
        with self._get_connection() as conn:
            conn.execute("UPDATE sessions SET rolled_back = 1 WHERE id = ?", (session_id,))
            conn.execute("UPDATE changes SET rolled_back = 1 WHERE session_id = ?", (session_id,))
            conn.commit()

    def prune_history(self, days: int = 30) -> int:
        """Delete changelog entries older than specified days."""
        with self._get_connection() as conn:
            cur = conn.execute(
                """DELETE FROM changes
                   WHERE timestamp < datetime('now', ?)""",
                (f"-{days} days",)
            )
            deleted_changes = cur.rowcount
            conn.execute(
                """DELETE FROM sessions
                   WHERE started_at < datetime('now', ?)
                   AND id NOT IN (SELECT DISTINCT session_id FROM changes WHERE session_id IS NOT NULL)""",
                (f"-{days} days",)
            )
            conn.commit()
            return deleted_changes


# Global changelog database instance
_changelog_db: Optional[ChangelogDB] = None
_tracking_enabled = False


def _get_db() -> ChangelogDB:
    """Get or create the global changelog database."""
    global _changelog_db
    if _changelog_db is None:
        _changelog_db = ChangelogDB()
    return _changelog_db


def enable_tracking(db_path: Path = None) -> None:
    """Enable change tracking."""
    global _changelog_db, _tracking_enabled
    _changelog_db = ChangelogDB(db_path)
    _tracking_enabled = True
    logger.info("Change tracking enabled")


def disable_tracking() -> None:
    """Disable change tracking."""
    global _tracking_enabled
    _tracking_enabled = False
    logger.info("Change tracking disabled")


def is_tracking_enabled() -> bool:
    """Check if tracking is enabled."""
    return _tracking_enabled


def get_active_session() -> Optional[Session]:
    """Get the currently active session for this thread."""
    return getattr(_local, "active_session", None)


def _set_active_session(session: Optional[Session]) -> None:
    """Set the active session for this thread."""
    _local.active_session = session


def start_session(name: str = None, description: str = None) -> Session:
    """Start a new tracking session."""
    if not _tracking_enabled:
        enable_tracking()

    session = _get_db().create_session(name, description)
    _set_active_session(session)
    logger.debug(f"Started session {session.id}: {name}")
    return session


def end_session(session_id: int = None) -> bool:
    """End a tracking session.

    Args:
        session_id: The session ID to end. If not provided, ends the active
            session (from thread-local storage) or falls back to the most
            recent unclosed session in the database.

    Returns:
        True if a session was ended, False if no session was found to end.
    """
    if session_id is None:
        active = get_active_session()
        if active:
            session_id = active.id
        else:
            # Fall back to querying the database for unclosed sessions
            # This handles the case where session state was lost (e.g., across
            # separate process invocations)
            unclosed = get_most_recent_unclosed_session()
            if unclosed:
                session_id = unclosed.id
            else:
                return False

    _get_db().end_session(session_id)

    active = get_active_session()
    if active and active.id == session_id:
        _set_active_session(None)

    logger.debug(f"Ended session {session_id}")
    return True


def get_most_recent_unclosed_session() -> Optional[Session]:
    """Get the most recent unclosed session from the database.

    This is useful for recovering session state across process invocations,
    where thread-local storage is lost but the database retains the session
    information.

    Returns:
        The most recent session with ended_at=NULL, or None if all sessions
        are closed or rolled back.
    """
    if not _tracking_enabled:
        enable_tracking()
    return _get_db().get_unclosed_session()


@contextmanager
def tracking_session(name: str = None, description: str = None):
    """Context manager for a tracking session.

    Example:
        with tracking_session("Add vocabulary") as session:
            synset = lex.create_synset()
            synset.add_word("example")

        # If unhappy with changes:
        rollback_session(session.id)
    """
    session = start_session(name, description)
    try:
        yield session
    finally:
        end_session(session.id)


def record_change(
    editor_class: str,
    method_name: str,
    target_table: str,
    target_rowid: Optional[int],
    operation: str,
    old_data: Optional[Dict] = None,
    new_data: Optional[Dict] = None,
    lexicon_rowid: Optional[int] = None,
) -> Optional[int]:
    """Record a change if tracking is enabled."""
    if not _tracking_enabled:
        return None

    session = get_active_session()
    session_id = session.id if session else None

    return _get_db().record_change(
        editor_class=editor_class,
        method_name=method_name,
        target_table=target_table,
        target_rowid=target_rowid,
        operation=operation,
        old_data=old_data,
        new_data=new_data,
        lexicon_rowid=lexicon_rowid,
        session_id=session_id,
    )


def get_session_history(limit: int = 10, include_rolled_back: bool = False) -> List[Session]:
    """Get recent tracking sessions."""
    return _get_db().get_sessions(limit, include_rolled_back)


def get_changes(
    session_id: int = None,
    target_table: str = None,
    limit: int = 100,
    include_rolled_back: bool = False,
) -> List[Change]:
    """Get recorded changes with optional filters."""
    return _get_db().get_changes(session_id, target_table, limit, include_rolled_back)


def get_change_by_id(change_id: int) -> Optional[Change]:
    """Get a specific change by ID."""
    return _get_db().get_change(change_id)


# Table column mappings for rollback operations
TABLE_COLUMNS = {
    "synsets": ["id", "lexicon_rowid", "ili_rowid", "pos", "lexicalized", "metadata"],
    "senses": ["id", "lexicon_rowid", "entry_rowid", "synset_rowid", "sense_key", "lexicalized", "metadata"],
    "entries": ["id", "lexicon_rowid", "pos", "metadata"],
    "forms": ["lexicon_rowid", "entry_rowid", "form", "normalized_form", "script", "rank"],
    "definitions": ["lexicon_rowid", "synset_rowid", "definition", "language", "sense_rowid", "metadata"],
    "synset_examples": ["lexicon_rowid", "synset_rowid", "example", "language", "metadata"],
    "sense_examples": ["lexicon_rowid", "sense_rowid", "example", "language", "metadata"],
    "synset_relations": ["lexicon_rowid", "source_rowid", "target_rowid", "type_rowid", "metadata"],
    "sense_relations": ["lexicon_rowid", "source_rowid", "target_rowid", "type_rowid", "metadata"],
    "sense_synset_relations": ["lexicon_rowid", "source_rowid", "target_rowid", "type_rowid", "metadata"],
    "ilis": ["id", "status_rowid", "definition", "metadata"],
    "proposed_ilis": ["synset_rowid", "definition", "metadata"],
    "counts": ["lexicon_rowid", "sense_rowid", "count", "metadata"],
    "adjpositions": ["sense_rowid", "adjposition"],
    "pronunciations": ["form_rowid", "value", "variety", "notation", "phonemic", "audio"],
    "tags": ["form_rowid", "tag", "category"],
    "syntactic_behaviours": ["id", "lexicon_rowid", "frame"],
    "syntactic_behaviour_senses": ["syntactic_behaviour_rowid", "sense_rowid"],
}


def _fetch_row_data(table: str, rowid: int) -> Optional[Dict[str, Any]]:
    """Fetch current data for a row from the wn database."""
    if table not in TABLE_COLUMNS:
        logger.warning(f"Unknown table: {table}")
        return None

    columns = TABLE_COLUMNS[table]
    col_str = ", ".join(columns)

    with wn_connect() as conn:
        cur = conn.execute(f"SELECT rowid, {col_str} FROM {table} WHERE rowid = ?", (rowid,))
        row = cur.fetchone()
        if row:
            result = {"rowid": row[0]}
            for i, col in enumerate(columns):
                result[col] = row[i + 1]
            return result
    return None


def can_rollback(change_id: int) -> Tuple[bool, str]:
    """Check if a change can be rolled back.

    Returns:
        Tuple of (can_rollback, reason)
    """
    change = _get_db().get_change(change_id)
    if not change:
        return False, "Change not found"

    if change.rolled_back:
        return False, "Change already rolled back"

    if change.operation == "DELETE":
        # For DELETE, we need old_data to restore
        if not change.old_data:
            return False, "No old data available to restore"

    if change.operation == "UPDATE":
        # For UPDATE, check if row still exists
        if change.target_rowid:
            current = _fetch_row_data(change.target_table, change.target_rowid)
            if not current:
                return False, "Target row no longer exists"

    if change.operation == "INSERT":
        # For INSERT, check if row still exists to delete
        if change.target_rowid:
            current = _fetch_row_data(change.target_table, change.target_rowid)
            if not current:
                return False, "Inserted row no longer exists"

    return True, "OK"


def rollback_change(change_id: int) -> bool:
    """Roll back a single change.

    Returns:
        True if rollback succeeded, False otherwise
    """
    can_rb, reason = can_rollback(change_id)
    if not can_rb:
        logger.warning(f"Cannot rollback change {change_id}: {reason}")
        return False

    change = _get_db().get_change(change_id)

    try:
        with wn_connect() as conn:
            if change.operation == "INSERT":
                # Rollback INSERT by deleting the row
                conn.execute(
                    f"DELETE FROM {change.target_table} WHERE rowid = ?",
                    (change.target_rowid,)
                )
                logger.debug(f"Rolled back INSERT: deleted rowid {change.target_rowid} from {change.target_table}")

            elif change.operation == "DELETE":
                # Rollback DELETE by re-inserting with old data
                old = change.old_data
                if "rowid" in old:
                    del old["rowid"]  # Don't try to set rowid

                columns = list(old.keys())
                placeholders = ", ".join(["?"] * len(columns))
                col_str = ", ".join(columns)
                values = [old[c] for c in columns]

                conn.execute(
                    f"INSERT INTO {change.target_table} ({col_str}) VALUES ({placeholders})",
                    values
                )
                logger.debug(f"Rolled back DELETE: re-inserted into {change.target_table}")

            elif change.operation == "UPDATE":
                # Rollback UPDATE by restoring old values
                old = change.old_data
                if "rowid" in old:
                    del old["rowid"]

                set_clause = ", ".join([f"{k} = ?" for k in old.keys()])
                values = list(old.values()) + [change.target_rowid]

                conn.execute(
                    f"UPDATE {change.target_table} SET {set_clause} WHERE rowid = ?",
                    values
                )
                logger.debug(f"Rolled back UPDATE: restored old values for rowid {change.target_rowid}")

            conn.commit()

        _get_db().mark_change_rolled_back(change_id)
        return True

    except Exception as e:
        logger.error(f"Error rolling back change {change_id}: {e}")
        return False


def rollback_session(session_id: int) -> int:
    """Roll back all changes in a session.

    Changes are rolled back in reverse order (newest first).

    Returns:
        Number of successfully rolled back changes
    """
    changes = _get_db().get_changes(session_id=session_id, include_rolled_back=False)

    # Sort by ID descending to rollback in reverse order
    changes.sort(key=lambda c: c.id, reverse=True)

    rolled_back_count = 0
    for change in changes:
        if rollback_change(change.id):
            rolled_back_count += 1
        else:
            logger.warning(f"Failed to rollback change {change.id}, stopping session rollback")
            break

    if rolled_back_count == len(changes):
        _get_db().mark_session_rolled_back(session_id)

    return rolled_back_count


def prune_history(days: int = 30) -> int:
    """Delete changelog entries older than specified days.

    Returns:
        Number of deleted change records
    """
    return _get_db().prune_history(days)


# Capture utilities for the editor hooks

@dataclass
class CaptureContext:
    """Context passed between pre and post hooks."""
    editor_class: str
    method_name: str
    target_table: Optional[str] = None
    target_rowid: Optional[int] = None
    old_data: Optional[Dict] = None
    operation: Optional[str] = None
    lexicon_rowid: Optional[int] = None


# Method to table/operation mappings
METHOD_MAPPINGS: Dict[str, Dict[str, Tuple[str, str, Optional[List[str]]]]] = {
    "SynsetEditor": {
        "_create": ("synsets", "INSERT", None),
        "add_word": ("senses", "INSERT", None),  # Composite - handled specially
        "delete_word": ("senses", "DELETE", None),
        "delete": ("synsets", "DELETE", None),
        "set_ili": ("synsets", "UPDATE", ["ili_rowid"]),
        "delete_ili": ("synsets", "UPDATE", ["ili_rowid"]),
        "set_pos": ("synsets", "UPDATE", ["pos"]),
        "set_metadata": ("synsets", "UPDATE", ["metadata"]),
        "add_definition": ("definitions", "INSERT", None),
        "mod_definition": ("definitions", "UPDATE", ["definition"]),
        "delete_definition": ("definitions", "DELETE", None),
        "add_example": ("synset_examples", "INSERT", None),
        "delete_example": ("synset_examples", "DELETE", None),
        "set_proposed_ili": ("proposed_ilis", "INSERT", None),  # or UPDATE
        "delete_proposed_ili": ("proposed_ilis", "DELETE", None),
        "set_relation_to_synset": ("synset_relations", "INSERT", None),
        "delete_relation_to_synset": ("synset_relations", "DELETE", None),
        "set_relation_to_sense": ("sense_synset_relations", "INSERT", None),
        "delete_relation_to_sense": ("sense_synset_relations", "DELETE", None),
    },
    "SenseEditor": {
        "_create": ("senses", "INSERT", None),
        "delete": ("senses", "DELETE", None),
        "set_id": ("senses", "UPDATE", ["id"]),
        "set_metadata": ("senses", "UPDATE", ["metadata"]),
        "set_relation_to_synset": ("sense_synset_relations", "INSERT", None),
        "delete_relation_to_synset": ("sense_synset_relations", "DELETE", None),
        "set_relation_to_sense": ("sense_relations", "INSERT", None),
        "delete_relation_to_sense": ("sense_relations", "DELETE", None),
        "add_adjposition": ("adjpositions", "INSERT", None),
        "delete_adjposition": ("adjpositions", "DELETE", None),
        "set_count": ("counts", "INSERT", None),
        "delete_count": ("counts", "DELETE", None),
        "update_count": ("counts", "UPDATE", ["count"]),
        "add_example": ("sense_examples", "INSERT", None),
        "delete_example": ("sense_examples", "DELETE", None),
        "add_syntactic_behaviour": ("syntactic_behaviour_senses", "INSERT", None),
        "delete_syntactic_behaviour": ("syntactic_behaviour_senses", "DELETE", None),
    },
    "EntryEditor": {
        "_create": ("entries", "INSERT", None),
        "delete": ("entries", "DELETE", None),
        "set_pos": ("entries", "UPDATE", ["pos"]),
        "set_metadata": ("entries", "UPDATE", ["metadata"]),
        "_set_id": ("entries", "UPDATE", ["id"]),
    },
    "FormEditor": {
        "_create": ("forms", "INSERT", None),
        "delete": ("forms", "DELETE", None),
        "set_form": ("forms", "UPDATE", ["form"]),
        "set_normalized_form": ("forms", "UPDATE", ["normalized_form"]),
        "_set_entry_rowid": ("forms", "UPDATE", ["entry_rowid"]),
        "_set_id": ("forms", "UPDATE", ["id"]),
        "add_pronunciation": ("pronunciations", "INSERT", None),
        "delete_pronunciation": ("pronunciations", "DELETE", None),
        "add_tag": ("tags", "INSERT", None),
        "delete_tag": ("tags", "DELETE", None),
    },
    "IlIEditor": {
        "_create": ("ilis", "INSERT", None),
        "delete": ("ilis", "DELETE", None),
        "set_definition": ("ilis", "UPDATE", ["definition"]),
        "set_status": ("ilis", "UPDATE", ["status_rowid"]),
        "set_meta": ("ilis", "UPDATE", ["metadata"]),
    },
    "LexiconEditor": {
        "_id": ("lexicons", "UPDATE", ["id"]),
        "delete": ("lexicons", "DELETE", None),
    },
}


def _get_editor_rowid(editor) -> Optional[int]:
    """Extract the relevant rowid from an editor instance."""
    editor_class = editor.__class__.__name__

    if editor_class == "SynsetEditor":
        return getattr(editor, "rowid", None)
    elif editor_class == "SenseEditor":
        return getattr(editor, "row_id", None)
    elif editor_class == "EntryEditor":
        return getattr(editor, "entry_id", None)
    elif editor_class == "FormEditor":
        return getattr(editor, "row_id", None)
    elif editor_class == "IlIEditor":
        return getattr(editor, "row_id", None)
    elif editor_class == "LexiconEditor":
        return getattr(editor, "lex_rowid", None)
    return None


def pre_change_hook(editor, method_name: str, args: tuple, kwargs: dict) -> Optional[CaptureContext]:
    """Hook called before a modifying operation.

    Captures the current state for UPDATE and DELETE operations.
    """
    if not _tracking_enabled:
        return None

    editor_class = editor.__class__.__name__
    mappings = METHOD_MAPPINGS.get(editor_class, {})
    mapping = mappings.get(method_name)

    if not mapping:
        logger.debug(f"No mapping for {editor_class}.{method_name}")
        return None

    target_table, operation, columns = mapping
    target_rowid = _get_editor_rowid(editor)
    lex_rowid = getattr(editor, "lex_rowid", None)

    ctx = CaptureContext(
        editor_class=editor_class,
        method_name=method_name,
        target_table=target_table,
        target_rowid=target_rowid,
        operation=operation,
        lexicon_rowid=lex_rowid,
    )

    # For UPDATE and DELETE, capture old data
    if operation in ("UPDATE", "DELETE") and target_rowid:
        ctx.old_data = _fetch_row_data(target_table, target_rowid)

    return ctx


def post_change_hook(
    editor,
    method_name: str,
    args: tuple,
    kwargs: dict,
    result,
    pre_context: Optional[CaptureContext],
) -> None:
    """Hook called after a modifying operation.

    Records the change with before/after data.
    """
    if not _tracking_enabled or not pre_context:
        return

    target_rowid = pre_context.target_rowid
    new_data = None

    # For INSERT operations, get the new rowid from the result or editor
    if pre_context.operation == "INSERT":
        # After creation, the rowid should be set on the editor
        target_rowid = _get_editor_rowid(editor)
        if target_rowid:
            new_data = _fetch_row_data(pre_context.target_table, target_rowid)

    # For UPDATE operations, capture the new state
    elif pre_context.operation == "UPDATE" and target_rowid:
        new_data = _fetch_row_data(pre_context.target_table, target_rowid)

    record_change(
        editor_class=pre_context.editor_class,
        method_name=method_name,
        target_table=pre_context.target_table,
        target_rowid=target_rowid,
        operation=pre_context.operation,
        old_data=pre_context.old_data,
        new_data=new_data,
        lexicon_rowid=pre_context.lexicon_rowid,
    )
