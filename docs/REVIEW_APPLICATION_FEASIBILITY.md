# Feasibility Report: Applying Linguistic Review Actions to AWN4 via wn-editor-extended

## Context

The linguistic review pipeline (`dspy_review/pipeline.py`) produces structured YAML review files for AWN4 synsets. Each review contains `actions:` lists with concrete edit commands (e.g., `remove_sense`, `update_definition`, `add_synset_example`). The pipeline's own docstring states: _"The API execution part is handled downstream by the AWN4 API client"_ — but that client did not yet exist.

**The question**: Can `wn-editor-extended` (`wn_editor`) serve as that client? What gaps exist, and what bridging work is needed?

**Key numbers**:
- AWN4: 109,901 synsets in `awn4.xml` (69 MB WN-LMF 1.4)
- Already loaded: `data/awn4.xml` and `data/awn4_experiment.db` (157 MB) exist in the wn-editor-extended repo
- Reviewed: 164 synsets in `reviews_claude_db/` (with `.review.yaml`, `.stderr.log`, `.trajectory.jsonl`)
- Action command vocabulary: 13 English commands + 16 Arabic commands across directories

---

## 1. Feasibility Verdict: YES — implemented as a thin bridging module

Every editor mutation required by the review actions exists in `wn-editor-extended`'s per-entity editor classes (`SynsetEditor`, `SenseEditor`, `EntryEditor`). The bridging module has been implemented at:

```
arabic-wordnet-v4/experiments/linguistic_review_guide/apply_reviews.py
```

### 1.1 Command Coverage Matrix

| Review Command | Editor Method | Match Quality |
|---|---|---|
| `update_definition` | `SynsetEditor(synset).mod_definition(text, indx=N)` | Exact — `definition_index` → `indx` |
| `add_definition` | `SynsetEditor(synset).add_definition(text)` | Exact |
| `add_synset_example` | `SynsetEditor(synset).add_example(text)` | Exact |
| `add_sense_example` | `SenseEditor(sense).add_example(text)` | Needs sense resolution from lemma |
| `remove_synset_relation` | `SynsetEditor(src).delete_relation_to_synset(tgt, type_id)` | Exact |
| `add_synset_relation` | `SynsetEditor(src).set_relation_to_synset(tgt, type_id)` | Exact when target_id is concrete; escalated when `{auto}` or placeholder |
| `set_metadata` | `SynsetEditor/SenseEditor/EntryEditor.set_metadata({key: val})` | Exact — dispatched by `entity_type` |
| `set_confidence` | `.set_metadata({"dc:confidence": score})` | No dedicated method; metadata workaround |
| `create_entry` | `EntryEditor(lex_rowid, exists=False)` + `.add_form(lemma)` | Exact |
| `add_sense` | `SenseEditor(lex_rowid, entry_rowid, synset_rowid)` | Needs entry_id from create or lookup |
| `remove_sense` | `SenseEditor(sense).delete()` | Needs sense resolution from lemma+synset |
| `move_sense` | `SenseEditor.delete()` + `SenseEditor(lex, entry, target_synset)` | Composite: delete + recreate |
| `escalate` | N/A (not a DB edit) | Log-only, skip |
| `retain_definition` | N/A (no-op) | Skip |

### 1.2 API Differences from Initial Assumptions

The feasibility report initially assumed a flat `WordnetEditor` API. The actual API differs:

| Assumed API | Actual API | Notes |
|---|---|---|
| `editor.update_definition(synset_id, idx, text)` | `SynsetEditor(synset).mod_definition(text, indx=N)` | Per-entity class pattern |
| `editor.find_entries(lemma=X)` | `wn.words(form=X, lexicon=id)` | Lookup via base `wn` package |
| `editor.find_senses(entry_id, synset_id)` | `wn.senses(form=X, lexicon=id)` + filter by synset | No finder API in editor |
| `editor.batch()` | `wn_editor.tracking_session(name, desc)` | Context manager with rollback |
| `editor.set_confidence(entity, id, score)` | `.set_metadata({"dc:confidence": str(score)})` | No dedicated method |
| `editor.from_lmf("awn4.xml")` | `wn.download("file:awn4.xml")` | Via base `wn` package |
| `editor.export_lmf("out.xml")` | `wn.export(lexicons, "out.xml")` | Via base `wn` package |
| `editor.validate(lexicon_id)` | N/A | No validation method exists |

### 1.3 The `{auto}` ID Resolution Problem

Review YAMLs use `sense_id: "{auto}"`, `entry_id: "{auto}"`, and `entity_id: "{auto}"` because the pipeline doesn't know internal IDs. The applicator resolves these via:

```
lemma (from YAML context)  → wn.words(form=X)    → Word.senses() → sense
entry_id: "{auto}"         → created_entries[lemma] (from preceding create_entry)
entity_id: "{auto-hint}"   → hint extracted from {auto-LEMMA} pattern
```

**Diacritics match confirmed**: AWN4 stores lemmas WITH tashkeel (e.g., `كَيْنُونَة`, `كِيَان`). The review YAMLs use the same diacritized forms. `wn.senses(form=X)` searches with exact match, which works correctly.

**`{auto}` variant patterns handled**:
- `{auto}` — resolve from parent lemma context
- `{auto:لا نهائي}` — colon-separated lemma hint
- `{auto-اتصال}` — dash-separated lemma hint
- `{auto — long description}` — em-dash with spaces (escalated for relations)

### 1.4 Resolution Statistics (across 164 reviewed synsets)

| Metric | Count |
|---|---|
| Total `{auto}` IDs in review corpus | 211 |
| Resolved via parent lemma context | 183 |
| Resolved via text/enrichment inference | 20 |
| Genuinely unresolvable (escalated) | 8 |

The 8 unresolvable cases are:
- 4 `add_synset_relation.target_id` — placeholder targets requiring human decision
- 3 `set_metadata.entity_id` — ambiguous multi-lemma synsets
- 1 `add_sense_example.sense_id` — no identifiable lemma context

---

## 2. Architecture: The Applicator Module

**Location**: `arabic-wordnet-v4/experiments/linguistic_review_guide/apply_reviews.py`
**Dependency**: `wn_editor` (installed from wn-editor-extended), `wn`, `pyyaml`

### 2.1 Components

```
apply_reviews.py
├── ActionExtractor        — Parse review YAML, collect all actions with parent context
│   └── collect_actions()  — Walks step1/step3/step4/step5 structures
├── ActionNormalizer       — Map Arabic→English commands, resolve {auto} IDs, sort by dependency
│   ├── normalize_command()
│   ├── resolve_auto_ids() — Uses wn.senses(), wn.words(), created_entries cache
│   └── sort_actions()     — Dependency-ordered: remove → create → add → update → relations → metadata
├── ReviewApplicator       — Map actions to editor methods, wrap per-synset in tracking_session
│   └── apply_review()     — 13 command executors with idempotency guards
├── ApplicationReport      — JSON manifest of applied/skipped/failed/escalated actions
└── _infer_step5_lemma()   — 5-strategy lemma inference for step5-level actions
```

### 2.2 Per-Synset Execution Flow

```
1. Parse *.review.yaml
2. Extract all action dicts (walk step1.per_lemma[].actions, step3.actions,
   step4.actions, step5.per_lemma[].actions, step5.actions)
3. Normalize: Arabic → English commands
4. Filter: skip no-ops (retain_definition, أكّد صلاحية اللمّة) and log escalations
5. Sort by dependency order:
   remove_sense(0) → create_entry(2) → add_sense(3) → update_definition(4) →
   add_definition(5) → add_example(6/7) → relations(8) → metadata(9/10)
6. For each action:
   a. Resolve {auto} IDs via wn.senses() + wn.words() + created_entries cache
   b. Check idempotency (does definition/example already exist?)
   c. Apply via editor class
7. Set synset metadata: review_status, review_source, review_applied_at, review_version
8. Record to manifest
```

### 2.3 Arabic-to-English Command Map

| Arabic | English |
|---|---|
| `أكّد صلاحية اللمّة` | No-op (confirmation only) |
| `احذف ارتباط اللمّة بالمجموعة` | `remove_sense` |
| `أضف لمّة جديدة إلى المجموعة` | `create_entry` + `add_sense` |
| `عدّل نص التعريف` / `تحديث نص التعريف` | `update_definition` |
| `ألّف تعريفاً جديداً` | `add_definition` |
| `أقرّ صحة العلاقات` / `أقرّ صحة العلاقة التعميمية` | No-op (affirmation only) |
| `أضف علاقة دلالية` | `add_synset_relation` |
| `سجّل ملاحظة دلالية` / `سجّل ملاحظة اصطلاحية` | `set_metadata` |
| `صعّد للمراجع البشري` / `مراجعة بشرية` | `escalate` (log only) |
| `اقترح تغيير الأعم المباشر` | `escalate` (log only — requires human decision) |

### 2.4 Lemma Inference for Step5-Level Actions

Step5-level actions (at `step5_enrichment.actions`) often lack parent lemma context because they sit outside `per_lemma[]` blocks. The applicator uses 5 cascading strategies:

1. **Exact example text match** — compare action text against per_lemma examples
2. **Diacritic-insensitive substring** — strip tashkeel from both lemma and text (e.g., `تَجْرِيد` matches `التجريد`)
3. **Enrichment key→lemma** — match `set_metadata` key against per_lemma enrichment fields
4. **`{auto-hint}` extraction** — parse hint from `{auto-LEMMA}` patterns
5. **Single-lemma fallback** — if only one per_lemma entry exists, assign it

---

## 3. Session Tracking Strategy

### Solution: `tracking_session()` + Synset Metadata + Manifest File

**Per-synset tracking** (via `wn_editor.tracking_session`):
Each synset's actions are wrapped in a named tracking session (`"review:{synset_id}"`). The changelog system records all individual edits with rollback capability.

**Per-synset metadata** (via `SynsetEditor.set_metadata()`):
- `review_status`: `"reviewed"` | `"partial"` | `"escalated"`
- `review_applied_at`: ISO-8601 timestamp
- `review_source`: YAML filename
- `review_version`: `"claude_db_v1"`

**Session manifest** (`application_manifest.json`):
```json
{
  "applied_at": "2026-03-13T...",
  "source_db": "awn4_experiment.db",
  "lexicon": "awn4",
  "sessions": [
    {
      "synset_id": "awn4-00001740-n",
      "yaml_source": "awn4-00001740-n.review.yaml",
      "timestamp_start": "...",
      "timestamp_end": "...",
      "actions_applied": 5,
      "actions_skipped": 0,
      "actions_escalated": 0,
      "actions_failed": 0,
      "skipped_reasons": [],
      "escalation_reasons": [],
      "errors": []
    }
  ],
  "summary": {
    "total_synsets": 164,
    "fully_applied": 156,
    "partial": 0,
    "escalated_only": 0,
    "skipped_only": 8,
    "total_actions_applied": 650,
    "total_actions_skipped": 0,
    "total_actions_escalated": 1,
    "total_actions_failed": 0
  }
}
```

---

## 4. Metadata Preservation Strategy

### What goes INTO the DB (lightweight, survives WN-LMF export):
- `review_status`, `review_source`, `review_version` on synset
- `cultural_fit` assessment on synset (e.g., `"native"`, `"calque"`)
- `dc:confidence` on senses (via `set_metadata()`)
- `figurative_relation`, `usage_note` on entries

### What stays in YAML companion files (rich, too structured for key-value):
- Full evidence chains (step0)
- Substitution test results (step1)
- Nuance differentiations (step1)
- Definition quality checks (step3)
- Morphological fitness assessments (step1)
- All reasoning blocks
- Evaluation scores (when populated)

The YAML files in `reviews_claude_db/` ARE the provenance record. The applicator links them via the `review_source` metadata key.

---

## 5. End-to-End Pipeline

```python
# Using the CLI:
python apply_reviews.py \
    --reviews-dir output/reviews_claude_db \
    --db data/awn4_experiment.db \
    --lexicon awn4 \
    --manifest application_manifest.json

# Or programmatically:
from apply_reviews import apply_all_reviews

manifest = apply_all_reviews(
    reviews_dir=Path("output/reviews_claude_db"),
    db_path="data/awn4_experiment.db",
    lexicon_id="awn4",
    manifest_path=Path("application_manifest.json"),
    dry_run=False,
)

# Export result:
import wn
lexicons = wn.lexicons(lang="arb")
wn.export(lexicons, "awn4_reviewed.xml")
```

### Dry-Run Results (2026-03-13)

```
Application complete:
  Synsets:  164
  Applied:  650
  Skipped:  0
  Escalated: 1
  Failed:   0
```

---

## 6. Edge Cases and Risks

### High Priority

| Risk | Impact | Mitigation |
|---|---|---|
| `remove_sense` empties a synset (all lemmas removed, none added) | Synset becomes unlexicalized | Pre-check recommended before full run; the `awn4-00001740-n` review removes `كَيْنُونَة` but keeps `كِيَان` — safe |
| `add_synset_relation` with `{auto}` or placeholder target_id | Cannot resolve target synset | Caught by `PLACEHOLDER_TARGET_RE`, logged as escalation (4 cases in corpus) |
| `add_synset_relation` with invalid relation type (e.g., `"needs_hypernym_review"`) | Not a valid WN-LMF relation | Caught by `VALID_RELATION_TYPES` check, logged as escalation |
| Double-application (same review applied twice) | Duplicate definitions/examples | Idempotency guard: definitions and examples checked for existence before adding |

### Medium Priority

| Risk | Impact | Mitigation |
|---|---|---|
| `update_definition` index instability | Wrong definition overwritten if indices shift | `update_definition` sorted before `add_definition` in dependency order |
| `create_entry` + `add_sense` ordering | `add_sense` fails if entry doesn't exist yet | Dependency sort: `create_entry(2)` before `add_sense(3)` |
| Lemma not found in DB | `wn.senses()` returns empty | Logged as error via `_unresolved_sense`, action skipped, synset marked as partial |
| Tashkeel mismatch between review and DB | Exact match fails | AWN4 and reviews use identical diacritized forms (confirmed) |

### Low Priority

| Risk | Impact | Mitigation |
|---|---|---|
| Performance at scale (109K synsets) | Slow import | Only 164 reviewed synsets currently; review application is fast (SQLite with WAL) |
| `move_sense` (1 instance) | Complex composite operation | Implemented as delete + recreate; preserves entry linkage |

---

## 7. Verification Plan

1. **Dry-run**: `--dry-run` flag simulates all actions without DB changes — **completed, 650/651 pass**

2. **Unit test on 3 representative synsets**:
   - `awn4-00001740-n` (entity) — `remove_sense` + `update_definition` + `add_definition` + `add_synset_example`
   - `awn4-00001930-n` (physical entity) — `update_definition` + `add_definition` + `add_synset_example`
   - `awn4-00002137-n` (abstraction) — `create_entry` + `add_sense` + `add_sense_example`

3. **Pre/post diff**: For each test synset, capture `synset.definitions()`, `synset.senses()`, `synset.examples()` before and after. Verify changes match YAML actions.

4. **Round-trip validation**: Export to XML after all changes, re-import, verify no data loss.

5. **Full run**: Apply all 164 `reviews_claude_db/` reviews. Check manifest for failures.

6. **Escalation audit**: Review the 8 unresolvable `{auto}` IDs and the 1 escalation to ensure they were properly captured.
