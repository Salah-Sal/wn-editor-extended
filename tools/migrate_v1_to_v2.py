#!/usr/bin/env python3
"""Migrate a wordnet-editor v1.0 database to v2.0 schema.

Eliminates anti-pattern satellite tables by inlining their data into
the parent tables, then drops the old tables.  Uses create-copy-rename
for tables that need new constraints (e.g. CHECK, UNIQUE) that ALTER
TABLE cannot add.

Usage:
    python tools/migrate_v1_to_v2.py path/to/database.db
"""
from __future__ import annotations

import argparse
import shutil
import sqlite3
import sys
from pathlib import Path


def _check_version(conn: sqlite3.Connection) -> str:
    row = conn.execute(
        "SELECT value FROM meta WHERE key = 'schema_version'"
    ).fetchone()
    if row is None:
        sys.exit("ERROR: No schema_version found in meta table.")
    return row[0]


def _rebuild_ilis_table(conn: sqlite3.Connection) -> None:
    """Rebuild ilis table with CHECK constraint and status text column."""
    has_ili_statuses = conn.execute(
        "SELECT name FROM sqlite_master WHERE type='table' AND name='ili_statuses'"
    ).fetchone()

    conn.execute(
        "CREATE TABLE ilis_v2 ("
        "id TEXT NOT NULL UNIQUE, "
        "definition TEXT, "
        "status TEXT NOT NULL DEFAULT 'presupposed' "
        "CHECK(status IN ('active','presupposed','deprecated')), "
        "metadata TEXT"
        ")"
    )

    if has_ili_statuses:
        has_status_rowid = conn.execute(
            "SELECT 1 FROM pragma_table_info('ilis') WHERE name='status_rowid'"
        ).fetchone()
        if has_status_rowid:
            conn.execute(
                "INSERT INTO ilis_v2 (rowid, id, definition, status, metadata) "
                "SELECT i.rowid, i.id, i.definition, s.status, i.metadata "
                "FROM ilis i LEFT JOIN ili_statuses s ON i.status_rowid = s.rowid"
            )
        else:
            conn.execute(
                "INSERT INTO ilis_v2 (rowid, id, definition, status, metadata) "
                "SELECT rowid, id, definition, "
                "COALESCE(status, 'presupposed'), metadata FROM ilis"
            )
    else:
        conn.execute(
            "INSERT INTO ilis_v2 (rowid, id, definition, metadata) "
            "SELECT rowid, id, definition, metadata FROM ilis"
        )

    conn.execute("DROP TABLE ilis")
    conn.execute("ALTER TABLE ilis_v2 RENAME TO ilis")


def _verify_migration(conn: sqlite3.Connection) -> None:
    """Post-migration schema verification."""
    checks = [
        ("synsets.lexicalized column exists",
         "SELECT 1 FROM pragma_table_info('synsets') WHERE name='lexicalized'"),
        ("synsets.proposed_ili_definition column exists",
         "SELECT 1 FROM pragma_table_info('synsets') WHERE name='proposed_ili_definition'"),
        ("senses.lexicalized column exists",
         "SELECT 1 FROM pragma_table_info('senses') WHERE name='lexicalized'"),
        ("senses.adjposition column exists",
         "SELECT 1 FROM pragma_table_info('senses') WHERE name='adjposition'"),
        ("entries.lemma column exists",
         "SELECT 1 FROM pragma_table_info('entries') WHERE name='lemma'"),
        ("ilis.status column exists",
         "SELECT 1 FROM pragma_table_info('ilis') WHERE name='status'"),
    ]
    for desc, sql in checks:
        if conn.execute(sql).fetchone() is None:
            sys.exit(f"VERIFICATION FAILED: {desc}")

    removed_tables = [
        "unlexicalized_synsets", "unlexicalized_senses",
        "proposed_ilis", "adjpositions", "entry_index", "ili_statuses",
    ]
    for tbl in removed_tables:
        if conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (tbl,),
        ).fetchone() is not None:
            sys.exit(f"VERIFICATION FAILED: table '{tbl}' still exists")

    print("Post-migration verification passed.")


def migrate(db_path: str) -> None:
    backup = Path(db_path).with_suffix(".v1-backup.db")
    shutil.copy2(db_path, backup)
    print(f"Backup created: {backup}")

    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=OFF")

    version = _check_version(conn)
    if version == "2.0":
        print("Database is already at schema v2.0. Nothing to do.")
        conn.close()
        return
    if version != "1.0":
        sys.exit(f"ERROR: Unexpected schema version '{version}'. Expected '1.0'.")

    print("Migrating from v1.0 to v2.0...")

    conn.execute("ALTER TABLE synsets ADD COLUMN lexicalized BOOLEAN NOT NULL DEFAULT 1")
    conn.execute("ALTER TABLE synsets ADD COLUMN proposed_ili_definition TEXT")
    conn.execute("ALTER TABLE synsets ADD COLUMN proposed_ili_metadata TEXT")

    conn.execute("ALTER TABLE senses ADD COLUMN lexicalized BOOLEAN NOT NULL DEFAULT 1")
    conn.execute("ALTER TABLE senses ADD COLUMN adjposition TEXT")

    conn.execute("ALTER TABLE entries ADD COLUMN lemma TEXT NOT NULL DEFAULT ''")

    conn.execute(
        "UPDATE synsets SET lexicalized = 0 "
        "WHERE rowid IN (SELECT synset_rowid FROM unlexicalized_synsets)"
    )

    conn.execute(
        "UPDATE synsets SET "
        "proposed_ili_definition = (SELECT definition FROM proposed_ilis "
        "WHERE proposed_ilis.synset_rowid = synsets.rowid), "
        "proposed_ili_metadata = (SELECT metadata FROM proposed_ilis "
        "WHERE proposed_ilis.synset_rowid = synsets.rowid) "
        "WHERE rowid IN (SELECT synset_rowid FROM proposed_ilis)"
    )

    conn.execute(
        "UPDATE senses SET lexicalized = 0 "
        "WHERE rowid IN (SELECT sense_rowid FROM unlexicalized_senses)"
    )

    conn.execute(
        "UPDATE senses SET adjposition = ("
        "SELECT adjposition FROM adjpositions "
        "WHERE adjpositions.sense_rowid = senses.rowid"
        ") WHERE rowid IN (SELECT sense_rowid FROM adjpositions)"
    )

    conn.execute(
        "UPDATE entries SET lemma = ("
        "SELECT lemma FROM entry_index "
        "WHERE entry_index.entry_rowid = entries.rowid"
        ") WHERE rowid IN (SELECT entry_rowid FROM entry_index)"
    )

    _rebuild_ilis_table(conn)

    conn.execute(
        "CREATE UNIQUE INDEX IF NOT EXISTS "
        "sense_id_lexicon_unique ON senses (id, lexicon_rowid)"
    )

    conn.execute(
        "CREATE INDEX IF NOT EXISTS entry_lemma_index ON entries (lemma)"
    )

    conn.execute("DROP TABLE IF EXISTS unlexicalized_synsets")
    conn.execute("DROP TABLE IF EXISTS unlexicalized_senses")
    conn.execute("DROP TABLE IF EXISTS proposed_ilis")
    conn.execute("DROP TABLE IF EXISTS adjpositions")
    conn.execute("DROP TABLE IF EXISTS entry_index")
    conn.execute("DROP TABLE IF EXISTS ili_statuses")

    conn.execute("ALTER TABLE edit_history ADD COLUMN session_id TEXT")

    conn.execute("UPDATE meta SET value = '2.0' WHERE key = 'schema_version'")

    conn.execute("PRAGMA foreign_keys=ON")
    conn.commit()

    _verify_migration(conn)

    conn.execute("VACUUM")
    conn.close()

    print("Migration complete. Schema is now v2.0.")


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Migrate wordnet-editor database from v1.0 to v2.0"
    )
    parser.add_argument("database", help="Path to the SQLite database file")
    args = parser.parse_args()

    if not Path(args.database).exists():
        sys.exit(f"ERROR: File not found: {args.database}")

    migrate(args.database)


if __name__ == "__main__":
    main()
