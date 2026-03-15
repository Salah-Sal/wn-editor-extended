# Feasibility Report V2: Applying Linguistic Review Actions via v1.0.0 WordnetEditor

## Context

The v1 report (`REVIEW_APPLICATION_FEASIBILITY.md`) was written against the **legacy** `wn_editor` API — per-entity editor classes (`SynsetEditor`, `SenseEditor`, `EntryEditor`). The `apply_reviews.py` bridging module uses that legacy pattern: `SynsetEditor(synset).mod_definition(text, indx=N)`, `wn.words(form=X, lexicon=id)`, and `tracking_session()`.

The repository has since been **rewritten to v1.0.0** with a single `WordnetEditor` facade (`src/wordnet_editor/editor.py`) exposing **36 mutation methods** via one entry point. This report evaluates whether the v1.0.0 API can serve as the downstream client for applying **687 production review YAML files** (169 in `reviews_claude_db` + 518 in `reviews_gemini_db`).

**Key numbers:**
- AWN4: 109,901 synsets in `awn4.xml` (69 MB WN-LMF 1.4)
- Reviewed: 687 synsets across two directories
- Command vocabulary: 14 English commands + 14+ Arabic commands
- v1.0.0 API: 36 mutation methods, 22 validation rules, nestable batch transactions

---

## Section 1: Feasibility Verdict

### YES — every action maps to v1.0.0 API, with significant improvements

The v1.0.0 `WordnetEditor` covers 100% of the command vocabulary found in the 687 production review files. Several operations that were workarounds or composite hacks in the legacy API are now native, atomic operations.

### Summary of Improvements Over Legacy

| Capability | Legacy (`wn_editor`) | v1.0.0 (`WordnetEditor`) |
|---|---|---|
| **`move_sense`** | Composite: `SenseEditor.delete()` + recreate | Native atomic: `editor.move_sense(sense_id, target_synset_id)` |
| **`set_confidence`** | Workaround: `.set_metadata({"dc:confidence": score})` | Dedicated: `editor.set_confidence(entity_type, entity_id, score)` |
| **Batch/rollback** | Thread-local `tracking_session(name, desc)` | Nestable `editor.batch()` context manager with `BEGIN`/`COMMIT`/`ROLLBACK` |
| **Entity lookup** | Reach into `wn.words()` / `wn.senses()` + manual filter | Native `editor.find_entries(lemma=X)` / `editor.find_senses(entry_id=X)` |
| **Relation inverses** | Manual (hardcoded `RelationType` IntEnum) | Automatic (`auto_inverse=True` default), 93 inverse pairs |
| **Validation** | Not available | `editor.validate()` — 22 rules (VAL-GEN, VAL-ENT, VAL-SYN, VAL-REL, VAL-TAX, VAL-EDT) |
| **Split synset** | Not available as single operation | `editor.split_synset(synset_id, sense_groups)` |
| **Merge synsets** | Not available | `editor.merge_synsets(source_id, target_id)` — atomic with dedup |
| **Update sentinel** | N/A (all fields always sent) | `_UNSET` sentinel — only changed fields are written |
| **Edit history** | Basic tracking session log | Field-level `EditRecord` with old/new values |
| **LMF import/export** | Via base `wn` package | `editor.import_lmf()` / `editor.export_lmf()` (integrated) |

---

## Section 2: Command Coverage Matrix

### 2.1 English Commands (14 found in production reviews)

| Review Command | v1.0.0 Method | Match Quality | Notes |
|---|---|---|---|
| `create_entry` | `editor.create_entry(lexicon_id, lemma, pos)` | **Exact** | Auto-generates `{lex}-{lemma}-{pos}` ID |
| `add_sense` | `editor.add_sense(entry_id, synset_id)` | **Exact** | Auto-generates sense ID, handles unlexicalized→lexicalized |
| `remove_sense` | `editor.remove_sense(sense_id)` | **Exact** | Cascade: removes relations, examples, counts; handles unlexicalization |
| `move_sense` | `editor.move_sense(sense_id, target_synset_id)` | **Improved** | Was composite delete+recreate, now atomic |
| `update_definition` | `editor.update_definition(synset_id, definition_index, text)` | **Exact** | Zero-based index addressing |
| `add_definition` | `editor.add_definition(synset_id, text)` | **Exact** | Appends to definition list |
| `add_synset_example` | `editor.add_synset_example(synset_id, text)` | **Exact** | |
| `add_sense_example` | `editor.add_sense_example(sense_id, text)` | **Exact** | |
| `add_synset_relation` | `editor.add_synset_relation(source_id, relation_type, target_id)` | **Improved** | Auto-inverse by default |
| `remove_synset_relation` | `editor.remove_synset_relation(source_id, relation_type, target_id)` | **Improved** | Auto-inverse removal by default |
| `set_metadata` | `editor.set_metadata(entity_type, entity_id, key, value)` | **Exact** | Accepts: `"lexicon"`, `"synset"`, `"entry"`, `"sense"` |
| `set_confidence` | `editor.set_confidence(entity_type, entity_id, score)` | **Improved** | Was metadata workaround, now dedicated method |
| `escalate` | N/A (log-only) | **Skip** | Not a DB edit — record in manifest |
| `retain_definition` | N/A (no-op) | **Skip** | Affirmation, no mutation |

### 2.2 Arabic→English Command Normalization Map

These Arabic commands appear primarily in `reviews_gemini_db`. Each must be normalized to its English equivalent before dispatch.

| Arabic Command | English Equivalent | v1.0.0 Method |
|---|---|---|
| `أكّد صلاحية اللمّة` | `_noop` (confirm) | `editor.set_confidence("sense", sense_id, 1.0)` |
| `سجّل ملاحظة دلالية` | `set_metadata` | `editor.set_metadata("sense", sense_id, "nuance", text)` |
| `احذف ارتباط اللمّة بالمجموعة` | `remove_sense` | `editor.remove_sense(sense_id)` |
| `أضف لمّة جديدة إلى المجموعة` | `create_entry` + `add_sense` | `editor.create_entry()` → `editor.add_sense()` |
| `أضف علاقة دلالية` | `add_synset_relation` | `editor.add_synset_relation(source, type, target)` |
| `أقرّ صحة العلاقات` | `_noop` | No-op — affirmation |
| `أقرّ صحة العلاقة التعميمية` | `_noop` | No-op — affirmation |
| `أقرّ صحة العلاقة` | `_noop` | No-op — affirmation |
| `عدّل نص التعريف` | `update_definition` | `editor.update_definition(synset_id, idx, text)` |
| `ألّف تعريفاً جديداً` | `add_definition` | `editor.add_definition(synset_id, text)` |
| `صعّد للمراجع البشري` | `escalate` | `editor.set_metadata("synset", id, "escalation", reason)` + `editor.set_confidence("synset", id, 0.0)` |
| `مراجعة بشرية` | `escalate` | Same as above |
| `اقبل التعبير المركب` | `set_metadata` | `editor.set_metadata("sense", id, "mwe", true)` |
| `اقترح تغيير الأعم المباشر` | `escalate` | Escalated — hypernym changes require human review |

### 2.3 Invalid/Placeholder Commands Requiring Special Handling

| Command Pattern | Disposition |
|---|---|
| `أشر إلى ضرورة فصل المجموعة` | Internal flag — not a DB command. Set `split_needed` metadata. |
| `أشر إلى ضرورة مراجعة التعريف` | Internal flag for step3 — no DB command. |
| `اقبل اللفظ المعرّب` | Map to `set_metadata("entry", id, "etymology", "loanword")` |
| `عيّن حقل إثراء` | Map to `set_metadata("sense", id, key, value)` per field |
| `حدّد الإطار التركيبي` | Map to `set_metadata("sense", id, "syntactic_frame", frame)` |

---

## Section 3: API Mapping Details

### 3.1 Method Signatures for Each English Command

#### `create_entry`
```python
editor.create_entry(
    lexicon_id: str,       # e.g. "awn4"
    lemma: str,            # e.g. "كَيْنُونَة"
    pos: str,              # e.g. "n"
    *,
    id: str | None = None, # auto-generates if None: "{lex}-{lemma}-{pos}"
    forms: list[str] | None = None,
    metadata: dict | None = None,
) -> EntryModel
```

#### `add_sense`
```python
editor.add_sense(
    entry_id: str,         # e.g. "awn4-كينونة-n"
    synset_id: str,        # e.g. "awn4-00001740-n"
    *,
    id: str | None = None, # auto-generates: "{entry}-{synset_local}-{rank:02d}"
    lexicalized: bool = True,
    adjposition: str | None = None,
    metadata: dict | None = None,
) -> SenseModel
```

#### `remove_sense`
```python
editor.remove_sense(sense_id: str) -> None
# Side effects:
#   - Removes all sense relations and their inverses
#   - Removes sense-synset relations
#   - Removes examples, counts, adjpositions (via CASCADE)
#   - If synset now has 0 senses → marks synset as unlexicalized
```

#### `move_sense`
```python
editor.move_sense(
    sense_id: str,
    target_synset_id: str,
) -> SenseModel
# Atomic operation:
#   - Moves sense to target synset
#   - Source synset becomes unlexicalized if emptied
#   - Target synset becomes lexicalized if it was unlexicalized
#   - Raises DuplicateEntityError if entry already has sense in target
```

#### `update_definition`
```python
editor.update_definition(
    synset_id: str,
    definition_index: int,  # zero-based
    text: str,
) -> None
# Raises IndexError if definition_index out of range
```

#### `add_definition`
```python
editor.add_definition(
    synset_id: str,
    text: str,
    *,
    language: str | None = None,
    source_sense: str | None = None,
    metadata: dict | None = None,
) -> None
```

#### `add_synset_example`
```python
editor.add_synset_example(
    synset_id: str,
    text: str,
    *,
    language: str | None = None,
    metadata: dict | None = None,
) -> None
```

#### `add_sense_example`
```python
editor.add_sense_example(
    sense_id: str,
    text: str,
    *,
    language: str | None = None,
    metadata: dict | None = None,
) -> None
```

#### `add_synset_relation`
```python
editor.add_synset_relation(
    source_id: str,
    relation_type: str,     # must be a valid SynsetRelationType value
    target_id: str,
    *,
    auto_inverse: bool = True,  # creates inverse automatically
    metadata: dict | None = None,
) -> None
# Silently ignores duplicate relations
# Validates: relation_type in SynsetRelationType enum (85 values)
# Rejects self-referential relations
```

#### `remove_synset_relation`
```python
editor.remove_synset_relation(
    source_id: str,
    relation_type: str,
    target_id: str,
    *,
    auto_inverse: bool = True,  # removes inverse automatically
) -> None
# No-op if relation doesn't exist
```

#### `set_metadata`
```python
editor.set_metadata(
    entity_type: str,  # "lexicon" | "synset" | "entry" | "sense"
    entity_id: str,
    key: str,
    value: str | float | None,  # None deletes the key
) -> None
```

#### `set_confidence`
```python
editor.set_confidence(
    entity_type: str,  # "lexicon" | "synset" | "entry" | "sense"
    entity_id: str,
    score: float,      # typically 0.0–1.0
) -> None
# Convenience wrapper: calls set_metadata(entity_type, entity_id, "confidenceScore", score)
```

### 3.2 Entity Lookup Strategy

The v1.0.0 API provides native finders that eliminate the need to reach into `wn._db` internals:

| Legacy Pattern | v1.0.0 Replacement |
|---|---|
| `wn.words(form=X, lexicon=id)` | `editor.find_entries(lexicon_id=X, lemma=Y)` |
| `wn.senses(form=X)` + manual synset filter | `editor.find_senses(entry_id=X, synset_id=Y)` |
| `wn.synsets(ili=X)` | `editor.find_synsets(ili=X)` |
| Direct SQL on `wn._db` | Not needed — all lookups via editor methods |

**Example: Resolving a sense from lemma + synset context**

```python
# Legacy
words = wn.words(form="كَيْنُونَة", lexicon="awn4")
for w in words:
    for s in w.senses():
        if s.synset().id() == synset_id:
            sense_id = s.id()

# v1.0.0
entries = editor.find_entries(lexicon_id="awn4", lemma="كَيْنُونَة")
if entries:
    senses = editor.find_senses(entry_id=entries[0].id, synset_id=synset_id)
    if senses:
        sense_id = senses[0].id
```

### 3.3 The `_UNSET` Sentinel

The v1.0.0 API uses a `_UNSET` sentinel to distinguish "not passed" from `None` in update methods:

```python
_UNSET: Any = type("_UNSET", (), {"__repr__": lambda self: "..."})()
```

This means `update_synset(synset_id, metadata=None)` **clears** the metadata, while `update_synset(synset_id)` (metadata not passed) leaves it unchanged. The review applicator should only pass fields that are explicitly being changed.

---

## Section 4: `{auto}` ID Resolution Strategy

### 4.1 How v1.0.0 Finders Simplify Resolution

The legacy applicator resolved `{auto}` IDs by reaching into `wn.words()` and `wn.senses()`. The v1.0.0 API makes this cleaner:

```python
def resolve_entry_id(editor, lexicon_id, lemma, pos):
    """Resolve {auto} entry_id from lemma + pos."""
    entries = editor.find_entries(lexicon_id=lexicon_id, lemma=lemma, pos=pos)
    if entries:
        return entries[0].id
    return None

def resolve_sense_id(editor, entry_id, synset_id):
    """Resolve {auto} sense_id from entry + synset."""
    senses = editor.find_senses(entry_id=entry_id, synset_id=synset_id)
    if senses:
        return senses[0].id
    return None
```

### 4.2 The 5 `{auto}` Variant Patterns

| Pattern | Example | Resolution Strategy |
|---|---|---|
| `{auto}` | `sense_id: "{auto}"` | Resolve from parent lemma context: `find_entries(lemma=X)` → `find_senses(entry_id=E, synset_id=S)` |
| `{auto:hint}` | `entity_id: "{auto:لا نهائي}"` | Extract hint after colon, use as lemma for lookup |
| `{auto-hint}` | `entry_id: "{auto-اتصال}"` | Extract hint after dash, use as lemma for lookup |
| `{auto — desc}` | `target_id: "{auto — synset for جزء}"` | Extract hint after em-dash; if unresolvable, escalate |
| `{synset_for_X}` | `target_id: "{synset_for_جزء}"` | Placeholder — resolve via `find_synsets(definition_contains=X)` or escalate |

### 4.3 ID Generation Patterns

The v1.0.0 API auto-generates predictable IDs when `id=None`:

| Entity | Pattern | Example |
|---|---|---|
| Entry | `{lex}-{normalized_lemma}-{pos}` | `awn4-كينونة-n` |
| Synset | `{lex}-{counter:08d}-{pos}` | `awn4-00001740-n` |
| Sense | `{entry_id}-{synset_local}-{rank:02d}` | `awn4-كينونة-n-00001740-n-01` |

For entries, the lemma is normalized: `lower()` → spaces to `_` → strip non-`[\w\-]`. Duplicate IDs get a `-N` suffix.

---

## Section 5: Batch/Transaction Strategy

### 5.1 `editor.batch()` Replaces `tracking_session()`

```python
# Legacy
with wn_editor.tracking_session("review", "Apply review actions"):
    synset_ed = SynsetEditor(synset)
    synset_ed.mod_definition(text, indx=0)
    # ... more operations ...

# v1.0.0
with editor.batch():
    editor.update_definition(synset_id, 0, text)
    editor.add_synset_example(synset_id, example_text)
    editor.set_metadata("synset", synset_id, "nuance", note)
    # All committed atomically, or all rolled back
```

### 5.2 Nesting Support

The v1.0.0 `batch()` supports nesting. Only the outermost batch issues `COMMIT`/`ROLLBACK`:

```python
with editor.batch():                    # depth 1 → BEGIN
    editor.update_definition(...)
    with editor.batch():                # depth 2 → no-op
        editor.add_synset_example(...)
        editor.set_metadata(...)
    # depth back to 1 — no commit yet
# depth 0 → COMMIT
```

### 5.3 Per-Synset Batching for Atomicity

The recommended pattern for the review applicator:

```python
for review_file in review_files:
    review = yaml.safe_load(review_file.read_text())
    synset_id = extract_synset_id(review)

    try:
        with editor.batch():
            for action in normalize_actions(review):
                dispatch(editor, action)
    except Exception as e:
        # Entire synset's changes rolled back
        report.record_failure(synset_id, str(e))
```

### 5.4 Error Handling

Within a batch, any exception triggers a rollback of all changes since the outermost `batch()`. This guarantees that a partially-applied review never corrupts the database — either all actions for a synset succeed, or none do.

---

## Section 6: Metadata Key Vocabulary

### 6.1 All `set_metadata` Keys Found in Production Reviews

| Key | Entity Type | Source | Example Value |
|---|---|---|---|
| `nuance` | `sense` | Step 1 nuance differentiation | `"يتميّز عن «سطّر» بشمول الدلالة"` |
| `root` | `entry` | Step 5 enrichment | `"ك-ت-ب"` |
| `etymology` | `entry` | Step 5 loanword detection | `"loanword"` |
| `syntactic_frame` | `sense` | Step 4/5 verb checks | `"متعدٍ بنفسه"` |
| `mwe` | `sense` | Step 1 MWE acceptance | `true` |
| `cultural_fit` | `synset` | Step 5 cultural adequacy | `"native"` / `"lexical_gap"` / `"omission"` / `"phraset"` |
| `escalation` | `synset` | Escalation to human reviewer | `"أدلة متضاربة — يحتاج حسماً بشرياً"` |
| `semantic_accuracy` | `synset` | Step 6 evaluation | `2` (0–3 scale) |
| `gloss_quality` | `synset` | Step 6 evaluation | `3` (0–3 scale) |
| `synonym_coherence` | `synset` | Step 6 evaluation | `2` (0–2 scale) |
| `completeness` | `synset` | Step 6 evaluation | `1` (0–2 scale) |
| `cultural_adequacy` | `synset` | Step 6 evaluation | `"direct"` / `"near_synonym"` / `"phraset"` / `"gap"` |
| `overall` | `synset` | Step 6 evaluation | `"good"` |
| `confidenceScore` | `synset`/`sense` | Via `set_confidence()` | `1.0` / `0.0` |
| `collocation` | `sense` | Step 5 collocation | `"كتب + رسالة"` |
| `adverb_note` | `sense` | Step 5 adverb acceptance | `"جار ومجرور يؤدي معنى الظرف"` |
| `usage_note` | `sense` | Step 5 temporal shift | `"المعنى تطوّر عبر العصور"` |
| `eloquence` | `sense` | Step 5 enrichment | `"neologism/loanword"` |

### 6.2 `entity_type` Normalization

The v1.0.0 `set_metadata` and `set_confidence` methods accept exactly these entity types:

```python
# From _resolve_entity_table():
"lexicon" → lexicons table
"synset"  → synsets table
"entry"   → entries table
"sense"   → senses table
```

**Issue found in review corpus**: Some `set_metadata` actions use `entity_type: "lemma"`. The v1.0.0 API does not accept `"lemma"` — it must be mapped to `"entry"`:

```python
def normalize_entity_type(entity_type: str) -> str:
    if entity_type == "lemma":
        return "entry"
    return entity_type
```

### 6.3 `cultural_fit` Assessment Values

The production reviews use four cultural fit assessment values:

| Value | Meaning | API Call |
|---|---|---|
| `"native"` | Concept has direct Arabic equivalent | `set_metadata("synset", id, "cultural_fit", "native")` |
| `"phraset"` | Gap filled by idiomatic expression | `set_metadata("synset", id, "cultural_fit", "phraset")` |
| `"lexical_gap"` | No single Arabic word exists | `set_metadata("synset", id, "cultural_fit", "lexical_gap")` |
| `"omission"` | Concept has no relevance in Arabic context | `set_metadata("synset", id, "cultural_fit", "omission")` |

---

## Section 7: Relation Type Validation

### 7.1 Valid Synset Relation Types

The v1.0.0 API validates relation types against the `SynsetRelationType` enum (85 values). The full set includes:

`agent`, `also`, `antonym`, `anto_converse`, `anto_gradable`, `anto_simple`, `attribute`, `augmentative`, `be_in_state`, `causes`, `classified_by`, `classifies`, `co_agent_instrument`, `co_agent_patient`, `co_agent_result`, `co_instrument_agent`, `co_instrument_patient`, `co_instrument_result`, `co_patient_agent`, `co_patient_instrument`, `co_result_agent`, `co_result_instrument`, `co_role`, `diminutive`, `direction`, `domain_region`, `domain_topic`, `entails`, `eq_synonym`, `exemplifies`, `feminine`, `has_augmentative`, `has_diminutive`, `has_domain_region`, `has_domain_topic`, `has_feminine`, `has_masculine`, `has_young`, `holo_location`, `holo_member`, `holo_part`, `holo_portion`, `holo_substance`, `holonym`, `hypernym`, `hyponym`, `in_manner`, `instance_hypernym`, `instance_hyponym`, `instrument`, `involved`, `involved_agent`, `involved_direction`, `involved_instrument`, `involved_location`, `involved_patient`, `involved_result`, `involved_source_direction`, `involved_target_direction`, `ir_synonym`, `is_caused_by`, `is_entailed_by`, `is_exemplified_by`, `is_subevent_of`, `location`, `manner_of`, `masculine`, `mero_location`, `mero_member`, `mero_part`, `mero_portion`, `mero_substance`, `meronym`, `other`, `patient`, `restricted_by`, `restricts`, `result`, `role`, `similar`, `source_direction`, `state_of`, `subevent`, `target_direction`, `young`

### 7.2 Invalid Relation Types Found in Review Corpus

The following non-standard relation types appear in some review YAMLs and need normalization:

| Invalid Type | Normalization | Rationale |
|---|---|---|
| `"is-a"` | → `"hypernym"` | English alias for hypernym |
| `"has_hypernym"` | → `"hypernym"` | Redundant prefix |
| `"near_antonym"` | → `"similar"` or escalate | Not a standard WN relation; `similar` is closest |
| `"needs_hypernym_review"` | → escalate | Placeholder, not a real relation |
| `"needs_closer_hypernym_review"` | → escalate | Placeholder, not a real relation |

**Normalization map for the applicator:**

```python
RELATION_NORMALIZATION = {
    "is-a": "hypernym",
    "has_hypernym": "hypernym",
    "near_antonym": "similar",  # or escalate for human review
}

RELATION_ESCALATION = {
    "needs_hypernym_review",
    "needs_closer_hypernym_review",
}
```

### 7.3 `auto_inverse` Behavior

The v1.0.0 `add_synset_relation` creates inverse relations automatically by default. The `SYNSET_RELATION_INVERSES` dict contains 93 mappings:

- **Asymmetric pairs** (46 pairs): `hypernym` ↔ `hyponym`, `causes` ↔ `is_caused_by`, `mero_part` ↔ `holo_part`, etc.
- **Symmetric relations** (9): `antonym`, `eq_synonym`, `similar`, `attribute`, `co_role`, `ir_synonym`, `anto_gradable`, `anto_simple`, `anto_converse`

When calling `add_synset_relation("A", "hypernym", "B")`, the API automatically creates `("B", "hyponym", "A")`. This eliminates the need for the applicator to manually manage inverse relations — a significant simplification over the legacy approach.

To opt out: `add_synset_relation(source, type, target, auto_inverse=False)`.

---

## Section 8: Post-Application Validation

### 8.1 Using `editor.validate()`

The v1.0.0 validation engine runs 22 rules. After applying a batch of reviews, run:

```python
results = editor.validate(lexicon_id="awn4")
errors = [r for r in results if r.severity == "ERROR"]
warnings = [r for r in results if r.severity == "WARNING"]
```

### 8.2 Applicable Validation Rules

| Rule ID | Severity | What It Checks | Relevance to Reviews |
|---|---|---|---|
| **VAL-GEN-001** | ERROR | Duplicate IDs (synset, entry, sense) | After `create_entry`/`add_sense` |
| **VAL-ENT-001** | WARNING | Entries with no senses | After `remove_sense` — detects orphaned entries |
| **VAL-ENT-002** | WARNING | Entry with multiple senses for same synset | After `add_sense` — detects redundant senses |
| **VAL-ENT-003** | WARNING | Multiple entries with same lemma referencing same synset | After `create_entry` + `add_sense` |
| **VAL-ENT-004** | ERROR | Sense references missing synset | Structural integrity |
| **VAL-SYN-001** | WARNING | Empty synsets (unlexicalized) | After `remove_sense` — expected for rejected synsets |
| **VAL-SYN-002** | WARNING | ILI used by multiple synsets | After `link_ili` |
| **VAL-SYN-003** | WARNING | Proposed ILI missing definition | After `propose_ili` |
| **VAL-SYN-004** | WARNING | Existing ILI has spurious proposed ILI entry | After `link_ili` — stale proposed ILI not cleaned up |
| **VAL-SYN-005** | WARNING | Blank definitions | After `update_definition` with empty text |
| **VAL-SYN-006** | WARNING | Blank examples | After `add_synset_example` with empty text |
| **VAL-SYN-007** | WARNING | Duplicate definitions across synsets | After `add_definition` |
| **VAL-SYN-008** | ERROR | Proposed ILI definition less than 20 characters | After `propose_ili` with short definition |
| **VAL-REL-001** | ERROR | Dangling relation targets | After `delete_synset` |
| **VAL-REL-002** | WARNING | Invalid relation type for entity pair | After `add_synset_relation` with bad type |
| **VAL-REL-003** | WARNING | Redundant relations (duplicate source+type+target) | After `add_synset_relation` |
| **VAL-REL-004** | WARNING | Missing inverse relations | Should not occur with `auto_inverse=True` |
| **VAL-REL-005** | ERROR | Self-loop relations | Prevented by API validation |
| **VAL-TAX-001** | WARNING | POS mismatch with hypernym | After `add_synset_relation("hypernym")` |
| **VAL-EDT-001** | ERROR | ID prefix doesn't match lexicon | After `create_entry`/`add_sense` with explicit IDs |
| **VAL-EDT-002** | WARNING | Synsets with no definitions | After `remove_definition` |
| **VAL-EDT-003** | WARNING | Sense with low confidence (<0.5) | After `set_confidence` — expected for escalated items |

### 8.3 Per-Synset Validation

For targeted validation after applying a single review:

```python
synset_results = editor.validate_synset(synset_id)
entry_results = editor.validate_entry(entry_id)
relation_results = editor.validate_relations(lexicon_id="awn4")
```

### 8.4 Pre/Post Diff Strategy

```python
# Before applying review
pre_defs = editor.get_definitions(synset_id)
pre_senses = editor.find_senses(synset_id=synset_id)
pre_rels = editor.get_synset_relations(synset_id)

# Apply review actions within batch
with editor.batch():
    for action in actions:
        dispatch(editor, action)

# After applying review
post_defs = editor.get_definitions(synset_id)
post_senses = editor.find_senses(synset_id=synset_id)
post_rels = editor.get_synset_relations(synset_id)

# Compute diff for audit log
diff = compute_diff(pre_defs, post_defs, pre_senses, post_senses, pre_rels, post_rels)
```

---

## Section 9: Edge Cases and Risks

### 9.1 Unlexicalized Synset Risk from `remove_sense`

When `remove_sense` is called and the synset has no remaining senses, the synset becomes unlexicalized (inserted into `unlexicalized_synsets`). This is correct behavior for rejected lemmas, but the applicator should:

1. Log a warning when a synset becomes unlexicalized
2. Check whether the review also adds new senses to the same synset (net effect may be neutral)
3. Run `VAL-SYN-001` post-application to inventory unlexicalized synsets

### 9.2 Definition Index Instability

Definitions are addressed by zero-based index. If a review contains both `remove_definition(synset_id, 0)` and `update_definition(synset_id, 1, text)`, the second operation's index is now wrong because the first operation shifted all subsequent definitions down.

**Mitigation**: Apply definition operations in reverse index order (highest index first), or resolve indexes at execution time rather than at extraction time.

### 9.3 Diacritics Matching

AWN4 stores lemmas with full tashkeel (e.g., `كَيْنُونَة`). The review YAMLs also use diacritized forms. The v1.0.0 `find_entries(lemma=X)` does exact matching on the `forms` table.

**Risk**: If the review YAML's diacritization differs slightly from the database form, the lookup will fail silently (returning an empty list).

**Mitigation**: The applicator should implement a diacritics-insensitive fallback:

```python
def find_entry_fuzzy(editor, lexicon_id, lemma, pos):
    # Try exact match first
    entries = editor.find_entries(lexicon_id=lexicon_id, lemma=lemma, pos=pos)
    if entries:
        return entries[0]

    # Fallback: strip tashkeel and try all entries with same pos
    bare = strip_tashkeel(lemma)
    all_entries = editor.find_entries(lexicon_id=lexicon_id, pos=pos)
    for e in all_entries:
        if strip_tashkeel(e.lemma) == bare:
            return e
    return None
```

### 9.4 Double-Application Idempotency

Running the same review twice may cause issues:

| Operation | Idempotent? | Risk |
|---|---|---|
| `add_definition` | **No** — creates duplicates | Duplicate definitions |
| `add_synset_example` | **No** — creates duplicates | Duplicate examples |
| `add_synset_relation` | **Yes** — silently ignores duplicates | Safe |
| `remove_sense` | **No** — raises `EntityNotFoundError` on second run | Applicator should catch |
| `set_metadata` | **Yes** — overwrites | Safe |
| `set_confidence` | **Yes** — overwrites | Safe |
| `create_entry` | **No** — may raise `DuplicateEntityError` | Applicator should check first |
| `update_definition` | **Yes** — overwrites | Safe |

**Mitigation**: The applicator should maintain a manifest of applied reviews. Before applying, check whether the synset has already been processed:

```python
if synset_id in manifest["applied"]:
    logger.warning(f"Skipping already-applied review: {synset_id}")
    continue
```

### 9.5 `create_entry` + `add_sense` Atomicity

The Arabic command `أضف لمّة جديدة إلى المجموعة` requires two API calls: `create_entry()` followed by `add_sense()`. If the entry already exists (from a previous review or pre-existing in AWN4), `create_entry()` will raise `DuplicateEntityError`.

**Mitigation**: Check for existing entry first:

```python
entries = editor.find_entries(lexicon_id=lex_id, lemma=lemma, pos=pos)
if entries:
    entry_id = entries[0].id
else:
    entry = editor.create_entry(lex_id, lemma, pos)
    entry_id = entry.id

editor.add_sense(entry_id, synset_id)
```

---

## Section 10: Execution Pipeline

### 10.1 CLI Usage Example

```bash
python apply_reviews_v2.py \
    --reviews-dir output/reviews_claude_db \
    --db data/awn4_experiment.db \
    --lexicon awn4 \
    --manifest manifest_claude.json \
    --dry-run
```

### 10.2 Programmatic Usage Example

```python
from pathlib import Path
from wordnet_editor import WordnetEditor

with WordnetEditor("data/awn4_experiment.db") as editor:
    reviews_dir = Path("output/reviews_claude_db")

    for yaml_file in sorted(reviews_dir.glob("*.yaml")):
        review = yaml.safe_load(yaml_file.read_text())
        synset_id = extract_synset_id(review)

        # Extract and normalize actions from all steps
        actions = extract_actions(review, synset_id)
        actions = normalize_commands(actions)       # Arabic → English
        actions = resolve_auto_ids(editor, actions) # {auto} → real IDs
        actions = sort_by_dependency(actions)        # deletions first

        try:
            with editor.batch():
                for action in actions:
                    dispatch(editor, action)

            # Post-application validation
            issues = editor.validate_synset(synset_id)
            manifest.record_success(synset_id, len(actions), issues)

        except Exception as e:
            manifest.record_failure(synset_id, str(e))

    # Full validation pass
    all_issues = editor.validate(lexicon_id="awn4")
    manifest.record_validation_summary(all_issues)
```

### 10.3 Dependency-Ordered Execution Phases

Actions within a single synset review must be applied in dependency order:

| Phase | Priority | Operations | Rationale |
|---|---|---|---|
| **Phase 1: Removals** | 0–1 | `remove_sense`, `remove_synset_relation`, `move_sense` | Clear space before creating |
| **Phase 2: Modifications** | 2–5 | `update_definition`, `update_lemma`, `update_entry`, `update_synset` | Modify existing entities |
| **Phase 3: Creations** | 6–9 | `create_entry`, `add_sense`, `add_definition`, `add_synset_example`, `add_sense_example` | Create new entities |
| **Phase 4: Relations** | 10 | `add_synset_relation`, `add_sense_relation` | Connect entities (targets must exist) |
| **Phase 5: Metadata** | 11–12 | `set_metadata`, `set_confidence` | Annotate (entities must exist) |
| **Phase 6: Escalation** | 13 | `escalate` | Log-only, no DB mutation |

```python
COMMAND_ORDER = {
    "remove_sense": 0,
    "remove_synset_relation": 1,
    "move_sense": 2,
    "update_definition": 3,
    "update_lemma": 4,
    "update_entry": 5,
    "update_synset": 5,
    "create_entry": 6,
    "add_sense": 7,
    "add_definition": 8,
    "add_synset_example": 9,
    "add_sense_example": 9,
    "add_synset_relation": 10,
    "add_sense_relation": 10,
    "set_metadata": 11,
    "set_confidence": 12,
    "escalate": 13,
}
```

---

## Appendix A: Structural Differences Between Review Directories

| Aspect | `reviews_claude_db` (169 files) | `reviews_gemini_db` (518 files) |
|---|---|---|
| **Command language** | English | Mix of Arabic + English |
| **Step structure** | step0 → step05 → step1 → step3 → step4 → step5 | Same structure |
| **`{auto}` IDs** | Common | Common |
| **step2** | Absent | Absent |
| **Decision strictness** | Conservative (more rejections) | Permissive (more confirmations) |
| **Commands generated** | Narrower: mostly `update_definition`, `add_definition`, `add_synset_example`, `remove_sense` | Broader: includes `create_entry`, `add_sense`, `add_synset_relation` |
| **Definition authoring** | Frequent — authors `terminological` + `linguistic` alternatives | Infrequent — often retains existing definition |
| **File headers** | 3-line comment with synset ID, gloss, date | No header |
| **Root actions** | step5 consolidated | step1 + step5 both emit actions |

## Appendix B: v1.0.0 API Quick Reference (36 Mutation Methods)

| # | Category | Method |
|---|---|---|
| 1 | Lexicon | `create_lexicon(id, label, language, email, license, version, ...)` |
| 2 | Lexicon | `update_lexicon(lexicon_id, *, label, email, license, url, ...)` |
| 3 | Lexicon | `delete_lexicon(lexicon_id)` |
| 4 | Synset | `create_synset(lexicon_id, pos, definition, *, id, ili, ...)` |
| 5 | Synset | `update_synset(synset_id, *, pos, metadata)` |
| 6 | Synset | `delete_synset(synset_id, cascade=False)` |
| 7 | Entry | `create_entry(lexicon_id, lemma, pos, *, id, forms, metadata)` |
| 8 | Entry | `update_entry(entry_id, *, pos, metadata)` |
| 9 | Entry | `delete_entry(entry_id, cascade=False)` |
| 10 | Entry | `update_lemma(entry_id, new_lemma)` |
| 11 | Form | `add_form(entry_id, written_form, *, id, script, tags)` |
| 12 | Form | `remove_form(entry_id, written_form)` |
| 13 | Sense | `add_sense(entry_id, synset_id, *, id, lexicalized, ...)` |
| 14 | Sense | `remove_sense(sense_id)` |
| 15 | Sense | `move_sense(sense_id, target_synset_id)` |
| 16 | Sense | `reorder_senses(entry_id, sense_id_order)` |
| 17 | Definition | `add_definition(synset_id, text, *, language, source_sense, ...)` |
| 18 | Definition | `update_definition(synset_id, definition_index, text)` |
| 19 | Definition | `remove_definition(synset_id, definition_index)` |
| 20 | Example | `add_synset_example(synset_id, text, *, language, metadata)` |
| 21 | Example | `remove_synset_example(synset_id, example_index)` |
| 22 | Example | `add_sense_example(sense_id, text, *, language, metadata)` |
| 23 | Example | `remove_sense_example(sense_id, example_index)` |
| 24 | Relation | `add_synset_relation(source_id, relation_type, target_id, *, auto_inverse, ...)` |
| 25 | Relation | `remove_synset_relation(source_id, relation_type, target_id, *, auto_inverse)` |
| 26 | Relation | `add_sense_relation(source_id, relation_type, target_id, *, auto_inverse, ...)` |
| 27 | Relation | `remove_sense_relation(source_id, relation_type, target_id, *, auto_inverse)` |
| 28 | Relation | `add_sense_synset_relation(source_sense_id, relation_type, target_synset_id, ...)` |
| 29 | Relation | `remove_sense_synset_relation(source_sense_id, relation_type, target_synset_id)` |
| 30 | ILI | `link_ili(synset_id, ili_id)` |
| 31 | ILI | `unlink_ili(synset_id)` |
| 32 | ILI | `propose_ili(synset_id, definition, *, metadata)` |
| 33 | Metadata | `set_metadata(entity_type, entity_id, key, value)` |
| 34 | Metadata | `set_confidence(entity_type, entity_id, score)` |
| 35 | Compound | `merge_synsets(source_id, target_id)` |
| 36 | Compound | `split_synset(synset_id, sense_groups)` |
