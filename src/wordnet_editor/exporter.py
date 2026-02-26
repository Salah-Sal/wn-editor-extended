"""Export pipeline for wordnet-editor."""

from __future__ import annotations

import json
import logging
import os
import sqlite3
import tempfile
from collections import defaultdict
from pathlib import Path
from typing import Any

logger = logging.getLogger(__name__)


def export_to_lmf(
    conn: sqlite3.Connection,
    destination: str | Path,
    *,
    lexicon_ids: list[str] | None = None,
    lmf_version: str = "1.4",
) -> None:
    """Export editor database to WN-LMF XML."""
    import wn.lmf

    resource = _build_resource(conn, lexicon_ids=lexicon_ids, lmf_version=lmf_version)

    # Write XML
    wn.lmf.dump(resource, str(destination))  # type: ignore[arg-type]

    # Validate output
    loaded = wn.lmf.load(str(destination))
    _validate_export(loaded)  # type: ignore[arg-type]


def commit_to_wn(
    conn: sqlite3.Connection,
    *,
    db_path: str | Path | None = None,
    lexicon_ids: list[str] | None = None,
) -> None:
    """Export to WN-LMF and import into wn's database."""
    import wn

    original_path = None
    if db_path is not None:
        original_path = wn.config._dbpath
        wn.config._dbpath = Path(db_path)

    try:
        with tempfile.TemporaryDirectory() as tmp_dir:
            tmp_path = os.path.join(tmp_dir, "export.xml")

            export_to_lmf(conn, tmp_path, lexicon_ids=lexicon_ids)

            # Remove existing lexicons from wn
            ids_to_commit = lexicon_ids or _all_lexicon_ids(conn)
            for lex_id in ids_to_commit:
                row = conn.execute(
                    "SELECT version FROM lexicons WHERE id = ?",
                    (lex_id,),
                ).fetchone()
                if row:
                    spec = f"{lex_id}:{row['version']}"
                    for lex in wn.lexicons():
                        if lex.specifier() == spec:
                            wn.remove(spec)
                            break

            wn.add(tmp_path)
    finally:
        if original_path is not None:
            wn.config._dbpath = original_path


def _all_lexicon_ids(conn: sqlite3.Connection) -> list[str]:
    """Get all lexicon IDs."""
    rows = conn.execute("SELECT id FROM lexicons").fetchall()
    return [r["id"] for r in rows]


def _build_resource(
    conn: sqlite3.Connection,
    *,
    lexicon_ids: list[str] | None = None,
    lmf_version: str = "1.4",
) -> dict:
    """Build a LexicalResource TypedDict from the editor database."""
    if lexicon_ids:
        placeholders = ",".join("?" for _ in lexicon_ids)
        lex_rows = conn.execute(
            f"SELECT rowid, * FROM lexicons WHERE id IN ({placeholders})",
            lexicon_ids,
        ).fetchall()
    else:
        lex_rows = conn.execute("SELECT rowid, * FROM lexicons").fetchall()

    # Check for data loss at lower LMF versions
    if lmf_version < "1.1":
        _warn_data_loss(conn, lex_rows, lmf_version)

    lexicons = []
    for lex_row in lex_rows:
        lexicons.append(_build_lexicon(conn, lex_row, lmf_version))

    return {"lmf_version": lmf_version, "lexicons": lexicons}


def _build_lexicon(
    conn: sqlite3.Connection,
    lex_row: sqlite3.Row,
    lmf_version: str,
) -> dict:
    """Build a single Lexicon TypedDict."""
    lex_rowid = lex_row["rowid"]
    meta = lex_row["metadata"]
    if isinstance(meta, str):
        meta = json.loads(meta)

    lexicon: dict[str, Any] = {
        "id": lex_row["id"],
        "label": lex_row["label"],
        "language": lex_row["language"],
        "email": lex_row["email"],
        "license": lex_row["license"],
        "version": lex_row["version"],
        "url": lex_row["url"] or "",
        "citation": lex_row["citation"] or "",
        "logo": lex_row["logo"] or "",
        "meta": meta,
        "entries": [],
        "synsets": [],
        "requires": [],
        "frames": [],
    }

    # Dependencies
    deps = conn.execute(
        "SELECT * FROM lexicon_dependencies WHERE dependent_rowid = ?",
        (lex_rowid,),
    ).fetchall()
    for dep in deps:
        lexicon["requires"].append({
            "id": dep["provider_id"],
            "version": dep["provider_version"],
            "url": dep["provider_url"] or "",
        })

    # Entries
    entry_rows = conn.execute(
        "SELECT rowid, * FROM entries WHERE lexicon_rowid = ?",
        (lex_rowid,),
    ).fetchall()

    for er in entry_rows:
        lexicon["entries"].append(
            _build_entry(conn, er, lex_rowid)
        )

    # Pre-fetch synset data to avoid N+1 queries
    definitions_map = defaultdict(list)
    for row in conn.execute(
        "SELECT d.synset_rowid, d.definition, d.language, d.metadata, "
        "s.id as source_sense_id "
        "FROM definitions d "
        "LEFT JOIN senses s ON d.sense_rowid = s.rowid "
        "WHERE d.lexicon_rowid = ? ORDER BY d.rowid",
        (lex_rowid,),
    ).fetchall():
        definitions_map[row["synset_rowid"]].append(row)

    examples_map = defaultdict(list)
    for row in conn.execute(
        "SELECT synset_rowid, example, language, metadata "
        "FROM synset_examples WHERE lexicon_rowid = ? ORDER BY rowid",
        (lex_rowid,),
    ).fetchall():
        examples_map[row["synset_rowid"]].append(row)

    relations_map = defaultdict(list)
    for row in conn.execute(
        "SELECT sr.source_rowid, tgt.id as target_id, rt.type as rel_type, "
        "sr.metadata "
        "FROM synset_relations sr "
        "JOIN synsets tgt ON sr.target_rowid = tgt.rowid "
        "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
        "WHERE sr.lexicon_rowid = ?",
        (lex_rowid,),
    ).fetchall():
        relations_map[row["source_rowid"]].append(row)

    proposed_ili_map = {}
    for row in conn.execute(
        "SELECT p.synset_rowid, p.definition, p.metadata "
        "FROM proposed_ilis p "
        "JOIN synsets s ON p.synset_rowid = s.rowid "
        "WHERE s.lexicon_rowid = ?",
        (lex_rowid,),
    ).fetchall():
        proposed_ili_map[row["synset_rowid"]] = row

    unlexicalized_set = set()
    for row in conn.execute(
        "SELECT u.synset_rowid "
        "FROM unlexicalized_synsets u "
        "JOIN synsets s ON u.synset_rowid = s.rowid "
        "WHERE s.lexicon_rowid = ?",
        (lex_rowid,),
    ).fetchall():
        unlexicalized_set.add(row["synset_rowid"])

    members_map = defaultdict(list)
    for row in conn.execute(
        "SELECT s.synset_rowid, s.id "
        "FROM senses s "
        "JOIN synsets syn ON s.synset_rowid = syn.rowid "
        "WHERE syn.lexicon_rowid = ? "
        "ORDER BY s.synset_rank",
        (lex_rowid,),
    ).fetchall():
        members_map[row["synset_rowid"]].append(row["id"])

    # Synsets
    synset_rows = conn.execute(
        "SELECT s.rowid, s.id, s.pos, s.metadata, i.id as ili_id, "
        "lf.name as lexfile_name "
        "FROM synsets s "
        "LEFT JOIN ilis i ON s.ili_rowid = i.rowid "
        "LEFT JOIN lexfiles lf ON s.lexfile_rowid = lf.rowid "
        "WHERE s.lexicon_rowid = ?",
        (lex_rowid,),
    ).fetchall()

    for sr in synset_rows:
        lexicon["synsets"].append(
            _build_synset(
                sr,
                definitions=definitions_map[sr["rowid"]],
                examples=examples_map[sr["rowid"]],
                relations=relations_map[sr["rowid"]],
                proposed=proposed_ili_map.get(sr["rowid"]),
                unlexicalized=sr["rowid"] in unlexicalized_set,
                members=members_map[sr["rowid"]],
            )
        )

    # Syntactic behaviours
    sb_rows = conn.execute(
        "SELECT rowid, * FROM syntactic_behaviours WHERE lexicon_rowid = ?",
        (lex_rowid,),
    ).fetchall()
    for sb in sb_rows:
        sense_ids = [
            s["id"]
            for s in conn.execute(
                "SELECT s.id FROM syntactic_behaviour_senses sbs "
                "JOIN senses s ON sbs.sense_rowid = s.rowid "
                "WHERE sbs.syntactic_behaviour_rowid = ?",
                (sb["rowid"],),
            ).fetchall()
        ]
        lexicon["frames"].append({
            "id": sb["id"] or "",
            "subcategorizationFrame": sb["frame"],
            "senses": sense_ids,
        })

    return lexicon


def _build_entry(
    conn: sqlite3.Connection,
    er: sqlite3.Row,
    lex_rowid: int,
) -> dict:
    """Build a LexicalEntry TypedDict."""
    entry_rowid = er["rowid"]
    meta = er["metadata"]
    if isinstance(meta, str):
        meta = json.loads(meta)

    # Forms
    form_rows = conn.execute(
        "SELECT rowid, * FROM forms WHERE entry_rowid = ? ORDER BY rank",
        (entry_rowid,),
    ).fetchall()

    lemma_dict: dict[str, Any] = {
        "writtenForm": "",
        "partOfSpeech": er["pos"],
    }
    forms_list = []

    for fr in form_rows:
        prons = _build_pronunciations(conn, fr["rowid"])
        tags_list = _build_tags(conn, fr["rowid"])

        if fr["rank"] == 0:
            lemma_dict = {
                "writtenForm": fr["form"],
                "partOfSpeech": er["pos"],
                "script": fr["script"] or "",
                "pronunciations": prons,
                "tags": tags_list,
            }
        else:
            forms_list.append({
                "writtenForm": fr["form"],
                "id": fr["id"] or "",
                "script": fr["script"] or "",
                "pronunciations": prons,
                "tags": tags_list,
            })

    # Senses
    sense_rows = conn.execute(
        "SELECT rowid, * FROM senses WHERE entry_rowid = ? ORDER BY entry_rank",
        (entry_rowid,),
    ).fetchall()

    senses_list = []
    for sr in sense_rows:
        senses_list.append(_build_sense(conn, sr, lex_rowid))

    # Entry index
    idx_row = conn.execute(
        "SELECT lemma FROM entry_index WHERE entry_rowid = ?",
        (entry_rowid,),
    ).fetchone()

    entry: dict[str, Any] = {
        "id": er["id"],
        "lemma": lemma_dict,
        "forms": forms_list,
        "senses": senses_list,
        "meta": meta,
    }
    if idx_row:
        entry["index"] = idx_row["lemma"]

    return entry


def _build_sense(
    conn: sqlite3.Connection,
    sr: sqlite3.Row,
    lex_rowid: int,
) -> dict:
    """Build a Sense TypedDict."""
    sense_rowid = sr["rowid"]
    meta = sr["metadata"]
    if isinstance(meta, str):
        meta = json.loads(meta)

    # Get synset ID
    syn_row = conn.execute(
        "SELECT id FROM synsets WHERE rowid = ?",
        (sr["synset_rowid"],),
    ).fetchone()
    synset_id = syn_row["id"] if syn_row else ""

    # Sense relations
    relations = []
    for rel in conn.execute(
        "SELECT sr.*, rt.type FROM sense_relations sr "
        "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
        "WHERE sr.source_rowid = ?",
        (sense_rowid,),
    ).fetchall():
        tgt = conn.execute(
            "SELECT id FROM senses WHERE rowid = ?",
            (rel["target_rowid"],),
        ).fetchone()
        if tgt:
            rel_meta = rel["metadata"]
            if isinstance(rel_meta, str):
                rel_meta = json.loads(rel_meta)
            relations.append({
                "target": tgt["id"],
                "relType": rel["type"],
                "meta": rel_meta,
            })

    # Sense-synset relations
    for ssrel in conn.execute(
        "SELECT sr.*, rt.type FROM sense_synset_relations sr "
        "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
        "WHERE sr.source_rowid = ?",
        (sense_rowid,),
    ).fetchall():
        tgt = conn.execute(
            "SELECT id FROM synsets WHERE rowid = ?",
            (ssrel["target_rowid"],),
        ).fetchone()
        if tgt:
            rel_meta = ssrel["metadata"]
            if isinstance(rel_meta, str):
                rel_meta = json.loads(rel_meta)
            relations.append({
                "target": tgt["id"],
                "relType": ssrel["type"],
                "meta": rel_meta,
            })

    # Examples
    examples = []
    for ex in conn.execute(
        "SELECT * FROM sense_examples WHERE sense_rowid = ? ORDER BY rowid",
        (sense_rowid,),
    ).fetchall():
        ex_meta = ex["metadata"]
        if isinstance(ex_meta, str):
            ex_meta = json.loads(ex_meta)
        ex_dict: dict[str, Any] = {"text": ex["example"] or ""}
        if ex["language"]:
            ex_dict["language"] = ex["language"]
        ex_dict["meta"] = ex_meta
        examples.append(ex_dict)

    # Counts
    counts = []
    for c in conn.execute(
        "SELECT * FROM counts WHERE sense_rowid = ?",
        (sense_rowid,),
    ).fetchall():
        c_meta = c["metadata"]
        if isinstance(c_meta, str):
            c_meta = json.loads(c_meta)
        counts.append({"value": c["count"], "meta": c_meta})

    # Adjposition
    adj_row = conn.execute(
        "SELECT adjposition FROM adjpositions WHERE sense_rowid = ?",
        (sense_rowid,),
    ).fetchone()

    # Unlexicalized
    unlex = conn.execute(
        "SELECT 1 FROM unlexicalized_senses WHERE sense_rowid = ?",
        (sense_rowid,),
    ).fetchone()

    # Subcat
    subcat = [
        sb["id"]
        for sb in conn.execute(
            "SELECT sb.id FROM syntactic_behaviour_senses sbs "
            "JOIN syntactic_behaviours sb ON sbs.syntactic_behaviour_rowid = sb.rowid "
            "WHERE sbs.sense_rowid = ? AND sb.id IS NOT NULL",
            (sense_rowid,),
        ).fetchall()
    ]

    sense: dict[str, Any] = {
        "id": sr["id"],
        "synset": synset_id,
        "n": sr["entry_rank"] or 0,
        "lexicalized": unlex is None,
        "adjposition": adj_row["adjposition"] if adj_row else "",
        "meta": meta,
        "relations": relations,
        "examples": examples,
        "counts": counts,
        "subcat": subcat,
    }
    return sense


def _build_synset(
    sr: sqlite3.Row,
    definitions: list[sqlite3.Row],
    examples: list[sqlite3.Row],
    relations: list[sqlite3.Row],
    proposed: sqlite3.Row | None,
    unlexicalized: bool,
    members: list[str],
) -> dict:
    """Build a Synset TypedDict."""
    meta = sr["metadata"]
    if isinstance(meta, str):
        meta = json.loads(meta)

    # ILI
    ili_str = sr["ili_id"] or ""
    if proposed:
        ili_str = "in"

    # Lexfile
    lexfile = sr["lexfile_name"] or ""

    # Definitions
    defs = []
    for d in definitions:
        def_meta = d["metadata"]
        if isinstance(def_meta, str):
            def_meta = json.loads(def_meta)
        defn: dict[str, Any] = {"text": d["definition"] or ""}
        if d["language"]:
            defn["language"] = d["language"]
        if d["source_sense_id"]:
            defn["sourceSense"] = d["source_sense_id"]
        defn["meta"] = def_meta
        defs.append(defn)

    # Examples
    exs = []
    for e in examples:
        ex_meta = e["metadata"]
        if isinstance(ex_meta, str):
            ex_meta = json.loads(ex_meta)
        ex: dict[str, Any] = {"text": e["example"] or ""}
        if e["language"]:
            ex["language"] = e["language"]
        ex["meta"] = ex_meta
        exs.append(ex)

    # Relations
    rels = []
    for rel in relations:
        rel_meta = rel["metadata"]
        if isinstance(rel_meta, str):
            rel_meta = json.loads(rel_meta)
        rels.append({
            "target": rel["target_id"],
            "relType": rel["rel_type"],
            "meta": rel_meta,
        })

    synset: dict[str, Any] = {
        "id": sr["id"],
        "partOfSpeech": sr["pos"] or "",
        "ili": ili_str,
        "lexicalized": not unlexicalized,
        "lexfile": lexfile,
        "meta": meta,
        "definitions": defs,
        "relations": rels,
        "examples": exs,
        "members": members,
    }

    if proposed:
        p_meta = proposed["metadata"]
        if isinstance(p_meta, str):
            p_meta = json.loads(p_meta)
        synset["ili_definition"] = {
            "text": proposed["definition"] or "",
            "meta": p_meta,
        }

    return synset


def _build_pronunciations(
    conn: sqlite3.Connection, form_rowid: int
) -> list[dict]:
    """Build pronunciation dicts for a form."""
    return [
        {
            "text": p["value"] or "",
            "variety": p["variety"] or "",
            "notation": p["notation"] or "",
            "phonemic": bool(p["phonemic"]),
            "audio": p["audio"] or "",
        }
        for p in conn.execute(
            "SELECT * FROM pronunciations WHERE form_rowid = ?",
            (form_rowid,),
        ).fetchall()
    ]


def _build_tags(
    conn: sqlite3.Connection, form_rowid: int
) -> list[dict]:
    """Build tag dicts for a form."""
    return [
        {"text": t["tag"], "category": t["category"]}
        for t in conn.execute(
            "SELECT * FROM tags WHERE form_rowid = ?",
            (form_rowid,),
        ).fetchall()
    ]


def _validate_export(resource: dict) -> None:
    """Validate exported resource for errors."""
    # Placeholder: validation of the TypedDict structure
    for _lex in resource.get("lexicons", []):
        pass


def _warn_data_loss(
    conn: sqlite3.Connection,
    lex_rows: list,
    lmf_version: str,
) -> None:
    """Log warnings about data that will be lost at lower LMF versions."""
    if lmf_version < "1.1":
        for lex_row in lex_rows:
            lex_rowid = lex_row["rowid"]
            # Check for lexfile data
            has_lexfile = conn.execute(
                "SELECT 1 FROM synsets WHERE lexicon_rowid = ? "
                "AND lexfile_rowid IS NOT NULL LIMIT 1",
                (lex_rowid,),
            ).fetchone()
            if has_lexfile:
                logger.warning(
                    "Exporting at LMF %s will drop lexfile data for %s",
                    lmf_version, lex_row["id"],
                )

            has_counts = conn.execute(
                "SELECT 1 FROM counts WHERE lexicon_rowid = ? LIMIT 1",
                (lex_rowid,),
            ).fetchone()
            if has_counts:
                logger.warning(
                    "Exporting at LMF %s will drop count data for %s",
                    lmf_version, lex_row["id"],
                )
