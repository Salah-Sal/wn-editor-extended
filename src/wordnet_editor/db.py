"""Database connection, DDL, and low-level CRUD for wordnet-editor."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path

from wordnet_editor.exceptions import DatabaseError

SCHEMA_VERSION = "1.0"

# ---------------------------------------------------------------------------
# META type adapter/converter (matches wn's pattern)
# ---------------------------------------------------------------------------

def _adapt_metadata(obj: dict) -> str:
    return json.dumps(obj)


def _convert_metadata(data: bytes) -> dict | None:
    if data is None or data == b"":
        return None
    return json.loads(data)


sqlite3.register_adapter(dict, _adapt_metadata)
sqlite3.register_converter("META", _convert_metadata)


# ---------------------------------------------------------------------------
# DDL statements
# ---------------------------------------------------------------------------

_DDL = """
-- Meta table
CREATE TABLE IF NOT EXISTS meta (
    key TEXT NOT NULL,
    value TEXT,
    UNIQUE (key)
);

-- Lookup tables
CREATE TABLE IF NOT EXISTS relation_types (
    rowid INTEGER PRIMARY KEY,
    type TEXT NOT NULL,
    UNIQUE (type)
);
CREATE INDEX IF NOT EXISTS relation_type_index ON relation_types (type);

CREATE TABLE IF NOT EXISTS ili_statuses (
    rowid INTEGER PRIMARY KEY,
    status TEXT NOT NULL,
    UNIQUE (status)
);
CREATE INDEX IF NOT EXISTS ili_status_index ON ili_statuses (status);

CREATE TABLE IF NOT EXISTS lexfiles (
    rowid INTEGER PRIMARY KEY,
    name TEXT NOT NULL,
    UNIQUE (name)
);
CREATE INDEX IF NOT EXISTS lexfile_index ON lexfiles (name);

-- ILI tables
CREATE TABLE IF NOT EXISTS ilis (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    status_rowid INTEGER NOT NULL REFERENCES ili_statuses (rowid),
    definition TEXT,
    metadata META,
    UNIQUE (id)
);
CREATE INDEX IF NOT EXISTS ili_id_index ON ilis (id);

CREATE TABLE IF NOT EXISTS proposed_ilis (
    rowid INTEGER PRIMARY KEY,
    synset_rowid INTEGER REFERENCES synsets (rowid) ON DELETE CASCADE,
    definition TEXT,
    metadata META,
    UNIQUE (synset_rowid)
);
CREATE INDEX IF NOT EXISTS proposed_ili_synset_rowid_index ON proposed_ilis (synset_rowid);

-- Lexicon tables
CREATE TABLE IF NOT EXISTS lexicons (
    rowid INTEGER PRIMARY KEY,
    specifier TEXT NOT NULL,
    id TEXT NOT NULL,
    label TEXT NOT NULL,
    language TEXT NOT NULL,
    email TEXT NOT NULL,
    license TEXT NOT NULL,
    version TEXT NOT NULL,
    url TEXT,
    citation TEXT,
    logo TEXT,
    metadata META,
    modified BOOLEAN CHECK( modified IN (0, 1) ) DEFAULT 0 NOT NULL,
    UNIQUE (id, version),
    UNIQUE (specifier)
);
CREATE INDEX IF NOT EXISTS lexicon_specifier_index ON lexicons (specifier);

CREATE TABLE IF NOT EXISTS lexicon_dependencies (
    dependent_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    provider_id TEXT NOT NULL,
    provider_version TEXT NOT NULL,
    provider_url TEXT,
    provider_rowid INTEGER REFERENCES lexicons (rowid) ON DELETE SET NULL
);
CREATE INDEX IF NOT EXISTS lexicon_dependent_index ON lexicon_dependencies(dependent_rowid);

CREATE TABLE IF NOT EXISTS lexicon_extensions (
    extension_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    base_id TEXT NOT NULL,
    base_version TEXT NOT NULL,
    base_url TEXT,
    base_rowid INTEGER REFERENCES lexicons (rowid),
    UNIQUE (extension_rowid, base_rowid)
);
CREATE INDEX IF NOT EXISTS lexicon_extension_index ON lexicon_extensions(extension_rowid);

-- Entry tables
CREATE TABLE IF NOT EXISTS entries (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    pos TEXT NOT NULL,
    metadata META,
    UNIQUE (id, lexicon_rowid)
);
CREATE INDEX IF NOT EXISTS entry_id_index ON entries (id);

CREATE TABLE IF NOT EXISTS entry_index (
    entry_rowid INTEGER NOT NULL REFERENCES entries (rowid) ON DELETE CASCADE,
    lemma TEXT NOT NULL,
    UNIQUE (entry_rowid)
);
CREATE INDEX IF NOT EXISTS entry_index_entry_index ON entry_index(entry_rowid);
CREATE INDEX IF NOT EXISTS entry_index_lemma_index ON entry_index(lemma);

CREATE TABLE IF NOT EXISTS forms (
    rowid INTEGER PRIMARY KEY,
    id TEXT,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    entry_rowid INTEGER NOT NULL REFERENCES entries(rowid) ON DELETE CASCADE,
    form TEXT NOT NULL,
    normalized_form TEXT,
    script TEXT,
    rank INTEGER DEFAULT 1,
    UNIQUE (entry_rowid, form, script)
);
CREATE INDEX IF NOT EXISTS form_entry_index ON forms (entry_rowid);
CREATE INDEX IF NOT EXISTS form_index ON forms (form);
CREATE INDEX IF NOT EXISTS form_norm_index ON forms (normalized_form);

CREATE TABLE IF NOT EXISTS pronunciations (
    form_rowid INTEGER NOT NULL REFERENCES forms (rowid) ON DELETE CASCADE,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    value TEXT,
    variety TEXT,
    notation TEXT,
    phonemic BOOLEAN CHECK( phonemic IN (0, 1) ) DEFAULT 1 NOT NULL,
    audio TEXT
);
CREATE INDEX IF NOT EXISTS pronunciation_form_index ON pronunciations (form_rowid);

CREATE TABLE IF NOT EXISTS tags (
    form_rowid INTEGER NOT NULL REFERENCES forms (rowid) ON DELETE CASCADE,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    tag TEXT,
    category TEXT
);
CREATE INDEX IF NOT EXISTS tag_form_index ON tags (form_rowid);

-- Synset tables
CREATE TABLE IF NOT EXISTS synsets (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    ili_rowid INTEGER REFERENCES ilis (rowid),
    pos TEXT,
    lexfile_rowid INTEGER REFERENCES lexfiles (rowid),
    metadata META,
    UNIQUE (id, lexicon_rowid)
);
CREATE INDEX IF NOT EXISTS synset_id_index ON synsets (id);
CREATE INDEX IF NOT EXISTS synset_ili_rowid_index ON synsets (ili_rowid);

CREATE TABLE IF NOT EXISTS unlexicalized_synsets (
    synset_rowid INTEGER NOT NULL REFERENCES synsets (rowid) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS unlexicalized_synsets_index ON unlexicalized_synsets (synset_rowid);

CREATE TABLE IF NOT EXISTS synset_relations (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    source_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    target_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    type_rowid INTEGER NOT NULL REFERENCES relation_types(rowid),
    metadata META,
    UNIQUE (source_rowid, target_rowid, type_rowid)
);
CREATE INDEX IF NOT EXISTS synset_relation_source_index ON synset_relations (source_rowid);
CREATE INDEX IF NOT EXISTS synset_relation_target_index ON synset_relations (target_rowid);

CREATE TABLE IF NOT EXISTS definitions (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    synset_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    definition TEXT,
    language TEXT,
    sense_rowid INTEGER REFERENCES senses(rowid) ON DELETE SET NULL,
    metadata META
);
CREATE INDEX IF NOT EXISTS definition_rowid_index ON definitions (synset_rowid);
CREATE INDEX IF NOT EXISTS definition_sense_index ON definitions (sense_rowid);

CREATE TABLE IF NOT EXISTS synset_examples (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    synset_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    example TEXT,
    language TEXT,
    metadata META
);
CREATE INDEX IF NOT EXISTS synset_example_rowid_index ON synset_examples(synset_rowid);

-- Sense tables
CREATE TABLE IF NOT EXISTS senses (
    rowid INTEGER PRIMARY KEY,
    id TEXT NOT NULL,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    entry_rowid INTEGER NOT NULL REFERENCES entries(rowid) ON DELETE CASCADE,
    entry_rank INTEGER DEFAULT 1,
    synset_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    synset_rank INTEGER DEFAULT 1,
    metadata META
);
CREATE INDEX IF NOT EXISTS sense_id_index ON senses(id);
CREATE INDEX IF NOT EXISTS sense_entry_rowid_index ON senses (entry_rowid);
CREATE INDEX IF NOT EXISTS sense_synset_rowid_index ON senses (synset_rowid);

CREATE TABLE IF NOT EXISTS unlexicalized_senses (
    sense_rowid INTEGER NOT NULL REFERENCES senses (rowid) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS unlexicalized_senses_index ON unlexicalized_senses (sense_rowid);

CREATE TABLE IF NOT EXISTS sense_relations (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    source_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    target_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    type_rowid INTEGER NOT NULL REFERENCES relation_types(rowid),
    metadata META,
    UNIQUE (source_rowid, target_rowid, type_rowid)
);
CREATE INDEX IF NOT EXISTS sense_relation_source_index ON sense_relations (source_rowid);
CREATE INDEX IF NOT EXISTS sense_relation_target_index ON sense_relations (target_rowid);

CREATE TABLE IF NOT EXISTS sense_synset_relations (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    source_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    target_rowid INTEGER NOT NULL REFERENCES synsets(rowid) ON DELETE CASCADE,
    type_rowid INTEGER NOT NULL REFERENCES relation_types(rowid),
    metadata META,
    UNIQUE (source_rowid, target_rowid, type_rowid)
);
CREATE INDEX IF NOT EXISTS sense_synset_relation_source_index ON sense_synset_relations (source_rowid);
CREATE INDEX IF NOT EXISTS sense_synset_relation_target_index ON sense_synset_relations (target_rowid);

CREATE TABLE IF NOT EXISTS adjpositions (
    sense_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    adjposition TEXT NOT NULL
);
CREATE INDEX IF NOT EXISTS adjposition_sense_index ON adjpositions (sense_rowid);

CREATE TABLE IF NOT EXISTS sense_examples (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    sense_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    example TEXT,
    language TEXT,
    metadata META
);
CREATE INDEX IF NOT EXISTS sense_example_index ON sense_examples (sense_rowid);

CREATE TABLE IF NOT EXISTS counts (
    rowid INTEGER PRIMARY KEY,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons(rowid) ON DELETE CASCADE,
    sense_rowid INTEGER NOT NULL REFERENCES senses(rowid) ON DELETE CASCADE,
    count INTEGER NOT NULL,
    metadata META
);
CREATE INDEX IF NOT EXISTS count_index ON counts(sense_rowid);

-- Syntactic behaviour tables
CREATE TABLE IF NOT EXISTS syntactic_behaviours (
    rowid INTEGER PRIMARY KEY,
    id TEXT,
    lexicon_rowid INTEGER NOT NULL REFERENCES lexicons (rowid) ON DELETE CASCADE,
    frame TEXT NOT NULL,
    UNIQUE (lexicon_rowid, id),
    UNIQUE (lexicon_rowid, frame)
);
CREATE INDEX IF NOT EXISTS syntactic_behaviour_id_index ON syntactic_behaviours (id);

CREATE TABLE IF NOT EXISTS syntactic_behaviour_senses (
    syntactic_behaviour_rowid INTEGER NOT NULL REFERENCES syntactic_behaviours (rowid) ON DELETE CASCADE,
    sense_rowid INTEGER NOT NULL REFERENCES senses (rowid) ON DELETE CASCADE
);
CREATE INDEX IF NOT EXISTS syntactic_behaviour_sense_sb_index
    ON syntactic_behaviour_senses (syntactic_behaviour_rowid);
CREATE INDEX IF NOT EXISTS syntactic_behaviour_sense_sense_index
    ON syntactic_behaviour_senses (sense_rowid);

-- Edit history
CREATE TABLE IF NOT EXISTS edit_history (
    rowid INTEGER PRIMARY KEY,
    entity_type TEXT NOT NULL CHECK( entity_type IN ('lexicon','synset','entry','sense','relation','definition','example','form','ili') ),
    entity_id TEXT NOT NULL,
    field_name TEXT,
    operation TEXT NOT NULL CHECK( operation IN ('CREATE', 'UPDATE', 'DELETE') ),
    old_value TEXT,
    new_value TEXT,
    timestamp TEXT NOT NULL DEFAULT (strftime('%Y-%m-%dT%H:%M:%f', 'now'))
);
CREATE INDEX IF NOT EXISTS edit_history_entity_index ON edit_history (entity_type, entity_id);
CREATE INDEX IF NOT EXISTS edit_history_timestamp_index ON edit_history (timestamp);
"""


def connect(db_path: str | Path = ":memory:") -> sqlite3.Connection:
    """Open a database connection with editor PRAGMA settings."""
    db_path_str = str(db_path)
    conn = sqlite3.connect(
        db_path_str,
        detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES,
    )
    conn.execute("PRAGMA foreign_keys = ON")
    if db_path_str != ":memory:":
        conn.execute("PRAGMA journal_mode = WAL")
    conn.row_factory = sqlite3.Row
    return conn


def init_db(conn: sqlite3.Connection) -> None:
    """Initialize all tables if they don't exist. Set schema version."""
    conn.executescript(_DDL)
    # Insert schema version if not present
    conn.execute(
        "INSERT OR IGNORE INTO meta (key, value) VALUES ('schema_version', ?)",
        (SCHEMA_VERSION,),
    )
    conn.execute(
        "INSERT OR IGNORE INTO meta (key, value) "
        "VALUES ('created_at', strftime('%Y-%m-%dT%H:%M:%f', 'now'))",
    )
    # Seed ili_statuses
    for status in ("active", "presupposed", "deprecated"):
        conn.execute(
            "INSERT OR IGNORE INTO ili_statuses (status) VALUES (?)",
            (status,),
        )
    conn.commit()


def check_schema_version(conn: sqlite3.Connection) -> None:
    """Verify the database schema version is compatible."""
    try:
        row = conn.execute(
            "SELECT value FROM meta WHERE key = 'schema_version'"
        ).fetchone()
    except sqlite3.OperationalError:
        # meta table doesn't exist - uninitialized DB
        return
    if row is None:
        return
    version = row[0]
    if version != SCHEMA_VERSION:
        raise DatabaseError(
            f"Incompatible schema version: {version} "
            f"(expected {SCHEMA_VERSION})"
        )


# ---------------------------------------------------------------------------
# Lookup table helpers
# ---------------------------------------------------------------------------

def get_or_create_relation_type(conn: sqlite3.Connection, rel_type: str) -> int:
    """Get the rowid for a relation type, inserting if needed."""
    conn.execute(
        "INSERT OR IGNORE INTO relation_types (type) VALUES (?)",
        (rel_type,),
    )
    row = conn.execute(
        "SELECT rowid FROM relation_types WHERE type = ?",
        (rel_type,),
    ).fetchone()
    return row[0]


def get_or_create_lexfile(conn: sqlite3.Connection, name: str) -> int:
    """Get the rowid for a lexfile, inserting if needed."""
    conn.execute(
        "INSERT OR IGNORE INTO lexfiles (name) VALUES (?)",
        (name,),
    )
    row = conn.execute(
        "SELECT rowid FROM lexfiles WHERE name = ?",
        (name,),
    ).fetchone()
    return row[0]


def get_or_create_ili(
    conn: sqlite3.Connection,
    ili_id: str,
    status: str = "presupposed",
) -> int:
    """Get or create an ILI entry, returning its rowid."""
    status_rowid = conn.execute(
        "SELECT rowid FROM ili_statuses WHERE status = ?",
        (status,),
    ).fetchone()[0]
    conn.execute(
        "INSERT OR IGNORE INTO ilis (id, status_rowid) VALUES (?, ?)",
        (ili_id, status_rowid),
    )
    row = conn.execute(
        "SELECT rowid FROM ilis WHERE id = ?",
        (ili_id,),
    ).fetchone()
    return row[0]


# ---------------------------------------------------------------------------
# Lexicon CRUD helpers
# ---------------------------------------------------------------------------

def get_lexicon_rowid(conn: sqlite3.Connection, lexicon_id: str) -> int | None:
    """Get the rowid for a lexicon by ID or specifier, or None.

    Accepts a bare ID (``"awn"``) or a specifier (``"awn:1.0"``).
    Specifier format is tried first for unambiguous matching; bare ID
    is the fallback.  Because the editor prevents same-ID multi-version
    coexistence, the bare-ID path will always match at most one row.
    """
    # Try specifier first (id:version format, indexed)
    row = conn.execute(
        "SELECT rowid FROM lexicons WHERE specifier = ?",
        (lexicon_id,),
    ).fetchone()
    if row:
        return row[0]
    # Fall back to bare id
    row = conn.execute(
        "SELECT rowid FROM lexicons WHERE id = ?",
        (lexicon_id,),
    ).fetchone()
    return row[0] if row else None


def get_lexicon_row(conn: sqlite3.Connection, lexicon_id: str) -> sqlite3.Row | None:
    """Get a full lexicon row by ID or specifier.

    Accepts a bare ID (``"awn"``) or a specifier (``"awn:1.0"``).
    See :func:`get_lexicon_rowid` for resolution strategy.
    """
    # Try specifier first
    row = conn.execute(
        "SELECT rowid, * FROM lexicons WHERE specifier = ?",
        (lexicon_id,),
    ).fetchone()
    if row:
        return row
    # Fall back to bare id
    return conn.execute(
        "SELECT rowid, * FROM lexicons WHERE id = ?",
        (lexicon_id,),
    ).fetchone()


# ---------------------------------------------------------------------------
# Synset CRUD helpers
# ---------------------------------------------------------------------------

def get_synset_rowid(conn: sqlite3.Connection, synset_id: str) -> int | None:
    """Get the rowid for a synset by its ID, or None."""
    row = conn.execute(
        "SELECT rowid FROM synsets WHERE id = ?",
        (synset_id,),
    ).fetchone()
    return row[0] if row else None


def get_synset_row(conn: sqlite3.Connection, synset_id: str) -> sqlite3.Row | None:
    """Get a full synset row by ID."""
    return conn.execute(
        "SELECT rowid, * FROM synsets WHERE id = ?",
        (synset_id,),
    ).fetchone()


# ---------------------------------------------------------------------------
# Entry CRUD helpers
# ---------------------------------------------------------------------------

def get_entry_rowid(conn: sqlite3.Connection, entry_id: str) -> int | None:
    """Get the rowid for an entry by its ID, or None."""
    row = conn.execute(
        "SELECT rowid FROM entries WHERE id = ?",
        (entry_id,),
    ).fetchone()
    return row[0] if row else None


def get_entry_row(conn: sqlite3.Connection, entry_id: str) -> sqlite3.Row | None:
    """Get a full entry row by ID."""
    return conn.execute(
        "SELECT rowid, * FROM entries WHERE id = ?",
        (entry_id,),
    ).fetchone()


# ---------------------------------------------------------------------------
# Sense CRUD helpers
# ---------------------------------------------------------------------------

def get_sense_rowid(conn: sqlite3.Connection, sense_id: str) -> int | None:
    """Get the rowid for a sense by its ID, or None."""
    row = conn.execute(
        "SELECT rowid FROM senses WHERE id = ?",
        (sense_id,),
    ).fetchone()
    return row[0] if row else None


def get_sense_row(conn: sqlite3.Connection, sense_id: str) -> sqlite3.Row | None:
    """Get a full sense row by ID."""
    return conn.execute(
        "SELECT rowid, * FROM senses WHERE id = ?",
        (sense_id,),
    ).fetchone()
