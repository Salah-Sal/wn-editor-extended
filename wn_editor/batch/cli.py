"""
Command-line interface for batch change requests.
"""
from __future__ import annotations

import argparse
import sys
from pathlib import Path
from typing import Optional

from .parser import load_change_request, ParseError
from .validator import validate_change_request
from .executor import execute_change_request
from .schema import ValidationResult, BatchResult


def main(argv: Optional[list] = None) -> int:
    """Main entry point for wn-batch CLI."""
    parser = create_parser()
    args = parser.parse_args(argv)

    if not hasattr(args, "func"):
        parser.print_help()
        return 1

    return args.func(args)


def create_parser() -> argparse.ArgumentParser:
    """Create the argument parser."""
    parser = argparse.ArgumentParser(
        prog="wn-batch",
        description="Batch change request tool for WordNet databases",
    )
    parser.add_argument(
        "--version",
        action="version",
        version="%(prog)s (wn-editor-extended)",
    )

    subparsers = parser.add_subparsers(title="commands", dest="command")

    # validate command
    validate_parser = subparsers.add_parser(
        "validate",
        help="Validate a change request file",
    )
    validate_parser.add_argument(
        "file",
        type=Path,
        help="YAML file containing change request",
    )
    validate_parser.add_argument(
        "--no-check-refs",
        action="store_true",
        help="Skip referential validation (synset existence checks)",
    )
    validate_parser.set_defaults(func=cmd_validate)

    # apply command
    apply_parser = subparsers.add_parser(
        "apply",
        help="Apply changes from a request file",
    )
    apply_parser.add_argument(
        "file",
        type=Path,
        help="YAML file containing change request",
    )
    apply_parser.add_argument(
        "--dry-run",
        action="store_true",
        help="Simulate execution without making changes",
    )
    apply_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    apply_parser.add_argument(
        "--lexicon",
        type=str,
        help="Override lexicon from file",
    )
    apply_parser.add_argument(
        "--no-tracking",
        action="store_true",
        help="Disable change tracking",
    )
    apply_parser.set_defaults(func=cmd_apply)

    # history command
    history_parser = subparsers.add_parser(
        "history",
        help="View batch execution history",
    )
    history_parser.add_argument(
        "--limit",
        type=int,
        default=10,
        help="Number of sessions to show (default: 10)",
    )
    history_parser.add_argument(
        "--include-rolled-back",
        action="store_true",
        help="Include rolled-back sessions",
    )
    history_parser.set_defaults(func=cmd_history)

    # rollback command
    rollback_parser = subparsers.add_parser(
        "rollback",
        help="Rollback a batch session",
    )
    rollback_parser.add_argument(
        "session_id",
        type=int,
        help="Session ID to rollback",
    )
    rollback_parser.add_argument(
        "--yes", "-y",
        action="store_true",
        help="Skip confirmation prompt",
    )
    rollback_parser.set_defaults(func=cmd_rollback)

    # show command
    show_parser = subparsers.add_parser(
        "show",
        help="Show details of a session",
    )
    show_parser.add_argument(
        "session_id",
        type=int,
        help="Session ID to show",
    )
    show_parser.set_defaults(func=cmd_show)

    return parser


def cmd_validate(args: argparse.Namespace) -> int:
    """Handle validate command."""
    print(f"\nValidating {args.file}...")

    try:
        request = load_change_request(args.file)
    except ParseError as e:
        print(f"\n  [PARSE ERROR] {e}")
        if e.line:
            print(f"               Line: {e.line}")
        return 1
    except FileNotFoundError as e:
        print(f"\n  [ERROR] {e}")
        return 1

    print(f"  Lexicon: {request.lexicon}")
    print(f"  Changes: {len(request.changes)}")
    if request.session_name:
        print(f"  Session: {request.session_name}")

    # Run validation
    check_refs = not args.no_check_refs
    result = validate_change_request(request, check_references=check_refs)

    print("\nValidation Results:")
    _print_validation_result(result)

    if result.is_valid:
        print("\nValidation passed!")
        return 0
    else:
        print(f"\nFound {result.error_count} error(s), {result.warning_count} warning(s)")
        return 1


def cmd_apply(args: argparse.Namespace) -> int:
    """Handle apply command."""
    print(f"\nLoading {args.file}...")

    try:
        request = load_change_request(args.file)
    except ParseError as e:
        print(f"\n  [PARSE ERROR] {e}")
        if e.line:
            print(f"               Line: {e.line}")
        return 1
    except FileNotFoundError as e:
        print(f"\n  [ERROR] {e}")
        return 1

    # Override lexicon if specified
    if args.lexicon:
        request.lexicon = args.lexicon

    print(f"  Lexicon: {request.lexicon}")
    print(f"  Changes: {len(request.changes)}")
    if request.session_name:
        print(f"  Session: \"{request.session_name}\"")

    # Validate first
    print("\nValidating...")
    validation = validate_change_request(request)

    if not validation.is_valid:
        print("\nValidation failed:")
        _print_validation_result(validation)
        print(f"\nFound {validation.error_count} error(s). Fix errors before applying.")
        return 1

    if validation.warning_count > 0:
        print("\nWarnings:")
        _print_validation_result(validation, errors_only=False, warnings_only=True)

    # Confirm unless --yes or --dry-run
    if args.dry_run:
        print("\n[DRY RUN] Simulating execution...")
    elif not args.yes:
        response = input(f"\nApply {len(request.changes)} changes to {request.lexicon}? [y/N] ")
        if response.lower() not in ("y", "yes"):
            print("Aborted.")
            return 1

    # Execute
    print(f"\n{'Simulating' if args.dry_run else 'Applying'} changes...")
    result = execute_change_request(
        request,
        dry_run=args.dry_run,
        enable_tracking=not args.no_tracking,
    )

    _print_batch_result(result)

    if result.failure_count > 0:
        return 1
    return 0


def cmd_history(args: argparse.Namespace) -> int:
    """Handle history command."""
    from ..changelog import get_session_history, is_tracking_enabled, enable_tracking

    if not is_tracking_enabled():
        enable_tracking()

    sessions = get_session_history(
        limit=args.limit,
        include_rolled_back=args.include_rolled_back,
    )

    if not sessions:
        print("No batch sessions found.")
        return 0

    print(f"\nRecent batch sessions (showing {len(sessions)}):\n")
    print(f"{'ID':<6} {'Name':<30} {'Changes':<8} {'Status':<12} {'Date'}")
    print("-" * 80)

    for session in sessions:
        status = "rolled back" if session.rolled_back else "applied"
        name = (session.name[:27] + "...") if len(session.name or "") > 30 else (session.name or "(unnamed)")
        date = session.started_at.split("T")[0] if session.started_at else ""
        print(f"{session.id:<6} {name:<30} {session.change_count:<8} {status:<12} {date}")

    print(f"\nTo see details: wn-batch show <session_id>")
    print(f"To rollback:    wn-batch rollback <session_id>")

    return 0


def cmd_rollback(args: argparse.Namespace) -> int:
    """Handle rollback command."""
    from ..changelog import (
        rollback_session,
        get_session_history,
        is_tracking_enabled,
        enable_tracking,
    )

    if not is_tracking_enabled():
        enable_tracking()

    # Find the session
    sessions = get_session_history(limit=1000, include_rolled_back=True)
    session = next((s for s in sessions if s.id == args.session_id), None)

    if not session:
        print(f"Session {args.session_id} not found.")
        return 1

    if session.rolled_back:
        print(f"Session {args.session_id} has already been rolled back.")
        return 1

    print(f"\nSession {args.session_id}: {session.name or '(unnamed)'}")
    print(f"  Changes: {session.change_count}")
    print(f"  Date: {session.started_at}")

    # Confirm unless --yes
    if not args.yes:
        response = input(f"\nRollback {session.change_count} changes? [y/N] ")
        if response.lower() not in ("y", "yes"):
            print("Aborted.")
            return 1

    print("\nRolling back...")
    count = rollback_session(args.session_id)

    print(f"\nRolled back {count} change(s).")
    return 0


def cmd_show(args: argparse.Namespace) -> int:
    """Handle show command."""
    from ..changelog import (
        get_session_history,
        get_changes,
        is_tracking_enabled,
        enable_tracking,
    )

    if not is_tracking_enabled():
        enable_tracking()

    # Find the session
    sessions = get_session_history(limit=1000, include_rolled_back=True)
    session = next((s for s in sessions if s.id == args.session_id), None)

    if not session:
        print(f"Session {args.session_id} not found.")
        return 1

    print(f"\nSession {args.session_id}")
    print(f"  Name: {session.name or '(unnamed)'}")
    if session.description:
        print(f"  Description: {session.description}")
    print(f"  Started: {session.started_at}")
    if session.ended_at:
        print(f"  Ended: {session.ended_at}")
    print(f"  Changes: {session.change_count}")
    print(f"  Status: {'rolled back' if session.rolled_back else 'applied'}")

    # Get changes
    changes = get_changes(session_id=args.session_id, include_rolled_back=True)

    if changes:
        print(f"\nChanges:")
        for change in changes:
            status = "[RB]" if change.rolled_back else "[OK]"
            print(f"  {status} {change.operation} on {change.target_table}")
            if change.target_rowid:
                print(f"       rowid: {change.target_rowid}")

    return 0


def _print_validation_result(
    result: ValidationResult,
    errors_only: bool = False,
    warnings_only: bool = False,
) -> None:
    """Print validation errors and warnings."""
    if not warnings_only:
        for error in result.errors:
            line_info = f" (line {error.line_number})" if error.line_number else ""
            print(f"  [ERROR] Change #{error.index + 1} ({error.operation}): {error.message}{line_info}")
            if error.field:
                print(f"          Field: {error.field}")

    if not errors_only:
        for warning in result.warnings:
            line_info = f" (line {warning.line_number})" if warning.line_number else ""
            print(f"  [WARN]  Change #{warning.index + 1} ({warning.operation}): {warning.message}{line_info}")


def _print_batch_result(result: BatchResult) -> None:
    """Print batch execution result."""
    print()
    for change in result.changes:
        idx = change.index + 1
        status = "OK" if change.success else "FAILED"
        msg = change.message
        print(f"  [{idx}/{result.total_count}] {change.operation}: {status}")
        if change.message:
            print(f"         {change.message}")

    print(f"\nResults:")
    print(f"  Total:   {result.total_count}")
    print(f"  Success: {result.success_count}")
    print(f"  Failed:  {result.failure_count}")
    print(f"  Time:    {result.duration_seconds:.2f}s")

    if result.session_id:
        print(f"  Session: {result.session_id}")
        print(f"\nTo rollback: wn-batch rollback {result.session_id}")


if __name__ == "__main__":
    sys.exit(main())
