"""Validation engine for wordnet-editor."""

from __future__ import annotations

import json
import sqlite3

from wordnet_editor.models import ValidationResult
from wordnet_editor.relations import (
    SENSE_RELATIONS,
    SENSE_SYNSET_RELATIONS,
    SYNSET_RELATION_INVERSES,
    SYNSET_RELATIONS,
)


def validate_all(
    conn: sqlite3.Connection,
    *,
    lexicon_id: str | None = None,
) -> list[ValidationResult]:
    """Run all validation rules."""
    results: list[ValidationResult] = []
    results.extend(_val_gen_001(conn, lexicon_id))
    results.extend(_val_ent_001(conn, lexicon_id))
    results.extend(_val_ent_002(conn, lexicon_id))
    results.extend(_val_ent_003(conn, lexicon_id))
    results.extend(_val_ent_004(conn, lexicon_id))
    results.extend(_val_syn_001(conn, lexicon_id))
    results.extend(_val_syn_002(conn, lexicon_id))
    results.extend(_val_syn_003(conn, lexicon_id))
    results.extend(_val_syn_004(conn, lexicon_id))
    results.extend(_val_syn_005(conn, lexicon_id))
    results.extend(_val_syn_006(conn, lexicon_id))
    results.extend(_val_syn_007(conn, lexicon_id))
    results.extend(_val_syn_008(conn, lexicon_id))
    results.extend(_val_rel_001(conn, lexicon_id))
    results.extend(_val_rel_002(conn, lexicon_id))
    results.extend(_val_rel_003(conn, lexicon_id))
    results.extend(_val_rel_004(conn, lexicon_id))
    results.extend(_val_rel_005(conn, lexicon_id))
    results.extend(_val_tax_001(conn, lexicon_id))
    results.extend(_val_edt_001(conn, lexicon_id))
    results.extend(_val_edt_002(conn, lexicon_id))
    results.extend(_val_edt_003(conn, lexicon_id))
    return results


def validate_synset(
    conn: sqlite3.Connection, synset_id: str
) -> list[ValidationResult]:
    """Validate a specific synset."""
    results: list[ValidationResult] = []
    row = conn.execute(
        "SELECT s.rowid, s.id, s.pos, l.id as lex_id "
        "FROM synsets s JOIN lexicons l ON s.lexicon_rowid = l.rowid "
        "WHERE s.id = ?",
        (synset_id,),
    ).fetchone()
    if row is None:
        return results

    # Check unlexicalized (VAL-SYN-001)
    unlex = conn.execute(
        "SELECT 1 FROM unlexicalized_synsets WHERE synset_rowid = ?",
        (row["rowid"],),
    ).fetchone()
    if unlex is not None:
        results.append(ValidationResult(
            rule_id="VAL-SYN-001",
            severity="WARNING",
            entity_type="synset",
            entity_id=synset_id,
            message="Synset is empty (unlexicalized)",
            details=None,
        ))

    # Check no definitions (VAL-EDT-002)
    def_count = conn.execute(
        "SELECT COUNT(*) FROM definitions WHERE synset_rowid = ?",
        (row["rowid"],),
    ).fetchone()[0]
    if def_count == 0:
        results.append(ValidationResult(
            rule_id="VAL-EDT-002",
            severity="WARNING",
            entity_type="synset",
            entity_id=synset_id,
            message="Synset has no definitions",
            details=None,
        ))

    # Check blank definitions (VAL-SYN-005)
    blank_defs = conn.execute(
        "SELECT definition FROM definitions WHERE synset_rowid = ? "
        "AND (definition IS NULL OR TRIM(definition) = '')",
        (row["rowid"],),
    ).fetchall()
    for _ in blank_defs:
        results.append(ValidationResult(
            rule_id="VAL-SYN-005",
            severity="WARNING",
            entity_type="synset",
            entity_id=synset_id,
            message="Synset has a blank definition",
            details=None,
        ))

    # ID prefix check (VAL-EDT-001)
    if not synset_id.startswith(f"{row['lex_id']}-"):
        results.append(ValidationResult(
            rule_id="VAL-EDT-001",
            severity="ERROR",
            entity_type="synset",
            entity_id=synset_id,
            message=f"ID does not start with lexicon prefix: {row['lex_id']}-",
            details=None,
        ))

    return results


def validate_entry(
    conn: sqlite3.Connection, entry_id: str
) -> list[ValidationResult]:
    """Validate a specific entry."""
    results: list[ValidationResult] = []
    row = conn.execute(
        "SELECT e.rowid, e.id, l.id as lex_id "
        "FROM entries e JOIN lexicons l ON e.lexicon_rowid = l.rowid "
        "WHERE e.id = ?",
        (entry_id,),
    ).fetchone()
    if row is None:
        return results

    # VAL-ENT-001: no senses
    sense_count = conn.execute(
        "SELECT COUNT(*) FROM senses WHERE entry_rowid = ?",
        (row["rowid"],),
    ).fetchone()[0]
    if sense_count == 0:
        results.append(ValidationResult(
            rule_id="VAL-ENT-001",
            severity="WARNING",
            entity_type="entry",
            entity_id=entry_id,
            message="Entry has no senses",
            details=None,
        ))

    # VAL-EDT-001: ID prefix
    if not entry_id.startswith(f"{row['lex_id']}-"):
        results.append(ValidationResult(
            rule_id="VAL-EDT-001",
            severity="ERROR",
            entity_type="entry",
            entity_id=entry_id,
            message=f"ID does not start with lexicon prefix: {row['lex_id']}-",
            details=None,
        ))

    return results


def validate_relations(
    conn: sqlite3.Connection,
    *,
    lexicon_id: str | None = None,
) -> list[ValidationResult]:
    """Check all relations for issues."""
    results: list[ValidationResult] = []
    results.extend(_val_rel_001(conn, lexicon_id))
    results.extend(_val_rel_004(conn, lexicon_id))
    results.extend(_val_rel_005(conn, lexicon_id))
    return results


# ------------------------------------------------------------------
# Individual rule implementations
# ------------------------------------------------------------------

def _lex_filter(lexicon_id: str | None) -> tuple[str, list]:
    if lexicon_id is None:
        return "", []
    return (
        " AND lexicon_rowid = (SELECT rowid FROM lexicons WHERE id = ?)",
        [lexicon_id],
    )


def _check_duplicate_ids(
    conn: sqlite3.Connection,
    table: str,
    etype: str,
    filt: str,
    params: list,
) -> list[ValidationResult]:
    """Check for duplicate IDs in a given table."""
    results = []
    sql = (
        f"SELECT id, COUNT(*) as cnt FROM {table} WHERE 1=1 {filt} "
        "GROUP BY id HAVING cnt > 1"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-GEN-001",
            severity="ERROR",
            entity_type=etype,
            entity_id=row["id"],
            message=f"Duplicate {etype} ID: {row['id']}",
            details={"count": row["cnt"]},
        ))
    return results


def _val_gen_001(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Duplicate IDs within a lexicon."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    for table, etype in [
        ("synsets", "synset"),
        ("entries", "entry"),
        ("senses", "sense"),
    ]:
        results.extend(_check_duplicate_ids(conn, table, etype, filt, params))
    return results


def _val_ent_001(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Entries with no senses."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT e.id FROM entries e WHERE NOT EXISTS "
        "(SELECT 1 FROM senses s WHERE s.entry_rowid = e.rowid)"
        f" {filt.replace('lexicon_rowid', 'e.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-ENT-001",
            severity="WARNING",
            entity_type="entry",
            entity_id=row["id"],
            message="Entry has no senses",
            details=None,
        ))
    return results


def _val_ent_002(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Redundant senses: entry with multiple senses for same synset."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT s.entry_rowid, s.synset_rowid, COUNT(*) as cnt, "
        "e.id as entry_id, syn.id as synset_id "
        "FROM senses s "
        "JOIN entries e ON s.entry_rowid = e.rowid "
        "JOIN synsets syn ON s.synset_rowid = syn.rowid "
        f"WHERE 1=1 {filt.replace('lexicon_rowid', 's.lexicon_rowid')} "
        "GROUP BY s.entry_rowid, s.synset_rowid HAVING cnt > 1"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-ENT-002",
            severity="WARNING",
            entity_type="sense",
            entity_id=row["entry_id"],
            message=(
                f"Entry {row['entry_id']} has {row['cnt']} senses "
                f"for synset {row['synset_id']}"
            ),
            details=None,
        ))
    return results


def _val_ent_003(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Redundant entries: same lemma references same synset."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT f.form, s.synset_rowid, COUNT(DISTINCT e.rowid) as cnt "
        "FROM entries e "
        "JOIN forms f ON f.entry_rowid = e.rowid AND f.rank = 0 "
        "JOIN senses s ON s.entry_rowid = e.rowid "
        f"WHERE 1=1 {filt.replace('lexicon_rowid', 'e.lexicon_rowid')} "
        "GROUP BY f.form, s.synset_rowid HAVING cnt > 1"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-ENT-003",
            severity="WARNING",
            entity_type="entry",
            entity_id=row["form"],
            message=(
                f"Multiple entries with lemma '{row['form']}'"
                " reference the same synset"
            ),
            details=None,
        ))
    return results


def _val_ent_004(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Sense references missing synset."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT s.id, s.synset_rowid FROM senses s "
        f"WHERE NOT EXISTS (SELECT 1 FROM synsets syn WHERE syn.rowid = s.synset_rowid)"
        f" {filt.replace('lexicon_rowid', 's.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-ENT-004",
            severity="ERROR",
            entity_type="sense",
            entity_id=row["id"],
            message="Sense references missing synset",
            details=None,
        ))
    return results


def _val_syn_001(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Empty synsets (unlexicalized)."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT s.id FROM synsets s "
        "JOIN unlexicalized_synsets u ON u.synset_rowid = s.rowid"
        f" WHERE 1=1 {filt.replace('lexicon_rowid', 's.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-SYN-001",
            severity="WARNING",
            entity_type="synset",
            entity_id=row["id"],
            message="Synset is empty (unlexicalized)",
            details=None,
        ))
    return results


def _val_syn_002(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """ILI used by multiple synsets."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT i.id as ili_id, COUNT(*) as cnt "
        "FROM synsets s JOIN ilis i ON s.ili_rowid = i.rowid "
        "WHERE s.ili_rowid IS NOT NULL"
        f" {filt.replace('lexicon_rowid', 's.lexicon_rowid')} "
        "GROUP BY s.ili_rowid, s.lexicon_rowid HAVING cnt > 1"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-SYN-002",
            severity="WARNING",
            entity_type="synset",
            entity_id=row["ili_id"],
            message=f"ILI {row['ili_id']} used by {row['cnt']} synsets",
            details=None,
        ))
    return results


def _val_syn_005(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Blank definitions."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT s.id, d.definition FROM definitions d "
        "JOIN synsets s ON d.synset_rowid = s.rowid "
        f"WHERE (d.definition IS NULL OR TRIM(d.definition) = '')"
        f" {filt.replace('lexicon_rowid', 'd.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-SYN-005",
            severity="WARNING",
            entity_type="synset",
            entity_id=row["id"],
            message="Synset has a blank definition",
            details=None,
        ))
    return results


def _val_syn_007(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Duplicate definitions across synsets."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT d.definition, COUNT(DISTINCT d.synset_rowid) as cnt "
        "FROM definitions d "
        f"WHERE d.definition IS NOT NULL AND TRIM(d.definition) != ''"
        f" {filt.replace('lexicon_rowid', 'd.lexicon_rowid')} "
        "GROUP BY d.definition HAVING cnt > 1"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-SYN-007",
            severity="WARNING",
            entity_type="synset",
            entity_id="",
            message=f"Definition duplicated across {row['cnt']} synsets",
            details={"definition": row["definition"][:50]},
        ))
    return results


def _val_syn_008(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Proposed ILI definition < 20 chars."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT s.id, p.definition FROM proposed_ilis p "
        "JOIN synsets s ON p.synset_rowid = s.rowid "
        f"WHERE LENGTH(p.definition) < 20"
        f" {filt.replace('lexicon_rowid', 's.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-SYN-008",
            severity="ERROR",
            entity_type="synset",
            entity_id=row["id"],
            message="Proposed ILI definition is less than 20 characters",
            details=None,
        ))
    return results


def _val_rel_001(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Dangling relation targets."""
    results = []
    filt, params = _lex_filter(lexicon_id)

    # Synset relations with missing target
    sql = (
        "SELECT src.id as source_id, sr.target_rowid "
        "FROM synset_relations sr "
        "JOIN synsets src ON sr.source_rowid = src.rowid "
        "WHERE NOT EXISTS (SELECT 1 FROM synsets t WHERE t.rowid = sr.target_rowid)"
        f" {filt.replace('lexicon_rowid', 'sr.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-REL-001",
            severity="ERROR",
            entity_type="relation",
            entity_id=row["source_id"],
            message="Relation target synset is missing",
            details=None,
        ))

    return results


def _val_rel_004(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Missing inverse relations."""
    results = []
    filt, params = _lex_filter(lexicon_id)

    sql = (
        "SELECT src.id as source_id, tgt.id as target_id, rt.type "
        "FROM synset_relations sr "
        "JOIN synsets src ON sr.source_rowid = src.rowid "
        "JOIN synsets tgt ON sr.target_rowid = tgt.rowid "
        "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
        f"WHERE 1=1 {filt.replace('lexicon_rowid', 'sr.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        rel_type = row["type"]
        inverse = SYNSET_RELATION_INVERSES.get(rel_type)
        if inverse is None:
            continue  # No inverse defined

        # Check if inverse exists
        inv_type_row = conn.execute(
            "SELECT rowid FROM relation_types WHERE type = ?",
            (inverse,),
        ).fetchone()
        if inv_type_row is None:
            results.append(ValidationResult(
                rule_id="VAL-REL-004",
                severity="WARNING",
                entity_type="relation",
                entity_id=f"{row['source_id']}->{rel_type}->{row['target_id']}",
                message=f"Missing inverse relation: {inverse}",
                details=None,
            ))
            continue

        target_rowid = conn.execute(
            "SELECT rowid FROM synsets WHERE id = ?",
            (row["target_id"],),
        ).fetchone()
        source_rowid = conn.execute(
            "SELECT rowid FROM synsets WHERE id = ?",
            (row["source_id"],),
        ).fetchone()

        if target_rowid and source_rowid:
            inv_exists = conn.execute(
                "SELECT 1 FROM synset_relations "
                "WHERE source_rowid = ? AND target_rowid = ? AND type_rowid = ?",
                (target_rowid["rowid"], source_rowid["rowid"],
                 inv_type_row["rowid"]),
            ).fetchone()
            if inv_exists is None:
                results.append(ValidationResult(
                    rule_id="VAL-REL-004",
                    severity="WARNING",
                    entity_type="relation",
                    entity_id=f"{row['source_id']}->{rel_type}->{row['target_id']}",
                    message=f"Missing inverse relation: {inverse}",
                    details=None,
                ))

    return results


def _val_rel_005(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Self-loop relations."""
    results = []
    filt, params = _lex_filter(lexicon_id)

    sql = (
        "SELECT src.id as source_id, rt.type "
        "FROM synset_relations sr "
        "JOIN synsets src ON sr.source_rowid = src.rowid "
        "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
        f"WHERE sr.source_rowid = sr.target_rowid"
        f" {filt.replace('lexicon_rowid', 'sr.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-REL-005",
            severity="ERROR",
            entity_type="relation",
            entity_id=row["source_id"],
            message=f"Self-loop: {row['type']}",
            details=None,
        ))

    return results


def _val_tax_001(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """POS mismatch with hypernym."""
    results: list[ValidationResult] = []
    filt, params = _lex_filter(lexicon_id)

    hypernym_type = conn.execute(
        "SELECT rowid FROM relation_types WHERE type = 'hypernym'"
    ).fetchone()
    if hypernym_type is None:
        return results

    sql = (
        "SELECT src.id as source_id, src.pos as src_pos, "
        "tgt.id as target_id, tgt.pos as tgt_pos "
        "FROM synset_relations sr "
        "JOIN synsets src ON sr.source_rowid = src.rowid "
        "JOIN synsets tgt ON sr.target_rowid = tgt.rowid "
        f"WHERE sr.type_rowid = ? AND src.pos IS NOT NULL "
        f"AND tgt.pos IS NOT NULL AND src.pos != tgt.pos"
        f" {filt.replace('lexicon_rowid', 'sr.lexicon_rowid')}"
    )
    for row in conn.execute(sql, [hypernym_type["rowid"]] + params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-TAX-001",
            severity="WARNING",
            entity_type="synset",
            entity_id=row["source_id"],
            message=(
                f"POS mismatch: {row['source_id']} ({row['src_pos']}) "
                f"has hypernym {row['target_id']} ({row['tgt_pos']})"
            ),
            details=None,
        ))

    return results


def _val_edt_001(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """ID prefix validation."""
    results = []
    filt, params = _lex_filter(lexicon_id)

    for table, etype in [
        ("synsets", "synset"),
        ("entries", "entry"),
        ("senses", "sense"),
    ]:
        sql = (
            f"SELECT t.id, l.id as lex_id FROM {table} t "
            f"JOIN lexicons l ON t.lexicon_rowid = l.rowid "
            f"WHERE 1=1 {filt.replace('lexicon_rowid', 't.lexicon_rowid')}"
        )
        for row in conn.execute(sql, params).fetchall():
            if not row["id"].startswith(f"{row['lex_id']}-"):
                results.append(ValidationResult(
                    rule_id="VAL-EDT-001",
                    severity="ERROR",
                    entity_type=etype,
                    entity_id=row["id"],
                    message=f"ID does not start with lexicon prefix: {row['lex_id']}-",
                    details=None,
                ))

    return results


def _val_edt_002(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Synsets with no definitions."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT s.id FROM synsets s WHERE NOT EXISTS "
        "(SELECT 1 FROM definitions d WHERE d.synset_rowid = s.rowid)"
        f" {filt.replace('lexicon_rowid', 's.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-EDT-002",
            severity="WARNING",
            entity_type="synset",
            entity_id=row["id"],
            message="Synset has no definitions",
            details=None,
        ))
    return results


def _val_edt_003(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Sense with low confidence."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT s.id, s.metadata FROM senses s "
        f"WHERE s.metadata IS NOT NULL"
        f" {filt.replace('lexicon_rowid', 's.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        meta = row["metadata"]
        if isinstance(meta, str):
            try:
                meta = json.loads(meta)
            except (json.JSONDecodeError, TypeError):
                continue
        if meta and isinstance(meta, dict):
            score = meta.get("confidenceScore")
            if score is not None and float(score) < 0.5:
                results.append(ValidationResult(
                    rule_id="VAL-EDT-003",
                    severity="WARNING",
                    entity_type="sense",
                    entity_id=row["id"],
                    message=f"Sense has low confidence: {score}",
                    details=None,
                ))
    return results


def _val_syn_003(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Proposed ILI (ili='in') missing definition in proposed_ilis."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT s.id FROM synsets s "
        "JOIN proposed_ilis p ON p.synset_rowid = s.rowid "
        f"WHERE (p.definition IS NULL OR TRIM(p.definition) = '')"
        f" {filt.replace('lexicon_rowid', 's.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-SYN-003",
            severity="WARNING",
            entity_type="synset",
            entity_id=row["id"],
            message="Proposed ILI is missing a definition",
            details=None,
        ))
    return results


def _val_syn_004(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Existing ILI has spurious proposed ILI entry."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT s.id FROM synsets s "
        "JOIN proposed_ilis p ON p.synset_rowid = s.rowid "
        f"WHERE s.ili_rowid IS NOT NULL"
        f" {filt.replace('lexicon_rowid', 's.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-SYN-004",
            severity="WARNING",
            entity_type="synset",
            entity_id=row["id"],
            message="Existing ILI has a spurious ILI definition",
            details=None,
        ))
    return results


def _val_syn_006(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Blank synset examples."""
    results = []
    filt, params = _lex_filter(lexicon_id)
    sql = (
        "SELECT s.id FROM synset_examples e "
        "JOIN synsets s ON e.synset_rowid = s.rowid "
        f"WHERE (e.example IS NULL OR TRIM(e.example) = '')"
        f" {filt.replace('lexicon_rowid', 'e.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        results.append(ValidationResult(
            rule_id="VAL-SYN-006",
            severity="WARNING",
            entity_type="synset",
            entity_id=row["id"],
            message="Synset has a blank example",
            details=None,
        ))
    return results


def _val_rel_002(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Relation type invalid for source/target entity pair."""
    results = []
    filt, params = _lex_filter(lexicon_id)

    # Synset relations with invalid type
    sql = (
        "SELECT src.id as source_id, rt.type "
        "FROM synset_relations sr "
        "JOIN synsets src ON sr.source_rowid = src.rowid "
        "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
        f"WHERE 1=1 {filt.replace('lexicon_rowid', 'sr.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        if row["type"] not in SYNSET_RELATIONS:
            results.append(ValidationResult(
                rule_id="VAL-REL-002",
                severity="WARNING",
                entity_type="relation",
                entity_id=row["source_id"],
                message=f"Invalid synset relation type: {row['type']}",
                details={"relation_type": row["type"]},
            ))

    # Sense relations with invalid type
    sql = (
        "SELECT src.id as source_id, rt.type, "
        "CASE WHEN EXISTS (SELECT 1 FROM senses t WHERE t.rowid = sr.target_rowid) "
        "THEN 'sense' ELSE 'unknown' END as target_kind "
        "FROM sense_relations sr "
        "JOIN senses src ON sr.source_rowid = src.rowid "
        "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
        f"WHERE 1=1 {filt.replace('lexicon_rowid', 'sr.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        if row["type"] not in SENSE_RELATIONS:
            results.append(ValidationResult(
                rule_id="VAL-REL-002",
                severity="WARNING",
                entity_type="relation",
                entity_id=row["source_id"],
                message=f"Invalid sense relation type: {row['type']}",
                details={"relation_type": row["type"]},
            ))

    # Sense-synset relations with invalid type
    sql = (
        "SELECT src.id as source_id, rt.type "
        "FROM sense_synset_relations ssr "
        "JOIN senses src ON ssr.source_rowid = src.rowid "
        "JOIN relation_types rt ON ssr.type_rowid = rt.rowid "
        f"WHERE 1=1 {filt.replace('lexicon_rowid', 'ssr.lexicon_rowid')}"
    )
    for row in conn.execute(sql, params).fetchall():
        if row["type"] not in SENSE_SYNSET_RELATIONS:
            results.append(ValidationResult(
                rule_id="VAL-REL-002",
                severity="WARNING",
                entity_type="relation",
                entity_id=row["source_id"],
                message=f"Invalid sense-synset relation type: {row['type']}",
                details={"relation_type": row["type"]},
            ))

    return results


def _val_rel_003(
    conn: sqlite3.Connection, lexicon_id: str | None
) -> list[ValidationResult]:
    """Redundant relations (duplicate source, type, target)."""
    results = []
    filt, params = _lex_filter(lexicon_id)

    for table, etype, src_join, src_id_col in [
        ("synset_relations", "synset", "synsets", "id"),
        ("sense_relations", "sense", "senses", "id"),
    ]:
        sql = (
            f"SELECT src.{src_id_col} as source_id, rt.type, COUNT(*) as cnt "
            f"FROM {table} r "
            f"JOIN {src_join} src ON r.source_rowid = src.rowid "
            f"JOIN relation_types rt ON r.type_rowid = rt.rowid "
            f"WHERE 1=1 {filt.replace('lexicon_rowid', 'r.lexicon_rowid')} "
            f"GROUP BY r.source_rowid, r.target_rowid, r.type_rowid "
            f"HAVING cnt > 1"
        )
        for row in conn.execute(sql, params).fetchall():
            results.append(ValidationResult(
                rule_id="VAL-REL-003",
                severity="WARNING",
                entity_type="relation",
                entity_id=row["source_id"],
                message=(
                    f"Redundant {etype} relation: {row['type']} "
                    f"appears {row['cnt']} times"
                ),
                details={"count": row["cnt"]},
            ))

    return results
