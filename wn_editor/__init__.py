__version__ = "0.7.0"

from .editor import (
    LexiconEditor as LexiconEditor,
    SynsetEditor as SynsetEditor,
    SenseEditor as SenseEditor,
    EntryEditor as EntryEditor,
    FormEditor as FormEditor,
    IlIEditor as IlIEditor,
    RelationType as RelationType,
    IliStatus as IliStatus,
    ARTIFICIAL_LEXICON_MARKER as ARTIFICIAL_LEXICON_MARKER,
    get_wordnet_overview as get_wordnet_overview,
    reset_all_wordnets as reset_all_wordnets,
    get_row_id as get_row_id,
    _set_relation_to_synset as _set_relation_to_synset,
    _set_relation_to_sense as _set_relation_to_sense,
    set_changelog_hooks as set_changelog_hooks,
    clear_changelog_hooks as clear_changelog_hooks,
)

from .changelog import (
    Session as Session,
    Change as Change,
    enable_tracking as enable_tracking,
    disable_tracking as disable_tracking,
    is_tracking_enabled as is_tracking_enabled,
    start_session as start_session,
    end_session as end_session,
    tracking_session as tracking_session,
    get_session_history as get_session_history,
    get_changes as get_changes,
    get_change_by_id as get_change_by_id,
    rollback_change as rollback_change,
    rollback_session as rollback_session,
    can_rollback as can_rollback,
    prune_history as prune_history,
)

# Batch module - import as submodule to avoid naming conflicts
from . import batch

__all__ = [
    # Batch module
    "batch",
    # Editor classes
    "LexiconEditor",
    "SynsetEditor",
    "SenseEditor",
    "EntryEditor",
    "FormEditor",
    "IlIEditor",
    # Enums
    "RelationType",
    "IliStatus",
    # Constants
    "ARTIFICIAL_LEXICON_MARKER",
    # Utility functions
    "get_wordnet_overview",
    "reset_all_wordnets",
    "get_row_id",
    "_set_relation_to_synset",
    "_set_relation_to_sense",
    "set_changelog_hooks",
    "clear_changelog_hooks",
    # Changelog classes
    "Session",
    "Change",
    # Changelog functions
    "enable_tracking",
    "disable_tracking",
    "is_tracking_enabled",
    "start_session",
    "end_session",
    "tracking_session",
    "get_session_history",
    "get_changes",
    "get_change_by_id",
    "rollback_change",
    "rollback_session",
    "can_rollback",
    "prune_history",
]
