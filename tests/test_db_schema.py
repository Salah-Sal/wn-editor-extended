import sqlite3
import pytest
from wordnet_editor.db import check_schema_version, SCHEMA_VERSION
from wordnet_editor.exceptions import DatabaseError

def test_incompatible_schema_version():
    """Test that check_schema_version raises DatabaseError for incompatible version."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE meta (key TEXT, value TEXT)")
    conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', '99.9')")

    with pytest.raises(DatabaseError, match=rf"Incompatible schema version: 99.9 \(expected {SCHEMA_VERSION}\)"):
        check_schema_version(conn)
    conn.close()

def test_uninitialized_database():
    """Test that check_schema_version returns for uninitialized database (no meta table)."""
    conn = sqlite3.connect(":memory:")
    # No meta table created
    try:
        check_schema_version(conn)
    except Exception as e:
        pytest.fail(f"check_schema_version raised unexpected exception: {e}")
    conn.close()

def test_compatible_schema_version():
    """Test that check_schema_version passes for compatible version."""
    conn = sqlite3.connect(":memory:")
    conn.execute("CREATE TABLE meta (key TEXT, value TEXT)")
    conn.execute("INSERT INTO meta (key, value) VALUES ('schema_version', ?)", (SCHEMA_VERSION,))

    try:
        check_schema_version(conn)
    except Exception as e:
        pytest.fail(f"check_schema_version raised unexpected exception: {e}")
    conn.close()
