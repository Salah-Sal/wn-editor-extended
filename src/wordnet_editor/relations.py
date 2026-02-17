"""Relation type constants and inverse mapping for wordnet-editor."""

from __future__ import annotations

# Complete bidirectional mapping of relation types to their inverses.
# Source: wn/wn/constants.py REVERSE_RELATIONS dict.

SYNSET_RELATION_INVERSES: dict[str, str] = {
    # Asymmetric pairs
    "hypernym": "hyponym",
    "hyponym": "hypernym",
    "instance_hypernym": "instance_hyponym",
    "instance_hyponym": "instance_hypernym",
    "meronym": "holonym",
    "holonym": "meronym",
    "mero_location": "holo_location",
    "holo_location": "mero_location",
    "mero_member": "holo_member",
    "holo_member": "mero_member",
    "mero_part": "holo_part",
    "holo_part": "mero_part",
    "mero_portion": "holo_portion",
    "holo_portion": "mero_portion",
    "mero_substance": "holo_substance",
    "holo_substance": "mero_substance",
    "state_of": "be_in_state",
    "be_in_state": "state_of",
    "causes": "is_caused_by",
    "is_caused_by": "causes",
    "subevent": "is_subevent_of",
    "is_subevent_of": "subevent",
    "manner_of": "in_manner",
    "in_manner": "manner_of",
    "restricts": "restricted_by",
    "restricted_by": "restricts",
    "classifies": "classified_by",
    "classified_by": "classifies",
    "entails": "is_entailed_by",
    "is_entailed_by": "entails",
    "domain_topic": "has_domain_topic",
    "has_domain_topic": "domain_topic",
    "domain_region": "has_domain_region",
    "has_domain_region": "domain_region",
    "exemplifies": "is_exemplified_by",
    "is_exemplified_by": "exemplifies",
    "role": "involved",
    "involved": "role",
    "agent": "involved_agent",
    "involved_agent": "agent",
    "patient": "involved_patient",
    "involved_patient": "patient",
    "result": "involved_result",
    "involved_result": "result",
    "instrument": "involved_instrument",
    "involved_instrument": "instrument",
    "location": "involved_location",
    "involved_location": "location",
    "direction": "involved_direction",
    "involved_direction": "direction",
    "target_direction": "involved_target_direction",
    "involved_target_direction": "target_direction",
    "source_direction": "involved_source_direction",
    "involved_source_direction": "source_direction",
    "co_agent_patient": "co_patient_agent",
    "co_patient_agent": "co_agent_patient",
    "co_agent_instrument": "co_instrument_agent",
    "co_instrument_agent": "co_agent_instrument",
    "co_agent_result": "co_result_agent",
    "co_result_agent": "co_agent_result",
    "co_patient_instrument": "co_instrument_patient",
    "co_instrument_patient": "co_patient_instrument",
    "co_result_instrument": "co_instrument_result",
    "co_instrument_result": "co_result_instrument",
    "feminine": "has_feminine",
    "has_feminine": "feminine",
    "masculine": "has_masculine",
    "has_masculine": "masculine",
    "young": "has_young",
    "has_young": "young",
    "diminutive": "has_diminutive",
    "has_diminutive": "diminutive",
    "augmentative": "has_augmentative",
    "has_augmentative": "augmentative",
    # Symmetric (map to themselves)
    "antonym": "antonym",
    "eq_synonym": "eq_synonym",
    "similar": "similar",
    "attribute": "attribute",
    "co_role": "co_role",
    "ir_synonym": "ir_synonym",
    "anto_gradable": "anto_gradable",
    "anto_simple": "anto_simple",
    "anto_converse": "anto_converse",
}

SENSE_RELATION_INVERSES: dict[str, str] = {
    # Asymmetric pairs (subset relevant to sense relations)
    "agent": "involved_agent",
    "involved_agent": "agent",
    "patient": "involved_patient",
    "involved_patient": "patient",
    "result": "involved_result",
    "involved_result": "result",
    "instrument": "involved_instrument",
    "involved_instrument": "instrument",
    "location": "involved_location",
    "involved_location": "location",
    "direction": "involved_direction",
    "involved_direction": "direction",
    "target_direction": "involved_target_direction",
    "involved_target_direction": "target_direction",
    "source_direction": "involved_source_direction",
    "involved_source_direction": "source_direction",
    "domain_topic": "has_domain_topic",
    "has_domain_topic": "domain_topic",
    "domain_region": "has_domain_region",
    "has_domain_region": "domain_region",
    "exemplifies": "is_exemplified_by",
    "is_exemplified_by": "exemplifies",
    "feminine": "has_feminine",
    "has_feminine": "feminine",
    "masculine": "has_masculine",
    "has_masculine": "masculine",
    "young": "has_young",
    "has_young": "young",
    "diminutive": "has_diminutive",
    "has_diminutive": "diminutive",
    "augmentative": "has_augmentative",
    "has_augmentative": "augmentative",
    "metaphor": "has_metaphor",
    "has_metaphor": "metaphor",
    "metonym": "has_metonym",
    "has_metonym": "metonym",
    "simple_aspect_ip": "simple_aspect_pi",
    "simple_aspect_pi": "simple_aspect_ip",
    "secondary_aspect_ip": "secondary_aspect_pi",
    "secondary_aspect_pi": "secondary_aspect_ip",
    "co_agent_patient": "co_patient_agent",
    "co_patient_agent": "co_agent_patient",
    "co_agent_instrument": "co_instrument_agent",
    "co_instrument_agent": "co_agent_instrument",
    "co_agent_result": "co_result_agent",
    "co_result_agent": "co_agent_result",
    "co_patient_instrument": "co_instrument_patient",
    "co_instrument_patient": "co_patient_instrument",
    "co_result_instrument": "co_instrument_result",
    "co_instrument_result": "co_result_instrument",
    # Symmetric
    "antonym": "antonym",
    "similar": "similar",
    "derivation": "derivation",
    "anto_gradable": "anto_gradable",
    "anto_simple": "anto_simple",
    "anto_converse": "anto_converse",
}

# Valid relation type sets for validation
def _load_enum(name: str) -> frozenset[str]:
    """Lazily load enum values from models to avoid circular imports."""
    import importlib
    mod = importlib.import_module("wordnet_editor.models")
    return frozenset(m.value for m in getattr(mod, name))


SYNSET_RELATIONS: frozenset[str] = _load_enum("SynsetRelationType")
SENSE_RELATIONS: frozenset[str] = _load_enum("SenseRelationType")
SENSE_SYNSET_RELATIONS: frozenset[str] = _load_enum(
    "SenseSynsetRelationType"
)


def get_synset_inverse(relation_type: str) -> str | None:
    """Get the inverse of a synset relation type, or None if no inverse."""
    return SYNSET_RELATION_INVERSES.get(relation_type)


def get_sense_inverse(relation_type: str) -> str | None:
    """Get the inverse of a sense relation type, or None if no inverse."""
    return SENSE_RELATION_INVERSES.get(relation_type)


def is_symmetric(relation_type: str) -> bool:
    """Check if a relation type is symmetric (maps to itself)."""
    for inverses in (SYNSET_RELATION_INVERSES, SENSE_RELATION_INVERSES):
        if relation_type in inverses:
            return inverses[relation_type] == relation_type
    return False


def is_valid_synset_relation(relation_type: str) -> bool:
    """Check if a string is a valid synset relation type."""
    return relation_type in SYNSET_RELATIONS


def is_valid_sense_relation(relation_type: str) -> bool:
    """Check if a string is a valid sense relation type."""
    return relation_type in SENSE_RELATIONS


def is_valid_sense_synset_relation(relation_type: str) -> bool:
    """Check if a string is a valid sense-synset relation type."""
    return relation_type in SENSE_SYNSET_RELATIONS
