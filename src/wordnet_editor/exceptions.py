"""Custom exception hierarchy for wordnet-editor."""


class WordnetEditorError(Exception):
    """Base exception for all wordnet-editor errors."""


class ValidationError(WordnetEditorError):
    """Invalid data (bad POS, self-loop, invalid ID prefix)."""


class EntityNotFoundError(WordnetEditorError):
    """Entity doesn't exist in the database."""


class DuplicateEntityError(WordnetEditorError):
    """Entity with same ID already exists."""


class RelationError(WordnetEditorError):
    """Relation constraint violation (e.g., delete with references)."""


class ConflictError(WordnetEditorError):
    """Conflicting state (e.g., both synsets have ILI in merge)."""


class DataImportError(WordnetEditorError):
    """Failed to import data (malformed XML, etc.)."""


class ExportError(WordnetEditorError):
    """Failed to export (validation errors in output)."""


class DatabaseError(WordnetEditorError):
    """Schema version mismatch, connection failure."""
