"""
Validation for batch change requests.

Provides both schema validation (required fields, types) and
referential validation (synset IDs exist, relation types valid).
"""
from __future__ import annotations

import logging
from typing import List, Optional, Set

import wn

from .schema import (
    Change,
    ChangeRequest,
    OperationType,
    RELATION_TYPES,
    REQUIRED_FIELDS,
    VALID_POS,
    ValidationError,
    ValidationResult,
    ValidationWarning,
)

logger = logging.getLogger(__name__)


def validate_change_request(
    request: ChangeRequest,
    check_references: bool = True,
) -> ValidationResult:
    """Validate a change request.

    Args:
        request: The change request to validate
        check_references: If True, verify synset IDs exist in database

    Returns:
        ValidationResult with errors and warnings
    """
    errors: List[ValidationError] = []
    warnings: List[ValidationWarning] = []

    # Validate lexicon exists
    if check_references:
        lexicon_error = _validate_lexicon(request.lexicon)
        if lexicon_error:
            errors.append(
                ValidationError(
                    index=-1,
                    operation="",
                    field="lexicon",
                    message=lexicon_error,
                )
            )

    # Validate each change
    for i, change in enumerate(request.changes):
        change_errors, change_warnings = _validate_change(
            change,
            index=i,
            lexicon=request.lexicon,
            check_references=check_references,
        )
        errors.extend(change_errors)
        warnings.extend(change_warnings)

    return ValidationResult(
        is_valid=len(errors) == 0,
        errors=errors,
        warnings=warnings,
    )


def _validate_lexicon(lexicon: str) -> Optional[str]:
    """Validate that the lexicon exists.

    Returns:
        Error message if invalid, None if valid
    """
    try:
        lexicons = wn.lexicons()
        lexicon_ids = [lex.id for lex in lexicons]  # id is a property, not a method
        if lexicon not in lexicon_ids:
            return f"Lexicon '{lexicon}' not found. Available: {', '.join(lexicon_ids)}"
        return None
    except Exception as e:
        logger.debug(f"Error checking lexicon: {e}")
        return f"Error checking lexicon: {e}"


def _validate_change(
    change: Change,
    index: int,
    lexicon: str,
    check_references: bool,
) -> tuple[List[ValidationError], List[ValidationWarning]]:
    """Validate a single change operation.

    Returns:
        Tuple of (errors, warnings)
    """
    errors: List[ValidationError] = []
    warnings: List[ValidationWarning] = []

    # Validate operation type
    valid_operations = {op.value for op in OperationType}
    if change.operation not in valid_operations:
        errors.append(
            ValidationError(
                index=index,
                operation=change.operation,
                field="operation",
                message=f"Unknown operation '{change.operation}'. Valid: {', '.join(sorted(valid_operations))}",
                line_number=change.line_number,
            )
        )
        return errors, warnings

    # Validate required fields
    required = REQUIRED_FIELDS.get(change.operation, [])
    for field in required:
        if field not in change.params or change.params[field] is None:
            errors.append(
                ValidationError(
                    index=index,
                    operation=change.operation,
                    field=field,
                    message=f"Missing required field '{field}'",
                    line_number=change.line_number,
                )
            )

    # Operation-specific validation
    op = change.operation

    if op == OperationType.CREATE_SYNSET.value:
        errors.extend(_validate_create_synset(change, index, lexicon, check_references))

    elif op in (OperationType.ADD_WORD.value, OperationType.DELETE_WORD.value):
        errors.extend(_validate_word_op(change, index, lexicon, check_references))

    elif op in (
        OperationType.ADD_DEFINITION.value,
        OperationType.MODIFY_DEFINITION.value,
        OperationType.DELETE_DEFINITION.value,
    ):
        errors.extend(_validate_definition_op(change, index, lexicon, check_references))

    elif op in (OperationType.ADD_EXAMPLE.value, OperationType.DELETE_EXAMPLE.value):
        errors.extend(_validate_example_op(change, index, lexicon, check_references))

    elif op == OperationType.SET_POS.value:
        errors.extend(_validate_set_pos(change, index, lexicon, check_references))

    elif op in (OperationType.ADD_RELATION.value, OperationType.DELETE_RELATION.value):
        errors.extend(_validate_relation_op(change, index, lexicon, check_references))

    elif op in (OperationType.SET_ILI.value, OperationType.DELETE_ILI.value):
        errors.extend(_validate_ili_op(change, index, lexicon, check_references))

    return errors, warnings


def _validate_create_synset(
    change: Change,
    index: int,
    lexicon: str,
    check_references: bool,
) -> List[ValidationError]:
    """Validate create_synset operation."""
    errors: List[ValidationError] = []

    # Validate words list
    words = change.params.get("words", [])
    if not isinstance(words, list):
        errors.append(
            ValidationError(
                index=index,
                operation=change.operation,
                field="words",
                message="Field 'words' must be a list",
                line_number=change.line_number,
            )
        )
    elif len(words) == 0:
        errors.append(
            ValidationError(
                index=index,
                operation=change.operation,
                field="words",
                message="Field 'words' cannot be empty",
                line_number=change.line_number,
            )
        )
    else:
        for i, word_spec in enumerate(words):
            if isinstance(word_spec, str):
                # Simple string word is OK
                continue
            elif isinstance(word_spec, dict):
                if "word" not in word_spec:
                    errors.append(
                        ValidationError(
                            index=index,
                            operation=change.operation,
                            field=f"words[{i}]",
                            message="Word spec missing 'word' field",
                            line_number=change.line_number,
                        )
                    )
                if "pos" in word_spec and word_spec["pos"] not in VALID_POS:
                    errors.append(
                        ValidationError(
                            index=index,
                            operation=change.operation,
                            field=f"words[{i}].pos",
                            message=f"Invalid POS '{word_spec['pos']}'. Valid: {', '.join(sorted(VALID_POS))}",
                            line_number=change.line_number,
                        )
                    )
            else:
                errors.append(
                    ValidationError(
                        index=index,
                        operation=change.operation,
                        field=f"words[{i}]",
                        message="Word must be a string or {word: ..., pos: ...}",
                        line_number=change.line_number,
                    )
                )

    # Validate definition
    definition = change.params.get("definition")
    if definition is not None and not isinstance(definition, str):
        errors.append(
            ValidationError(
                index=index,
                operation=change.operation,
                field="definition",
                message="Field 'definition' must be a string",
                line_number=change.line_number,
            )
        )

    # Validate POS if provided
    pos = change.params.get("pos")
    if pos is not None and pos not in VALID_POS:
        errors.append(
            ValidationError(
                index=index,
                operation=change.operation,
                field="pos",
                message=f"Invalid POS '{pos}'. Valid: {', '.join(sorted(VALID_POS))}",
                line_number=change.line_number,
            )
        )

    # Validate relations if provided
    relations = change.params.get("relations", {})
    if relations and check_references:
        errors.extend(_validate_relations_block(relations, index, change, lexicon))

    return errors


def _validate_relations_block(
    relations: dict,
    index: int,
    change: Change,
    lexicon: str,
) -> List[ValidationError]:
    """Validate a relations block in create_synset."""
    errors: List[ValidationError] = []

    if not isinstance(relations, dict):
        errors.append(
            ValidationError(
                index=index,
                operation=change.operation,
                field="relations",
                message="Field 'relations' must be a mapping",
                line_number=change.line_number,
            )
        )
        return errors

    for rel_type, targets in relations.items():
        if rel_type not in RELATION_TYPES:
            errors.append(
                ValidationError(
                    index=index,
                    operation=change.operation,
                    field=f"relations.{rel_type}",
                    message=f"Unknown relation type '{rel_type}'",
                    line_number=change.line_number,
                )
            )
            continue

        if not isinstance(targets, list):
            targets = [targets]

        for target in targets:
            error = _validate_synset_exists(target, lexicon)
            if error:
                errors.append(
                    ValidationError(
                        index=index,
                        operation=change.operation,
                        field=f"relations.{rel_type}",
                        message=error,
                        line_number=change.line_number,
                    )
                )

    return errors


def _validate_word_op(
    change: Change,
    index: int,
    lexicon: str,
    check_references: bool,
) -> List[ValidationError]:
    """Validate add_word or delete_word operation."""
    errors: List[ValidationError] = []

    # Validate synset reference
    synset_id = change.params.get("synset")
    if synset_id and check_references:
        error = _validate_synset_exists(synset_id, lexicon)
        if error:
            errors.append(
                ValidationError(
                    index=index,
                    operation=change.operation,
                    field="synset",
                    message=error,
                    line_number=change.line_number,
                )
            )

    # Validate word field
    word = change.params.get("word")
    if word is not None and not isinstance(word, str):
        errors.append(
            ValidationError(
                index=index,
                operation=change.operation,
                field="word",
                message="Field 'word' must be a string",
                line_number=change.line_number,
            )
        )

    # Validate POS if provided
    pos = change.params.get("pos")
    if pos is not None and pos not in VALID_POS:
        errors.append(
            ValidationError(
                index=index,
                operation=change.operation,
                field="pos",
                message=f"Invalid POS '{pos}'. Valid: {', '.join(sorted(VALID_POS))}",
                line_number=change.line_number,
            )
        )

    return errors


def _validate_definition_op(
    change: Change,
    index: int,
    lexicon: str,
    check_references: bool,
) -> List[ValidationError]:
    """Validate definition operations."""
    errors: List[ValidationError] = []

    # Validate synset reference
    synset_id = change.params.get("synset")
    if synset_id and check_references:
        error = _validate_synset_exists(synset_id, lexicon)
        if error:
            errors.append(
                ValidationError(
                    index=index,
                    operation=change.operation,
                    field="synset",
                    message=error,
                    line_number=change.line_number,
                )
            )

    # Validate definition field for add/modify
    if change.operation in (
        OperationType.ADD_DEFINITION.value,
        OperationType.MODIFY_DEFINITION.value,
    ):
        definition = change.params.get("definition")
        if definition is not None and not isinstance(definition, str):
            errors.append(
                ValidationError(
                    index=index,
                    operation=change.operation,
                    field="definition",
                    message="Field 'definition' must be a string",
                    line_number=change.line_number,
                )
            )

    # Validate index field
    idx = change.params.get("index")
    if idx is not None and not isinstance(idx, int):
        errors.append(
            ValidationError(
                index=index,
                operation=change.operation,
                field="index",
                message="Field 'index' must be an integer",
                line_number=change.line_number,
            )
        )

    return errors


def _validate_example_op(
    change: Change,
    index: int,
    lexicon: str,
    check_references: bool,
) -> List[ValidationError]:
    """Validate example operations."""
    errors: List[ValidationError] = []

    # Validate synset reference
    synset_id = change.params.get("synset")
    if synset_id and check_references:
        error = _validate_synset_exists(synset_id, lexicon)
        if error:
            errors.append(
                ValidationError(
                    index=index,
                    operation=change.operation,
                    field="synset",
                    message=error,
                    line_number=change.line_number,
                )
            )

    # Validate example field
    example = change.params.get("example")
    if example is not None and not isinstance(example, str):
        errors.append(
            ValidationError(
                index=index,
                operation=change.operation,
                field="example",
                message="Field 'example' must be a string",
                line_number=change.line_number,
            )
        )

    return errors


def _validate_set_pos(
    change: Change,
    index: int,
    lexicon: str,
    check_references: bool,
) -> List[ValidationError]:
    """Validate set_pos operation."""
    errors: List[ValidationError] = []

    # Validate synset reference
    synset_id = change.params.get("synset")
    if synset_id and check_references:
        error = _validate_synset_exists(synset_id, lexicon)
        if error:
            errors.append(
                ValidationError(
                    index=index,
                    operation=change.operation,
                    field="synset",
                    message=error,
                    line_number=change.line_number,
                )
            )

    # Validate POS
    pos = change.params.get("pos")
    if pos is not None and pos not in VALID_POS:
        errors.append(
            ValidationError(
                index=index,
                operation=change.operation,
                field="pos",
                message=f"Invalid POS '{pos}'. Valid: {', '.join(sorted(VALID_POS))}",
                line_number=change.line_number,
            )
        )

    return errors


def _validate_relation_op(
    change: Change,
    index: int,
    lexicon: str,
    check_references: bool,
) -> List[ValidationError]:
    """Validate relation operations."""
    errors: List[ValidationError] = []

    # Validate source synset
    source = change.params.get("source")
    if source and check_references:
        error = _validate_synset_exists(source, lexicon)
        if error:
            errors.append(
                ValidationError(
                    index=index,
                    operation=change.operation,
                    field="source",
                    message=error,
                    line_number=change.line_number,
                )
            )

    # Validate target synset
    target = change.params.get("target")
    if target and check_references:
        error = _validate_synset_exists(target, lexicon)
        if error:
            errors.append(
                ValidationError(
                    index=index,
                    operation=change.operation,
                    field="target",
                    message=error,
                    line_number=change.line_number,
                )
            )

    # Validate relation type
    rel_type = change.params.get("type")
    if rel_type is not None and rel_type not in RELATION_TYPES:
        errors.append(
            ValidationError(
                index=index,
                operation=change.operation,
                field="type",
                message=f"Unknown relation type '{rel_type}'. Valid: {', '.join(sorted(RELATION_TYPES.keys()))}",
                line_number=change.line_number,
            )
        )

    return errors


def _validate_ili_op(
    change: Change,
    index: int,
    lexicon: str,
    check_references: bool,
) -> List[ValidationError]:
    """Validate ILI operations."""
    errors: List[ValidationError] = []

    # Validate synset reference
    synset_id = change.params.get("synset")
    if synset_id and check_references:
        error = _validate_synset_exists(synset_id, lexicon)
        if error:
            errors.append(
                ValidationError(
                    index=index,
                    operation=change.operation,
                    field="synset",
                    message=error,
                    line_number=change.line_number,
                )
            )

    # Validate ILI format for set_ili
    if change.operation == OperationType.SET_ILI.value:
        ili = change.params.get("ili")
        if ili is not None and not isinstance(ili, str):
            errors.append(
                ValidationError(
                    index=index,
                    operation=change.operation,
                    field="ili",
                    message="Field 'ili' must be a string",
                    line_number=change.line_number,
                )
            )

    return errors


def _validate_synset_exists(synset_id: str, lexicon: str) -> Optional[str]:
    """Check if a synset exists in the database.

    Returns:
        Error message if not found, None if exists
    """
    try:
        # Try to find the synset
        synset = wn.synset(id=synset_id)
        if synset is None:
            return f"Synset '{synset_id}' not found"
        return None
    except wn.Error as e:
        return f"Synset '{synset_id}' not found: {e}"
    except Exception as e:
        logger.debug(f"Error checking synset {synset_id}: {e}")
        return f"Error checking synset '{synset_id}': {e}"
