"""Edit history recording and querying for wordnet-editor."""

from __future__ import annotations

import json
import sqlite3

from wordnet_editor.models import EditRecord


def record_create(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    new_value: dict | None = None,
) -> None:
    """Record a CREATE operation in edit history."""
    conn.execute(
        "INSERT INTO edit_history (entity_type, entity_id, operation, new_value) "
        "VALUES (?, ?, 'CREATE', ?)",
        (entity_type, entity_id, json.dumps(new_value) if new_value else None),
    )


def record_update(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    field_name: str,
    old_value: str | int | float | bool | None,
    new_value: str | int | float | bool | None,
) -> None:
    """Record an UPDATE operation in edit history."""
    conn.execute(
        "INSERT INTO edit_history "
        "(entity_type, entity_id, field_name, operation, old_value, new_value) "
        "VALUES (?, ?, ?, 'UPDATE', ?, ?)",
        (
            entity_type,
            entity_id,
            field_name,
            json.dumps(old_value),
            json.dumps(new_value),
        ),
    )


def record_delete(
    conn: sqlite3.Connection,
    entity_type: str,
    entity_id: str,
    old_value: dict | None = None,
) -> None:
    """Record a DELETE operation in edit history."""
    conn.execute(
        "INSERT INTO edit_history (entity_type, entity_id, operation, old_value) "
        "VALUES (?, ?, 'DELETE', ?)",
        (entity_type, entity_id, json.dumps(old_value) if old_value else None),
    )


def query_history(
    conn: sqlite3.Connection,
    *,
    entity_type: str | None = None,
    entity_id: str | None = None,
    since: str | None = None,
    operation: str | None = None,
) -> list[EditRecord]:
    """Query edit history with optional filters."""
    clauses: list[str] = []
    params: list[str] = []

    if entity_type is not None:
        clauses.append("entity_type = ?")
        params.append(entity_type)
    if entity_id is not None:
        clauses.append("entity_id = ?")
        params.append(entity_id)
    if since is not None:
        clauses.append("timestamp > ?")
        params.append(since)
    if operation is not None:
        clauses.append("operation = ?")
        params.append(operation)

    where = " AND ".join(clauses) if clauses else "1=1"
    sql = f"SELECT rowid, * FROM edit_history WHERE {where} ORDER BY timestamp ASC"

    rows = conn.execute(sql, params).fetchall()
    return [
        EditRecord(
            id=row["rowid"],
            entity_type=row["entity_type"],
            entity_id=row["entity_id"],
            field_name=row["field_name"],
            operation=row["operation"],
            old_value=row["old_value"],
            new_value=row["new_value"],
            timestamp=row["timestamp"],
        )
        for row in rows
    ]
