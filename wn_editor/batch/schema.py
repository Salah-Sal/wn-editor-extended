"""
Data classes and constants for the batch change request system.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Dict, List, Optional


# =============================================================================
# Operation Types
# =============================================================================

class OperationType(str, Enum):
    """Supported batch operations."""
    CREATE_SYNSET = "create_synset"
    ADD_WORD = "add_word"
    DELETE_WORD = "delete_word"
    ADD_DEFINITION = "add_definition"
    MODIFY_DEFINITION = "modify_definition"
    DELETE_DEFINITION = "delete_definition"
    ADD_EXAMPLE = "add_example"
    DELETE_EXAMPLE = "delete_example"
    SET_POS = "set_pos"
    ADD_RELATION = "add_relation"
    DELETE_RELATION = "delete_relation"
    SET_ILI = "set_ili"
    DELETE_ILI = "delete_ili"


# =============================================================================
# Relation Types Mapping
# =============================================================================

# Map user-friendly relation names to database IDs
# These IDs must match the rowids in the wn database's relation_types table
RELATION_TYPES: Dict[str, int] = {
    "also": 1,
    "antonym": 2,
    "attribute": 3,
    "causes": 4,
    "derivation": 5,
    "domain_region": 6,
    "domain_topic": 7,
    "entails": 8,
    "exemplifies": 9,
    "has_domain_region": 10,
    "has_domain_topic": 11,
    "holo_member": 12,
    "holo_part": 13,
    "holo_substance": 14,
    "hypernym": 15,
    "hyponym": 16,
    "instance_hypernym": 17,
    "instance_hyponym": 18,
    "is_caused_by": 19,
    "is_entailed_by": 20,
    "is_exemplified_by": 21,
    "mero_member": 22,
    "mero_part": 23,
    "mero_substance": 24,
    "other": 25,
    "participle": 26,
    "pertainym": 27,
    "similar": 28,
}

# Reverse mapping for display
RELATION_IDS: Dict[int, str] = {v: k for k, v in RELATION_TYPES.items()}


# =============================================================================
# Valid POS Codes
# =============================================================================

VALID_POS = {"n", "v", "a", "r", "s"}


# =============================================================================
# Field Requirements
# =============================================================================

# Required fields for each operation
REQUIRED_FIELDS: Dict[str, List[str]] = {
    OperationType.CREATE_SYNSET.value: ["words", "definition"],
    OperationType.ADD_WORD.value: ["synset", "word"],
    OperationType.DELETE_WORD.value: ["synset", "word"],
    OperationType.ADD_DEFINITION.value: ["synset", "definition"],
    OperationType.MODIFY_DEFINITION.value: ["synset", "definition"],
    OperationType.DELETE_DEFINITION.value: ["synset"],
    OperationType.ADD_EXAMPLE.value: ["synset", "example"],
    OperationType.DELETE_EXAMPLE.value: ["synset", "example"],
    OperationType.SET_POS.value: ["synset", "pos"],
    OperationType.ADD_RELATION.value: ["source", "target", "type"],
    OperationType.DELETE_RELATION.value: ["source", "target", "type"],
    OperationType.SET_ILI.value: ["synset", "ili"],
    OperationType.DELETE_ILI.value: ["synset"],
}

# Optional fields for each operation
OPTIONAL_FIELDS: Dict[str, List[str]] = {
    OperationType.CREATE_SYNSET.value: ["pos", "examples", "relations"],
    OperationType.ADD_WORD.value: ["pos"],
    OperationType.DELETE_WORD.value: [],
    OperationType.ADD_DEFINITION.value: ["language"],
    OperationType.MODIFY_DEFINITION.value: ["index", "language"],
    OperationType.DELETE_DEFINITION.value: ["index"],
    OperationType.ADD_EXAMPLE.value: ["language"],
    OperationType.DELETE_EXAMPLE.value: [],
    OperationType.SET_POS.value: [],
    OperationType.ADD_RELATION.value: [],
    OperationType.DELETE_RELATION.value: [],
    OperationType.SET_ILI.value: [],
    OperationType.DELETE_ILI.value: [],
}


# =============================================================================
# Data Classes
# =============================================================================

@dataclass
class WordSpec:
    """Specification for a word in a synset."""
    word: str
    pos: Optional[str] = None


@dataclass
class Change:
    """Single change operation."""
    operation: str
    params: Dict[str, Any]
    line_number: Optional[int] = None

    @property
    def synset(self) -> Optional[str]:
        """Get synset ID if present in params."""
        return self.params.get("synset")

    @property
    def source(self) -> Optional[str]:
        """Get source synset ID for relation operations."""
        return self.params.get("source")

    @property
    def target(self) -> Optional[str]:
        """Get target synset ID for relation operations."""
        return self.params.get("target")


@dataclass
class ChangeRequest:
    """Parsed change request from YAML."""
    lexicon: str
    changes: List[Change]
    session_name: Optional[str] = None
    session_description: Optional[str] = None
    source_file: Optional[Path] = None


@dataclass
class ValidationError:
    """Validation error for a specific change."""
    index: int
    operation: str
    field: str
    message: str
    line_number: Optional[int] = None


@dataclass
class ValidationWarning:
    """Validation warning for a specific change."""
    index: int
    operation: str
    message: str
    line_number: Optional[int] = None


@dataclass
class ValidationResult:
    """Result of validating a change request."""
    is_valid: bool
    errors: List[ValidationError] = field(default_factory=list)
    warnings: List[ValidationWarning] = field(default_factory=list)

    @property
    def error_count(self) -> int:
        return len(self.errors)

    @property
    def warning_count(self) -> int:
        return len(self.warnings)


@dataclass
class ChangeResult:
    """Result of executing a single change."""
    index: int
    operation: str
    success: bool
    message: str
    target: Optional[str] = None
    created_id: Optional[str] = None
    error: Optional[str] = None


@dataclass
class BatchResult:
    """Result of executing a batch change request."""
    session_id: Optional[int]
    total_count: int
    success_count: int
    failure_count: int
    changes: List[ChangeResult]
    duration_seconds: float

    @property
    def skipped_count(self) -> int:
        return self.total_count - self.success_count - self.failure_count
