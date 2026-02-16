# Import/Export Pipeline Specification

**Library**: `wordnet-editor`
**Version**: 1.0
**Date**: 2026-02-16

This document defines the step-by-step data transformations for import and export operations.

---

## 6.1 — Import from WN-LMF XML

### Pipeline

```
WN-LMF XML → wn.lmf.load() → LexicalResource dict → editor DB
```

### Step-by-step

All steps execute within a single transaction.

**Step 1: Parse XML**
```python
resource: lmf.LexicalResource = wn.lmf.load(source)
```

**Step 2: Populate lookup tables**

For each lexicon in `resource["lexicons"]`:
1. Collect all unique relation type strings from synset relations and sense relations
2. `INSERT OR IGNORE INTO relation_types VALUES (null, ?)` for each type
3. Collect all unique lexfile names from synsets
4. `INSERT OR IGNORE INTO lexfiles VALUES (null, ?)` for each
5. Ensure `ili_statuses` has entries for "active", "presupposed", "deprecated"

**Step 3: Insert lexicon** (for each lexicon)
```sql
INSERT INTO lexicons VALUES (null, :specifier, :id, :label, :language,
    :email, :license, :version, :url, :citation, :logo, :metadata, 0)
```
Where `specifier = f"{id}:{version}"`.

Then insert dependencies:
```sql
INSERT INTO lexicon_dependencies VALUES (:dependent_rowid, :id, :version, :url, :provider_rowid)
```

Then insert extensions (if `LexiconExtension`):
```sql
INSERT INTO lexicon_extensions VALUES (:extension_rowid, :base_id, :base_version, :base_url, :base_rowid)
```

**Step 4: Insert synsets** (for each synset in lexicon)

For each `synset` in `lexicon.get("synsets", [])`:

1. Handle ILI:
   - If `ili` is a non-empty string and not `"in"`: `INSERT OR IGNORE INTO ilis` with status "presupposed"
   - If `ili == "in"`: defer to step 4c

2. Insert synset:
```sql
INSERT INTO synsets VALUES (null, :id, :lexicon_rowid,
    (SELECT rowid FROM ilis WHERE id = :ili),
    :pos,
    (SELECT rowid FROM lexfiles WHERE name = :lexfile),
    :metadata)
```

3. If `ili == "in"` and `ili_definition` exists:
```sql
INSERT INTO proposed_ilis VALUES (null, :synset_rowid, :definition, :metadata)
```

4. If `lexicalized == False`:
```sql
INSERT INTO unlexicalized_synsets VALUES (:synset_rowid)
```

**Step 5: Insert entries** (for each entry in lexicon)

For each `entry` in `lexicon.get("entries", [])`:

1. Insert entry:
```sql
INSERT INTO entries VALUES (null, :id, :lexicon_rowid, :pos, :metadata)
```

2. If entry has `index` field:
```sql
INSERT INTO entry_index VALUES (:entry_rowid, :index_value)
```

**Step 6: Insert forms** (for each entry)

1. Insert lemma (rank = 0):
```sql
INSERT INTO forms VALUES (null, null, :lexicon_rowid, :entry_rowid,
    :written_form, :normalized_form, :script, 0)
```
Where `normalized_form` is set only if `written_form.casefold() != written_form`.

2. Insert additional forms (rank = 1, 2, ...):
```sql
INSERT INTO forms VALUES (null, :form_id, :lexicon_rowid, :entry_rowid,
    :written_form, :normalized_form, :script, :rank)
```

3. For each form, insert pronunciations:
```sql
INSERT INTO pronunciations VALUES (:form_rowid, :lexicon_rowid,
    :value, :variety, :notation, :phonemic, :audio)
```

4. For each form, insert tags:
```sql
INSERT INTO tags VALUES (:form_rowid, :lexicon_rowid, :tag, :category)
```

**Step 7: Insert senses** (for each entry)

For each `sense` in `entry.get("senses", [])`:

1. Resolve `synset_rowid`:
```sql
SELECT rowid FROM synsets WHERE id = :synset_id AND lexicon_rowid = :lexicon_rowid
```
If not found in same lexicon, search across all lexicons.

2. Insert sense:
```sql
INSERT INTO senses VALUES (null, :id, :lexicon_rowid, :entry_rowid,
    :entry_rank, :synset_rowid, :synset_rank, :metadata)
```
Where `entry_rank` is the 1-based position of this sense in the entry.

3. If `lexicalized == False`:
```sql
INSERT INTO unlexicalized_senses VALUES (:sense_rowid)
```

4. If `adjposition` is set:
```sql
INSERT INTO adjpositions VALUES (:sense_rowid, :adjposition)
```

**Step 8: Insert sense counts**
```sql
INSERT INTO counts VALUES (null, :lexicon_rowid, :sense_rowid, :count_value, :metadata)
```

**Step 9: Insert syntactic behaviours**

For lexicons (LMF ≥1.1):
```sql
INSERT OR IGNORE INTO syntactic_behaviours VALUES (null, :id, :lexicon_rowid, :frame)
```

Then for each sense with `subcat` references:
```sql
INSERT INTO syntactic_behaviour_senses VALUES (:sb_rowid, :sense_rowid)
```

**Step 10: Insert synset relations**

For each synset, for each relation in `synset.get("relations", [])`:
```sql
INSERT INTO synset_relations VALUES (null, :lexicon_rowid, :source_rowid, :target_rowid,
    (SELECT rowid FROM relation_types WHERE type = :rel_type), :metadata)
```

Target rowid resolved via: `SELECT rowid FROM synsets WHERE id = :target_id`.

**Step 11: Insert sense relations**

For each sense, for each relation in `sense.get("relations", [])`:
- If target is a sense ID: insert into `sense_relations`
- If target is a synset ID: insert into `sense_synset_relations`

```sql
-- sense-to-sense
INSERT INTO sense_relations VALUES (null, :lexicon_rowid, :source_rowid, :target_rowid,
    (SELECT rowid FROM relation_types WHERE type = :rel_type), :metadata)

-- sense-to-synset
INSERT INTO sense_synset_relations VALUES (null, :lexicon_rowid, :source_rowid, :target_rowid,
    (SELECT rowid FROM relation_types WHERE type = :rel_type), :metadata)
```

**Step 12: Insert definitions and examples**

Synset definitions:
```sql
INSERT INTO definitions VALUES (null, :lexicon_rowid, :synset_rowid,
    :text, :language, :sense_rowid, :metadata)
```

Synset examples:
```sql
INSERT INTO synset_examples VALUES (null, :lexicon_rowid, :synset_rowid,
    :text, :language, :metadata)
```

Sense examples:
```sql
INSERT INTO sense_examples VALUES (null, :lexicon_rowid, :sense_rowid,
    :text, :language, :metadata)
```

**Step 13: Record edit history** (optional, controlled by `record_history` parameter)

For each entity inserted, record a CREATE entry:
```sql
INSERT INTO edit_history (entity_type, entity_id, operation, new_value)
VALUES (:type, :id, 'CREATE', :json_summary)
```

**Performance note**: For large WordNets (e.g., OEWN ~120K synsets), history recording during import can double the number of rows written. The `import_lmf()` and `import_from_wn()` methods accept a `record_history: bool = True` parameter. Set to `False` for bulk imports where import provenance is not needed.

### Foreign Key Resolution Order

The insertion order above is critical because of foreign key constraints:

```
ili_statuses → relation_types → lexfiles → ilis → lexicons
    → lexicon_dependencies → lexicon_extensions
    → synsets → entries → entry_index → forms → pronunciations → tags
    → senses → unlexicalized_senses → adjpositions → counts
    → syntactic_behaviours → syntactic_behaviour_senses
    → synset_relations → sense_relations → sense_synset_relations
    → definitions → synset_examples → sense_examples
    → proposed_ilis → unlexicalized_synsets
```

Note: `definitions.sense_rowid` references senses, so definitions must be inserted after senses.

---

## 6.2 — Import from `wn` Database

### Pipeline

```
wn DB → wn.export() → temp WN-LMF XML → XML import pipeline (6.1)
```

### Step-by-step

**Step 1: Export from `wn` to temp file**
```python
import tempfile
import wn

lexicons = wn.lexicons(lexicon=specifier)
with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
    wn.export(lexicons, tmp.name)
    temp_path = tmp.name
```

**Step 2: Import temp file via XML pipeline**
```python
self.import_lmf(temp_path)
```

**Step 3: Clean up**
```python
os.unlink(temp_path)
```

**Rationale for this approach vs. direct DB query**: Using `wn.export()` leverages `wn`'s own tested export logic, guaranteeing that all data (including extensions, metadata, syntactic behaviours) is captured correctly. Direct DB querying would require reimplementing `wn/_export.py`'s logic.

---

## 6.3 — Export to WN-LMF XML

### Pipeline

```
editor DB → query rows → LexicalResource TypedDict → wn.lmf.dump() → XML file
```

### Step-by-step

**Step 1: Select lexicons**

If `lexicon_ids` specified, query those. Otherwise, query all.

```sql
SELECT rowid, specifier, id, label, language, email, license, version,
       url, citation, logo, metadata FROM lexicons
WHERE id IN (:ids)  -- or no WHERE for all
```

**Step 2: Build LexicalResource dict**

For each lexicon:

```python
lex = lmf.Lexicon(
    id=row.id, label=row.label, language=row.language,
    email=row.email, license=row.license, version=row.version,
    url=row.url or "", citation=row.citation or "",
    logo=row.logo or "", meta=row.metadata,
    entries=[], synsets=[], requires=[], frames=[],
)
```

**Step 3: Query and build entries**

For each entry in lexicon:
1. Query entry row
2. Query forms (ordered by rank): rank=0 is lemma, rank>0 are forms
3. Query pronunciations for each form
4. Query tags for each form
5. Query senses for this entry
6. For each sense: query sense relations, sense examples, counts
7. Query syntactic behaviours
8. Construct `lmf.LexicalEntry` TypedDict

**Step 4: Query and build synsets**

For each synset in lexicon:
1. Query synset row
2. Resolve ILI (join with ilis table)
3. Query definitions
4. Query synset examples
5. Query synset relations
6. Query proposed ILI (if any)
7. Check unlexicalized status
8. Query synset members (sense IDs ordered by synset_rank)
9. Construct `lmf.Synset` TypedDict

**Step 5: Assemble resource**
```python
resource = lmf.LexicalResource(
    lmf_version="1.4",
    lexicons=[lex1, lex2, ...]
)
```

**Step 6: Write XML**
```python
wn.lmf.dump(resource, destination)
```

**Step 7: Validate output**
```python
resource = wn.lmf.load(destination)
for lex in resource["lexicons"]:
    report = wn.validate(lex, select=("E",))
    if any(check["items"] for check in report.values()):
        raise ExportError("Export validation failed", report)
```

---

## 6.4 — Commit to `wn` Database

### Pipeline

```
editor DB → export XML (6.3) → validate → wn.remove() → wn.add() → cleanup
```

### Step-by-step

**Step 1: Configure wn database path**
```python
if db_path is not None:
    original_path = wn.config.database_path
    wn.config.database_path = db_path
```

**Step 2: Export to temp file**
```python
with tempfile.NamedTemporaryFile(suffix=".xml", delete=False) as tmp:
    self.export_lmf(tmp.name, lexicon_ids=lexicon_ids)
    temp_path = tmp.name
```

This includes validation (Step 7 of 6.3). If export fails validation, `ExportError` is raised and the `wn` database is untouched. **Validation MUST pass before proceeding** — Step 3 is only reached if Step 2 succeeds without error.

**Step 3: Remove existing lexicons from wn** (if they exist)
```python
for lex_id in lexicon_ids or self._all_lexicon_ids():
    for lex in wn.lexicons(lexicon=lex_id):
        wn.remove(lex.specifier())
```

**Step 4: Add to wn**
```python
wn.add(temp_path)
```

**Step 5: Clean up**
```python
os.unlink(temp_path)
if db_path is not None:
    wn.config.database_path = original_path
```

### Failure handling

If `wn.add()` fails after `wn.remove()`, the lexicon data is lost from `wn`'s database. However:
- The editor database is unchanged (it's the source of truth)
- The temp XML file can be re-imported manually
- Step 2's validation makes this scenario extremely unlikely

---

## 6.5 — Round-Trip Fidelity

The following data MUST survive import → edit → export without loss:

| Data | Preserved | Notes |
|------|-----------|-------|
| Synset IDs | Yes | Stored as-is in `synsets.id` |
| Entry IDs | Yes | Stored as-is in `entries.id` |
| Sense IDs | Yes | Stored as-is in `senses.id` |
| Form IDs | Yes | Stored in `forms.id` |
| Synset definitions | Yes | Stored in `definitions` table |
| Synset examples | Yes | Stored in `synset_examples` table |
| Sense examples | Yes | Stored in `sense_examples` table |
| Synset relations | Yes | Stored in `synset_relations` with `relation_types` normalization |
| Sense relations | Yes | Stored in `sense_relations` |
| Sense-synset relations | Yes | Stored in `sense_synset_relations` |
| ILI mappings | Yes | Stored via `synsets.ili_rowid` → `ilis` |
| Proposed ILIs | Yes | Stored in `proposed_ilis` |
| Metadata (Dublin Core) | Yes | Stored as JSON in `metadata` columns |
| Confidence scores | Yes | Part of metadata JSON |
| Form ordering (rank) | Yes | Stored in `forms.rank` |
| Pronunciation data | Yes | Stored in `pronunciations` table |
| Tags | Yes | Stored in `tags` table |
| Syntactic behaviours | Yes | Stored in `syntactic_behaviours` + junction table |
| Adjective positions | Yes | Stored in `adjpositions` table |
| Sense counts | Yes | Stored in `counts` table |
| Lexicalized flags | Yes | Stored in `unlexicalized_synsets`/`unlexicalized_senses` |
| Sense ordering (n) | Yes | Stored as `entry_rank` in `senses` |
| Entry index | Yes | Stored in `entry_index` table |
| Lexicon dependencies | Yes | Stored in `lexicon_dependencies` |
| Lexicon extensions | Yes | Stored in `lexicon_extensions` |
| Lexfile names | Yes | Stored via `synsets.lexfile_rowid` → `lexfiles` |
| Synset members order | Yes | Derived from `senses.synset_rank` |

**Not preserved** (intentionally):
- XML formatting, whitespace, and comments
- DOCTYPE version (always exports as 1.4)
- Element ordering within XML (may differ from original but is semantically equivalent)
