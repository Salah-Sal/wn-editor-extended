
import sqlite3
import pytest
from wordnet_editor.db import connect, init_db, get_or_create_relation_type

def test_get_or_create_relation_type():
    """Test that get_or_create_relation_type returns correct rowid and doesn't duplicate."""
    # Setup
    conn = connect(":memory:")
    init_db(conn)

    # 1. Create a relation type
    rel_type = "hypernym"
    rowid1 = get_or_create_relation_type(conn, rel_type)
    assert isinstance(rowid1, int)

    # Verify it exists in DB
    row = conn.execute("SELECT * FROM relation_types WHERE rowid = ?", (rowid1,)).fetchone()
    assert row is not None
    assert row["type"] == rel_type

    # 2. Get the same relation type again
    rowid2 = get_or_create_relation_type(conn, rel_type)
    assert rowid2 == rowid1

    # Verify no duplicates
    count = conn.execute("SELECT COUNT(*) FROM relation_types WHERE type = ?", (rel_type,)).fetchone()[0]
    assert count == 1

    # 3. Create a different relation type
    rel_type2 = "hyponym"
    rowid3 = get_or_create_relation_type(conn, rel_type2)
    assert isinstance(rowid3, int)
    assert rowid3 != rowid1

    # Verify distinct entries
    count_total = conn.execute("SELECT COUNT(*) FROM relation_types").fetchone()[0]
    assert count_total == 2

    conn.close()
