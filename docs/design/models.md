# Domain Model Specification

**Library**: `wordnet-editor`
**Version**: 1.0
**Date**: 2026-02-16

This document defines every type, enum, and data structure the library uses. All other specifications reference these definitions.

---

## 4.1 — Dataclasses

All model dataclasses are **frozen** (immutable) and use `__slots__` for memory efficiency. They are returned from query/get methods. Mutation methods accept keyword arguments rather than mutable model objects.

### LexiconModel

Represents a WordNet lexicon (package).

```python
@dataclass(frozen=True, slots=True)
class LexiconModel:
    id: str                    # Unique identifier (e.g., "ewn", "awn")
    label: str                 # Human-readable name
    language: str              # BCP-47 language code
    email: str                 # Contact email
    license: str               # License URL
    version: str               # Version string (e.g., "1.0")
    url: str | None            # Project homepage URL
    citation: str | None       # Citation text
    logo: str | None           # Logo image URL
    metadata: dict | None      # Dublin Core metadata (dc:publisher, etc.)

    @property
    def specifier(self) -> str:
        """Returns ``"id:version"`` (e.g., ``"awn:1.0"``)."""
```

### SynsetModel

Represents a concept (synset) — a group of words sharing a meaning.

```python
@dataclass(frozen=True, slots=True)
class SynsetModel:
    id: str                    # Unique ID (e.g., "ewn-10161911-n")
    lexicon_id: str            # Owning lexicon ID
    pos: str | None            # Part of speech (from PartOfSpeech enum)
    ili: str | None            # ILI identifier ("i90287", "in", or None)
    lexicalized: bool          # Whether any senses reference this synset
    lexfile: str | None        # Lexicographer file name (e.g., "noun.person")
    metadata: dict | None      # Dublin Core metadata
```

### EntryModel

Represents a lexical entry — a word with a specific part of speech.

```python
@dataclass(frozen=True, slots=True)
class EntryModel:
    id: str                    # Unique ID (e.g., "ewn-grandfather-n")
    lexicon_id: str            # Owning lexicon ID
    lemma: str                 # Written form of the lemma
    pos: str                   # Part of speech (from PartOfSpeech enum)
    index: str | None          # Normalized form for sense ordering
    metadata: dict | None      # Dublin Core metadata
```

### SenseModel

Represents a specific meaning of a word — the link between an entry and a synset.

```python
@dataclass(frozen=True, slots=True)
class SenseModel:
    id: str                    # Unique ID (e.g., "ewn-grandfather-n-10161911-01")
    entry_id: str              # Owning entry ID
    synset_id: str             # Referenced synset ID
    lexicon_id: str            # Owning lexicon ID
    entry_rank: int            # Positional ordering within entry (1-based, derived from XML element order)
    synset_rank: int           # Positional ordering within synset (1-based, from synset members attribute)
    lexicalized: bool          # Whether this sense is lexicalized
    adjposition: str | None    # Adjective position ("a", "ip", "p") or None
    n: int | None              # WN-LMF sense number hint (explicit `n` attribute, distinct from entry_rank)
    metadata: dict | None      # Dublin Core metadata
```

### FormModel

Represents a written form of a word (lemma or inflected form).

```python
@dataclass(frozen=True, slots=True)
class FormModel:
    written_form: str          # The text of the form
    id: str | None             # Optional form ID
    script: str | None         # Script code (e.g., "Latn")
    rank: int                  # 0 = lemma, 1+ = additional forms
    pronunciations: tuple[PronunciationModel, ...]  # Pronunciation data
    tags: tuple[TagModel, ...]                      # Grammatical tags
```

### PronunciationModel

```python
@dataclass(frozen=True, slots=True)
class PronunciationModel:
    value: str                 # IPA or other transcription text
    variety: str | None        # Dialect/variety (e.g., "US", "GB")
    notation: str | None       # Notation system (e.g., "IPA")
    phonemic: bool             # True = phonemic, False = phonetic
    audio: str | None          # URL to audio file
```

### TagModel

```python
@dataclass(frozen=True, slots=True)
class TagModel:
    tag: str                   # Tag value (e.g., "NNS")
    category: str              # Tag category (e.g., "penn")
```

### DefinitionModel

```python
@dataclass(frozen=True, slots=True)
class DefinitionModel:
    text: str                  # Definition text
    language: str | None       # Language code (defaults to lexicon language)
    source_sense: str | None   # Sense ID if definition is sense-specific
    metadata: dict | None      # Dublin Core metadata
```

### ExampleModel

```python
@dataclass(frozen=True, slots=True)
class ExampleModel:
    text: str                  # Example text
    language: str | None       # Language code
    metadata: dict | None      # Dublin Core metadata
```

### RelationModel

Represents a directed relation between entities (synset→synset, sense→sense, or sense→synset).

```python
@dataclass(frozen=True, slots=True)
class RelationModel:
    source_id: str             # Source entity ID
    target_id: str             # Target entity ID
    relation_type: str         # Relation type string (e.g., "hypernym")
    metadata: dict | None      # Dublin Core metadata (dc:type for "other" relations)
```

### ILIModel

Represents an Interlingual Index entry.

```python
@dataclass(frozen=True, slots=True)
class ILIModel:
    id: str                    # ILI identifier (e.g., "i90287")
    status: str                # Status: "active", "deprecated", "presupposed"
    definition: str | None     # ILI definition text
    metadata: dict | None      # Dublin Core metadata
```

### ProposedILIModel

Represents a proposed (new) ILI concept linked to a synset.

```python
@dataclass(frozen=True, slots=True)
class ProposedILIModel:
    synset_id: str             # Synset proposing the new ILI
    definition: str            # Definition text (≥20 chars per WN-LMF spec)
    metadata: dict | None      # Dublin Core metadata
```

### CountModel

```python
@dataclass(frozen=True, slots=True)
class CountModel:
    value: int                 # Frequency count (maps to DB column `count`)
    metadata: dict | None      # Dublin Core metadata
```

### SyntacticBehaviourModel

```python
@dataclass(frozen=True, slots=True)
class SyntacticBehaviourModel:
    id: str | None             # Optional ID (e.g., "intransitive")
    frame: str                 # Subcategorization frame (e.g., "Somebody ----s")
    sense_ids: tuple[str, ...] # Senses that use this frame
```

### EditRecord

Records a single field-level change in the edit history.

```python
@dataclass(frozen=True, slots=True)
class EditRecord:
    id: int                    # Auto-increment row ID
    entity_type: str           # "synset", "entry", "sense", "lexicon", etc.
    entity_id: str             # ID of the modified entity
    field_name: str | None     # Field that changed (None for CREATE/DELETE)
    operation: str             # "CREATE", "UPDATE", "DELETE"
    old_value: str | None      # JSON of previous value (None for CREATE)
    new_value: str | None      # JSON of new value (None for DELETE)
    timestamp: str             # ISO 8601 timestamp
```

### ValidationResult

Represents a single validation finding.

```python
@dataclass(frozen=True, slots=True)
class ValidationResult:
    rule_id: str               # Rule identifier (e.g., "VAL-SYN-001")
    severity: str              # "ERROR" or "WARNING"
    entity_type: str           # Entity type checked
    entity_id: str             # Specific entity ID (or "" for global rules)
    message: str               # Human-readable description
    details: dict | None       # Additional context (e.g., {"target": "missing-id"})
```

---

## 4.2 — Enums

### PartOfSpeech

Valid WN-LMF 1.4 part-of-speech values. Source: `wn/wn/constants.py` lines 268–292.

```python
class PartOfSpeech(str, Enum):
    NOUN = "n"
    VERB = "v"
    ADJECTIVE = "a"
    ADVERB = "r"
    ADJECTIVE_SATELLITE = "s"
    PHRASE = "t"
    CONJUNCTION = "c"
    ADPOSITION = "p"
    OTHER = "x"
    UNKNOWN = "u"
```

### AdjPosition

Valid adjective positions. Source: `wn/wn/constants.py` lines 257–263.

```python
class AdjPosition(str, Enum):
    ATTRIBUTIVE = "a"
    IMMEDIATE_POSTNOMINAL = "ip"
    PREDICATIVE = "p"
```

### SynsetRelationType

All valid synset relation type strings. Source: `wn/wn/constants.py` lines 67–155 (`SYNSET_RELATIONS` frozenset, 85 members).

```python
class SynsetRelationType(str, Enum):
    AGENT = "agent"
    ALSO = "also"
    ANTONYM = "antonym"
    ANTO_CONVERSE = "anto_converse"
    ANTO_GRADABLE = "anto_gradable"
    ANTO_SIMPLE = "anto_simple"
    ATTRIBUTE = "attribute"
    AUGMENTATIVE = "augmentative"
    BE_IN_STATE = "be_in_state"
    CAUSES = "causes"
    CLASSIFIED_BY = "classified_by"
    CLASSIFIES = "classifies"
    CO_AGENT_INSTRUMENT = "co_agent_instrument"
    CO_AGENT_PATIENT = "co_agent_patient"
    CO_AGENT_RESULT = "co_agent_result"
    CO_INSTRUMENT_AGENT = "co_instrument_agent"
    CO_INSTRUMENT_PATIENT = "co_instrument_patient"
    CO_INSTRUMENT_RESULT = "co_instrument_result"
    CO_PATIENT_AGENT = "co_patient_agent"
    CO_PATIENT_INSTRUMENT = "co_patient_instrument"
    CO_RESULT_AGENT = "co_result_agent"
    CO_RESULT_INSTRUMENT = "co_result_instrument"
    CO_ROLE = "co_role"
    DIMINUTIVE = "diminutive"
    DIRECTION = "direction"
    DOMAIN_REGION = "domain_region"
    DOMAIN_TOPIC = "domain_topic"
    ENTAILS = "entails"
    EQ_SYNONYM = "eq_synonym"
    EXEMPLIFIES = "exemplifies"
    FEMININE = "feminine"
    HAS_AUGMENTATIVE = "has_augmentative"
    HAS_DIMINUTIVE = "has_diminutive"
    HAS_DOMAIN_REGION = "has_domain_region"
    HAS_DOMAIN_TOPIC = "has_domain_topic"
    HAS_FEMININE = "has_feminine"
    HAS_MASCULINE = "has_masculine"
    HAS_YOUNG = "has_young"
    HOLO_LOCATION = "holo_location"
    HOLO_MEMBER = "holo_member"
    HOLO_PART = "holo_part"
    HOLO_PORTION = "holo_portion"
    HOLO_SUBSTANCE = "holo_substance"
    HOLONYM = "holonym"
    HYPERNYM = "hypernym"
    HYPONYM = "hyponym"
    IN_MANNER = "in_manner"
    INSTANCE_HYPERNYM = "instance_hypernym"
    INSTANCE_HYPONYM = "instance_hyponym"
    INSTRUMENT = "instrument"
    INVOLVED = "involved"
    INVOLVED_AGENT = "involved_agent"
    INVOLVED_DIRECTION = "involved_direction"
    INVOLVED_INSTRUMENT = "involved_instrument"
    INVOLVED_LOCATION = "involved_location"
    INVOLVED_PATIENT = "involved_patient"
    INVOLVED_RESULT = "involved_result"
    INVOLVED_SOURCE_DIRECTION = "involved_source_direction"
    INVOLVED_TARGET_DIRECTION = "involved_target_direction"
    IR_SYNONYM = "ir_synonym"
    IS_CAUSED_BY = "is_caused_by"
    IS_ENTAILED_BY = "is_entailed_by"
    IS_EXEMPLIFIED_BY = "is_exemplified_by"
    IS_SUBEVENT_OF = "is_subevent_of"
    LOCATION = "location"
    MANNER_OF = "manner_of"
    MASCULINE = "masculine"
    MERO_LOCATION = "mero_location"
    MERO_MEMBER = "mero_member"
    MERO_PART = "mero_part"
    MERO_PORTION = "mero_portion"
    MERO_SUBSTANCE = "mero_substance"
    MERONYM = "meronym"
    OTHER = "other"
    PATIENT = "patient"
    RESTRICTED_BY = "restricted_by"
    RESTRICTS = "restricts"
    RESULT = "result"
    ROLE = "role"
    SIMILAR = "similar"
    SOURCE_DIRECTION = "source_direction"
    STATE_OF = "state_of"
    SUBEVENT = "subevent"
    TARGET_DIRECTION = "target_direction"
    YOUNG = "young"
```

### SenseRelationType

All valid sense relation type strings. Source: `wn/wn/constants.py` lines 5–56 (`SENSE_RELATIONS` frozenset, 48 members).

```python
class SenseRelationType(str, Enum):
    AGENT = "agent"
    ALSO = "also"
    ANTONYM = "antonym"
    ANTO_CONVERSE = "anto_converse"
    ANTO_GRADABLE = "anto_gradable"
    ANTO_SIMPLE = "anto_simple"
    AUGMENTATIVE = "augmentative"
    BODY_PART = "body_part"
    BY_MEANS_OF = "by_means_of"
    DERIVATION = "derivation"
    DESTINATION = "destination"
    DIMINUTIVE = "diminutive"
    DOMAIN_REGION = "domain_region"
    DOMAIN_TOPIC = "domain_topic"
    EVENT = "event"
    EXEMPLIFIES = "exemplifies"
    FEMININE = "feminine"
    HAS_AUGMENTATIVE = "has_augmentative"
    HAS_DIMINUTIVE = "has_diminutive"
    HAS_DOMAIN_REGION = "has_domain_region"
    HAS_DOMAIN_TOPIC = "has_domain_topic"
    HAS_FEMININE = "has_feminine"
    HAS_MASCULINE = "has_masculine"
    HAS_METAPHOR = "has_metaphor"
    HAS_METONYM = "has_metonym"
    HAS_YOUNG = "has_young"
    INSTRUMENT = "instrument"
    IS_EXEMPLIFIED_BY = "is_exemplified_by"
    LOCATION = "location"
    MASCULINE = "masculine"
    MATERIAL = "material"
    METAPHOR = "metaphor"
    METONYM = "metonym"
    OTHER = "other"
    PARTICIPLE = "participle"
    PERTAINYM = "pertainym"
    PROPERTY = "property"
    RESULT = "result"
    SECONDARY_ASPECT_IP = "secondary_aspect_ip"
    SECONDARY_ASPECT_PI = "secondary_aspect_pi"
    SIMILAR = "similar"
    SIMPLE_ASPECT_IP = "simple_aspect_ip"
    SIMPLE_ASPECT_PI = "simple_aspect_pi"
    STATE = "state"
    UNDERGOER = "undergoer"
    USES = "uses"
    VEHICLE = "vehicle"
    YOUNG = "young"
```

### SenseSynsetRelationType

Valid relation types for sense-to-synset relations. Source: `wn/wn/constants.py` lines 58–65.

```python
class SenseSynsetRelationType(str, Enum):
    OTHER = "other"
    DOMAIN_TOPIC = "domain_topic"
    DOMAIN_REGION = "domain_region"
    EXEMPLIFIES = "exemplifies"
```

### EditOperation

```python
class EditOperation(str, Enum):
    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"
```

### ValidationSeverity

```python
class ValidationSeverity(str, Enum):
    ERROR = "ERROR"
    WARNING = "WARNING"
```

---

## 4.3 — Inverse Relation Map

The complete bidirectional mapping of relation types to their inverses. Source: `wn/wn/constants.py` lines 158–253 (`REVERSE_RELATIONS` dict).

This map is used by both synset relations and sense relations. Relation types that appear in the map get automatic inverse maintenance when `auto_inverse=True`.

### Asymmetric relations (each maps to a different inverse)

| Relation | Inverse |
|----------|---------|
| `hypernym` | `hyponym` |
| `hyponym` | `hypernym` |
| `instance_hypernym` | `instance_hyponym` |
| `instance_hyponym` | `instance_hypernym` |
| `meronym` | `holonym` |
| `holonym` | `meronym` |
| `mero_location` | `holo_location` |
| `holo_location` | `mero_location` |
| `mero_member` | `holo_member` |
| `holo_member` | `mero_member` |
| `mero_part` | `holo_part` |
| `holo_part` | `mero_part` |
| `mero_portion` | `holo_portion` |
| `holo_portion` | `mero_portion` |
| `mero_substance` | `holo_substance` |
| `holo_substance` | `mero_substance` |
| `state_of` | `be_in_state` |
| `be_in_state` | `state_of` |
| `causes` | `is_caused_by` |
| `is_caused_by` | `causes` |
| `subevent` | `is_subevent_of` |
| `is_subevent_of` | `subevent` |
| `manner_of` | `in_manner` |
| `in_manner` | `manner_of` |
| `restricts` | `restricted_by` |
| `restricted_by` | `restricts` |
| `classifies` | `classified_by` |
| `classified_by` | `classifies` |
| `entails` | `is_entailed_by` |
| `is_entailed_by` | `entails` |
| `domain_topic` | `has_domain_topic` |
| `has_domain_topic` | `domain_topic` |
| `domain_region` | `has_domain_region` |
| `has_domain_region` | `domain_region` |
| `exemplifies` | `is_exemplified_by` |
| `is_exemplified_by` | `exemplifies` |
| `role` | `involved` |
| `involved` | `role` |
| `agent` | `involved_agent` |
| `involved_agent` | `agent` |
| `patient` | `involved_patient` |
| `involved_patient` | `patient` |
| `result` | `involved_result` |
| `involved_result` | `result` |
| `instrument` | `involved_instrument` |
| `involved_instrument` | `instrument` |
| `location` | `involved_location` |
| `involved_location` | `location` |
| `direction` | `involved_direction` |
| `involved_direction` | `direction` |
| `target_direction` | `involved_target_direction` |
| `involved_target_direction` | `target_direction` |
| `source_direction` | `involved_source_direction` |
| `involved_source_direction` | `source_direction` |
| `co_agent_patient` | `co_patient_agent` |
| `co_patient_agent` | `co_agent_patient` |
| `co_agent_instrument` | `co_instrument_agent` |
| `co_instrument_agent` | `co_agent_instrument` |
| `co_agent_result` | `co_result_agent` |
| `co_result_agent` | `co_agent_result` |
| `co_patient_instrument` | `co_instrument_patient` |
| `co_instrument_patient` | `co_patient_instrument` |
| `co_result_instrument` | `co_instrument_result` |
| `co_instrument_result` | `co_result_instrument` |
| `simple_aspect_ip` | `simple_aspect_pi` |
| `simple_aspect_pi` | `simple_aspect_ip` |
| `secondary_aspect_ip` | `secondary_aspect_pi` |
| `secondary_aspect_pi` | `secondary_aspect_ip` |
| `feminine` | `has_feminine` |
| `has_feminine` | `feminine` |
| `masculine` | `has_masculine` |
| `has_masculine` | `masculine` |
| `young` | `has_young` |
| `has_young` | `young` |
| `diminutive` | `has_diminutive` |
| `has_diminutive` | `diminutive` |
| `augmentative` | `has_augmentative` |
| `has_augmentative` | `augmentative` |
| `metaphor` | `has_metaphor` |
| `has_metaphor` | `metaphor` |
| `metonym` | `has_metonym` |
| `has_metonym` | `metonym` |

### Symmetric relations (map to themselves)

| Relation |
|----------|
| `antonym` |
| `eq_synonym` |
| `similar` |
| `attribute` |
| `co_role` |
| `derivation` |
| `anto_gradable` |
| `anto_simple` |
| `anto_converse` |
| `ir_synonym` |

### Relations with NO defined inverse (auto_inverse is no-op)

These are commented out in `wn/constants.py` and have no inverse entry:

| Relation | Reason |
|----------|--------|
| `also` | Semantically loose, no clear inverse |
| `pertainym` | No standard inverse in GWA |
| `participle` | No standard inverse in GWA |
| `other` | Custom relations; inverse unknown |

For these, `auto_inverse=True` has no effect. The relation is stored as a single directional link. Users can manually add a reverse if needed using `other` with `dc:type`.

---

## 4.4 — Mapping to Database Rows

### LexiconModel ↔ `lexicons` table

| Model field | DB column | Notes |
|------------|-----------|-------|
| `id` | `id` | TEXT NOT NULL |
| `label` | `label` | TEXT NOT NULL |
| `language` | `language` | TEXT NOT NULL |
| `email` | `email` | TEXT NOT NULL |
| `license` | `license` | TEXT NOT NULL |
| `version` | `version` | TEXT NOT NULL |
| `url` | `url` | TEXT (nullable) |
| `citation` | `citation` | TEXT (nullable) |
| `logo` | `logo` | TEXT (nullable) |
| `metadata` | `metadata` | META (JSON) |
| — | `rowid` | INTEGER PRIMARY KEY (internal) |
| — | `specifier` | TEXT NOT NULL, computed as `{id}:{version}` |
| — | `modified` | BOOLEAN DEFAULT 0 (internal) |

### SynsetModel ↔ `synsets` table

| Model field | DB column | Notes |
|------------|-----------|-------|
| `id` | `id` | TEXT NOT NULL |
| `lexicon_id` | `lexicon_rowid` | FK → lexicons.rowid (resolved to lexicon ID) |
| `pos` | `pos` | TEXT (nullable) |
| `ili` | `ili_rowid` | FK → ilis.rowid (resolved to ILI id string) |
| `lexicalized` | — | Derived: True unless rowid in `unlexicalized_synsets` |
| `lexfile` | `lexfile_rowid` | FK → lexfiles.rowid (resolved to name) |
| `metadata` | `metadata` | META (JSON) |

Additional data in child tables:
- Definitions → `definitions` table (keyed by `synset_rowid`)
- Examples → `synset_examples` table
- Relations → `synset_relations` table
- Proposed ILI → `proposed_ilis` table

### EntryModel ↔ `entries` table

| Model field | DB column | Notes |
|------------|-----------|-------|
| `id` | `id` | TEXT NOT NULL |
| `lexicon_id` | `lexicon_rowid` | FK → lexicons.rowid |
| `lemma` | — | From `forms` table where `rank = 0` |
| `pos` | `pos` | TEXT NOT NULL |
| `index` | — | From `entry_index` table |
| `metadata` | `metadata` | META (JSON) |

### SenseModel ↔ `senses` table

| Model field | DB column | Notes |
|------------|-----------|-------|
| `id` | `id` | TEXT NOT NULL |
| `entry_id` | `entry_rowid` | FK → entries.rowid (resolved to entry ID) |
| `synset_id` | `synset_rowid` | FK → synsets.rowid (resolved to synset ID) |
| `lexicon_id` | `lexicon_rowid` | FK → lexicons.rowid |
| `entry_rank` | `entry_rank` | INTEGER DEFAULT 1 |
| `synset_rank` | `synset_rank` | INTEGER DEFAULT 1 |
| `lexicalized` | — | Derived: True unless rowid in `unlexicalized_senses` |
| `adjposition` | — | From `adjpositions` table |
| `n` | — | Stored implicitly via `entry_rank` |
| `metadata` | `metadata` | META (JSON) |

### FormModel ↔ `forms` table

| Model field | DB column | Notes |
|------------|-----------|-------|
| `written_form` | `form` | TEXT NOT NULL |
| `id` | `id` | TEXT (nullable) |
| `script` | `script` | TEXT (nullable) |
| `rank` | `rank` | INTEGER DEFAULT 1 (0 = lemma) |
| `pronunciations` | — | From `pronunciations` table |
| `tags` | — | From `tags` table |
| — | `normalized_form` | TEXT, only stored when differs from `form` |
| — | `entry_rowid` | FK → entries.rowid |
| — | `lexicon_rowid` | FK → lexicons.rowid |

### RelationModel ↔ `synset_relations` / `sense_relations` / `sense_synset_relations` tables

| Model field | DB column | Notes |
|------------|-----------|-------|
| `source_id` | `source_rowid` | FK → synsets/senses.rowid (resolved to ID) |
| `target_id` | `target_rowid` | FK → synsets/senses.rowid (resolved to ID) |
| `relation_type` | `type_rowid` | FK → relation_types.rowid (resolved to type string) |
| `metadata` | `metadata` | META (JSON) |

### EditRecord ↔ `edit_history` table

| Model field | DB column | Notes |
|------------|-----------|-------|
| `id` | `rowid` | INTEGER PRIMARY KEY |
| `entity_type` | `entity_type` | TEXT NOT NULL |
| `entity_id` | `entity_id` | TEXT NOT NULL |
| `field_name` | `field_name` | TEXT (nullable) |
| `operation` | `operation` | TEXT NOT NULL |
| `old_value` | `old_value` | TEXT (JSON, nullable) |
| `new_value` | `new_value` | TEXT (JSON, nullable) |
| `timestamp` | `timestamp` | TEXT NOT NULL (ISO 8601) |

---

## 4.5 — Mapping to `wn` Types

The editor delegates read queries to `wn` after `commit_to_wn()`. These mappings show how editor models correspond to `wn`'s public classes (defined in `wn/wn/_core.py`).

| Editor Model | `wn` Class | Conversion Notes |
|-------------|-----------|------------------|
| `LexiconModel` | `wn.Lexicon` | Field names match directly. `wn.Lexicon` has `.specifier()` method not on model. |
| `SynsetModel` | `wn.Synset` | `wn.Synset` has `.definition()`, `.definitions()`, `.examples()`, `.senses()`, `.relations()` methods that return child data. Editor model stores these in separate tables. |
| `EntryModel` | `wn.Word` | `wn` calls entries "Words". `wn.Word` has `.lemma()`, `.forms()`, `.senses()` methods. |
| `SenseModel` | `wn.Sense` | `wn.Sense` has `.word()`, `.synset()`, `.relations()`, `.examples()` methods. |
| `FormModel` | `wn.Form` | `wn.Form` is a frozen dataclass with `.value`, `.id`, `.script` attributes. |
| `DefinitionModel` | `wn.Definition` | `wn.Definition` has `.text`, `.language`, `.source_sense_id` attributes. |
| `ExampleModel` | `wn.Example` | `wn.Example` has `.text`, `.language` attributes. |
| `RelationModel` | `wn.Relation` | `wn.Relation` has `.name`, `.source_id`, `.target_id`, `.subtype` properties. |
| `PronunciationModel` | `wn.Pronunciation` | Direct attribute correspondence. |
| `TagModel` | `wn.Tag` | Direct attribute correspondence. |
| `CountModel` | `wn.Count` | `wn.Count` has `.value` attribute. |

---

## 4.6 — Mapping to WN-LMF TypedDicts

These mappings show how editor models convert to/from `wn.lmf` TypedDicts (defined in `wn/wn/lmf.py`) for import/export.

### LexiconModel ↔ `lmf.Lexicon`

| Model field | TypedDict key | Notes |
|------------|---------------|-------|
| `id` | `id` | Required |
| `label` | `label` | Required |
| `language` | `language` | Required |
| `email` | `email` | Required |
| `license` | `license` | Required |
| `version` | `version` | Required |
| `url` | `url` | Optional (default "") |
| `citation` | `citation` | Optional (default "") |
| `logo` | `logo` | Optional (default "", LMF ≥1.1) |
| `metadata` | `meta` | Optional `Metadata | None` |
| — | `entries` | List of `LexicalEntry` (child data) |
| — | `synsets` | List of `Synset` (child data) |
| — | `requires` | List of `Dependency` (LMF ≥1.1) |
| — | `frames` | List of `SyntacticBehaviour` (LMF ≥1.1) |

### SynsetModel ↔ `lmf.Synset`

| Model field | TypedDict key | Notes |
|------------|---------------|-------|
| `id` | `id` | Required |
| `pos` | `partOfSpeech` | Optional |
| `ili` | `ili` | Required (empty string if unmapped) |
| `lexicalized` | `lexicalized` | Optional (default True) |
| `lexfile` | `lexfile` | Optional (default "") |
| `metadata` | `meta` | Optional |
| — | `definitions` | List of `Definition` |
| — | `relations` | List of `Relation` |
| — | `examples` | List of `Example` |
| — | `ili_definition` | `ILIDefinition` (when `ili="in"`) |
| — | `members` | List of sense IDs (LMF ≥1.1) |

### EntryModel ↔ `lmf.LexicalEntry`

| Model field | TypedDict key | Notes |
|------------|---------------|-------|
| `id` | `id` | Required |
| `lemma` | `lemma.writtenForm` | Via nested `Lemma` dict |
| `pos` | `lemma.partOfSpeech` | Via nested `Lemma` dict |
| `index` | `index` | Optional (LMF 1.4) |
| `metadata` | `meta` | Optional |
| — | `forms` | List of `Form` |
| — | `senses` | List of `Sense` |
| — | `frames` | List of `SyntacticBehaviour` (LMF 1.0 only) |

### SenseModel ↔ `lmf.Sense`

| Model field | TypedDict key | Notes |
|------------|---------------|-------|
| `id` | `id` | Required |
| `synset_id` | `synset` | Required |
| `entry_rank` | `n` | Optional (0 means unset) |
| `lexicalized` | `lexicalized` | Optional (default True) |
| `adjposition` | `adjposition` | Optional (default "") |
| `metadata` | `meta` | Optional |
| — | `relations` | List of `Relation` |
| — | `examples` | List of `Example` |
| — | `counts` | List of `Count` |
| — | `subcat` | List of SyntacticBehaviour IDs (LMF ≥1.1) |

### RelationModel ↔ `lmf.Relation`

| Model field | TypedDict key | Notes |
|------------|---------------|-------|
| `target_id` | `target` | Required |
| `relation_type` | `relType` | Required |
| `metadata` | `meta` | Optional (dc:type for "other" relations) |
| `source_id` | — | Implicit from parent (Synset or Sense) |

### DefinitionModel ↔ `lmf.Definition`

| Model field | TypedDict key | Notes |
|------------|---------------|-------|
| `text` | `text` | Required |
| `language` | `language` | Optional |
| `source_sense` | `sourceSense` | Optional |
| `metadata` | `meta` | Optional |

### ExampleModel ↔ `lmf.Example`

| Model field | TypedDict key | Notes |
|------------|---------------|-------|
| `text` | `text` | Required |
| `language` | `language` | Optional |
| `metadata` | `meta` | Optional |

### FormModel ↔ `lmf.Form` / `lmf.Lemma`

When rank = 0, maps to `lmf.Lemma`:

| Model field | TypedDict key | Notes |
|------------|---------------|-------|
| `written_form` | `writtenForm` | Required |
| `script` | `script` | Optional (default "") |
| — | `partOfSpeech` | From parent EntryModel.pos |
| `pronunciations` | `pronunciations` | List of `Pronunciation` |
| `tags` | `tags` | List of `Tag` |

When rank > 0, maps to `lmf.Form`:

| Model field | TypedDict key | Notes |
|------------|---------------|-------|
| `written_form` | `writtenForm` | Required |
| `id` | `id` | Optional (default "") |
| `script` | `script` | Optional (default "") |
| `pronunciations` | `pronunciations` | List of `Pronunciation` |
| `tags` | `tags` | List of `Tag` |
