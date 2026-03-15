#!/usr/bin/env python3
"""Baseline metrics collection for wn-editor-extended database audit.

Collects row counts, PRAGMA settings, EXPLAIN QUERY PLAN output,
DB file metrics, and integrity checks for a given database file.

Usage:
    python docs/audit/run_baseline.py path/to/database.db

Output:
    - Formatted markdown to stdout
    - JSON data to {db_dir}/baseline_results.json
"""

from __future__ import annotations

import json
import os
import sqlite3
import sys
import time
from pathlib import Path

# All tables in the schema, ordered by dependency depth
TABLES = [
    "meta",
    "relation_types",
    "ili_statuses",
    "lexfiles",
    "ilis",
    "lexicons",
    "proposed_ilis",
    "lexicon_dependencies",
    "lexicon_extensions",
    "entries",
    "entry_index",
    "forms",
    "pronunciations",
    "tags",
    "synsets",
    "unlexicalized_synsets",
    "synset_relations",
    "definitions",
    "synset_examples",
    "senses",
    "unlexicalized_senses",
    "sense_relations",
    "sense_synset_relations",
    "adjpositions",
    "sense_examples",
    "counts",
    "syntactic_behaviours",
    "syntactic_behaviour_senses",
    "edit_history",
]

# Key queries to EXPLAIN
EXPLAIN_QUERIES = [
    (
        "Indexed range scan (synsets by lexicon)",
        "SELECT s.id FROM synsets s WHERE s.lexicon_rowid = 1",
    ),
    (
        "Full scan (definition LIKE search)",
        "SELECT synset_rowid FROM definitions WHERE definition LIKE '%word%'",
    ),
    (
        "Multi-table JOIN (synset relations)",
        "SELECT sr.rowid, sr.source_rowid, sr.target_rowid, rt.type "
        "FROM synset_relations sr "
        "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
        "WHERE sr.source_rowid = 1",
    ),
    (
        "Indexed composite (edit history by entity)",
        "SELECT rowid, * FROM edit_history "
        "WHERE entity_type = 'synset' AND entity_id = 'test'",
    ),
    (
        "Full scan (unfiltered history)",
        "SELECT rowid, * FROM edit_history ORDER BY timestamp ASC",
    ),
    (
        "4-table JOIN (sense model build)",
        "SELECT s.rowid, s.id, e.id as entry_id, syn.id as synset_id, "
        "l.id as lexicon_id "
        "FROM senses s "
        "JOIN entries e ON s.entry_rowid = e.rowid "
        "JOIN synsets syn ON s.synset_rowid = syn.rowid "
        "JOIN lexicons l ON s.lexicon_rowid = l.rowid "
        "WHERE s.id = 'test'",
    ),
]

PRAGMA_QUERIES = [
    "page_count",
    "page_size",
    "freelist_count",
    "journal_mode",
    "cache_size",
    "foreign_keys",
    "wal_autocheckpoint",
    "synchronous",
]


def collect_row_counts(conn: sqlite3.Connection) -> dict[str, int]:
    """Collect row counts for all tables."""
    counts = {}
    for table in TABLES:
        try:
            row = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()
            counts[table] = row[0]
        except sqlite3.OperationalError:
            counts[table] = -1  # table doesn't exist
    return counts


def collect_pragmas(conn: sqlite3.Connection) -> dict[str, str]:
    """Collect PRAGMA settings."""
    pragmas = {}
    for pragma in PRAGMA_QUERIES:
        try:
            row = conn.execute(f"PRAGMA {pragma}").fetchone()
            pragmas[pragma] = str(row[0]) if row else "N/A"
        except sqlite3.OperationalError:
            pragmas[pragma] = "ERROR"
    return pragmas


def collect_explain_plans(conn: sqlite3.Connection) -> list[dict[str, str]]:
    """Collect EXPLAIN QUERY PLAN output for key queries."""
    plans = []
    for label, query in EXPLAIN_QUERIES:
        try:
            rows = conn.execute(f"EXPLAIN QUERY PLAN {query}").fetchall()
            plan_lines = [
                f"  {r[0]}|{r[1]}|{r[2]}|{r[3]}" for r in rows
            ]
            plans.append({
                "label": label,
                "query": query,
                "plan": "\n".join(plan_lines),
            })
        except sqlite3.OperationalError as e:
            plans.append({
                "label": label,
                "query": query,
                "plan": f"ERROR: {e}",
            })
    return plans


def collect_file_metrics(db_path: Path) -> dict[str, int | str]:
    """Collect file size metrics."""
    metrics: dict[str, int | str] = {}
    metrics["db_size_bytes"] = db_path.stat().st_size if db_path.exists() else 0
    metrics["db_size_mb"] = round(metrics["db_size_bytes"] / (1024 * 1024), 2)

    wal_path = db_path.with_suffix(db_path.suffix + "-wal")
    metrics["wal_size_bytes"] = wal_path.stat().st_size if wal_path.exists() else 0
    metrics["wal_size_mb"] = round(metrics["wal_size_bytes"] / (1024 * 1024), 2)

    shm_path = db_path.with_suffix(db_path.suffix + "-shm")
    metrics["shm_size_bytes"] = shm_path.stat().st_size if shm_path.exists() else 0

    return metrics


def collect_integrity(conn: sqlite3.Connection) -> dict[str, str]:
    """Run integrity and foreign key checks."""
    results = {}

    start = time.perf_counter()
    row = conn.execute("PRAGMA quick_check").fetchone()
    elapsed = time.perf_counter() - start
    results["quick_check"] = row[0] if row else "N/A"
    results["quick_check_time_ms"] = round(elapsed * 1000, 1)

    start = time.perf_counter()
    fk_rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    elapsed = time.perf_counter() - start
    results["foreign_key_violations"] = len(fk_rows)
    results["foreign_key_check_time_ms"] = round(elapsed * 1000, 1)
    if fk_rows:
        results["foreign_key_details"] = [
            {"table": r[0], "rowid": r[1], "parent": r[2], "fkid": r[3]}
            for r in fk_rows[:10]  # limit to first 10
        ]

    return results


def collect_wal_checkpoint(conn: sqlite3.Connection) -> dict[str, int]:
    """Run a passive WAL checkpoint and report stats."""
    try:
        row = conn.execute("PRAGMA wal_checkpoint(PASSIVE)").fetchone()
        return {
            "busy": row[0],
            "log_frames": row[1],
            "checkpointed_frames": row[2],
        }
    except sqlite3.OperationalError:
        return {"busy": -1, "log_frames": -1, "checkpointed_frames": -1}


def collect_growth_estimate(conn: sqlite3.Connection) -> dict[str, str | float]:
    """Estimate edit history growth rate."""
    try:
        row = conn.execute(
            "SELECT MIN(timestamp), MAX(timestamp), COUNT(*) FROM edit_history"
        ).fetchone()
        if row and row[0] and row[2] > 0:
            return {
                "first_edit": row[0],
                "last_edit": row[1],
                "total_edits": row[2],
            }
    except sqlite3.OperationalError:
        pass
    return {"first_edit": "N/A", "last_edit": "N/A", "total_edits": 0}


def format_markdown(results: dict) -> str:
    """Format results as markdown."""
    lines = []
    lines.append("# Baseline Metrics Results")
    lines.append("")
    lines.append(f"**Database:** `{results['db_path']}`")
    lines.append(f"**Collected:** {results['timestamp']}")
    lines.append("")

    # File metrics
    lines.append("## File Metrics")
    lines.append("")
    fm = results["file_metrics"]
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| DB file size | {fm['db_size_mb']} MB ({fm['db_size_bytes']:,} bytes) |")
    lines.append(f"| WAL file size | {fm['wal_size_mb']} MB ({fm['wal_size_bytes']:,} bytes) |")
    lines.append(f"| SHM file size | {fm['shm_size_bytes']:,} bytes |")
    lines.append("")

    # PRAGMAs
    lines.append("## PRAGMA Settings")
    lines.append("")
    lines.append("| PRAGMA | Value |")
    lines.append("|--------|-------|")
    for k, v in results["pragmas"].items():
        lines.append(f"| `{k}` | `{v}` |")
    lines.append("")

    # Row counts
    lines.append("## Row Counts")
    lines.append("")
    lines.append("| Table | Rows |")
    lines.append("|-------|------|")
    sorted_counts = sorted(
        results["row_counts"].items(), key=lambda x: x[1], reverse=True
    )
    total = 0
    for table, count in sorted_counts:
        if count >= 0:
            lines.append(f"| `{table}` | {count:,} |")
            total += count
        else:
            lines.append(f"| `{table}` | *(missing)* |")
    lines.append(f"| **TOTAL** | **{total:,}** |")
    lines.append("")

    # EXPLAIN plans
    lines.append("## EXPLAIN QUERY PLAN")
    lines.append("")
    for plan in results["explain_plans"]:
        lines.append(f"### {plan['label']}")
        lines.append("")
        lines.append(f"```sql")
        lines.append(plan["query"])
        lines.append(f"```")
        lines.append("")
        lines.append(f"```")
        lines.append(plan["plan"])
        lines.append(f"```")
        lines.append("")

    # Integrity
    lines.append("## Integrity Checks")
    lines.append("")
    ic = results["integrity"]
    lines.append(f"| Check | Result | Time |")
    lines.append(f"|-------|--------|------|")
    lines.append(
        f"| `PRAGMA quick_check` | `{ic['quick_check']}` | {ic['quick_check_time_ms']} ms |"
    )
    lines.append(
        f"| `PRAGMA foreign_key_check` | {ic['foreign_key_violations']} violations | {ic['foreign_key_check_time_ms']} ms |"
    )
    lines.append("")

    # WAL checkpoint
    lines.append("## WAL Checkpoint (Passive)")
    lines.append("")
    wc = results["wal_checkpoint"]
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| Busy | {wc['busy']} |")
    lines.append(f"| WAL log frames | {wc['log_frames']} |")
    lines.append(f"| Checkpointed frames | {wc['checkpointed_frames']} |")
    lines.append("")

    # Growth estimate
    lines.append("## Edit History Growth")
    lines.append("")
    ge = results["growth_estimate"]
    lines.append(f"| Metric | Value |")
    lines.append(f"|--------|-------|")
    lines.append(f"| First edit | `{ge['first_edit']}` |")
    lines.append(f"| Last edit | `{ge['last_edit']}` |")
    lines.append(f"| Total edits | {ge['total_edits']:,} |")
    lines.append("")

    return "\n".join(lines)


def main() -> None:
    if len(sys.argv) < 2:
        print("Usage: python run_baseline.py <path_to_database.db>", file=sys.stderr)
        sys.exit(1)

    db_path = Path(sys.argv[1]).resolve()
    if not db_path.exists():
        print(f"Error: database file not found: {db_path}", file=sys.stderr)
        sys.exit(1)

    print(f"Collecting baseline metrics for: {db_path}", file=sys.stderr)

    conn = sqlite3.connect(str(db_path))
    conn.execute("PRAGMA foreign_keys = ON")

    results = {
        "db_path": str(db_path),
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%S"),
        "file_metrics": collect_file_metrics(db_path),
        "pragmas": collect_pragmas(conn),
        "row_counts": collect_row_counts(conn),
        "explain_plans": collect_explain_plans(conn),
        "integrity": collect_integrity(conn),
        "wal_checkpoint": collect_wal_checkpoint(conn),
        "growth_estimate": collect_growth_estimate(conn),
    }

    conn.close()

    # Output markdown to stdout
    print(format_markdown(results))

    # Save JSON to file next to the database
    json_path = db_path.parent / "baseline_results.json"
    with open(json_path, "w") as f:
        json.dump(results, f, indent=2, default=str)
    print(f"\nJSON results saved to: {json_path}", file=sys.stderr)


if __name__ == "__main__":
    main()
