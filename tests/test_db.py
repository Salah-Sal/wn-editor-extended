
import pytest
import sqlite3
from wordnet_editor import db

@pytest.fixture
def db_conn():
    """Create an in-memory database connection for testing."""
    conn = db.connect(":memory:")
    db.init_db(conn)
    yield conn
    conn.close()

def test_create_new_ili(db_conn):
    """Test creating a new ILI with default status."""
    ili_id = "i12345"
    rowid = db.get_or_create_ili(db_conn, ili_id)

    assert isinstance(rowid, int)

    # Verify it exists in the database
    row = db_conn.execute("SELECT * FROM ilis WHERE rowid = ?", (rowid,)).fetchone()
    assert row is not None
    assert row["id"] == ili_id

    # Verify default status is 'presupposed'
    status_row = db_conn.execute(
        "SELECT status FROM ili_statuses WHERE rowid = ?",
        (row["status_rowid"],)
    ).fetchone()
    assert status_row["status"] == "presupposed"

def test_retrieve_existing_ili(db_conn):
    """Test retrieving an existing ILI."""
    ili_id = "i67890"

    # First creation
    rowid1 = db.get_or_create_ili(db_conn, ili_id)

    # Second call should return the same rowid
    rowid2 = db.get_or_create_ili(db_conn, ili_id)

    assert rowid1 == rowid2

    # Verify count is still 1
    count = db_conn.execute("SELECT COUNT(*) FROM ilis WHERE id = ?", (ili_id,)).fetchone()[0]
    assert count == 1

def test_status_handling(db_conn):
    """Test creating an ILI with a specific status."""
    ili_id = "i54321"
    status = "active"

    rowid = db.get_or_create_ili(db_conn, ili_id, status=status)

    row = db_conn.execute("SELECT * FROM ilis WHERE rowid = ?", (rowid,)).fetchone()
    status_row = db_conn.execute(
        "SELECT status FROM ili_statuses WHERE rowid = ?",
        (row["status_rowid"],)
    ).fetchone()

    assert status_row["status"] == status
