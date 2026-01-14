"""
Batch change request module for wn-editor-extended.

This module provides functionality to submit standardized change requests
in YAML format to modify WordNet databases.

Example usage:
    from wn_editor.batch import (
        load_change_request,
        validate_change_request,
        execute_change_request,
    )

    # Load from YAML file
    request = load_change_request("changes.yaml")

    # Validate before execution
    validation = validate_change_request(request)
    if not validation.is_valid:
        for error in validation.errors:
            print(f"[{error.index}] {error.operation}: {error.message}")

    # Execute with change tracking
    result = execute_change_request(request)
    print(f"Applied {result.success_count}/{result.total_count} changes")
"""

from .schema import (
    # Enums and constants
    OperationType as OperationType,
    RELATION_TYPES as RELATION_TYPES,
    RELATION_IDS as RELATION_IDS,
    VALID_POS as VALID_POS,
    REQUIRED_FIELDS as REQUIRED_FIELDS,
    OPTIONAL_FIELDS as OPTIONAL_FIELDS,
    # Data classes
    WordSpec as WordSpec,
    Change as Change,
    ChangeRequest as ChangeRequest,
    ValidationError as ValidationError,
    ValidationWarning as ValidationWarning,
    ValidationResult as ValidationResult,
    ChangeResult as ChangeResult,
    BatchResult as BatchResult,
)

from .parser import (
    load_change_request as load_change_request,
    load_yaml_file as load_yaml_file,
    ParseError as ParseError,
)

from .validator import (
    validate_change_request as validate_change_request,
)

from .executor import (
    execute_change_request as execute_change_request,
)

__all__ = [
    # Enums and constants
    "OperationType",
    "RELATION_TYPES",
    "RELATION_IDS",
    "VALID_POS",
    "REQUIRED_FIELDS",
    "OPTIONAL_FIELDS",
    # Data classes
    "WordSpec",
    "Change",
    "ChangeRequest",
    "ValidationError",
    "ValidationWarning",
    "ValidationResult",
    "ChangeResult",
    "BatchResult",
    # Functions
    "load_change_request",
    "load_yaml_file",
    "validate_change_request",
    "execute_change_request",
    # Exceptions
    "ParseError",
]
