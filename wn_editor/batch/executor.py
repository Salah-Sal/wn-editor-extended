"""
Executor for batch change requests.

Applies changes to the WordNet database using the editor classes.
"""
from __future__ import annotations

import logging
import time
from typing import Any, Dict, List, Optional

import wn

from .schema import (
    BatchResult,
    Change,
    ChangeRequest,
    ChangeResult,
    OperationType,
    RELATION_TYPES,
)

logger = logging.getLogger(__name__)


def execute_change_request(
    request: ChangeRequest,
    dry_run: bool = False,
    enable_tracking: bool = True,
) -> BatchResult:
    """Execute a batch change request.

    Args:
        request: The change request to execute
        dry_run: If True, only simulate execution without making changes
        enable_tracking: If True, use changelog tracking for this batch

    Returns:
        BatchResult with details of each change
    """
    start_time = time.time()
    results: List[ChangeResult] = []
    session_id: Optional[int] = None

    # Import here to avoid circular imports
    from ..editor import LexiconEditor, SynsetEditor, _set_relation_to_synset
    from ..changelog import (
        enable_tracking as _enable_tracking,
        disable_tracking as _disable_tracking,
        tracking_session,
        is_tracking_enabled,
        pre_change_hook,
        post_change_hook,
    )
    from ..editor import set_changelog_hooks, clear_changelog_hooks

    # Set up tracking context
    tracking_context = None
    if enable_tracking and not dry_run:
        if not is_tracking_enabled():
            _enable_tracking()
        set_changelog_hooks(pre_change_hook, post_change_hook)

        session_name = request.session_name or f"Batch changes to {request.lexicon}"
        tracking_context = tracking_session(session_name, request.session_description)
        session = tracking_context.__enter__()
        session_id = session.id

    try:
        # Get lexicon editor
        lex_editor = LexiconEditor(request.lexicon)

        # Execute each change
        for i, change in enumerate(request.changes):
            result = _execute_change(
                change=change,
                index=i,
                lex_editor=lex_editor,
                lexicon=request.lexicon,
                dry_run=dry_run,
            )
            results.append(result)

    finally:
        # Clean up tracking context
        if tracking_context:
            tracking_context.__exit__(None, None, None)
            clear_changelog_hooks()

    # Calculate totals
    success_count = sum(1 for r in results if r.success)
    failure_count = sum(1 for r in results if not r.success)
    duration = time.time() - start_time

    return BatchResult(
        session_id=session_id,
        total_count=len(results),
        success_count=success_count,
        failure_count=failure_count,
        changes=results,
        duration_seconds=duration,
    )


def _execute_change(
    change: Change,
    index: int,
    lex_editor: Any,  # LexiconEditor
    lexicon: str,
    dry_run: bool,
) -> ChangeResult:
    """Execute a single change operation.

    Returns:
        ChangeResult with success/failure status
    """
    op = change.operation

    try:
        if dry_run:
            return _dry_run_change(change, index, lexicon)

        if op == OperationType.CREATE_SYNSET.value:
            return _exec_create_synset(change, index, lex_editor)

        elif op == OperationType.ADD_WORD.value:
            return _exec_add_word(change, index, lexicon)

        elif op == OperationType.DELETE_WORD.value:
            return _exec_delete_word(change, index, lexicon)

        elif op == OperationType.ADD_DEFINITION.value:
            return _exec_add_definition(change, index, lexicon)

        elif op == OperationType.MODIFY_DEFINITION.value:
            return _exec_modify_definition(change, index, lexicon)

        elif op == OperationType.DELETE_DEFINITION.value:
            return _exec_delete_definition(change, index, lexicon)

        elif op == OperationType.ADD_EXAMPLE.value:
            return _exec_add_example(change, index, lexicon)

        elif op == OperationType.DELETE_EXAMPLE.value:
            return _exec_delete_example(change, index, lexicon)

        elif op == OperationType.SET_POS.value:
            return _exec_set_pos(change, index, lexicon)

        elif op == OperationType.ADD_RELATION.value:
            return _exec_add_relation(change, index, lexicon)

        elif op == OperationType.DELETE_RELATION.value:
            return _exec_delete_relation(change, index, lexicon)

        elif op == OperationType.SET_ILI.value:
            return _exec_set_ili(change, index, lexicon)

        elif op == OperationType.DELETE_ILI.value:
            return _exec_delete_ili(change, index, lexicon)

        else:
            return ChangeResult(
                index=index,
                operation=op,
                success=False,
                message=f"Unknown operation: {op}",
                error=f"Unknown operation: {op}",
            )

    except Exception as e:
        logger.exception(f"Error executing change #{index + 1} ({op})")
        return ChangeResult(
            index=index,
            operation=op,
            success=False,
            message=f"Error: {e}",
            error=str(e),
        )


def _dry_run_change(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Simulate a change without actually executing it."""
    op = change.operation
    target = change.synset or change.source or "new synset"

    return ChangeResult(
        index=index,
        operation=op,
        success=True,
        message=f"Would execute {op}",
        target=target,
    )


def _exec_create_synset(
    change: Change,
    index: int,
    lex_editor: Any,
) -> ChangeResult:
    """Execute create_synset operation."""
    from ..editor import SynsetEditor, _set_relation_to_synset

    synset_editor = lex_editor.create_synset()

    # Add words
    words = change.params.get("words", [])
    pos = change.params.get("pos")

    for word_spec in words:
        if isinstance(word_spec, str):
            word = word_spec
            word_pos = pos
        else:
            word = word_spec.get("word")
            word_pos = word_spec.get("pos", pos)

        synset_editor.add_word(word, pos=word_pos)

    # Add definition
    definition = change.params.get("definition")
    if definition:
        language = change.params.get("language")
        synset_editor.add_definition(definition, language=language)

    # Add examples
    examples = change.params.get("examples", [])
    for example in examples:
        synset_editor.add_example(example)

    # Get the created synset
    synset = synset_editor.as_synset()
    synset_id = synset.id if synset else None

    # Add relations
    relations = change.params.get("relations", {})
    for rel_type_name, targets in relations.items():
        if rel_type_name in RELATION_TYPES:
            rel_type_id = RELATION_TYPES[rel_type_name]
            if not isinstance(targets, list):
                targets = [targets]
            for target_id in targets:
                try:
                    target_synset = wn.synset(id=target_id)
                    if target_synset:
                        _set_relation_to_synset(synset, target_synset, rel_type_id)
                except Exception as e:
                    logger.warning(f"Failed to add relation {rel_type_name} -> {target_id}: {e}")

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Created synset {synset_id}",
        target=synset_id,
        created_id=synset_id,
    )


def _exec_add_word(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Execute add_word operation."""
    from ..editor import SynsetEditor

    synset_id = change.params.get("synset")
    word = change.params.get("word")
    pos = change.params.get("pos")

    synset = wn.synset(id=synset_id)
    editor = SynsetEditor(synset)
    editor.add_word(word, pos=pos)

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Added word '{word}' to {synset_id}",
        target=synset_id,
    )


def _exec_delete_word(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Execute delete_word operation."""
    from ..editor import SynsetEditor

    synset_id = change.params.get("synset")
    word = change.params.get("word")

    synset = wn.synset(id=synset_id)
    editor = SynsetEditor(synset)
    editor.delete_word(word)

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Deleted word '{word}' from {synset_id}",
        target=synset_id,
    )


def _exec_add_definition(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Execute add_definition operation."""
    from ..editor import SynsetEditor

    synset_id = change.params.get("synset")
    definition = change.params.get("definition")
    language = change.params.get("language")

    synset = wn.synset(id=synset_id)
    editor = SynsetEditor(synset)
    editor.add_definition(definition, language=language)

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Added definition to {synset_id}",
        target=synset_id,
    )


def _exec_modify_definition(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Execute modify_definition operation."""
    from ..editor import SynsetEditor

    synset_id = change.params.get("synset")
    definition = change.params.get("definition")
    def_index = change.params.get("index", 0)
    language = change.params.get("language")

    synset = wn.synset(id=synset_id)
    editor = SynsetEditor(synset)
    editor.mod_definition(definition, indx=def_index, language=language)

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Modified definition {def_index} of {synset_id}",
        target=synset_id,
    )


def _exec_delete_definition(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Execute delete_definition operation."""
    from ..editor import SynsetEditor

    synset_id = change.params.get("synset")
    def_index = change.params.get("index", 0)

    synset = wn.synset(id=synset_id)
    editor = SynsetEditor(synset)
    editor.delete_definition(indx=def_index)

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Deleted definition {def_index} from {synset_id}",
        target=synset_id,
    )


def _exec_add_example(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Execute add_example operation."""
    from ..editor import SynsetEditor

    synset_id = change.params.get("synset")
    example = change.params.get("example")
    language = change.params.get("language")

    synset = wn.synset(id=synset_id)
    editor = SynsetEditor(synset)
    editor.add_example(example, language=language)

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Added example to {synset_id}",
        target=synset_id,
    )


def _exec_delete_example(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Execute delete_example operation."""
    from ..editor import SynsetEditor

    synset_id = change.params.get("synset")
    example = change.params.get("example")

    synset = wn.synset(id=synset_id)
    editor = SynsetEditor(synset)
    editor.delete_example(example)

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Deleted example from {synset_id}",
        target=synset_id,
    )


def _exec_set_pos(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Execute set_pos operation."""
    from ..editor import SynsetEditor

    synset_id = change.params.get("synset")
    pos = change.params.get("pos")

    synset = wn.synset(id=synset_id)
    editor = SynsetEditor(synset)
    editor.set_pos(pos)

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Set POS '{pos}' on {synset_id}",
        target=synset_id,
    )


def _exec_add_relation(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Execute add_relation operation."""
    from ..editor import _set_relation_to_synset

    source_id = change.params.get("source")
    target_id = change.params.get("target")
    rel_type_name = change.params.get("type")

    rel_type_id = RELATION_TYPES.get(rel_type_name)
    if rel_type_id is None:
        return ChangeResult(
            index=index,
            operation=change.operation,
            success=False,
            message=f"Unknown relation type: {rel_type_name}",
            error=f"Unknown relation type: {rel_type_name}",
        )

    source_synset = wn.synset(id=source_id)
    target_synset = wn.synset(id=target_id)

    _set_relation_to_synset(source_synset, target_synset, rel_type_id)

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Added {rel_type_name} relation: {source_id} -> {target_id}",
        target=source_id,
    )


def _exec_delete_relation(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Execute delete_relation operation."""
    from ..editor import SynsetEditor

    source_id = change.params.get("source")
    target_id = change.params.get("target")
    rel_type_name = change.params.get("type")

    rel_type_id = RELATION_TYPES.get(rel_type_name)
    if rel_type_id is None:
        return ChangeResult(
            index=index,
            operation=change.operation,
            success=False,
            message=f"Unknown relation type: {rel_type_name}",
            error=f"Unknown relation type: {rel_type_name}",
        )

    source_synset = wn.synset(id=source_id)
    target_synset = wn.synset(id=target_id)

    editor = SynsetEditor(source_synset)
    editor.delete_relation_to_synset(target_synset, rel_type_id)

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Deleted {rel_type_name} relation: {source_id} -> {target_id}",
        target=source_id,
    )


def _exec_set_ili(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Execute set_ili operation."""
    from ..editor import SynsetEditor, IlIEditor

    synset_id = change.params.get("synset")
    ili_id = change.params.get("ili")

    synset = wn.synset(id=synset_id)
    editor = SynsetEditor(synset)

    # Get or create ILI
    try:
        ili = wn.ili(id=ili_id)
        if ili:
            editor.set_ili(ili)
        else:
            # ILI not found - this might need special handling
            return ChangeResult(
                index=index,
                operation=change.operation,
                success=False,
                message=f"ILI '{ili_id}' not found",
                error=f"ILI '{ili_id}' not found",
                target=synset_id,
            )
    except Exception as e:
        return ChangeResult(
            index=index,
            operation=change.operation,
            success=False,
            message=f"Error setting ILI: {e}",
            error=str(e),
            target=synset_id,
        )

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Set ILI '{ili_id}' on {synset_id}",
        target=synset_id,
    )


def _exec_delete_ili(change: Change, index: int, lexicon: str) -> ChangeResult:
    """Execute delete_ili operation."""
    from ..editor import SynsetEditor

    synset_id = change.params.get("synset")

    synset = wn.synset(id=synset_id)
    editor = SynsetEditor(synset)
    editor.delete_ili()

    return ChangeResult(
        index=index,
        operation=change.operation,
        success=True,
        message=f"Removed ILI from {synset_id}",
        target=synset_id,
    )
