# Current State Documentation (As-Is)

**Project:** wn-editor-extended v1.0.0
**Date:** 2026-03-15
**Source:** `src/wordnet_editor/db.py` lines 35-332 (DDL), `editor.py`, `importer.py`, `exporter.py`

---

## Table of Contents

1. [Entity-Relationship Diagram (ERD)](#1-entity-relationship-diagram-erd)
2. [Schema Data Dictionary](#2-schema-data-dictionary)
3. [Index Inventory](#3-index-inventory)
4. [Constraint Catalog](#4-constraint-catalog)
5. [Storage & Volume Profile](#5-storage--volume-profile)
6. [Access Pattern Profile](#6-access-pattern-profile)

---

## 1. Entity-Relationship Diagram (ERD)

### Mermaid Diagram

```mermaid
erDiagram
    meta {
        TEXT key UK "NOT NULL"
        TEXT value
    }

    relation_types {
        INTEGER rowid PK
        TEXT type UK "NOT NULL"
    }

    ili_statuses {
        INTEGER rowid PK
        TEXT status UK "NOT NULL"
    }

    lexfiles {
        INTEGER rowid PK
        TEXT name UK "NOT NULL"
    }

    ilis {
        INTEGER rowid PK
        TEXT id UK "NOT NULL"
        INTEGER status_rowid FK "NOT NULL"
        TEXT definition
        META metadata
    }

    proposed_ilis {
        INTEGER rowid PK
        INTEGER synset_rowid FK_UK
        TEXT definition
        META metadata
    }

    lexicons {
        INTEGER rowid PK
        TEXT specifier UK "NOT NULL"
        TEXT id "NOT NULL"
        TEXT label "NOT NULL"
        TEXT language "NOT NULL"
        TEXT email "NOT NULL"
        TEXT license "NOT NULL"
        TEXT version "NOT NULL"
        TEXT url
        TEXT citation
        TEXT logo
        META metadata
        BOOLEAN modified "NOT NULL DEFAULT 0"
    }

    lexicon_dependencies {
        INTEGER dependent_rowid FK "NOT NULL"
        TEXT provider_id "NOT NULL"
        TEXT provider_version "NOT NULL"
        TEXT provider_url
        INTEGER provider_rowid FK
    }

    lexicon_extensions {
        INTEGER extension_rowid FK "NOT NULL"
        TEXT base_id "NOT NULL"
        TEXT base_version "NOT NULL"
        TEXT base_url
        INTEGER base_rowid FK
    }

    entries {
        INTEGER rowid PK
        TEXT id "NOT NULL"
        INTEGER lexicon_rowid FK "NOT NULL"
        TEXT pos "NOT NULL"
        META metadata
    }

    entry_index {
        INTEGER entry_rowid FK_UK "NOT NULL"
        TEXT lemma "NOT NULL"
    }

    forms {
        INTEGER rowid PK
        TEXT id
        INTEGER lexicon_rowid FK "NOT NULL"
        INTEGER entry_rowid FK "NOT NULL"
        TEXT form "NOT NULL"
        TEXT normalized_form
        TEXT script
        INTEGER rank "DEFAULT 1"
    }

    pronunciations {
        INTEGER form_rowid FK "NOT NULL"
        INTEGER lexicon_rowid FK "NOT NULL"
        TEXT value
        TEXT variety
        TEXT notation
        BOOLEAN phonemic "NOT NULL DEFAULT 1"
        TEXT audio
    }

    tags {
        INTEGER form_rowid FK "NOT NULL"
        INTEGER lexicon_rowid FK "NOT NULL"
        TEXT tag
        TEXT category
    }

    synsets {
        INTEGER rowid PK
        TEXT id "NOT NULL"
        INTEGER lexicon_rowid FK "NOT NULL"
        INTEGER ili_rowid FK
        TEXT pos
        INTEGER lexfile_rowid FK
        META metadata
    }

    unlexicalized_synsets {
        INTEGER synset_rowid FK "NOT NULL"
    }

    synset_relations {
        INTEGER rowid PK
        INTEGER lexicon_rowid FK "NOT NULL"
        INTEGER source_rowid FK "NOT NULL"
        INTEGER target_rowid FK "NOT NULL"
        INTEGER type_rowid FK "NOT NULL"
        META metadata
    }

    definitions {
        INTEGER rowid PK
        INTEGER lexicon_rowid FK "NOT NULL"
        INTEGER synset_rowid FK "NOT NULL"
        TEXT definition
        TEXT language
        INTEGER sense_rowid FK
        META metadata
    }

    synset_examples {
        INTEGER rowid PK
        INTEGER lexicon_rowid FK "NOT NULL"
        INTEGER synset_rowid FK "NOT NULL"
        TEXT example
        TEXT language
        META metadata
    }

    senses {
        INTEGER rowid PK
        TEXT id "NOT NULL"
        INTEGER lexicon_rowid FK "NOT NULL"
        INTEGER entry_rowid FK "NOT NULL"
        INTEGER entry_rank "DEFAULT 1"
        INTEGER synset_rowid FK "NOT NULL"
        INTEGER synset_rank "DEFAULT 1"
        META metadata
    }

    unlexicalized_senses {
        INTEGER sense_rowid FK "NOT NULL"
    }

    sense_relations {
        INTEGER rowid PK
        INTEGER lexicon_rowid FK "NOT NULL"
        INTEGER source_rowid FK "NOT NULL"
        INTEGER target_rowid FK "NOT NULL"
        INTEGER type_rowid FK "NOT NULL"
        META metadata
    }

    sense_synset_relations {
        INTEGER rowid PK
        INTEGER lexicon_rowid FK "NOT NULL"
        INTEGER source_rowid FK "NOT NULL"
        INTEGER target_rowid FK "NOT NULL"
        INTEGER type_rowid FK "NOT NULL"
        META metadata
    }

    adjpositions {
        INTEGER sense_rowid FK "NOT NULL"
        TEXT adjposition "NOT NULL"
    }

    sense_examples {
        INTEGER rowid PK
        INTEGER lexicon_rowid FK "NOT NULL"
        INTEGER sense_rowid FK "NOT NULL"
        TEXT example
        TEXT language
        META metadata
    }

    counts {
        INTEGER rowid PK
        INTEGER lexicon_rowid FK "NOT NULL"
        INTEGER sense_rowid FK "NOT NULL"
        INTEGER count "NOT NULL"
        META metadata
    }

    syntactic_behaviours {
        INTEGER rowid PK
        TEXT id
        INTEGER lexicon_rowid FK "NOT NULL"
        TEXT frame "NOT NULL"
    }

    syntactic_behaviour_senses {
        INTEGER syntactic_behaviour_rowid FK "NOT NULL"
        INTEGER sense_rowid FK "NOT NULL"
    }

    edit_history {
        INTEGER rowid PK
        TEXT entity_type "NOT NULL"
        TEXT entity_id "NOT NULL"
        TEXT field_name
        TEXT operation "NOT NULL"
        TEXT old_value
        TEXT new_value
        TEXT timestamp "NOT NULL"
    }

    %% Relationships
    ili_statuses ||--o{ ilis : "status_rowid"
    ilis ||--o| synsets : "ili_rowid"
    lexfiles ||--o| synsets : "lexfile_rowid"

    synsets ||--o| proposed_ilis : "synset_rowid"

    lexicons ||--o{ lexicon_dependencies : "dependent_rowid"
    lexicons ||--o| lexicon_dependencies : "provider_rowid"
    lexicons ||--o{ lexicon_extensions : "extension_rowid"
    lexicons ||--o| lexicon_extensions : "base_rowid"

    lexicons ||--o{ entries : "lexicon_rowid"
    lexicons ||--o{ synsets : "lexicon_rowid"
    lexicons ||--o{ forms : "lexicon_rowid"
    lexicons ||--o{ senses : "lexicon_rowid"

    entries ||--|| entry_index : "entry_rowid"
    entries ||--o{ forms : "entry_rowid"
    entries ||--o{ senses : "entry_rowid"

    forms ||--o{ pronunciations : "form_rowid"
    forms ||--o{ tags : "form_rowid"

    synsets ||--o| unlexicalized_synsets : "synset_rowid"
    synsets ||--o{ definitions : "synset_rowid"
    synsets ||--o{ synset_examples : "synset_rowid"

    senses ||--o{ synset_relations : "source_rowid"
    synsets ||--o{ synset_relations : "source_rowid"
    synsets ||--o{ synset_relations : "target_rowid"

    senses ||--o| unlexicalized_senses : "sense_rowid"
    senses ||--o{ sense_relations : "source_rowid"
    senses ||--o{ sense_relations : "target_rowid"
    senses ||--o{ sense_synset_relations : "source_rowid"
    synsets ||--o{ sense_synset_relations : "target_rowid"
    senses ||--o{ adjpositions : "sense_rowid"
    senses ||--o{ sense_examples : "sense_rowid"
    senses ||--o{ counts : "sense_rowid"
    senses ||--o{ synsets : "synset_rowid"

    relation_types ||--o{ synset_relations : "type_rowid"
    relation_types ||--o{ sense_relations : "type_rowid"
    relation_types ||--o{ sense_synset_relations : "type_rowid"

    syntactic_behaviours ||--o{ syntactic_behaviour_senses : "syntactic_behaviour_rowid"
    senses ||--o{ syntactic_behaviour_senses : "sense_rowid"

    senses ||--o| definitions : "sense_rowid"
```

### Cascade Chain Summary

Deleting a **lexicon** cascades through the entire object graph:

```
lexicons (DELETE)
├── entries (CASCADE)
│   ├── entry_index (CASCADE)
│   ├── forms (CASCADE)
│   │   ├── pronunciations (CASCADE)
│   │   └── tags (CASCADE)
│   └── senses (CASCADE)
│       ├── sense_relations (CASCADE, both source + target)
│       ├── sense_synset_relations (CASCADE, source side)
│       ├── sense_examples (CASCADE)
│       ├── counts (CASCADE)
│       ├── adjpositions (CASCADE)
│       ├── unlexicalized_senses (CASCADE)
│       ├── syntactic_behaviour_senses (CASCADE)
│       └── definitions.sense_rowid (SET NULL)
├── synsets (CASCADE)
│   ├── synset_relations (CASCADE, both source + target)
│   ├── definitions (CASCADE)
│   ├── synset_examples (CASCADE)
│   ├── unlexicalized_synsets (CASCADE)
│   └── proposed_ilis (CASCADE)
├── lexicon_dependencies (CASCADE on dependent_rowid)
├── lexicon_extensions (CASCADE on extension_rowid)
├── syntactic_behaviours (CASCADE)
│   └── syntactic_behaviour_senses (CASCADE)
└── [edit_history is NOT cascaded — audit trail survives deletion]
```

---

## 2. Schema Data Dictionary

### 2.1 `meta`
Key-value store for database-level metadata.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `key` | TEXT | NOT NULL | — | UNIQUE(key) | Metadata key name |
| `value` | TEXT | YES | — | — | Metadata value |

**Seeded rows:** `schema_version = "1.0"`, `created_at = <ISO 8601 timestamp>`

### 2.2 `relation_types`
Normalizes relation type strings (e.g., "hypernym") to integer rowids.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `type` | TEXT | NOT NULL | — | UNIQUE | Relation type string |

**Populated on-demand** via `get_or_create_relation_type()`.

### 2.3 `ili_statuses`
Normalizes ILI status strings.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `status` | TEXT | NOT NULL | — | UNIQUE | Status string |

**Seeded at init:** `"active"`, `"presupposed"`, `"deprecated"`

### 2.4 `lexfiles`
Normalizes lexicographer file names.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `name` | TEXT | NOT NULL | — | UNIQUE | Lexfile name |

**Populated on-demand** via `get_or_create_lexfile()`.

### 2.5 `ilis`
Interlingual Index entries shared across languages.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `id` | TEXT | NOT NULL | — | UNIQUE | ILI identifier (e.g., `i12345`) |
| `status_rowid` | INTEGER | NOT NULL | — | FK → `ili_statuses(rowid)` | ILI status |
| `definition` | TEXT | YES | — | — | ILI definition text |
| `metadata` | META | YES | — | — | JSON metadata dict |

**FK behavior:** `status_rowid` → RESTRICT (default, no ON DELETE clause).

### 2.6 `proposed_ilis`
Proposed new ILI entries (synsets with `ili="in"`) awaiting approval.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `synset_rowid` | INTEGER | YES | — | FK → `synsets(rowid)` ON DELETE CASCADE, UNIQUE | Owning synset |
| `definition` | TEXT | YES | — | — | Proposed definition |
| `metadata` | META | YES | — | — | JSON metadata |

### 2.7 `lexicons`
Language-specific WordNet resource containers.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `specifier` | TEXT | NOT NULL | — | UNIQUE | Format: `"id:version"` |
| `id` | TEXT | NOT NULL | — | UNIQUE(id, version) | Lexicon identifier |
| `label` | TEXT | NOT NULL | — | — | Human-readable name |
| `language` | TEXT | NOT NULL | — | — | BCP 47 language tag |
| `email` | TEXT | NOT NULL | — | — | Maintainer email |
| `license` | TEXT | NOT NULL | — | — | License URL or identifier |
| `version` | TEXT | NOT NULL | — | UNIQUE(id, version) | Version string |
| `url` | TEXT | YES | — | — | Project URL |
| `citation` | TEXT | YES | — | — | Citation text |
| `logo` | TEXT | YES | — | — | Logo URL |
| `metadata` | META | YES | — | — | JSON metadata |
| `modified` | BOOLEAN | NOT NULL | 0 | CHECK(modified IN (0,1)) | Dirty flag for export |

### 2.8 `lexicon_dependencies`
Tracks `<Requires>` relationships between lexicons.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `dependent_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Dependent lexicon |
| `provider_id` | TEXT | NOT NULL | — | — | Required lexicon ID |
| `provider_version` | TEXT | NOT NULL | — | — | Required version |
| `provider_url` | TEXT | YES | — | — | Provider URL |
| `provider_rowid` | INTEGER | YES | — | FK → `lexicons(rowid)` ON DELETE SET NULL | Resolved provider |

**No explicit PK.** No UNIQUE constraint.

### 2.9 `lexicon_extensions`
Tracks `<Extends>` relationships.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `extension_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Extension lexicon |
| `base_id` | TEXT | NOT NULL | — | — | Base lexicon ID |
| `base_version` | TEXT | NOT NULL | — | — | Base version |
| `base_url` | TEXT | YES | — | — | Base URL |
| `base_rowid` | INTEGER | YES | — | FK → `lexicons(rowid)` **NO ON DELETE** (RESTRICT) | Resolved base |

**UNIQUE(extension_rowid, base_rowid)**

### 2.10 `entries`
Lexical entries (word + POS).

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `id` | TEXT | NOT NULL | — | UNIQUE(id, lexicon_rowid) | Entry identifier |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `pos` | TEXT | NOT NULL | — | — | Part of speech |
| `metadata` | META | YES | — | — | JSON metadata |

### 2.11 `entry_index`
Fast lemma lookup table (denormalized from `forms` rank 0).

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `entry_rowid` | INTEGER | NOT NULL | — | FK → `entries(rowid)` ON DELETE CASCADE, UNIQUE | Entry reference |
| `lemma` | TEXT | NOT NULL | — | — | Canonical lemma text |

### 2.12 `forms`
Written forms of an entry (rank 0 = lemma, rank >= 1 = variants).

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `id` | TEXT | YES | — | — | Optional form ID |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `entry_rowid` | INTEGER | NOT NULL | — | FK → `entries(rowid)` ON DELETE CASCADE | Owning entry |
| `form` | TEXT | NOT NULL | — | UNIQUE(entry_rowid, form, script) | Written representation |
| `normalized_form` | TEXT | YES | — | — | Casefolded form (NULL if already lowercase) |
| `script` | TEXT | YES | — | — | ISO 15924 script tag |
| `rank` | INTEGER | YES | 1 | — | 0 = lemma; >= 1 = variant |

### 2.13 `pronunciations`
Pronunciation data attached to a form.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `form_rowid` | INTEGER | NOT NULL | — | FK → `forms(rowid)` ON DELETE CASCADE | Owning form |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `value` | TEXT | YES | — | — | Pronunciation string |
| `variety` | TEXT | YES | — | — | Regional variety |
| `notation` | TEXT | YES | — | — | Notation system |
| `phonemic` | BOOLEAN | NOT NULL | 1 | CHECK(phonemic IN (0,1)) | Phonemic vs phonetic |
| `audio` | TEXT | YES | — | — | Audio file URL |

**No PK, no UNIQUE.** Multiple pronunciations per form allowed.

### 2.14 `tags`
Categorized tags for forms.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `form_rowid` | INTEGER | NOT NULL | — | FK → `forms(rowid)` ON DELETE CASCADE | Owning form |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `tag` | TEXT | YES | — | — | Tag value |
| `category` | TEXT | YES | — | — | Tag category |

**No PK, no UNIQUE.**

### 2.15 `synsets`
Synonym sets representing concepts.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `id` | TEXT | NOT NULL | — | UNIQUE(id, lexicon_rowid) | Synset identifier |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `ili_rowid` | INTEGER | YES | — | FK → `ilis(rowid)` **NO ON DELETE** (RESTRICT) | ILI link |
| `pos` | TEXT | YES | — | — | Part of speech |
| `lexfile_rowid` | INTEGER | YES | — | FK → `lexfiles(rowid)` **NO ON DELETE** (RESTRICT) | Lexicographer file |
| `metadata` | META | YES | — | — | JSON metadata |

### 2.16 `unlexicalized_synsets`
Marker table for synsets with no senses.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `synset_rowid` | INTEGER | NOT NULL | — | FK → `synsets(rowid)` ON DELETE CASCADE | Marked synset |

**No PK, no UNIQUE.** Single-column presence/absence table.

### 2.17 `synset_relations`
Directed typed relations between synsets.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `source_rowid` | INTEGER | NOT NULL | — | FK → `synsets(rowid)` ON DELETE CASCADE | Source synset |
| `target_rowid` | INTEGER | NOT NULL | — | FK → `synsets(rowid)` ON DELETE CASCADE | Target synset |
| `type_rowid` | INTEGER | NOT NULL | — | FK → `relation_types(rowid)` **NO ON DELETE** (RESTRICT) | Relation type |
| `metadata` | META | YES | — | — | JSON metadata |

**UNIQUE(source_rowid, target_rowid, type_rowid)**

### 2.18 `definitions`
Textual definitions for synsets.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `synset_rowid` | INTEGER | NOT NULL | — | FK → `synsets(rowid)` ON DELETE CASCADE | Owning synset |
| `definition` | TEXT | YES | — | — | Definition text |
| `language` | TEXT | YES | — | — | Language tag |
| `sense_rowid` | INTEGER | YES | — | FK → `senses(rowid)` ON DELETE SET NULL | Source sense attribution |
| `metadata` | META | YES | — | — | JSON metadata |

Multiple definitions per synset allowed (no UNIQUE).

### 2.19 `synset_examples`
Usage examples for synsets.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `synset_rowid` | INTEGER | NOT NULL | — | FK → `synsets(rowid)` ON DELETE CASCADE | Owning synset |
| `example` | TEXT | YES | — | — | Example text |
| `language` | TEXT | YES | — | — | Language tag |
| `metadata` | META | YES | — | — | JSON metadata |

### 2.20 `senses`
Links a lexical entry to a synset.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `id` | TEXT | NOT NULL | — | *(no UNIQUE constraint)* | Sense identifier |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `entry_rowid` | INTEGER | NOT NULL | — | FK → `entries(rowid)` ON DELETE CASCADE | Owning entry |
| `entry_rank` | INTEGER | YES | 1 | — | Ordering within entry |
| `synset_rowid` | INTEGER | NOT NULL | — | FK → `synsets(rowid)` ON DELETE CASCADE | Target synset |
| `synset_rank` | INTEGER | YES | 1 | — | Ordering within synset |
| `metadata` | META | YES | — | — | JSON metadata |

**AUDIT FLAG `[SPEC]` (D3):** Unlike `entries` (UNIQUE(id, lexicon_rowid)) and `synsets` (UNIQUE(id, lexicon_rowid)), the `senses` table has **no UNIQUE constraint on `(id, lexicon_rowid)`**. Uniqueness is enforced only at the application level via `get_sense_rowid()`. **This is a design-level omission:** `schema.md` SCHEMA-024 also omits this constraint, while SCHEMA-003 (entries) and SCHEMA-010 (synsets) include it. The implementation correctly follows the flawed spec.

### 2.21 `unlexicalized_senses`
Marker table for unlexicalized senses.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `sense_rowid` | INTEGER | NOT NULL | — | FK → `senses(rowid)` ON DELETE CASCADE | Marked sense |

### 2.22 `sense_relations`
Directed typed relations between senses.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `source_rowid` | INTEGER | NOT NULL | — | FK → `senses(rowid)` ON DELETE CASCADE | Source sense |
| `target_rowid` | INTEGER | NOT NULL | — | FK → `senses(rowid)` ON DELETE CASCADE | Target sense |
| `type_rowid` | INTEGER | NOT NULL | — | FK → `relation_types(rowid)` **NO ON DELETE** (RESTRICT) | Relation type |
| `metadata` | META | YES | — | — | JSON metadata |

**UNIQUE(source_rowid, target_rowid, type_rowid)**

### 2.23 `sense_synset_relations`
Directed typed relations from senses to synsets.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `source_rowid` | INTEGER | NOT NULL | — | FK → `senses(rowid)` ON DELETE CASCADE | Source sense |
| `target_rowid` | INTEGER | NOT NULL | — | FK → `synsets(rowid)` ON DELETE CASCADE | Target synset |
| `type_rowid` | INTEGER | NOT NULL | — | FK → `relation_types(rowid)` **NO ON DELETE** (RESTRICT) | Relation type |
| `metadata` | META | YES | — | — | JSON metadata |

**UNIQUE(source_rowid, target_rowid, type_rowid)**

### 2.24 `adjpositions`
Adjective syntactic positions for senses.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `sense_rowid` | INTEGER | NOT NULL | — | FK → `senses(rowid)` ON DELETE CASCADE | Owning sense |
| `adjposition` | TEXT | NOT NULL | — | — | Position value |

**No PK, no UNIQUE.**

### 2.25 `sense_examples`
Usage examples for senses.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `sense_rowid` | INTEGER | NOT NULL | — | FK → `senses(rowid)` ON DELETE CASCADE | Owning sense |
| `example` | TEXT | YES | — | — | Example text |
| `language` | TEXT | YES | — | — | Language tag |
| `metadata` | META | YES | — | — | JSON metadata |

### 2.26 `counts`
Frequency counts for senses.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `sense_rowid` | INTEGER | NOT NULL | — | FK → `senses(rowid)` ON DELETE CASCADE | Owning sense |
| `count` | INTEGER | NOT NULL | — | — | Frequency count |
| `metadata` | META | YES | — | — | JSON metadata |

### 2.27 `syntactic_behaviours`
Subcategorization frames for verbs.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `id` | TEXT | YES | — | UNIQUE(lexicon_rowid, id) | Frame ID |
| `lexicon_rowid` | INTEGER | NOT NULL | — | FK → `lexicons(rowid)` ON DELETE CASCADE | Owning lexicon |
| `frame` | TEXT | NOT NULL | — | UNIQUE(lexicon_rowid, frame) | Frame text |

### 2.28 `syntactic_behaviour_senses`
M:N junction between frames and senses.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `syntactic_behaviour_rowid` | INTEGER | NOT NULL | — | FK → `syntactic_behaviours(rowid)` ON DELETE CASCADE | Frame reference |
| `sense_rowid` | INTEGER | NOT NULL | — | FK → `senses(rowid)` ON DELETE CASCADE | Sense reference |

**No PK, no UNIQUE.**

### 2.29 `edit_history`
Field-level audit log of all mutations.

| Column | Type | Nullable | Default | Constraints | Purpose |
|--------|------|----------|---------|-------------|---------|
| `rowid` | INTEGER | NOT NULL | auto | PK | Internal ID |
| `entity_type` | TEXT | NOT NULL | — | CHECK(IN 9 values) | Entity category |
| `entity_id` | TEXT | NOT NULL | — | — | Entity identifier (no FK) |
| `field_name` | TEXT | YES | — | — | Changed field (NULL for CREATE/DELETE) |
| `operation` | TEXT | NOT NULL | — | CHECK(IN 'CREATE','UPDATE','DELETE') | Mutation type |
| `old_value` | TEXT | YES | — | — | JSON-encoded previous value |
| `new_value` | TEXT | YES | — | — | JSON-encoded new value |
| `timestamp` | TEXT | NOT NULL | `strftime('%Y-%m-%dT%H:%M:%f','now')` | — | UTC ISO 8601 with ms |

**No FK to any entity table** — `entity_id` is TEXT, allowing history to survive entity deletion.

### META Custom Type

The `META` column type is a custom SQLite type adapter registered globally (`db.py` lines 17-28):

```python
sqlite3.register_adapter(dict, _adapt_metadata)     # dict → json.dumps()
sqlite3.register_converter("META", _convert_metadata) # bytes → json.loads()
```

Activated by `detect_types=sqlite3.PARSE_DECLTYPES | sqlite3.PARSE_COLNAMES` in `connect()`.

**13 columns** use the META type: `ilis.metadata`, `proposed_ilis.metadata`, `lexicons.metadata`, `entries.metadata`, `synsets.metadata`, `synset_relations.metadata`, `definitions.metadata`, `synset_examples.metadata`, `senses.metadata`, `sense_relations.metadata`, `sense_synset_relations.metadata`, `sense_examples.metadata`, `counts.metadata`.

Note: `edit_history.old_value` and `edit_history.new_value` are declared as `TEXT`, not `META` — they store JSON manually via `json.dumps()` but are NOT auto-converted on read.

---

## 3. Index Inventory

### Explicit Indexes (41 total)

| # | Index Name | Table | Column(s) | Type | Serves |
|---|-----------|-------|-----------|------|--------|
| 1 | `relation_type_index` | `relation_types` | `(type)` | B-tree | `get_or_create_relation_type()` lookups |
| 2 | `ili_status_index` | `ili_statuses` | `(status)` | B-tree | Status string lookups at seed/import |
| 3 | `lexfile_index` | `lexfiles` | `(name)` | B-tree | `get_or_create_lexfile()` lookups |
| 4 | `ili_id_index` | `ilis` | `(id)` | B-tree | ILI ID lookups in `link_ili`, `get_ili` |
| 5 | `proposed_ili_synset_rowid_index` | `proposed_ilis` | `(synset_rowid)` | B-tree | Proposed ILI checks in `create_synset`, `merge_synsets` |
| 6 | `lexicon_specifier_index` | `lexicons` | `(specifier)` | B-tree | Primary lookup path for all `get_lexicon_*` calls |
| 7 | `lexicon_dependent_index` | `lexicon_dependencies` | `(dependent_rowid)` | B-tree | Dependency resolution during import |
| 8 | `lexicon_extension_index` | `lexicon_extensions` | `(extension_rowid)` | B-tree | Extension resolution during import |
| 9 | `entry_id_index` | `entries` | `(id)` | B-tree | Entry lookups by ID across all methods |
| 10 | `entry_index_entry_index` | `entry_index` | `(entry_rowid)` | B-tree | Lemma retrieval for entry models |
| 11 | `entry_index_lemma_index` | `entry_index` | `(lemma)` | B-tree | Reverse lookup: lemma → entry |
| 12 | `form_entry_index` | `forms` | `(entry_rowid)` | B-tree | All forms for an entry |
| 13 | `form_index` | `forms` | `(form)` | B-tree | `find_entries(lemma=...)` filter |
| 14 | `form_norm_index` | `forms` | `(normalized_form)` | B-tree | Case-insensitive searches |
| 15 | `pronunciation_form_index` | `pronunciations` | `(form_rowid)` | B-tree | Pronunciations for a form |
| 16 | `tag_form_index` | `tags` | `(form_rowid)` | B-tree | Tags for a form |
| 17 | `synset_id_index` | `synsets` | `(id)` | B-tree | Synset lookups by ID |
| 18 | `synset_ili_rowid_index` | `synsets` | `(ili_rowid)` | B-tree | ILI → synset resolution |
| 19 | `unlexicalized_synsets_index` | `unlexicalized_synsets` | `(synset_rowid)` | B-tree | Unlexicalized check |
| 20 | `synset_relation_source_index` | `synset_relations` | `(source_rowid)` | B-tree | Outgoing relations for a synset |
| 21 | `synset_relation_target_index` | `synset_relations` | `(target_rowid)` | B-tree | Incoming relations for a synset |
| 22 | `definition_rowid_index` | `definitions` | `(synset_rowid)` | B-tree | Definitions for a synset |
| 23 | `definition_sense_index` | `definitions` | `(sense_rowid)` | B-tree | Sense-attributed definitions |
| 24 | `synset_example_rowid_index` | `synset_examples` | `(synset_rowid)` | B-tree | Examples for a synset |
| 25 | `sense_id_index` | `senses` | `(id)` | B-tree | Sense lookups by ID |
| 26 | `sense_entry_rowid_index` | `senses` | `(entry_rowid)` | B-tree | All senses for an entry |
| 27 | `sense_synset_rowid_index` | `senses` | `(synset_rowid)` | B-tree | All senses for a synset |
| 28 | `unlexicalized_senses_index` | `unlexicalized_senses` | `(sense_rowid)` | B-tree | Unlexicalized check |
| 29 | `sense_relation_source_index` | `sense_relations` | `(source_rowid)` | B-tree | Outgoing sense relations |
| 30 | `sense_relation_target_index` | `sense_relations` | `(target_rowid)` | B-tree | Incoming sense relations |
| 31 | `sense_synset_relation_source_index` | `sense_synset_relations` | `(source_rowid)` | B-tree | Outgoing sense-synset relations |
| 32 | `sense_synset_relation_target_index` | `sense_synset_relations` | `(target_rowid)` | B-tree | Incoming sense-synset relations |
| 33 | `adjposition_sense_index` | `adjpositions` | `(sense_rowid)` | B-tree | Adjpositions for a sense |
| 34 | `sense_example_index` | `sense_examples` | `(sense_rowid)` | B-tree | Examples for a sense |
| 35 | `count_index` | `counts` | `(sense_rowid)` | B-tree | Counts for a sense |
| 36 | `syntactic_behaviour_id_index` | `syntactic_behaviours` | `(id)` | B-tree | Frame ID lookups |
| 37 | `syntactic_behaviour_sense_sb_index` | `syntactic_behaviour_senses` | `(syntactic_behaviour_rowid)` | B-tree | Senses for a frame |
| 38 | `syntactic_behaviour_sense_sense_index` | `syntactic_behaviour_senses` | `(sense_rowid)` | B-tree | Frames for a sense |
| 39 | `edit_history_entity_index` | `edit_history` | `(entity_type, entity_id)` | B-tree | History by entity |
| 40 | `edit_history_timestamp_index` | `edit_history` | `(timestamp)` | B-tree | History by time range |

### Implicit UNIQUE Indexes (from constraints)

| Table | Columns | Source |
|-------|---------|--------|
| `meta` | `(key)` | UNIQUE(key) |
| `relation_types` | `(type)` | UNIQUE(type) |
| `ili_statuses` | `(status)` | UNIQUE(status) |
| `lexfiles` | `(name)` | UNIQUE(name) |
| `ilis` | `(id)` | UNIQUE(id) |
| `proposed_ilis` | `(synset_rowid)` | UNIQUE(synset_rowid) |
| `lexicons` | `(id, version)` | UNIQUE(id, version) |
| `lexicons` | `(specifier)` | UNIQUE(specifier) |
| `lexicon_extensions` | `(extension_rowid, base_rowid)` | UNIQUE constraint |
| `entries` | `(id, lexicon_rowid)` | UNIQUE(id, lexicon_rowid) |
| `entry_index` | `(entry_rowid)` | UNIQUE(entry_rowid) |
| `forms` | `(entry_rowid, form, script)` | UNIQUE(entry_rowid, form, script) |
| `synsets` | `(id, lexicon_rowid)` | UNIQUE(id, lexicon_rowid) |
| `synset_relations` | `(source_rowid, target_rowid, type_rowid)` | UNIQUE constraint |
| `sense_relations` | `(source_rowid, target_rowid, type_rowid)` | UNIQUE constraint |
| `sense_synset_relations` | `(source_rowid, target_rowid, type_rowid)` | UNIQUE constraint |
| `syntactic_behaviours` | `(lexicon_rowid, id)` | UNIQUE constraint |
| `syntactic_behaviours` | `(lexicon_rowid, frame)` | UNIQUE constraint |

### Potentially Redundant Indexes

These explicit indexes duplicate the implicit index created by a UNIQUE constraint on the same column(s):

| Explicit Index | Duplicates UNIQUE on |
|----------------|---------------------|
| `relation_type_index` on `(type)` | `UNIQUE(type)` on `relation_types` |
| `ili_status_index` on `(status)` | `UNIQUE(status)` on `ili_statuses` |
| `lexfile_index` on `(name)` | `UNIQUE(name)` on `lexfiles` |

### Missing Indexes (Audit Flags)

| Table | Missing Index | Impact |
|-------|--------------|--------|
| `senses` | No UNIQUE on `(id, lexicon_rowid)` | Duplicate sense IDs possible via direct SQL — **`[SPEC]` (D3): spec omits this too** |
| `definitions` | No FTS5 index on `definition` text | `LIKE '%...%'` full scan in `find_synsets(definition_contains=...)` |
| `entries` | No index on `(lexicon_rowid)` alone | `find_entries()` filtered by lexicon does range scan on composite UNIQUE |
| `senses` | No index on `(lexicon_rowid)` alone | Same issue for `find_senses()` by lexicon |

---

## 4. Constraint Catalog

### 4.1 Foreign Key Constraints (46 total)

| # | Child Table | Child Column | Parent Table | Parent Column | ON DELETE |
|---|-------------|-------------|-------------|---------------|-----------|
| 1 | `ilis` | `status_rowid` | `ili_statuses` | `rowid` | RESTRICT |
| 2 | `proposed_ilis` | `synset_rowid` | `synsets` | `rowid` | CASCADE |
| 3 | `lexicon_dependencies` | `dependent_rowid` | `lexicons` | `rowid` | CASCADE |
| 4 | `lexicon_dependencies` | `provider_rowid` | `lexicons` | `rowid` | SET NULL |
| 5 | `lexicon_extensions` | `extension_rowid` | `lexicons` | `rowid` | CASCADE |
| 6 | `lexicon_extensions` | `base_rowid` | `lexicons` | `rowid` | RESTRICT |
| 7 | `entries` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 8 | `entry_index` | `entry_rowid` | `entries` | `rowid` | CASCADE |
| 9 | `forms` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 10 | `forms` | `entry_rowid` | `entries` | `rowid` | CASCADE |
| 11 | `pronunciations` | `form_rowid` | `forms` | `rowid` | CASCADE |
| 12 | `pronunciations` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 13 | `tags` | `form_rowid` | `forms` | `rowid` | CASCADE |
| 14 | `tags` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 15 | `synsets` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 16 | `synsets` | `ili_rowid` | `ilis` | `rowid` | RESTRICT |
| 17 | `synsets` | `lexfile_rowid` | `lexfiles` | `rowid` | RESTRICT |
| 18 | `unlexicalized_synsets` | `synset_rowid` | `synsets` | `rowid` | CASCADE |
| 19 | `synset_relations` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 20 | `synset_relations` | `source_rowid` | `synsets` | `rowid` | CASCADE |
| 21 | `synset_relations` | `target_rowid` | `synsets` | `rowid` | CASCADE |
| 22 | `synset_relations` | `type_rowid` | `relation_types` | `rowid` | RESTRICT |
| 23 | `definitions` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 24 | `definitions` | `synset_rowid` | `synsets` | `rowid` | CASCADE |
| 25 | `definitions` | `sense_rowid` | `senses` | `rowid` | SET NULL |
| 26 | `synset_examples` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 27 | `synset_examples` | `synset_rowid` | `synsets` | `rowid` | CASCADE |
| 28 | `senses` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 29 | `senses` | `entry_rowid` | `entries` | `rowid` | CASCADE |
| 30 | `senses` | `synset_rowid` | `synsets` | `rowid` | CASCADE |
| 31 | `unlexicalized_senses` | `sense_rowid` | `senses` | `rowid` | CASCADE |
| 32 | `sense_relations` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 33 | `sense_relations` | `source_rowid` | `senses` | `rowid` | CASCADE |
| 34 | `sense_relations` | `target_rowid` | `senses` | `rowid` | CASCADE |
| 35 | `sense_relations` | `type_rowid` | `relation_types` | `rowid` | RESTRICT |
| 36 | `sense_synset_relations` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 37 | `sense_synset_relations` | `source_rowid` | `senses` | `rowid` | CASCADE |
| 38 | `sense_synset_relations` | `target_rowid` | `synsets` | `rowid` | CASCADE |
| 39 | `sense_synset_relations` | `type_rowid` | `relation_types` | `rowid` | RESTRICT |
| 40 | `adjpositions` | `sense_rowid` | `senses` | `rowid` | CASCADE |
| 41 | `sense_examples` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 42 | `sense_examples` | `sense_rowid` | `senses` | `rowid` | CASCADE |
| 43 | `counts` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 44 | `counts` | `sense_rowid` | `senses` | `rowid` | CASCADE |
| 45 | `syntactic_behaviours` | `lexicon_rowid` | `lexicons` | `rowid` | CASCADE |
| 46 | `syntactic_behaviour_senses` | `syntactic_behaviour_rowid` | `syntactic_behaviours` | `rowid` | CASCADE |
| 47 | `syntactic_behaviour_senses` | `sense_rowid` | `senses` | `rowid` | CASCADE |

**ON DELETE behavior distribution:** CASCADE (38), RESTRICT (7), SET NULL (2)

### 4.2 CHECK Constraints (4 total)

| Table | Column | Constraint |
|-------|--------|-----------|
| `lexicons` | `modified` | `CHECK(modified IN (0, 1))` |
| `pronunciations` | `phonemic` | `CHECK(phonemic IN (0, 1))` |
| `edit_history` | `entity_type` | `CHECK(entity_type IN ('lexicon','synset','entry','sense','relation','definition','example','form','ili'))` |
| `edit_history` | `operation` | `CHECK(operation IN ('CREATE', 'UPDATE', 'DELETE'))` |

### 4.3 DB-Level vs Application-Level Enforcement

| Rule | DB Constraint | App Enforcement | Gap? |
|------|--------------|-----------------|------|
| Synset ID uniqueness within lexicon | UNIQUE(id, lexicon_rowid) | `get_synset_rowid()` check | No |
| Entry ID uniqueness within lexicon | UNIQUE(id, lexicon_rowid) | `get_entry_rowid()` check | No |
| **Sense ID uniqueness within lexicon** | **None** | `get_sense_rowid()` check | **YES — DB gap `[SPEC]` (D3): spec also omits constraint** |
| Relation uniqueness (source, target, type) | UNIQUE triple on all 3 relation tables | `suppress(IntegrityError)` | No |
| Relation self-loop prevention | None | `validator.py` VAL-REL-005 | Yes — app only |
| Relation type validity | None | `validator.py` VAL-REL-002 | Yes — app only |
| ILI uniqueness per synset | None (only UNIQUE on `ilis.id`) | `validator.py` VAL-SYN-002 | Yes — app only |
| ID prefix convention | None | `validator.py` VAL-EDT-001 | Yes — app only |
| POS consistency with hypernym | None | `validator.py` VAL-TAX-001 | Yes — app only |
| Inverse relation completeness | None | `validator.py` VAL-REL-004 | Yes — app only |
| Definition not blank | None | `validator.py` VAL-SYN-005 | Yes — app only |

---

## 5. Storage & Volume Profile

> **Note:** This section contains template queries. Run `docs/audit/run_baseline.py` against a real database to populate actual numbers.

### Row Counts Per Table

```sql
-- Run this query to populate the table below
SELECT 'meta' as tbl, COUNT(*) as cnt FROM meta
UNION ALL SELECT 'relation_types', COUNT(*) FROM relation_types
UNION ALL SELECT 'ili_statuses', COUNT(*) FROM ili_statuses
UNION ALL SELECT 'lexfiles', COUNT(*) FROM lexfiles
UNION ALL SELECT 'ilis', COUNT(*) FROM ilis
UNION ALL SELECT 'proposed_ilis', COUNT(*) FROM proposed_ilis
UNION ALL SELECT 'lexicons', COUNT(*) FROM lexicons
UNION ALL SELECT 'lexicon_dependencies', COUNT(*) FROM lexicon_dependencies
UNION ALL SELECT 'lexicon_extensions', COUNT(*) FROM lexicon_extensions
UNION ALL SELECT 'entries', COUNT(*) FROM entries
UNION ALL SELECT 'entry_index', COUNT(*) FROM entry_index
UNION ALL SELECT 'forms', COUNT(*) FROM forms
UNION ALL SELECT 'pronunciations', COUNT(*) FROM pronunciations
UNION ALL SELECT 'tags', COUNT(*) FROM tags
UNION ALL SELECT 'synsets', COUNT(*) FROM synsets
UNION ALL SELECT 'unlexicalized_synsets', COUNT(*) FROM unlexicalized_synsets
UNION ALL SELECT 'synset_relations', COUNT(*) FROM synset_relations
UNION ALL SELECT 'definitions', COUNT(*) FROM definitions
UNION ALL SELECT 'synset_examples', COUNT(*) FROM synset_examples
UNION ALL SELECT 'senses', COUNT(*) FROM senses
UNION ALL SELECT 'unlexicalized_senses', COUNT(*) FROM unlexicalized_senses
UNION ALL SELECT 'sense_relations', COUNT(*) FROM sense_relations
UNION ALL SELECT 'sense_synset_relations', COUNT(*) FROM sense_synset_relations
UNION ALL SELECT 'adjpositions', COUNT(*) FROM adjpositions
UNION ALL SELECT 'sense_examples', COUNT(*) FROM sense_examples
UNION ALL SELECT 'counts', COUNT(*) FROM counts
UNION ALL SELECT 'syntactic_behaviours', COUNT(*) FROM syntactic_behaviours
UNION ALL SELECT 'syntactic_behaviour_senses', COUNT(*) FROM syntactic_behaviour_senses
UNION ALL SELECT 'edit_history', COUNT(*) FROM edit_history
ORDER BY cnt DESC;
```

| Table | Row Count | Notes |
|-------|-----------|-------|
| *(run query to populate)* | | |

### Database File Metrics

```sql
PRAGMA page_count;     -- total pages in DB
PRAGMA page_size;      -- bytes per page (default 4096)
PRAGMA freelist_count;  -- unused pages
PRAGMA journal_mode;    -- should report 'wal'
```

| Metric | Value | Notes |
|--------|-------|-------|
| DB file size | *(measure with os.path.getsize)* | |
| WAL file size | *(measure -wal file)* | |
| Page size | *(from PRAGMA)* | Default 4096 bytes |
| Total pages | *(from PRAGMA)* | |
| Free pages | *(from PRAGMA)* | Reclaimable via VACUUM |
| Utilization | *(1 - free/total)* | |

### Growth Rate Estimation

```sql
-- Estimate growth from edit_history timestamps
SELECT
    MIN(timestamp) as first_edit,
    MAX(timestamp) as last_edit,
    COUNT(*) as total_edits,
    CAST(COUNT(*) AS REAL) /
        MAX(1, julianday(MAX(timestamp)) - julianday(MIN(timestamp))) as edits_per_day
FROM edit_history;
```

---

## 6. Access Pattern Profile

### 6.1 Table Heat Map

| Table | Read Frequency | Write Frequency | Primary Access Pattern |
|-------|---------------|-----------------|----------------------|
| `synsets` | **Very High** | Medium (import/create) | Point lookup by `id`, range scan by `lexicon_rowid` |
| `entries` | **Very High** | Medium (import/create) | Point lookup by `id`, range scan by `lexicon_rowid` |
| `senses` | **Very High** | Medium (import/add) | Point lookup by `id`, FK scans by `entry_rowid`/`synset_rowid` |
| `forms` | **High** | Low (import/add_form) | FK scan by `entry_rowid`, point lookup by `form` text |
| `definitions` | **High** | Low | FK scan by `synset_rowid`, full scan for `LIKE` search |
| `relation_types` | **High** | Low (on-demand populate) | Point lookup by `type` string |
| `synset_relations` | **High** | Medium | FK scan by `source_rowid`/`target_rowid` |
| `sense_relations` | **High** | Medium | FK scan by `source_rowid`/`target_rowid` |
| `entry_index` | **High** | Low | Point lookup by `entry_rowid`, search by `lemma` |
| `edit_history` | Low | **Very High** (every mutation) | Append-only writes; occasional range scans |
| `lexicons` | Medium | Low | Point lookup by `specifier`; full scan for `list_lexicons()` |
| `ilis` | Medium | Low | Point lookup by `id`/`rowid` |
| `proposed_ilis` | Low | Low | FK lookup by `synset_rowid` |
| `pronunciations` | Low | Very Low | FK scan by `form_rowid` |
| `tags` | Low | Very Low | FK scan by `form_rowid` |
| `counts` | Low | Very Low | FK scan by `sense_rowid` |
| `synset_examples` | Low | Very Low | FK scan by `synset_rowid` |
| `sense_examples` | Low | Very Low | FK scan by `sense_rowid` |
| `adjpositions` | Low | Very Low | FK scan by `sense_rowid` |

### 6.2 Query Shape Distribution

| Shape | Frequency | Example |
|-------|-----------|---------|
| **Point lookup by rowid** | Very High | `SELECT * FROM synsets WHERE rowid = ?` |
| **Point lookup by business ID** | Very High | `SELECT rowid FROM synsets WHERE id = ?` |
| **FK range scan** | High | `SELECT * FROM forms WHERE entry_rowid = ?` |
| **Filtered range scan** | Medium | `SELECT id FROM synsets WHERE lexicon_rowid = ? AND pos = ?` |
| **Multi-table JOIN** | Medium | 4-table JOIN in `_build_sense_model` |
| **Aggregate (COUNT/MAX)** | Medium | `SELECT COUNT(*) FROM senses WHERE synset_rowid = ?` |
| **Full table scan** | Low (but costly) | `list_lexicons()`, `find_*()` with no filters |
| **LIKE pattern scan** | Low (but very costly) | `definition LIKE '%word%'` |
| **Bulk INSERT (executemany)** | Low (import only) | `INSERT INTO synsets ... VALUES (?,?,?,?,?,?)` batched |

### 6.3 Hot Paths (Most Frequently Called Internal Functions)

| Function | Queries/Call | Called By | N+1 Risk |
|----------|-------------|-----------|----------|
| `_build_synset_model()` | 3-5 | `get_synset`, `find_synsets`, `create_synset`, `update_synset`, `merge_synsets`, `split_synset` | **YES** — called per result row in `find_synsets` |
| `_build_entry_model()` | 3 | `get_entry`, `find_entries`, `create_entry`, `update_entry` | **YES** — called per result row in `find_entries` |
| `_build_sense_model()` | 3 | `get_sense`, `find_senses`, `add_sense`, `move_sense` | **YES** — called per result row in `find_senses` |
| `get_or_create_relation_type()` | 2 | Every relation add/remove | No (constant-time lookup) |
| `get_lexicon_rowid()` | 1-2 | Nearly all methods (lexicon resolution) | No |
| `record_create/update/delete()` | 1 | Every `@_modifies_db` method | No (single INSERT) |

### 6.4 N+1 Query Pattern Inventory

> **Source layer: `[IMPL]`** — All 16 N+1 patterns are implementation-level choices. The design specs are silent on query strategy — they define *what* data to fetch, not *how* to structure SQL queries. The implementation chose per-row sub-queries where batch pre-fetches would be more efficient.

| # | Location | Trigger | Pattern | Query Count |
|---|----------|---------|---------|-------------|
| 1 | `editor.find_synsets()` | Each result row | `_build_synset_model` × N | 1 + 5N |
| 2 | `editor.find_entries()` | Each result row | `_build_entry_model` × N | 1 + 3N |
| 3 | `editor.find_senses()` | Each result row | `_build_sense_model` × N | 1 + 3N |
| 4 | `editor.get_forms()` | Each form | pronunciations + tags queries | 1 + 2F |
| 5 | `editor.reorder_senses()` | Each sense | Individual UPDATE per sense | N UPDATEs |
| 6 | `editor.delete_synset(cascade)` | Each child sense | `_remove_sense_internal` + relation cleanup | O(S × R) |
| 7 | `editor._cleanup_synset_relations()` | Each relation | type lookup + inverse delete | 3 per relation |
| 8 | `editor._cleanup_sense_relations()` | Each relation | type lookup + inverse delete | 3 per relation |
| 9 | `editor.update_lexicon()` | Each changed field | Individual UPDATE per field | N UPDATEs |
| 10 | `editor.merge_synsets._merge_senses()` | Each sense | Duplicate check + UPDATE/DELETE | 2-3 per sense |
| 11 | `editor.merge_synsets._merge_relations()` | Each relation | UPDATE or DELETE | 1 per relation |
| 12 | `editor.merge_synsets._merge_definitions()` | Each definition | UPDATE or DELETE | 1 per def |
| 13 | `exporter._build_entry()` | Each entry | forms → senses → deep build | Cascading |
| 14 | `exporter._build_sense()` / `_query_relations()` | Each relation | Target ID lookup per relation | 1 + N |
| 15 | `exporter._build_lexicon_frames()` | Each frame | Sense IDs lookup per frame | 1 per frame |
| 16 | `importer._build_resource_from_wn_db()` | Each synset/entry | All children individually | M × N |

### 6.5 Full Table Scan Inventory

| Query | Table | Context | Mitigable? |
|-------|-------|---------|-----------|
| `SELECT rowid, * FROM lexicons` | `lexicons` | `list_lexicons()` | No (table is tiny, <10 rows) |
| `definition LIKE '%...%'` | `definitions` | `find_synsets(definition_contains=...)` | Yes — FTS5 virtual table |
| `SELECT id FROM entries WHERE 1=1` | `entries` | `find_entries()` with no filters | Yes — require at least one filter |
| `SELECT id FROM senses WHERE 1=1` | `senses` | `find_senses()` with no filters | Yes — require at least one filter |
| `SELECT rowid, * FROM edit_history` | `edit_history` | `get_history()` with no filters | Yes — add mandatory LIMIT or require filter |
| `SELECT id FROM lexicons` | `lexicons` | `exporter._all_lexicon_ids()` | No (table is tiny) |
