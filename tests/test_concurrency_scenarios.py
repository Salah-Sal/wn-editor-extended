"""
Multi-Pipeline Concurrency Scenarios
=====================================

Simulates multiple users/pipelines accessing the same WordNet editor database
concurrently. Each scenario uses multiprocessing (not threading) to exercise
real SQLite file-level locking behavior.

Scenarios:
    1. Two pipelines import the same LMF file simultaneously
    2. Two pipelines import different lexicons to the same DB
    3. One writer imports while another reader queries
    4. Two pipelines create synsets concurrently (ID generation race)
    5. Two pipelines create entries concurrently (ID generation race)
    6. Two pipelines do batch CRUD simultaneously
    7. Three concurrent batch writers (stress test)
    8. Import then immediate export from another process
    9. Concurrent updates to different synsets in same lexicon
   10. Concurrent updates to the SAME synset (true race)
"""

from __future__ import annotations

import json
import multiprocessing as mp
import os
import shutil
import sqlite3
import sys
import tempfile
import time
import traceback
from pathlib import Path

# Add the project source to path
PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "src"))

from wordnet_editor import WordnetEditor

FIXTURES = Path(__file__).resolve().parent / "fixtures"
MINIMAL_XML = FIXTURES / "minimal.xml"
FULL_XML = FIXTURES / "full_features.xml"
TWO_LEX_XML = FIXTURES / "two_lexicons.xml"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _result(scenario: str, status: str, detail: str, elapsed: float) -> dict:
    """Build a structured result dict."""
    return {
        "scenario": scenario,
        "status": status,  # "PASS", "FAIL", "ERROR"
        "detail": detail,
        "elapsed_s": round(elapsed, 4),
        "pid": os.getpid(),
    }


def _fresh_db(tmp_dir: str, name: str = "shared.db") -> str:
    """Return path to a fresh empty DB file."""
    return os.path.join(tmp_dir, name)


def _seed_db(db_path: str) -> None:
    """Create a DB with the minimal lexicon pre-loaded."""
    ed = WordnetEditor.from_lmf(MINIMAL_XML, db_path)
    ed.close()


def _seed_full_db(db_path: str) -> None:
    """Create a DB with the full-features lexicon pre-loaded."""
    ed = WordnetEditor.from_lmf(FULL_XML, db_path)
    ed.close()


# ---------------------------------------------------------------------------
# Scenario worker functions (each runs in a subprocess)
# ---------------------------------------------------------------------------

def worker_import_lmf(db_path: str, xml_path: str, label: str, q: mp.Queue):
    """Import an LMF file into an existing DB."""
    t0 = time.perf_counter()
    try:
        ed = WordnetEditor(db_path)
        ed.import_lmf(xml_path)
        lexicons = ed.list_lexicons()
        lex_ids = [l.id for l in lexicons]
        ed.close()
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "PASS", f"Imported OK. Lexicons: {lex_ids}", elapsed))
    except Exception as e:
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "ERROR", f"{type(e).__name__}: {e}", elapsed))


def worker_from_lmf(db_path: str, xml_path: str, label: str, q: mp.Queue):
    """Create a new editor via from_lmf (which creates tables + imports)."""
    t0 = time.perf_counter()
    try:
        ed = WordnetEditor.from_lmf(xml_path, db_path)
        lexicons = ed.list_lexicons()
        lex_ids = [l.id for l in lexicons]
        ed.close()
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "PASS", f"from_lmf OK. Lexicons: {lex_ids}", elapsed))
    except Exception as e:
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "ERROR", f"{type(e).__name__}: {e}", elapsed))


def worker_create_synsets(db_path: str, lexicon_id: str, count: int,
                          label: str, q: mp.Queue):
    """Create N synsets in a batch."""
    t0 = time.perf_counter()
    created_ids = []
    errors = []
    try:
        ed = WordnetEditor(db_path)
        with ed.batch():
            for i in range(count):
                try:
                    ss = ed.create_synset(
                        lexicon_id, "n",
                        f"Test concept {label}-{i} for concurrency testing purposes",
                    )
                    created_ids.append(ss.id)
                except Exception as inner:
                    errors.append(f"synset {i}: {type(inner).__name__}: {inner}")
        ed.close()
        elapsed = time.perf_counter() - t0
        detail = f"Created {len(created_ids)} synsets"
        if errors:
            detail += f"; {len(errors)} errors: {errors[:3]}"
        status = "PASS" if not errors else "FAIL"
        q.put(_result(label, status, detail, elapsed))
    except Exception as e:
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "ERROR", f"{type(e).__name__}: {e}", elapsed))


def worker_create_entries(db_path: str, lexicon_id: str, lemmas: list[str],
                          label: str, q: mp.Queue):
    """Create entries with given lemmas in a batch."""
    t0 = time.perf_counter()
    created_ids = []
    errors = []
    try:
        ed = WordnetEditor(db_path)
        with ed.batch():
            for lemma in lemmas:
                try:
                    entry = ed.create_entry(lexicon_id, lemma, "n")
                    created_ids.append(entry.id)
                except Exception as inner:
                    errors.append(f"{lemma}: {type(inner).__name__}: {inner}")
        ed.close()
        elapsed = time.perf_counter() - t0
        detail = f"Created {len(created_ids)} entries: {created_ids[:5]}"
        if errors:
            detail += f"; {len(errors)} errors: {errors[:3]}"
        status = "PASS" if not errors else "FAIL"
        q.put(_result(label, status, detail, elapsed))
    except Exception as e:
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "ERROR", f"{type(e).__name__}: {e}", elapsed))


def worker_read_synsets(db_path: str, delay: float, label: str, q: mp.Queue):
    """Read all synsets from the DB."""
    if delay:
        time.sleep(delay)
    t0 = time.perf_counter()
    try:
        ed = WordnetEditor(db_path)
        synsets = ed.find_synsets()
        ed.close()
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "PASS", f"Read {len(synsets)} synsets", elapsed))
    except Exception as e:
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "ERROR", f"{type(e).__name__}: {e}", elapsed))


def worker_batch_crud(db_path: str, lexicon_id: str, worker_num: int,
                      label: str, q: mp.Queue):
    """Create synsets, entries, senses, add relations — full CRUD pipeline."""
    t0 = time.perf_counter()
    ops = []
    try:
        ed = WordnetEditor(db_path)
        with ed.batch():
            # Create synsets
            ss1 = ed.create_synset(
                lexicon_id, "n",
                f"Worker {worker_num} concept alpha for testing",
            )
            ops.append(f"synset:{ss1.id}")

            ss2 = ed.create_synset(
                lexicon_id, "n",
                f"Worker {worker_num} concept beta for testing",
            )
            ops.append(f"synset:{ss2.id}")

            # Create entry + sense
            entry = ed.create_entry(
                lexicon_id, f"word{worker_num}a", "n"
            )
            ops.append(f"entry:{entry.id}")

            sense = ed.add_sense(entry.id, ss1.id)
            ops.append(f"sense:{sense.id}")

            # Add relation
            ed.add_synset_relation(ss1.id, "hypernym", ss2.id)
            ops.append("relation:hypernym")

        ed.close()
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "PASS", f"CRUD OK: {ops}", elapsed))
    except Exception as e:
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "ERROR", f"{type(e).__name__}: {e}\nOps so far: {ops}", elapsed))


def worker_export(db_path: str, out_path: str, delay: float, label: str, q: mp.Queue):
    """Export the DB to LMF XML."""
    if delay:
        time.sleep(delay)
    t0 = time.perf_counter()
    try:
        ed = WordnetEditor(db_path)
        ed.export_lmf(out_path)
        ed.close()
        size = os.path.getsize(out_path)
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "PASS", f"Exported {size} bytes to {out_path}", elapsed))
    except Exception as e:
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "ERROR", f"{type(e).__name__}: {e}", elapsed))


def worker_update_synset(db_path: str, synset_id: str, new_pos: str,
                         label: str, q: mp.Queue):
    """Update a synset's POS."""
    t0 = time.perf_counter()
    try:
        ed = WordnetEditor(db_path)
        result = ed.update_synset(synset_id, pos=new_pos)
        ed.close()
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "PASS", f"Updated {synset_id} pos={result.pos}", elapsed))
    except Exception as e:
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "ERROR", f"{type(e).__name__}: {e}", elapsed))


def worker_update_synset_metadata(db_path: str, synset_id: str, meta: dict,
                                  label: str, q: mp.Queue):
    """Update a synset's metadata."""
    t0 = time.perf_counter()
    try:
        ed = WordnetEditor(db_path)
        result = ed.update_synset(synset_id, metadata=meta)
        ed.close()
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "PASS",
                       f"Updated {synset_id} metadata={result.metadata}", elapsed))
    except Exception as e:
        elapsed = time.perf_counter() - t0
        q.put(_result(label, "ERROR", f"{type(e).__name__}: {e}", elapsed))


# ---------------------------------------------------------------------------
# Scenario runners
# ---------------------------------------------------------------------------

def _run_workers(workers: list[tuple], timeout: int = 30) -> list[dict]:
    """Launch workers in parallel, collect results."""
    q = mp.Queue()
    procs = []
    for target, args in workers:
        p = mp.Process(target=target, args=(*args, q))
        procs.append(p)

    for p in procs:
        p.start()

    results = []
    for p in procs:
        p.join(timeout)
        if p.is_alive():
            p.terminate()
            results.append(_result("timeout", "ERROR", f"PID {p.pid} timed out", timeout))

    while not q.empty():
        results.append(q.get_nowait())

    return results


def scenario_1(tmp_dir: str) -> dict:
    """S1: Two pipelines import the SAME lexicon simultaneously."""
    db_path = _fresh_db(tmp_dir, "s1.db")
    # Initialize empty DB
    ed = WordnetEditor(db_path)
    ed.close()

    workers = [
        (worker_import_lmf, (db_path, str(MINIMAL_XML), "S1-Pipeline-A")),
        (worker_import_lmf, (db_path, str(MINIMAL_XML), "S1-Pipeline-B")),
    ]
    results = _run_workers(workers)

    # Post-check: how many lexicons ended up in the DB?
    ed = WordnetEditor(db_path)
    lexicons = ed.list_lexicons()
    synsets = ed.find_synsets()
    ed.close()

    return {
        "title": "S1: Two pipelines import the SAME LMF file simultaneously",
        "description": "Both Pipeline A and B try to import minimal.xml (lexicon 'test-min') "
                       "into the same DB at the same time. Expected: one succeeds, one gets "
                       "DuplicateEntityError.",
        "results": results,
        "post_check": {
            "lexicon_count": len(lexicons),
            "lexicon_ids": [l.id for l in lexicons],
            "synset_count": len(synsets),
        },
    }


def scenario_2(tmp_dir: str) -> dict:
    """S2: Two pipelines import DIFFERENT lexicons simultaneously."""
    db_path = _fresh_db(tmp_dir, "s2.db")
    ed = WordnetEditor(db_path)
    ed.close()

    workers = [
        (worker_import_lmf, (db_path, str(MINIMAL_XML), "S2-Pipeline-A")),
        (worker_import_lmf, (db_path, str(FULL_XML), "S2-Pipeline-B")),
    ]
    results = _run_workers(workers)

    ed = WordnetEditor(db_path)
    lexicons = ed.list_lexicons()
    synsets = ed.find_synsets()
    ed.close()

    return {
        "title": "S2: Two pipelines import DIFFERENT lexicons simultaneously",
        "description": "Pipeline A imports minimal.xml (test-min), Pipeline B imports "
                       "full_features.xml (test-full). No ID conflicts expected. "
                       "Tests WAL concurrent write capability.",
        "results": results,
        "post_check": {
            "lexicon_count": len(lexicons),
            "lexicon_ids": [l.id for l in lexicons],
            "synset_count": len(synsets),
        },
    }


def scenario_3(tmp_dir: str) -> dict:
    """S3: One pipeline writes while another reads."""
    db_path = _fresh_db(tmp_dir, "s3.db")
    _seed_db(db_path)

    workers = [
        (worker_import_lmf, (db_path, str(FULL_XML), "S3-Writer")),
        (worker_read_synsets, (db_path, 0.05, "S3-Reader")),  # slight delay
    ]
    results = _run_workers(workers)

    ed = WordnetEditor(db_path)
    synsets = ed.find_synsets()
    ed.close()

    return {
        "title": "S3: One pipeline writes while another reads",
        "description": "Writer imports full_features.xml while Reader queries find_synsets(). "
                       "WAL mode should allow non-blocking reads. Reader may see pre-import "
                       "or post-import state (snapshot isolation).",
        "results": results,
        "post_check": {"synset_count": len(synsets)},
    }


def scenario_4(tmp_dir: str) -> dict:
    """S4: Two pipelines create synsets concurrently (ID race)."""
    db_path = _fresh_db(tmp_dir, "s4.db")
    _seed_db(db_path)

    workers = [
        (worker_create_synsets, (db_path, "test-min", 20, "S4-Pipeline-A")),
        (worker_create_synsets, (db_path, "test-min", 20, "S4-Pipeline-B")),
    ]
    results = _run_workers(workers)

    # Check for duplicate IDs
    ed = WordnetEditor(db_path)
    synsets = ed.find_synsets(lexicon_id="test-min")
    ids = [s.id for s in synsets]
    duplicates = [x for x in ids if ids.count(x) > 1]
    ed.close()

    return {
        "title": "S4: Two pipelines create synsets concurrently (ID generation race)",
        "description": "Both pipelines create 20 synsets each in the same lexicon. "
                       "Tests _generate_synset_id MAX(CAST) race condition (PP7-A). "
                       "Expected: one pipeline may get SQLITE_BUSY or IntegrityError "
                       "due to ID collision.",
        "results": results,
        "post_check": {
            "total_synsets": len(synsets),
            "unique_ids": len(set(ids)),
            "duplicate_ids": list(set(duplicates)),
        },
    }


def scenario_5(tmp_dir: str) -> dict:
    """S5: Two pipelines create entries concurrently (ID race)."""
    db_path = _fresh_db(tmp_dir, "s5.db")
    _seed_db(db_path)

    # Both pipelines try to create entries with overlapping lemmas
    lemmas_a = [f"word{i}" for i in range(10)]
    lemmas_b = [f"word{i}" for i in range(5, 15)]  # overlap on word5..word9

    workers = [
        (worker_create_entries, (db_path, "test-min", lemmas_a, "S5-Pipeline-A")),
        (worker_create_entries, (db_path, "test-min", lemmas_b, "S5-Pipeline-B")),
    ]
    results = _run_workers(workers)

    ed = WordnetEditor(db_path)
    entries = ed.find_entries(lexicon_id="test-min")
    ids = [e.id for e in entries]
    ed.close()

    return {
        "title": "S5: Two pipelines create entries with overlapping lemmas",
        "description": "Pipeline A creates word0-word9, Pipeline B creates word5-word14. "
                       "Lemmas word5-word9 overlap — both pipelines try to create the same "
                       "entry IDs. Tests _generate_entry_id TOCTOU race (PP7-B).",
        "results": results,
        "post_check": {
            "total_entries": len(entries),
            "unique_ids": len(set(ids)),
            "entry_ids": sorted(ids),
        },
    }


def scenario_6(tmp_dir: str) -> dict:
    """S6: Two pipelines do full batch CRUD simultaneously."""
    db_path = _fresh_db(tmp_dir, "s6.db")
    _seed_db(db_path)

    workers = [
        (worker_batch_crud, (db_path, "test-min", 1, "S6-Pipeline-A")),
        (worker_batch_crud, (db_path, "test-min", 2, "S6-Pipeline-B")),
    ]
    results = _run_workers(workers)

    ed = WordnetEditor(db_path)
    synsets = ed.find_synsets(lexicon_id="test-min")
    entries = ed.find_entries(lexicon_id="test-min")
    ed.close()

    return {
        "title": "S6: Two pipelines do full batch CRUD simultaneously",
        "description": "Each pipeline creates 2 synsets, 1 entry, 1 sense, and 1 relation "
                       "in a batch. Tests BEGIN IMMEDIATE contention and overall atomicity.",
        "results": results,
        "post_check": {
            "synset_count": len(synsets),
            "entry_count": len(entries),
        },
    }


def scenario_7(tmp_dir: str) -> dict:
    """S7: Three concurrent batch writers (stress test)."""
    db_path = _fresh_db(tmp_dir, "s7.db")
    _seed_db(db_path)

    workers = [
        (worker_batch_crud, (db_path, "test-min", 1, "S7-Pipeline-A")),
        (worker_batch_crud, (db_path, "test-min", 2, "S7-Pipeline-B")),
        (worker_batch_crud, (db_path, "test-min", 3, "S7-Pipeline-C")),
    ]
    results = _run_workers(workers)

    ed = WordnetEditor(db_path)
    synsets = ed.find_synsets(lexicon_id="test-min")
    entries = ed.find_entries(lexicon_id="test-min")
    history = ed.get_history()
    ed.close()

    return {
        "title": "S7: Three concurrent batch writers (stress test)",
        "description": "Three pipelines each create synsets, entries, senses, and relations "
                       "simultaneously. Tests whether busy_timeout=5000ms is sufficient "
                       "for 3-way write contention.",
        "results": results,
        "post_check": {
            "synset_count": len(synsets),
            "entry_count": len(entries),
            "history_count": len(history),
        },
    }


def scenario_8(tmp_dir: str) -> dict:
    """S8: Import then immediate export from another process."""
    db_path = _fresh_db(tmp_dir, "s8.db")
    ed = WordnetEditor(db_path)
    ed.close()

    export_path = os.path.join(tmp_dir, "s8_export.xml")

    workers = [
        (worker_import_lmf, (db_path, str(FULL_XML), "S8-Importer")),
        (worker_export, (db_path, export_path, 0.1, "S8-Exporter")),  # slight delay
    ]
    results = _run_workers(workers)

    export_exists = os.path.exists(export_path)
    export_size = os.path.getsize(export_path) if export_exists else 0

    return {
        "title": "S8: Import then immediate export from another process",
        "description": "One process imports full_features.xml, another exports after a "
                       "100ms delay. Tests WAL snapshot isolation — exporter may get "
                       "empty DB or partial/full import depending on timing.",
        "results": results,
        "post_check": {
            "export_exists": export_exists,
            "export_size_bytes": export_size,
        },
    }


def scenario_9(tmp_dir: str) -> dict:
    """S9: Concurrent updates to DIFFERENT synsets."""
    db_path = _fresh_db(tmp_dir, "s9.db")
    _seed_full_db(db_path)

    # Get two different synset IDs
    ed = WordnetEditor(db_path)
    synsets = ed.find_synsets(lexicon_id="test-full")
    ss_ids = [s.id for s in synsets]
    ed.close()

    if len(ss_ids) < 2:
        return {"title": "S9: SKIPPED — not enough synsets", "results": [], "post_check": {}}

    workers = [
        (worker_update_synset_metadata, (db_path, ss_ids[0],
         {"source": "pipeline-A", "confidence": 0.9}, "S9-Pipeline-A")),
        (worker_update_synset_metadata, (db_path, ss_ids[1],
         {"source": "pipeline-B", "confidence": 0.8}, "S9-Pipeline-B")),
    ]
    results = _run_workers(workers)

    ed = WordnetEditor(db_path)
    s0 = ed.get_synset(ss_ids[0])
    s1 = ed.get_synset(ss_ids[1])
    ed.close()

    return {
        "title": "S9: Concurrent updates to DIFFERENT synsets in same lexicon",
        "description": f"Pipeline A updates {ss_ids[0]} metadata, Pipeline B updates "
                       f"{ss_ids[1]} metadata. No logical conflict — tests write serialization.",
        "results": results,
        "post_check": {
            f"{ss_ids[0]}_metadata": s0.metadata,
            f"{ss_ids[1]}_metadata": s1.metadata,
        },
    }


def scenario_10(tmp_dir: str) -> dict:
    """S10: Concurrent updates to the SAME synset (true race)."""
    db_path = _fresh_db(tmp_dir, "s10.db")
    _seed_full_db(db_path)

    ed = WordnetEditor(db_path)
    synsets = ed.find_synsets(lexicon_id="test-full")
    target_id = synsets[0].id
    ed.close()

    workers = [
        (worker_update_synset_metadata, (db_path, target_id,
         {"source": "pipeline-A", "version": 1}, "S10-Pipeline-A")),
        (worker_update_synset_metadata, (db_path, target_id,
         {"source": "pipeline-B", "version": 2}, "S10-Pipeline-B")),
    ]
    results = _run_workers(workers)

    ed = WordnetEditor(db_path)
    final = ed.get_synset(target_id)
    history = ed.get_history(entity_type="synset", entity_id=target_id)
    ed.close()

    return {
        "title": "S10: Concurrent updates to the SAME synset (true write race)",
        "description": f"Both pipelines update metadata on {target_id}. Last writer wins. "
                       "Tests whether both writes succeed (serialized by busy_timeout) "
                       "or one fails. Also checks if history captures both updates.",
        "results": results,
        "post_check": {
            "final_metadata": final.metadata,
            "history_entries": len(history),
            "history_detail": [
                {"op": h.operation, "field": h.field_name, "new": h.new_value}
                for h in history
                if h.field_name == "metadata"
            ],
        },
    }


# ---------------------------------------------------------------------------
# Main: run all scenarios and produce output
# ---------------------------------------------------------------------------

ALL_SCENARIOS = [
    scenario_1, scenario_2, scenario_3, scenario_4, scenario_5,
    scenario_6, scenario_7, scenario_8, scenario_9, scenario_10,
]


def run_all() -> list[dict]:
    """Run all scenarios and return results."""
    all_results = []
    with tempfile.TemporaryDirectory(prefix="wn_concurrency_") as tmp_dir:
        for i, scenario_fn in enumerate(ALL_SCENARIOS, 1):
            print(f"\n{'='*60}")
            print(f"Running Scenario {i}: {scenario_fn.__doc__.strip()}")
            print(f"{'='*60}")
            try:
                result = scenario_fn(tmp_dir)
                all_results.append(result)

                # Print summary
                print(f"\n  Title: {result['title']}")
                for r in result.get("results", []):
                    status_icon = {"PASS": "OK", "FAIL": "!!", "ERROR": "XX"}
                    icon = status_icon.get(r["status"], "??")
                    print(f"  [{icon}] {r['scenario']}: {r['detail']} ({r['elapsed_s']}s)")
                if result.get("post_check"):
                    print(f"  Post-check: {json.dumps(result['post_check'], default=str, indent=4)}")
            except Exception as e:
                print(f"  SCENARIO CRASHED: {e}")
                traceback.print_exc()
                all_results.append({
                    "title": f"S{i}: CRASHED",
                    "results": [_result(f"S{i}", "ERROR", f"Scenario crash: {e}", 0)],
                    "post_check": {},
                })

    return all_results


def format_markdown(all_results: list[dict]) -> str:
    """Format results as a markdown report."""
    lines = [
        "# Multi-Pipeline Concurrency Test Report",
        "",
        f"**Date:** {time.strftime('%Y-%m-%d %H:%M:%S')}",
        f"**Python:** {sys.version.split()[0]}",
        f"**SQLite:** {sqlite3.sqlite_version}",
        f"**Platform:** {sys.platform}",
        "",
        "---",
        "",
        "## Summary",
        "",
        "| # | Scenario | Result | Notes |",
        "|---|----------|--------|-------|",
    ]

    for i, scenario in enumerate(all_results, 1):
        title = scenario.get("title", f"S{i}")
        statuses = [r["status"] for r in scenario.get("results", [])]
        if all(s == "PASS" for s in statuses):
            result_str = "ALL PASS"
        elif any(s == "ERROR" for s in statuses):
            result_str = "ERROR"
        elif any(s == "FAIL" for s in statuses):
            result_str = "PARTIAL FAIL"
        else:
            result_str = "UNKNOWN"

        # Build a short note from post_check
        pc = scenario.get("post_check", {})
        notes = []
        if "lexicon_count" in pc:
            notes.append(f"{pc['lexicon_count']} lexicons")
        if "synset_count" in pc:
            notes.append(f"{pc['synset_count']} synsets")
        if "duplicate_ids" in pc and pc["duplicate_ids"]:
            notes.append(f"DUPLICATES: {pc['duplicate_ids']}")
        note_str = "; ".join(notes) if notes else ""

        lines.append(f"| {i} | {title.split(': ', 1)[-1][:60]} | {result_str} | {note_str} |")

    lines.extend(["", "---", ""])

    for i, scenario in enumerate(all_results, 1):
        lines.append(f"## Scenario {i}: {scenario.get('title', 'Unknown')}")
        lines.append("")
        if "description" in scenario:
            lines.append(f"> {scenario['description']}")
            lines.append("")

        lines.append("### Worker Results")
        lines.append("")
        lines.append("| Worker | Status | Time (s) | Detail |")
        lines.append("|--------|--------|----------|--------|")

        for r in scenario.get("results", []):
            detail_escaped = r["detail"].replace("|", "\\|").replace("\n", " ")
            if len(detail_escaped) > 120:
                detail_escaped = detail_escaped[:117] + "..."
            lines.append(
                f"| {r['scenario']} | {r['status']} | {r['elapsed_s']} | {detail_escaped} |"
            )

        lines.append("")

        if scenario.get("post_check"):
            lines.append("### Post-Check")
            lines.append("")
            lines.append("```json")
            lines.append(json.dumps(scenario["post_check"], indent=2, default=str))
            lines.append("```")
            lines.append("")

        # Observation placeholder
        lines.append("### Observation")
        lines.append("")
        lines.append("_To be filled after reviewing results._")
        lines.append("")
        lines.append("---")
        lines.append("")

    return "\n".join(lines)


if __name__ == "__main__":
    mp.set_start_method("spawn", force=True)
    results = run_all()

    report = format_markdown(results)
    report_path = PROJECT_ROOT / "docs" / "audit" / "concurrency-test-report.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    report_path.write_text(report)
    print(f"\n\nReport written to: {report_path}")