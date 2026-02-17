"""Domain model dataclasses and enums for wordnet-editor."""

from __future__ import annotations

from dataclasses import dataclass
from enum import Enum
from typing import Any

# ---------------------------------------------------------------------------
# Enums
# ---------------------------------------------------------------------------

class PartOfSpeech(str, Enum):
    """Part-of-speech tags for lexical entries and synsets."""

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


class AdjPosition(str, Enum):
    """Syntactic position of an adjective relative to a noun."""

    ATTRIBUTIVE = "a"
    IMMEDIATE_POSTNOMINAL = "ip"
    PREDICATIVE = "p"


class SynsetRelationType(str, Enum):
    """Valid relation types between synsets."""

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


class SenseRelationType(str, Enum):
    """Valid relation types between senses."""

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


class SenseSynsetRelationType(str, Enum):
    """Valid relation types from a sense to a synset."""

    OTHER = "other"
    DOMAIN_TOPIC = "domain_topic"
    DOMAIN_REGION = "domain_region"
    EXEMPLIFIES = "exemplifies"


class EditOperation(str, Enum):
    """Type of mutation recorded in the edit history."""

    CREATE = "CREATE"
    UPDATE = "UPDATE"
    DELETE = "DELETE"


class ValidationSeverity(str, Enum):
    """Severity level for validation results."""

    ERROR = "ERROR"
    WARNING = "WARNING"


# ---------------------------------------------------------------------------
# Dataclasses
# ---------------------------------------------------------------------------

@dataclass(frozen=True, slots=True)
class LexiconModel:
    """A WordNet lexicon (language-specific resource container)."""

    id: str
    label: str
    language: str
    email: str
    license: str
    version: str
    url: str | None
    citation: str | None
    logo: str | None
    metadata: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class SynsetModel:
    """A synset (set of synonymous senses sharing a concept)."""

    id: str
    lexicon_id: str
    pos: str | None
    ili: str | None
    lexicalized: bool
    lexfile: str | None
    metadata: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class EntryModel:
    """A lexical entry (word + part of speech)."""

    id: str
    lexicon_id: str
    lemma: str
    pos: str
    index: str | None
    metadata: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class SenseModel:
    """A sense linking a lexical entry to a synset."""

    id: str
    entry_id: str
    synset_id: str
    lexicon_id: str
    entry_rank: int
    synset_rank: int
    lexicalized: bool
    adjposition: str | None
    metadata: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class FormModel:
    """A written form of a lexical entry (lemma or variant)."""

    written_form: str
    id: str | None
    script: str | None
    rank: int
    pronunciations: tuple[PronunciationModel, ...]
    tags: tuple[TagModel, ...]


@dataclass(frozen=True, slots=True)
class PronunciationModel:
    """A pronunciation of a written form."""

    value: str
    variety: str | None
    notation: str | None
    phonemic: bool
    audio: str | None


@dataclass(frozen=True, slots=True)
class TagModel:
    """A categorized tag attached to a form."""

    tag: str
    category: str


@dataclass(frozen=True, slots=True)
class DefinitionModel:
    """A definition of a synset, optionally language-tagged."""

    text: str
    language: str | None
    source_sense: str | None
    metadata: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class ExampleModel:
    """A usage example for a synset or sense."""

    text: str
    language: str | None
    metadata: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class RelationModel:
    """A typed, directed relation between two entities."""

    source_id: str
    target_id: str
    relation_type: str
    metadata: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class ILIModel:
    """An Interlingual Index entry linking synsets across languages."""

    id: str
    status: str
    definition: str | None
    metadata: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class ProposedILIModel:
    """A proposed new ILI entry awaiting approval."""

    synset_id: str
    definition: str
    metadata: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class CountModel:
    """A frequency count associated with a sense."""

    value: int
    metadata: dict[str, Any] | None


@dataclass(frozen=True, slots=True)
class SyntacticBehaviourModel:
    """A subcategorization frame shared by one or more senses."""

    id: str | None
    frame: str
    sense_ids: tuple[str, ...]


@dataclass(frozen=True, slots=True)
class EditRecord:
    """A single edit-history entry recording one field-level change."""

    id: int
    entity_type: str
    entity_id: str
    field_name: str | None
    operation: str
    old_value: str | None
    new_value: str | None
    timestamp: str


@dataclass(frozen=True, slots=True)
class ValidationResult:
    """A single validation finding (error or warning)."""

    rule_id: str
    severity: str
    entity_type: str
    entity_id: str
    message: str
    details: dict[str, Any] | None
