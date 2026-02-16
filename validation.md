# Validation Rules Catalog

**Library**: `wordnet-editor`
**Version**: 1.0
**Date**: 2026-02-16

All validation rules the editor checks, organized by entity type. Each rule has a unique ID, severity level, and source.

---

## Summary

| Severity | Count | Description |
|----------|-------|-------------|
| ERROR | 7 | Must be fixed before export. Indicates broken data. |
| WARNING | 16 | Should be reviewed. May indicate issues but doesn't block export. |

---

## Rules

### General (100 series)

| Rule ID | Severity | Entity | Description | Source |
|---------|----------|--------|-------------|--------|
| VAL-GEN-001 | ERROR | All | ID is not unique within the lexicon. Duplicate IDs found among entries, senses, synsets, forms, or syntactic behaviours. | `wn/validate.py` E101 |

### Lexical Entries & Senses (200 series)

| Rule ID | Severity | Entity | Description | Source |
|---------|----------|--------|-------------|--------|
| VAL-ENT-001 | WARNING | Entry | Lexical entry has no senses. | `wn/validate.py` W201 |
| VAL-ENT-002 | WARNING | Sense | Redundant sense: entry has multiple senses referencing the same synset. | `wn/validate.py` W202 |
| VAL-ENT-003 | WARNING | Entry | Redundant entry: another entry has the same lemma and references the same synset. | `wn/validate.py` W203 |
| VAL-ENT-004 | ERROR | Sense | Synset referenced by sense is missing from the database. | `wn/validate.py` E204 |

### Synsets & ILI (300 series)

| Rule ID | Severity | Entity | Description | Source |
|---------|----------|--------|-------------|--------|
| VAL-SYN-001 | WARNING | Synset | Synset is empty — not associated with any senses (unlexicalized). | `wn/validate.py` W301 |
| VAL-SYN-002 | WARNING | Synset | ILI identifier is used by more than one synset within the lexicon. | `wn/validate.py` W302 |
| VAL-SYN-003 | WARNING | Synset | Proposed ILI (`ili="in"`) is missing a definition in `proposed_ilis`. | `wn/validate.py` W303 |
| VAL-SYN-004 | WARNING | Synset | Existing ILI (mapped to a real ILI ID) has a spurious ILI definition. | `wn/validate.py` W304 |
| VAL-SYN-005 | WARNING | Synset | Synset has a blank (empty or whitespace-only) definition. | `wn/validate.py` W305 |
| VAL-SYN-006 | WARNING | Synset | Synset has a blank (empty or whitespace-only) example. | `wn/validate.py` W306 |
| VAL-SYN-007 | WARNING | Synset | Synset has a duplicate definition (same text appears in another synset). | `wn/validate.py` W307 |
| VAL-SYN-008 | ERROR | Synset | Proposed ILI definition is less than 20 characters. | WN-LMF 1.4 spec |

### Relations (400 series)

| Rule ID | Severity | Entity | Description | Source |
|---------|----------|--------|-------------|--------|
| VAL-REL-001 | ERROR | Relation | Relation target entity (synset or sense) is missing from the database. | `wn/validate.py` E401 |
| VAL-REL-002 | WARNING | Relation | Relation type is invalid for the source and target entity types. E.g., a synset relation type used in a sense relation, or vice versa. | `wn/validate.py` W402 |
| VAL-REL-003 | WARNING | Relation | Redundant relation: identical relation (same source, type, and target) appears more than once. | `wn/validate.py` W403 |
| VAL-REL-004 | WARNING | Relation | Reverse relation is missing. An asymmetric relation exists without its expected inverse. | `wn/validate.py` W404 |
| VAL-REL-005 | ERROR | Relation | Self-loop: a relation's source and target are the same entity. | Editor policy (stricter than `wn` W502) |

### Graph & Taxonomy (500 series)

| Rule ID | Severity | Entity | Description | Source |
|---------|----------|--------|-------------|--------|
| VAL-TAX-001 | WARNING | Synset | Synset's part-of-speech differs from its hypernym's part-of-speech. | `wn/validate.py` W501 |

### Editor-Specific Rules (600 series)

| Rule ID | Severity | Entity | Description | Source |
|---------|----------|--------|-------------|--------|
| VAL-EDT-001 | ERROR | All | Entity ID does not start with the owning lexicon's ID prefix followed by `-`. | Editor policy (RULE-ID-004) |
| VAL-EDT-002 | ERROR | Synset | Synset has no definitions. | Editor policy |
| VAL-EDT-003 | WARNING | Sense | Sense has confidence score below 0.5. | Editor policy |

---

## Rule Sources

| Source | Description | Rules |
|--------|-------------|-------|
| `wn/validate.py` | Validation rules from the `wn` library (E-codes are errors, W-codes are warnings) | VAL-GEN-001 through VAL-TAX-001 |
| WN-LMF 1.4 spec | Constraints from the schema specification document | VAL-SYN-008 |
| Editor policy | Rules specific to the editor's behavioral requirements | VAL-REL-005, VAL-EDT-001, VAL-EDT-002, VAL-EDT-003 |

---

## Mapping to `wn/validate.py` Codes

| Editor Rule | `wn` Code | Notes |
|------------|-----------|-------|
| VAL-GEN-001 | E101 | Identical check |
| VAL-ENT-001 | W201 | Identical check |
| VAL-ENT-002 | W202 | Identical check |
| VAL-ENT-003 | W203 | Identical check |
| VAL-ENT-004 | E204 | Identical check |
| VAL-SYN-001 | W301 | Identical check |
| VAL-SYN-002 | W302 | Identical check |
| VAL-SYN-003 | W303 | Identical check |
| VAL-SYN-004 | W304 | Identical check |
| VAL-SYN-005 | W305 | Identical check |
| VAL-SYN-006 | W306 | Identical check |
| VAL-SYN-007 | W307 | Identical check |
| VAL-REL-001 | E401 | Identical check |
| VAL-REL-002 | W402 | Identical check |
| VAL-REL-003 | W403 | Identical check |
| VAL-REL-004 | W404 | Identical check |
| VAL-REL-005 | W502 | Elevated from WARNING to ERROR in editor |
| VAL-TAX-001 | W501 | Identical check |
