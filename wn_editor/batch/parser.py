"""
YAML parser for batch change requests.
"""
from __future__ import annotations

from pathlib import Path
from typing import Any, Dict, List, Optional, Union

import yaml

from .schema import Change, ChangeRequest


class ParseError(Exception):
    """Error parsing a change request file."""

    def __init__(self, message: str, line: Optional[int] = None):
        self.line = line
        super().__init__(message)


def load_change_request(
    source: Union[str, Path, Dict[str, Any]],
) -> ChangeRequest:
    """Load a change request from a YAML file or dictionary.

    Args:
        source: Path to YAML file, YAML string, or parsed dictionary

    Returns:
        ChangeRequest object

    Raises:
        ParseError: If the file cannot be parsed or is invalid
        FileNotFoundError: If the file does not exist
    """
    source_path: Optional[Path] = None

    if isinstance(source, dict):
        data = source
    elif isinstance(source, Path) or (isinstance(source, str) and _is_file_path(source)):
        source_path = Path(source)
        if not source_path.exists():
            raise FileNotFoundError(f"File not found: {source_path}")
        data = _load_yaml_file(source_path)
    else:
        # Assume it's a YAML string
        data = _load_yaml_string(source)

    return _parse_change_request(data, source_path)


def _is_file_path(s: str) -> bool:
    """Check if a string looks like a file path."""
    # If it has path separators or ends with .yaml/.yml, treat as file
    if "/" in s or "\\" in s:
        return True
    if s.endswith((".yaml", ".yml")):
        return True
    return False


def _load_yaml_file(path: Path) -> Dict[str, Any]:
    """Load YAML from a file."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            data = yaml.safe_load(f)
    except yaml.YAMLError as e:
        line = getattr(e, "problem_mark", None)
        line_num = line.line + 1 if line else None
        raise ParseError(f"Invalid YAML: {e}", line=line_num) from e

    if data is None:
        raise ParseError("Empty YAML file")
    if not isinstance(data, dict):
        raise ParseError("YAML root must be a mapping (dictionary)")

    return data


def _load_yaml_string(s: str) -> Dict[str, Any]:
    """Load YAML from a string."""
    try:
        data = yaml.safe_load(s)
    except yaml.YAMLError as e:
        line = getattr(e, "problem_mark", None)
        line_num = line.line + 1 if line else None
        raise ParseError(f"Invalid YAML: {e}", line=line_num) from e

    if data is None:
        raise ParseError("Empty YAML content")
    if not isinstance(data, dict):
        raise ParseError("YAML root must be a mapping (dictionary)")

    return data


def _parse_change_request(
    data: Dict[str, Any],
    source_path: Optional[Path] = None,
) -> ChangeRequest:
    """Parse a dictionary into a ChangeRequest object."""
    # Extract lexicon (required)
    lexicon = data.get("lexicon")
    if not lexicon:
        raise ParseError("Missing required field: 'lexicon'")
    if not isinstance(lexicon, str):
        raise ParseError("Field 'lexicon' must be a string")

    # Extract session info (optional)
    session = data.get("session", {})
    if not isinstance(session, dict):
        raise ParseError("Field 'session' must be a mapping")

    session_name = session.get("name")
    session_description = session.get("description")

    # Extract changes (required)
    changes_data = data.get("changes")
    if changes_data is None:
        raise ParseError("Missing required field: 'changes'")
    if not isinstance(changes_data, list):
        raise ParseError("Field 'changes' must be a list")
    if len(changes_data) == 0:
        raise ParseError("Field 'changes' cannot be empty")

    changes = _parse_changes(changes_data)

    return ChangeRequest(
        lexicon=lexicon,
        changes=changes,
        session_name=session_name,
        session_description=session_description,
        source_file=source_path,
    )


def _parse_changes(changes_data: List[Any]) -> List[Change]:
    """Parse a list of change dictionaries into Change objects."""
    changes = []

    for i, change_data in enumerate(changes_data):
        if not isinstance(change_data, dict):
            raise ParseError(
                f"Change #{i + 1} must be a mapping (dictionary)",
                line=None,
            )

        operation = change_data.get("operation")
        if not operation:
            raise ParseError(
                f"Change #{i + 1}: Missing required field 'operation'"
            )
        if not isinstance(operation, str):
            raise ParseError(
                f"Change #{i + 1}: Field 'operation' must be a string"
            )

        # Extract all other fields as params
        params = {k: v for k, v in change_data.items() if k != "operation"}

        changes.append(
            Change(
                operation=operation,
                params=params,
                line_number=None,  # YAML doesn't provide line info easily
            )
        )

    return changes


def load_yaml_file(path: Union[str, Path]) -> Dict[str, Any]:
    """Load raw YAML from a file (exposed for testing).

    Args:
        path: Path to YAML file

    Returns:
        Parsed YAML as dictionary

    Raises:
        ParseError: If the file cannot be parsed
        FileNotFoundError: If the file does not exist
    """
    return _load_yaml_file(Path(path))
