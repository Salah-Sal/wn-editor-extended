"""Import pipeline for wordnet-editor."""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from wordnet_editor import db as _db
from wordnet_editor import history as _hist
from wordnet_editor.exceptions import (
    DataImportError,
    DuplicateEntityError,
    EntityNotFoundError,
)


def import_from_lmf(
    conn: sqlite3.Connection,
    source: str | Path,
    *,
    record_history: bool = True,
) -> None:
    """Import data from a WN-LMF XML file into the editor database."""
    import wn.lmf

    source = Path(source)
    if not source.exists():
        raise FileNotFoundError(f"File not found: {source}")

    try:
        resource = wn.lmf.load(str(source))
    except Exception as e:
        raise DataImportError(f"Failed to parse XML: {e}") from e

    _import_resource(conn, resource, record_history=record_history)  # type: ignore[arg-type]


def import_from_wn(
    conn: sqlite3.Connection,
    specifier: str,
    *,
    record_history: bool = True,
    overrides: dict[str, Any] | None = None,
) -> None:
    """Import data from wn library's database."""
    try:
        _import_from_wn_bulk(conn, specifier, record_history=record_history)
    except Exception:
        _import_from_wn_xml(conn, specifier, record_history=record_history)

    # Apply overrides
    if overrides:
        _apply_overrides(conn, specifier, overrides)


def _import_from_wn_bulk(
    conn: sqlite3.Connection,
    specifier: str,
    *,
    record_history: bool = True,
) -> None:
    """Fast path: bulk SQL from wn's internal database."""
    from wn._db import connect as wn_connect

    wn_conn = wn_connect()
    wn_conn.row_factory = sqlite3.Row

    # Find lexicon
    lex_row = wn_conn.execute(
        "SELECT rowid, * FROM lexicons WHERE specifier = ?",
        (specifier,),
    ).fetchone()
    if lex_row is None:
        raise EntityNotFoundError(
            f"Lexicon not found in wn: {specifier!r}"
        )

    # Build a LexicalResource dict from the wn database
    resource = _build_resource_from_wn_db(wn_conn, lex_row)
    _import_resource(conn, resource, record_history=record_history)


def _import_from_wn_xml(
    conn: sqlite3.Connection,
    specifier: str,
    *,
    record_history: bool = True,
) -> None:
    """Fallback: export from wn to temp XML, then import."""
    import os
    import tempfile

    import wn.lmf

    import wn

    lexicons = wn.lexicons()
    target = None
    for lex in lexicons:
        if lex.specifier() == specifier:
            target = lex
            break
        # Try matching id:version
        if f"{lex.id}:{lex.version}" == specifier:
            target = lex
            break

    if target is None:
        raise EntityNotFoundError(
            f"Lexicon not found in wn: {specifier!r}"
        )

    with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
        tmp_path = tmp.name

    try:
        wn.export([target], tmp_path)
        resource = wn.lmf.load(tmp_path)
        _import_resource(conn, resource, record_history=record_history)  # type: ignore[arg-type]
    finally:
        os.unlink(tmp_path)


def _build_resource_from_wn_db(
    wn_conn: sqlite3.Connection, lex_row: sqlite3.Row
) -> dict:
    """Build LexicalResource TypedDict from wn database rows."""
    lex_rowid = lex_row["rowid"]

    # Build lexicon dict
    lexicon: dict[str, Any] = {
        "id": lex_row["id"],
        "label": lex_row["label"],
        "language": lex_row["language"],
        "email": lex_row["email"],
        "license": lex_row["license"],
        "version": lex_row["version"],
        "url": lex_row["url"] or "",
        "citation": lex_row["citation"] or "",
        "logo": lex_row.get("logo") or "" if "logo" in lex_row else "",  # type: ignore[attr-defined]
        "meta": _parse_meta(lex_row.get("metadata", None)),  # type: ignore[attr-defined]
        "entries": [],
        "synsets": [],
        "requires": [],
        "frames": [],
    }

    # Fetch synsets
    synset_rows = wn_conn.execute(
        "SELECT rowid, * FROM synsets WHERE lexicon_rowid = ?",
        (lex_rowid,),
    ).fetchall()

    synset_rowid_to_id: dict[int, str] = {}
    for sr in synset_rows:
        synset_rowid_to_id[sr["rowid"]] = sr["id"]

        # ILI
        ili_str = ""
        if sr["ili_rowid"]:
            ili_row = wn_conn.execute(
                "SELECT id FROM ilis WHERE rowid = ?", (sr["ili_rowid"],)
            ).fetchone()
            if ili_row:
                ili_str = ili_row["id"]

        # Check proposed ILI
        proposed = wn_conn.execute(
            "SELECT definition, metadata FROM proposed_ilis WHERE synset_rowid = ?",
            (sr["rowid"],),
        ).fetchone()

        # Lexfile
        lexfile = ""
        if sr.get("lexfile_rowid") if "lexfile_rowid" in sr else None:
            lf_row = wn_conn.execute(
                "SELECT name FROM lexfiles WHERE rowid = ?",
                (sr["lexfile_rowid"],),
            ).fetchone()
            if lf_row:
                lexfile = lf_row["name"]

        # Definitions
        defs = []
        for d in wn_conn.execute(
            "SELECT * FROM definitions WHERE synset_rowid = ?",
            (sr["rowid"],),
        ).fetchall():
            defn: dict[str, Any] = {"text": d["definition"] or ""}
            if d.get("language"):
                defn["language"] = d["language"]
            if d.get("sense_rowid"):
                sense_row = wn_conn.execute(
                    "SELECT id FROM senses WHERE rowid = ?",
                    (d["sense_rowid"],),
                ).fetchone()
                if sense_row:
                    defn["sourceSense"] = sense_row["id"]
            defn["meta"] = _parse_meta(d.get("metadata"))
            defs.append(defn)

        # Examples
        examples = []
        for e in wn_conn.execute(
            "SELECT * FROM synset_examples WHERE synset_rowid = ?",
            (sr["rowid"],),
        ).fetchall():
            ex: dict[str, Any] = {"text": e["example"] or ""}
            if e.get("language"):
                ex["language"] = e["language"]
            ex["meta"] = _parse_meta(e.get("metadata"))
            examples.append(ex)

        # Relations
        relations = []
        for rel in wn_conn.execute(
            "SELECT sr.*, rt.type FROM synset_relations sr "
            "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
            "WHERE sr.source_rowid = ?",
            (sr["rowid"],),
        ).fetchall():
            tgt = wn_conn.execute(
                "SELECT id FROM synsets WHERE rowid = ?",
                (rel["target_rowid"],),
            ).fetchone()
            if tgt:
                r: dict[str, Any] = {
                    "target": tgt["id"],
                    "relType": rel["type"],
                    "meta": _parse_meta(rel.get("metadata")),
                }
                relations.append(r)

        # Unlexicalized
        unlex = wn_conn.execute(
            "SELECT 1 FROM unlexicalized_synsets WHERE synset_rowid = ?",
            (sr["rowid"],),
        ).fetchone()

        # Members (sense IDs ordered by synset_rank)
        members = [
            m["id"]
            for m in wn_conn.execute(
                "SELECT id FROM senses WHERE synset_rowid = ? ORDER BY synset_rank",
                (sr["rowid"],),
            ).fetchall()
        ]

        synset: dict[str, Any] = {
            "id": sr["id"],
            "partOfSpeech": sr["pos"] or "",
            "ili": ili_str if not proposed else "in",
            "lexicalized": unlex is None,
            "lexfile": lexfile,
            "meta": _parse_meta(sr.get("metadata") if "metadata" in sr else None),
            "definitions": defs,
            "relations": relations,
            "examples": examples,
            "members": members,
        }
        if proposed:
            synset["ili_definition"] = {
                "text": proposed["definition"] or "",
                "meta": _parse_meta(proposed.get("metadata")),
            }
        lexicon["synsets"].append(synset)

    # Fetch entries
    entry_rows = wn_conn.execute(
        "SELECT rowid, * FROM entries WHERE lexicon_rowid = ?",
        (lex_rowid,),
    ).fetchall()

    for er in entry_rows:
        # Forms
        form_rows = wn_conn.execute(
            "SELECT rowid, * FROM forms WHERE entry_rowid = ? ORDER BY rank",
            (er["rowid"],),
        ).fetchall()

        lemma_dict: dict[str, Any] = {"writtenForm": "", "partOfSpeech": er["pos"]}
        forms_list = []
        for fr in form_rows:
            pronunciations = [
                {
                    "value": p["value"] or "",
                    "variety": p.get("variety") or "",
                    "notation": p.get("notation") or "",
                    "phonemic": bool(p.get("phonemic", 1)),
                    "audio": p.get("audio") or "",
                }
                for p in wn_conn.execute(
                    "SELECT * FROM pronunciations WHERE form_rowid = ?",
                    (fr["rowid"],),
                ).fetchall()
            ]
            tags_list = [
                {"tag": t["tag"], "category": t["category"]}
                for t in wn_conn.execute(
                    "SELECT * FROM tags WHERE form_rowid = ?",
                    (fr["rowid"],),
                ).fetchall()
            ]

            if fr["rank"] == 0:
                lemma_dict = {
                    "writtenForm": fr["form"],
                    "partOfSpeech": er["pos"],
                    "script": fr.get("script") or "",
                    "pronunciations": pronunciations,
                    "tags": tags_list,
                }
            else:
                forms_list.append({
                    "writtenForm": fr["form"],
                    "id": fr.get("id") or "",
                    "script": fr.get("script") or "",
                    "pronunciations": pronunciations,
                    "tags": tags_list,
                })

        # Senses
        sense_rows = wn_conn.execute(
            "SELECT rowid, * FROM senses WHERE entry_rowid = ? ORDER BY entry_rank",
            (er["rowid"],),
        ).fetchall()

        senses_list = []
        for sr in sense_rows:
            synset_id_for_sense = wn_conn.execute(
                "SELECT id FROM synsets WHERE rowid = ?",
                (sr["synset_rowid"],),
            ).fetchone()

            # Sense relations
            sense_rels = []
            for srel in wn_conn.execute(
                "SELECT sr.*, rt.type FROM sense_relations sr "
                "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
                "WHERE sr.source_rowid = ?",
                (sr["rowid"],),
            ).fetchall():
                tgt_sense = wn_conn.execute(
                    "SELECT id FROM senses WHERE rowid = ?",
                    (srel["target_rowid"],),
                ).fetchone()
                if tgt_sense:
                    sense_rels.append({
                        "target": tgt_sense["id"],
                        "relType": srel["type"],
                        "meta": _parse_meta(srel.get("metadata")),
                    })

            # Sense-synset relations
            for ssrel in wn_conn.execute(
                "SELECT sr.*, rt.type FROM sense_synset_relations sr "
                "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
                "WHERE sr.source_rowid = ?",
                (sr["rowid"],),
            ).fetchall():
                tgt_syn = wn_conn.execute(
                    "SELECT id FROM synsets WHERE rowid = ?",
                    (ssrel["target_rowid"],),
                ).fetchone()
                if tgt_syn:
                    sense_rels.append({
                        "target": tgt_syn["id"],
                        "relType": ssrel["type"],
                        "meta": _parse_meta(ssrel.get("metadata")),
                    })

            # Sense examples
            sense_examples = []
            for se in wn_conn.execute(
                "SELECT * FROM sense_examples WHERE sense_rowid = ?",
                (sr["rowid"],),
            ).fetchall():
                sex: dict[str, Any] = {"text": se["example"] or ""}
                if se.get("language"):
                    sex["language"] = se["language"]
                sex["meta"] = _parse_meta(se.get("metadata"))
                sense_examples.append(sex)

            # Counts
            counts_list = []
            for c in wn_conn.execute(
                "SELECT * FROM counts WHERE sense_rowid = ?",
                (sr["rowid"],),
            ).fetchall():
                counts_list.append({
                    "value": c["count"],
                    "meta": _parse_meta(c.get("metadata")),
                })

            # Adjposition
            adj_row = wn_conn.execute(
                "SELECT adjposition FROM adjpositions WHERE sense_rowid = ?",
                (sr["rowid"],),
            ).fetchone()

            # Unlexicalized sense
            unlex_sense = wn_conn.execute(
                "SELECT 1 FROM unlexicalized_senses WHERE sense_rowid = ?",
                (sr["rowid"],),
            ).fetchone()

            sense: dict[str, Any] = {
                "id": sr["id"],
                "synset": synset_id_for_sense["id"] if synset_id_for_sense else "",
                "n": sr.get("entry_rank") or 0,
                "lexicalized": unlex_sense is None,
                "adjposition": adj_row["adjposition"] if adj_row else "",
                "meta": _parse_meta(sr.get("metadata") if "metadata" in sr else None),
                "relations": sense_rels,
                "examples": sense_examples,
                "counts": counts_list,
                "subcat": [],
            }
            senses_list.append(sense)

        # Entry index
        idx_row = wn_conn.execute(
            "SELECT lemma FROM entry_index WHERE entry_rowid = ?",
            (er["rowid"],),
        ).fetchone()

        entry: dict[str, Any] = {
            "id": er["id"],
            "lemma": lemma_dict,
            "forms": forms_list,
            "senses": senses_list,
            "meta": _parse_meta(er.get("metadata") if "metadata" in er else None),
        }
        if idx_row:
            entry["index"] = idx_row["lemma"]
        lexicon["entries"].append(entry)

    # Syntactic behaviours
    sb_rows = wn_conn.execute(
        "SELECT rowid, * FROM syntactic_behaviours WHERE lexicon_rowid = ?",
        (lex_rowid,),
    ).fetchall()
    for sb in sb_rows:
        sense_ids = [
            s["id"]
            for s in wn_conn.execute(
                "SELECT s.id FROM syntactic_behaviour_senses sbs "
                "JOIN senses s ON sbs.sense_rowid = s.rowid "
                "WHERE sbs.syntactic_behaviour_rowid = ?",
                (sb["rowid"],),
            ).fetchall()
        ]
        lexicon["frames"].append({
            "id": sb.get("id") or "",
            "subcategorizationFrame": sb["frame"],
            "senses": sense_ids,
        })

    # Dependencies
    deps = wn_conn.execute(
        "SELECT * FROM lexicon_dependencies WHERE dependent_rowid = ?",
        (lex_rowid,),
    ).fetchall()
    for dep in deps:
        lexicon["requires"].append({
            "id": dep["provider_id"],
            "version": dep["provider_version"],
            "url": dep.get("provider_url") or "",
        })

    return {"lmf_version": "1.4", "lexicons": [lexicon]}


def _parse_meta(val: Any) -> dict | None:
    """Parse metadata from various formats."""
    if val is None:
        return None
    if isinstance(val, dict):
        return val
    if isinstance(val, (str, bytes)):
        try:
            return json.loads(val)
        except (json.JSONDecodeError, TypeError):
            return None
    return None


def _import_resource(
    conn: sqlite3.Connection,
    resource: dict,
    *,
    record_history: bool = True,
) -> None:
    """Import a LexicalResource dict into the editor database."""
    with conn:
        for lex_data in resource.get("lexicons", []):
            _import_lexicon(conn, lex_data, record_history=record_history)


def _import_lexicon(
    conn: sqlite3.Connection,
    lex: dict,
    *,
    record_history: bool = True,
) -> None:
    """Import one lexicon from a LexicalResource dict."""
    lex_id = lex["id"]
    version = lex["version"]
    specifier = f"{lex_id}:{version}"

    # Check for duplicates
    existing = conn.execute(
        "SELECT 1 FROM lexicons WHERE id = ? AND version = ?",
        (lex_id, version),
    ).fetchone()
    if existing:
        raise DuplicateEntityError(
            f"Lexicon {lex_id}:{version} already exists"
        )

    meta = lex.get("meta")
    meta_json = json.dumps(meta) if meta else None

    conn.execute(
        "INSERT INTO lexicons "
        "(specifier, id, label, language, email, license, version, "
        "url, citation, logo, metadata, modified) "
        "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
        (specifier, lex_id, lex["label"], lex["language"],
         lex["email"], lex["license"], version,
         lex.get("url") or None, lex.get("citation") or None,
         lex.get("logo") or None, meta_json),
    )
    lex_rowid = conn.execute(
        "SELECT rowid FROM lexicons WHERE specifier = ?", (specifier,)
    ).fetchone()[0]

    if record_history:
        _hist.record_create(conn, "lexicon", lex_id)

    # Dependencies
    for dep in lex.get("requires", []):
        provider_rowid = None
        pr = conn.execute(
            "SELECT rowid FROM lexicons WHERE id = ? AND version = ?",
            (dep["id"], dep["version"]),
        ).fetchone()
        if pr:
            provider_rowid = pr[0]
        conn.execute(
            "INSERT INTO lexicon_dependencies "
            "(dependent_rowid, provider_id, provider_version, provider_url, provider_rowid) "
            "VALUES (?, ?, ?, ?, ?)",
            (lex_rowid, dep["id"], dep["version"],
             dep.get("url") or None, provider_rowid),
        )

    # Extensions
    for ext in lex.get("extends", []):
        base_rowid = None
        br = conn.execute(
            "SELECT rowid FROM lexicons WHERE id = ? AND version = ?",
            (ext.get("id", ""), ext.get("version", "")),
        ).fetchone()
        if br:
            base_rowid = br[0]
        conn.execute(
            "INSERT INTO lexicon_extensions "
            "(extension_rowid, base_id, base_version, base_url, base_rowid) "
            "VALUES (?, ?, ?, ?, ?)",
            (lex_rowid, ext.get("id", ""), ext.get("version", ""),
             ext.get("url") or None, base_rowid),
        )

    # Collect relation types and lexfiles
    rel_types: set[str] = set()
    lexfile_names: set[str] = set()

    for syn in lex.get("synsets", []):
        for r in syn.get("relations", []):
            rel_types.add(r["relType"])
        lf = syn.get("lexfile", "")
        if lf:
            lexfile_names.add(lf)

    for entry in lex.get("entries", []):
        for sense in entry.get("senses", []):
            for r in sense.get("relations", []):
                rel_types.add(r["relType"])

    for rt in rel_types:
        _db.get_or_create_relation_type(conn, rt)
    for lf in lexfile_names:
        _db.get_or_create_lexfile(conn, lf)

    # Build synset ID -> rowid mapping
    synset_id_to_rowid: dict[str, int] = {}

    # Pre-fetch lexfiles
    lexfile_map: dict[str, int] = {
        row["name"]: row["rowid"]
        for row in conn.execute("SELECT name, rowid FROM lexfiles").fetchall()
    }

    # Prepare bulk synset insert
    synset_params = []
    proposed_ili_params = []
    unlex_params = []

    # Store dependent data keyed by synset ID to resolve rowid later
    proposed_ili_data: dict[str, tuple] = {}
    unlex_data: set[str] = set()

    # Cache ILI status
    ili_status_rowid = conn.execute(
        "SELECT rowid FROM ili_statuses WHERE status = 'presupposed'"
    ).fetchone()[0]

    for syn in lex.get("synsets", []):
        syn_id = syn["id"]
        ili_str = syn.get("ili", "")

        ili_rowid = None
        if ili_str and ili_str != "in":
            # Inline get_or_create_ili with cached status
            conn.execute(
                "INSERT OR IGNORE INTO ilis (id, status_rowid) VALUES (?, ?)",
                (ili_str, ili_status_rowid),
            )
            ili_rowid = conn.execute(
                "SELECT rowid FROM ilis WHERE id = ?",
                (ili_str,),
            ).fetchone()[0]

        lexfile_rowid = None
        lf = syn.get("lexfile", "")
        if lf:
            lexfile_rowid = lexfile_map.get(lf)

        syn_meta = syn.get("meta")
        synset_params.append((
            syn_id,
            lex_rowid,
            ili_rowid,
            syn.get("partOfSpeech") or None,
            lexfile_rowid,
            json.dumps(syn_meta) if syn_meta else None
        ))

        # Proposed ILI
        if ili_str == "in":
            ili_def = syn.get("ili_definition", {})
            if isinstance(ili_def, dict):
                def_text = ili_def.get("text", "")
                def_meta = ili_def.get("meta")
            else:
                def_text = str(ili_def)
                def_meta = None
            proposed_ili_data[syn_id] = (
                def_text,
                json.dumps(def_meta) if def_meta else None
            )

        # Unlexicalized
        if not syn.get("lexicalized", True):
            unlex_data.add(syn_id)

    # Bulk insert synsets
    if synset_params:
        conn.executemany(
            "INSERT INTO synsets (id, lexicon_rowid, ili_rowid, pos, lexfile_rowid, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?)",
            synset_params,
        )

        # Recover rowids
        cur = conn.cursor()
        cur.row_factory = None
        synset_id_to_rowid = dict(
            cur.execute(
                "SELECT id, rowid FROM synsets WHERE lexicon_rowid = ?",
                (lex_rowid,),
            ).fetchall()
        )

        # Prepare dependent inserts
        for syn_id, (def_text, def_meta_json) in proposed_ili_data.items():
            s_rowid = synset_id_to_rowid.get(syn_id)
            if s_rowid:
                proposed_ili_params.append((s_rowid, def_text, def_meta_json))

        for syn_id in unlex_data:
            s_rowid = synset_id_to_rowid.get(syn_id)
            if s_rowid:
                unlex_params.append((s_rowid,))

        if proposed_ili_params:
            conn.executemany(
                "INSERT INTO proposed_ilis (synset_rowid, definition, metadata) "
                "VALUES (?, ?, ?)",
                proposed_ili_params,
            )

        if unlex_params:
            conn.executemany(
                "INSERT INTO unlexicalized_synsets (synset_rowid) VALUES (?)",
                unlex_params,
            )

        if record_history:
            # History recording (still sequential as API doesn't support bulk)
            for syn_id, _, _, _, _, _ in synset_params:
                _hist.record_create(conn, "synset", syn_id)

    # Insert entries and their children
    sense_id_to_rowid: dict[str, int] = {}

    for entry in lex.get("entries", []):
        entry_meta = entry.get("meta")
        lemma = entry.get("lemma", {})
        pos = lemma.get("partOfSpeech", "")

        conn.execute(
            "INSERT INTO entries (id, lexicon_rowid, pos, metadata) "
            "VALUES (?, ?, ?, ?)",
            (entry["id"], lex_rowid, pos,
             json.dumps(entry_meta) if entry_meta else None),
        )
        entry_rowid = conn.execute(
            "SELECT rowid FROM entries WHERE id = ? AND lexicon_rowid = ?",
            (entry["id"], lex_rowid),
        ).fetchone()[0]

        # Entry index
        if entry.get("index"):
            conn.execute(
                "INSERT INTO entry_index (entry_rowid, lemma) VALUES (?, ?)",
                (entry_rowid, entry["index"]),
            )
        else:
            conn.execute(
                "INSERT INTO entry_index (entry_rowid, lemma) VALUES (?, ?)",
                (entry_rowid, lemma.get("writtenForm", "")),
            )

        # Lemma form (rank=0)
        lemma_form = lemma.get("writtenForm", "")
        lemma_script = lemma.get("script") or None
        if lemma_script == "":
            lemma_script = None
        normalized = lemma_form.casefold() if lemma_form.casefold() != lemma_form else None
        conn.execute(
            "INSERT INTO forms (id, lexicon_rowid, entry_rowid, form, "
            "normalized_form, script, rank) VALUES (NULL, ?, ?, ?, ?, ?, 0)",
            (lex_rowid, entry_rowid, lemma_form, normalized, lemma_script),
        )
        lemma_form_rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

        # Lemma pronunciations
        for pron in lemma.get("pronunciations", []):
            conn.execute(
                "INSERT INTO pronunciations "
                "(form_rowid, lexicon_rowid, value, variety, notation, phonemic, audio) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (lemma_form_rowid, lex_rowid,
                 pron.get("value") or None,
                 pron.get("variety") or None,
                 pron.get("notation") or None,
                 1 if pron.get("phonemic", True) else 0,
                 pron.get("audio") or None),
            )

        # Lemma tags
        for tag in lemma.get("tags", []):
            conn.execute(
                "INSERT INTO tags (form_rowid, lexicon_rowid, tag, category) "
                "VALUES (?, ?, ?, ?)",
                (lemma_form_rowid, lex_rowid,
                 tag.get("tag"), tag.get("category")),
            )

        # Additional forms
        for rank, form in enumerate(entry.get("forms", []), start=1):
            form_text = form.get("writtenForm", "")
            form_script = form.get("script") or None
            if form_script == "":
                form_script = None
            form_id = form.get("id") or None
            if form_id == "":
                form_id = None
            norm = form_text.casefold() if form_text.casefold() != form_text else None
            conn.execute(
                "INSERT INTO forms (id, lexicon_rowid, entry_rowid, form, "
                "normalized_form, script, rank) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (form_id, lex_rowid, entry_rowid, form_text, norm,
                 form_script, rank),
            )
            form_rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]

            for pron in form.get("pronunciations", []):
                conn.execute(
                    "INSERT INTO pronunciations "
                    "(form_rowid, lexicon_rowid, value, variety, notation, phonemic, audio) "
                    "VALUES (?, ?, ?, ?, ?, ?, ?)",
                    (form_rowid, lex_rowid,
                     pron.get("value") or None,
                     pron.get("variety") or None,
                     pron.get("notation") or None,
                     1 if pron.get("phonemic", True) else 0,
                     pron.get("audio") or None),
                )

            for tag in form.get("tags", []):
                conn.execute(
                    "INSERT INTO tags (form_rowid, lexicon_rowid, tag, category) "
                    "VALUES (?, ?, ?, ?)",
                    (form_rowid, lex_rowid,
                     tag.get("tag"), tag.get("category")),
                )

        # Senses
        for rank, sense in enumerate(entry.get("senses", []), start=1):
            synset_id = sense.get("synset", "")
            # Resolve synset_rowid
            syn_rowid = synset_id_to_rowid.get(synset_id)
            if syn_rowid is None:
                # Try cross-lexicon lookup
                sr = conn.execute(
                    "SELECT rowid FROM synsets WHERE id = ?", (synset_id,)
                ).fetchone()
                if sr:
                    syn_rowid = sr[0]
                else:
                    continue  # Skip if synset not found

            n_val = sense.get("n", 0)
            entry_rank = n_val if n_val else rank
            synset_rank_val = rank  # Default

            # Check members for synset_rank
            sense_meta = sense.get("meta")
            conn.execute(
                "INSERT INTO senses (id, lexicon_rowid, entry_rowid, "
                "entry_rank, synset_rowid, synset_rank, metadata) "
                "VALUES (?, ?, ?, ?, ?, ?, ?)",
                (sense["id"], lex_rowid, entry_rowid,
                 entry_rank, syn_rowid, synset_rank_val,
                 json.dumps(sense_meta) if sense_meta else None),
            )
            sense_rowid = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
            sense_id_to_rowid[sense["id"]] = sense_rowid

            # Unlexicalized sense
            if not sense.get("lexicalized", True):
                conn.execute(
                    "INSERT INTO unlexicalized_senses (sense_rowid) VALUES (?)",
                    (sense_rowid,),
                )

            # Adjposition
            adj = sense.get("adjposition", "")
            if adj:
                conn.execute(
                    "INSERT INTO adjpositions (sense_rowid, adjposition) "
                    "VALUES (?, ?)",
                    (sense_rowid, adj),
                )

            # Counts
            for c in sense.get("counts", []):
                c_meta = c.get("meta")
                conn.execute(
                    "INSERT INTO counts (lexicon_rowid, sense_rowid, count, metadata) "
                    "VALUES (?, ?, ?, ?)",
                    (lex_rowid, sense_rowid, c.get("value", 0),
                     json.dumps(c_meta) if c_meta else None),
                )

            # Sense examples
            for ex in sense.get("examples", []):
                ex_meta = ex.get("meta")
                conn.execute(
                    "INSERT INTO sense_examples "
                    "(lexicon_rowid, sense_rowid, example, language, metadata) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (lex_rowid, sense_rowid, ex.get("text", ""),
                     ex.get("language") or None,
                     json.dumps(ex_meta) if ex_meta else None),
                )

            if record_history:
                _hist.record_create(conn, "sense", sense["id"])

        if record_history:
            _hist.record_create(conn, "entry", entry["id"])

    # Syntactic behaviours
    for frame in lex.get("frames", []):
        frame_text = frame.get("subcategorizationFrame", "")
        frame_id = frame.get("id") or None
        if frame_id == "":
            frame_id = None
        conn.execute(
            "INSERT OR IGNORE INTO syntactic_behaviours "
            "(id, lexicon_rowid, frame) VALUES (?, ?, ?)",
            (frame_id, lex_rowid, frame_text),
        )
        sb_rowid = conn.execute(
            "SELECT rowid FROM syntactic_behaviours "
            "WHERE lexicon_rowid = ? AND frame = ?",
            (lex_rowid, frame_text),
        ).fetchone()[0]

        for sense_id in frame.get("senses", []):
            s_rowid = sense_id_to_rowid.get(sense_id)
            if s_rowid:
                conn.execute(
                    "INSERT INTO syntactic_behaviour_senses "
                    "(syntactic_behaviour_rowid, sense_rowid) VALUES (?, ?)",
                    (sb_rowid, s_rowid),
                )

    # Insert synset relations (after all synsets exist)
    for syn in lex.get("synsets", []):
        syn_rowid = synset_id_to_rowid.get(syn["id"])
        if syn_rowid is None:
            continue
        for rel in syn.get("relations", []):
            target_id = rel["target"]
            tgt_rowid = synset_id_to_rowid.get(target_id)
            if tgt_rowid is None:
                tgt = conn.execute(
                    "SELECT rowid FROM synsets WHERE id = ?", (target_id,)
                ).fetchone()
                if tgt:
                    tgt_rowid = tgt[0]
                else:
                    continue

            type_rowid = _db.get_or_create_relation_type(conn, rel["relType"])
            rel_meta = rel.get("meta")
            conn.execute(
                "INSERT OR IGNORE INTO synset_relations "
                "(lexicon_rowid, source_rowid, target_rowid, type_rowid, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                (lex_rowid, syn_rowid, tgt_rowid, type_rowid,
                 json.dumps(rel_meta) if rel_meta else None),
            )

    # Insert sense relations (after all senses exist)
    for entry in lex.get("entries", []):
        for sense in entry.get("senses", []):
            src_rowid = sense_id_to_rowid.get(sense["id"])
            if src_rowid is None:
                continue
            for rel in sense.get("relations", []):
                target_id = rel["target"]
                type_rowid = _db.get_or_create_relation_type(conn, rel["relType"])
                rel_meta = rel.get("meta")

                # Is target a sense or a synset?
                tgt_sense = sense_id_to_rowid.get(target_id)
                if tgt_sense is None:
                    tgt_sense_row = conn.execute(
                        "SELECT rowid FROM senses WHERE id = ?", (target_id,)
                    ).fetchone()
                    if tgt_sense_row:
                        tgt_sense = tgt_sense_row[0]

                if tgt_sense is not None:
                    conn.execute(
                        "INSERT OR IGNORE INTO sense_relations "
                        "(lexicon_rowid, source_rowid, target_rowid, type_rowid, metadata) "
                        "VALUES (?, ?, ?, ?, ?)",
                        (lex_rowid, src_rowid, tgt_sense, type_rowid,
                         json.dumps(rel_meta) if rel_meta else None),
                    )
                else:
                    # Try as synset
                    tgt_syn = synset_id_to_rowid.get(target_id)
                    if tgt_syn is None:
                        tgt_syn_row = conn.execute(
                            "SELECT rowid FROM synsets WHERE id = ?",
                            (target_id,),
                        ).fetchone()
                        if tgt_syn_row:
                            tgt_syn = tgt_syn_row[0]

                    if tgt_syn is not None:
                        conn.execute(
                            "INSERT OR IGNORE INTO sense_synset_relations "
                            "(lexicon_rowid, source_rowid, target_rowid, type_rowid, metadata) "
                            "VALUES (?, ?, ?, ?, ?)",
                            (lex_rowid, src_rowid, tgt_syn, type_rowid,
                             json.dumps(rel_meta) if rel_meta else None),
                        )

    # Insert definitions (after senses for sense_rowid resolution)
    for syn in lex.get("synsets", []):
        syn_rowid = synset_id_to_rowid.get(syn["id"])
        if syn_rowid is None:
            continue
        for defn in syn.get("definitions", []):
            sense_rowid = None
            ss = defn.get("sourceSense")
            if ss:
                sense_rowid = sense_id_to_rowid.get(ss)
                if sense_rowid is None:
                    sr = conn.execute(
                        "SELECT rowid FROM senses WHERE id = ?", (ss,)
                    ).fetchone()
                    if sr:
                        sense_rowid = sr[0]

            def_meta = defn.get("meta")
            conn.execute(
                "INSERT INTO definitions "
                "(lexicon_rowid, synset_rowid, definition, language, "
                "sense_rowid, metadata) VALUES (?, ?, ?, ?, ?, ?)",
                (lex_rowid, syn_rowid, defn.get("text", ""),
                 defn.get("language") or None, sense_rowid,
                 json.dumps(def_meta) if def_meta else None),
            )

    # Insert synset examples
    for syn in lex.get("synsets", []):
        syn_rowid = synset_id_to_rowid.get(syn["id"])
        if syn_rowid is None:
            continue
        for ex in syn.get("examples", []):
            ex_meta = ex.get("meta")
            conn.execute(
                "INSERT INTO synset_examples "
                "(lexicon_rowid, synset_rowid, example, language, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                (lex_rowid, syn_rowid, ex.get("text", ""),
                 ex.get("language") or None,
                 json.dumps(ex_meta) if ex_meta else None),
            )


def _apply_overrides(
    conn: sqlite3.Connection,
    specifier: str,
    overrides: dict[str, Any],
) -> None:
    """Apply metadata overrides to an imported lexicon."""
    row = conn.execute(
        "SELECT rowid, id, version FROM lexicons WHERE specifier = ?",
        (specifier,),
    ).fetchone()
    if row is None:
        return

    lex_rowid = row["rowid"]
    updates: dict[str, Any] = {}

    new_id = overrides.get("lexicon_id")
    new_version = overrides.get("version")
    if new_id is not None:
        updates["id"] = new_id
    if new_version is not None:
        updates["version"] = new_version

    for key in ("label", "email", "license", "url", "citation"):
        val = overrides.get(key)
        if val is not None:
            updates[key] = val

    if updates:
        # Update specifier if id or version changed
        new_spec_id = updates.get("id", row["id"])
        new_spec_ver = updates.get("version", row["version"])
        updates["specifier"] = f"{new_spec_id}:{new_spec_ver}"

        set_clauses = ", ".join(f"{k} = ?" for k in updates)
        params = list(updates.values()) + [lex_rowid]
        conn.execute(
            f"UPDATE lexicons SET {set_clauses} WHERE rowid = ?",
            params,
        )
        conn.commit()
