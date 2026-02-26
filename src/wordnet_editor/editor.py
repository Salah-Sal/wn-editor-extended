"""WordnetEditor — main entry point for the wordnet-editor library."""

from __future__ import annotations

import functools
import json
import re
import sqlite3
from collections.abc import Callable, Generator
from contextlib import contextmanager, suppress
from pathlib import Path
from typing import Any, TypeVar

from wordnet_editor import db as _db
from wordnet_editor import history as _hist
from wordnet_editor.exceptions import (
    ConflictError,
    DuplicateEntityError,
    EntityNotFoundError,
    RelationError,
    ValidationError,
)
from wordnet_editor.models import (
    DefinitionModel,
    EditRecord,
    EntryModel,
    ExampleModel,
    FormModel,
    ILIModel,
    LexiconModel,
    PronunciationModel,
    RelationModel,
    SenseModel,
    SynsetModel,
    TagModel,
    ValidationResult,
)
from wordnet_editor.relations import (
    SENSE_RELATION_INVERSES,
    SYNSET_RELATION_INVERSES,
    is_valid_sense_relation,
    is_valid_sense_synset_relation,
    is_valid_synset_relation,
)

_F = TypeVar("_F", bound=Callable[..., Any])

# Sentinel for "no change" in update methods
_UNSET: Any = type("_UNSET", (), {"__repr__": lambda self: "..."})()

# Valid POS values
_VALID_POS = frozenset({"n", "v", "a", "r", "s", "t", "c", "p", "x", "u"})

# Normalization regex for entry IDs
_NORMALIZATION_REGEX = re.compile(r"[^\w\-]", flags=re.UNICODE)


def _modifies_db(method: _F) -> _F:
    """Decorator: wraps mutation methods in a transaction (unless in batch)."""

    @functools.wraps(method)
    def wrapper(self: WordnetEditor, *args: Any, **kwargs: Any) -> Any:
        if self._in_batch:
            return method(self, *args, **kwargs)
        with self._conn:
            return method(self, *args, **kwargs)

    return wrapper  # type: ignore[return-value]


class WordnetEditor:
    """A complete programmatic API for editing WordNets.

    Manages its own SQLite database and provides full CRUD operations on
    lexicons, synsets, entries, senses, definitions, examples, and relations.
    Supports atomic compound operations (merge, split, move), automatic
    inverse relations, 22-rule validation, field-level edit history, and
    round-trip WN-LMF 1.4 import/export.

    Use as a context manager to ensure the database connection is closed::

        with WordnetEditor("my.db") as editor:
            ...
    """

    def __init__(self, db_path: str | Path = ":memory:") -> None:
        """Open or create a WordNet editing database.

        Args:
            db_path: Path to the SQLite file, or ``":memory:"`` for an
                in-memory database.

        Raises:
            DatabaseError: If the file exists but has an incompatible schema.
        """
        self._db_path = str(db_path)
        self._conn = _db.connect(db_path)
        _db.check_schema_version(self._conn)
        _db.init_db(self._conn)
        self._in_batch = False
        self._batch_depth = 0

    def close(self) -> None:
        """Close the database connection."""
        self._conn.close()

    def __enter__(self) -> WordnetEditor:
        return self

    def __exit__(self, *exc: Any) -> None:
        self.close()

    # ------------------------------------------------------------------
    # Batch context manager
    # ------------------------------------------------------------------

    @contextmanager
    def batch(self) -> Generator[None, None, None]:
        """Group multiple mutations into a single transaction.

        All changes inside the ``with`` block are committed atomically on
        success or rolled back on exception.  Batches may be nested; only
        the outermost batch issues COMMIT/ROLLBACK.
        """
        self._batch_depth += 1
        if self._batch_depth == 1:
            self._in_batch = True
            self._conn.execute("BEGIN")
        try:
            yield
        except BaseException:
            if self._batch_depth == 1:
                self._conn.rollback()
                self._in_batch = False
            self._batch_depth -= 1
            raise
        else:
            self._batch_depth -= 1
            if self._batch_depth == 0:
                self._conn.commit()
                self._in_batch = False

    # ------------------------------------------------------------------
    # Lexicon Management (3.2)
    # ------------------------------------------------------------------

    @_modifies_db
    def create_lexicon(
        self,
        id: str,
        label: str,
        language: str,
        email: str,
        license: str,
        version: str,
        *,
        url: str | None = None,
        citation: str | None = None,
        logo: str | None = None,
        metadata: dict | None = None,
    ) -> LexiconModel:
        """Create a new lexicon.

        Args:
            id: Unique lexicon identifier (e.g. ``"ewn"``).
            label: Human-readable name.
            language: BCP-47 language tag (e.g. ``"en"``).
            email: Maintainer contact email.
            license: License URL.
            version: Version string (e.g. ``"1.0"``).
            url: Optional project URL.
            citation: Optional bibliographic citation.
            logo: Optional logo URL.
            metadata: Optional JSON-serializable metadata dict.

        Returns:
            The newly created lexicon.

        Raises:
            DuplicateEntityError: A lexicon with the same *id* and *version*
                already exists.
        """
        specifier = f"{id}:{version}"
        try:
            self._conn.execute(
                "INSERT INTO lexicons "
                "(specifier, id, label, language, email, license, version, "
                "url, citation, logo, metadata, modified) "
                "VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, 0)",
                (specifier, id, label, language, email, license, version,
                 url, citation, logo,
                 json.dumps(metadata) if metadata else None),
            )
        except sqlite3.IntegrityError as e:
            raise DuplicateEntityError(
                f"Lexicon with id={id!r} version={version!r} already exists"
            ) from e

        _hist.record_create(self._conn, "lexicon", id, {"id": id, "label": label})
        return LexiconModel(
            id=id, label=label, language=language, email=email,
            license=license, version=version, url=url,
            citation=citation, logo=logo, metadata=metadata,
        )

    @_modifies_db
    def update_lexicon(
        self,
        lexicon_id: str,
        *,
        label: str | None = None,
        email: str | None = None,
        license: str | None = None,
        url: Any = _UNSET,
        citation: Any = _UNSET,
        logo: Any = _UNSET,
        metadata: Any = _UNSET,
    ) -> LexiconModel:
        """Update mutable fields of an existing lexicon.

        Only the keyword arguments that are explicitly passed will be changed.
        Pass ``None`` for nullable fields (url, citation, logo, metadata) to
        clear them.

        Args:
            lexicon_id: ID of the lexicon to update.
            label: New human-readable name.
            email: New maintainer email.
            license: New license URL.
            url: New project URL, or ``None`` to clear.
            citation: New citation, or ``None`` to clear.
            logo: New logo URL, or ``None`` to clear.
            metadata: New metadata dict, or ``None`` to clear.

        Returns:
            The updated lexicon.

        Raises:
            EntityNotFoundError: No lexicon with *lexicon_id* exists.
        """
        row = _db.get_lexicon_row(self._conn, lexicon_id)
        if row is None:
            raise EntityNotFoundError(f"Lexicon not found: {lexicon_id!r}")

        updates: dict[str, Any] = {}
        if label is not None:
            updates["label"] = label
        if email is not None:
            updates["email"] = email
        if license is not None:
            updates["license"] = license
        if url is not _UNSET:
            updates["url"] = url
        if citation is not _UNSET:
            updates["citation"] = citation
        if logo is not _UNSET:
            updates["logo"] = logo
        if metadata is not _UNSET:
            updates["metadata"] = json.dumps(metadata) if metadata else None

        for field, val in updates.items():
            old_val = row[field]
            is_meta = field == "metadata"
            if is_meta and old_val is not None and isinstance(old_val, dict):
                old_val = json.dumps(old_val)
            _hist.record_update(
                self._conn, "lexicon", lexicon_id, field, row[field], val
            )
            self._conn.execute(
                f"UPDATE lexicons SET {field} = ? WHERE id = ?",
                (val, lexicon_id),
            )

        if updates:
            self._conn.execute(
                "UPDATE lexicons SET modified = 1 WHERE id = ?",
                (lexicon_id,),
            )

        return self.get_lexicon(lexicon_id)

    def get_lexicon(self, lexicon_id: str) -> LexiconModel:
        """Retrieve a lexicon by its ID.

        Args:
            lexicon_id: Lexicon identifier.

        Returns:
            The matching lexicon.

        Raises:
            EntityNotFoundError: No lexicon with *lexicon_id* exists.
        """
        row = _db.get_lexicon_row(self._conn, lexicon_id)
        if row is None:
            raise EntityNotFoundError(f"Lexicon not found: {lexicon_id!r}")
        return self._row_to_lexicon(row)

    def list_lexicons(self) -> list[LexiconModel]:
        """Return all lexicons in the database.

        Returns:
            List of all lexicons (may be empty).
        """
        rows = self._conn.execute("SELECT rowid, * FROM lexicons").fetchall()
        return [self._row_to_lexicon(r) for r in rows]

    @_modifies_db
    def delete_lexicon(self, lexicon_id: str) -> None:
        """Delete a lexicon and all its contents (synsets, entries, senses).

        Args:
            lexicon_id: ID of the lexicon to delete.

        Raises:
            EntityNotFoundError: No lexicon with *lexicon_id* exists.
        """
        row = _db.get_lexicon_row(self._conn, lexicon_id)
        if row is None:
            raise EntityNotFoundError(f"Lexicon not found: {lexicon_id!r}")
        _hist.record_delete(self._conn, "lexicon", lexicon_id)
        self._conn.execute("DELETE FROM lexicons WHERE id = ?", (lexicon_id,))

    def _row_to_lexicon(self, row: sqlite3.Row) -> LexiconModel:
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)
        return LexiconModel(
            id=row["id"],
            label=row["label"],
            language=row["language"],
            email=row["email"],
            license=row["license"],
            version=row["version"],
            url=row["url"],
            citation=row["citation"],
            logo=row["logo"],
            metadata=meta,
        )

    # ------------------------------------------------------------------
    # Synset Operations (3.3)
    # ------------------------------------------------------------------

    @_modifies_db
    def create_synset(
        self,
        lexicon_id: str,
        pos: str,
        definition: str,
        *,
        id: str | None = None,
        ili: str | None = None,
        ili_definition: str | None = None,
        lexicalized: bool = True,
        metadata: dict | None = None,
    ) -> SynsetModel:
        """Create a new synset with an initial definition.

        Args:
            lexicon_id: Parent lexicon ID.
            pos: Part-of-speech tag (one of ``PartOfSpeech`` values).
            definition: Initial definition text.
            id: Explicit synset ID, or ``None`` to auto-generate.
            ili: ILI identifier, or ``"in"`` to propose a new ILI entry.
            ili_definition: Required when *ili* is ``"in"`` (min 20 chars).
            lexicalized: Whether the synset is lexicalized (default ``True``).
            metadata: Optional metadata dict.

        Returns:
            The newly created synset.

        Raises:
            ValidationError: Invalid POS, invalid ID prefix, or bad ILI args.
            EntityNotFoundError: Lexicon not found.
            DuplicateEntityError: Synset with *id* already exists.
        """
        if pos not in _VALID_POS:
            raise ValidationError(f"Invalid POS: {pos!r}")

        lex_rowid = _db.get_lexicon_rowid(self._conn, lexicon_id)
        if lex_rowid is None:
            raise EntityNotFoundError(f"Lexicon not found: {lexicon_id!r}")

        if id is None:
            id = self._generate_synset_id(lexicon_id, lex_rowid, pos)
        else:
            if not id.startswith(f"{lexicon_id}-"):
                raise ValidationError(
                    f"ID must start with lexicon prefix: {lexicon_id}-"
                )

        # Check for duplicates
        if _db.get_synset_rowid(self._conn, id) is not None:
            raise DuplicateEntityError(f"Synset already exists: {id!r}")

        # Handle ILI
        ili_rowid = None
        if ili is not None and ili != "in":
            ili_rowid = _db.get_or_create_ili(self._conn, ili)
        if ili == "in":
            if ili_definition is None:
                raise ValidationError(
                    "ili_definition is required when ili='in'"
                )
            if len(ili_definition) < 20:
                raise ValidationError(
                    "ILI definition must be at least 20 characters"
                )

        self._conn.execute(
            "INSERT INTO synsets (id, lexicon_rowid, ili_rowid, pos, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (id, lex_rowid, ili_rowid, pos,
             json.dumps(metadata) if metadata else None),
        )
        synset_rowid = self._conn.execute(
            "SELECT rowid FROM synsets WHERE id = ?", (id,)
        ).fetchone()[0]

        # Insert proposed ILI
        if ili == "in":
            self._conn.execute(
                "INSERT INTO proposed_ilis (synset_rowid, definition) "
                "VALUES (?, ?)",
                (synset_rowid, ili_definition),
            )

        # Handle unlexicalized
        if not lexicalized:
            self._conn.execute(
                "INSERT INTO unlexicalized_synsets (synset_rowid) VALUES (?)",
                (synset_rowid,),
            )

        # Insert definition
        self._conn.execute(
            "INSERT INTO definitions (lexicon_rowid, synset_rowid, definition) "
            "VALUES (?, ?, ?)",
            (lex_rowid, synset_rowid, definition),
        )

        _hist.record_create(
            self._conn, "synset", id,
            {"pos": pos, "definition": definition, "lexicon_id": lexicon_id},
        )

        return self._build_synset_model(id)

    @_modifies_db
    def update_synset(
        self,
        synset_id: str,
        *,
        pos: str | None = None,
        metadata: Any = _UNSET,
    ) -> SynsetModel:
        """Update mutable fields of an existing synset.

        Args:
            synset_id: ID of the synset to update.
            pos: New part-of-speech tag.
            metadata: New metadata dict, or ``None`` to clear.

        Returns:
            The updated synset.

        Raises:
            EntityNotFoundError: Synset not found.
            ValidationError: Invalid POS value.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        if pos is not None:
            if pos not in _VALID_POS:
                raise ValidationError(f"Invalid POS: {pos!r}")
            _hist.record_update(
                self._conn, "synset", synset_id, "pos", row["pos"], pos
            )
            self._conn.execute(
                "UPDATE synsets SET pos = ? WHERE id = ?",
                (pos, synset_id),
            )

        if metadata is not _UNSET:
            _hist.record_update(
                self._conn, "synset", synset_id, "metadata",
                str(row["metadata"]), str(metadata),
            )
            self._conn.execute(
                "UPDATE synsets SET metadata = ? WHERE id = ?",
                (json.dumps(metadata) if metadata else None, synset_id),
            )

        return self._build_synset_model(synset_id)

    @_modifies_db
    def delete_synset(self, synset_id: str, cascade: bool = False) -> None:
        """Delete a synset.

        Args:
            synset_id: ID of the synset to delete.
            cascade: If ``True``, also delete all attached senses.

        Raises:
            EntityNotFoundError: Synset not found.
            RelationError: Synset has senses and *cascade* is ``False``.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        synset_rowid = row["rowid"]

        # Check for senses
        sense_count = self._conn.execute(
            "SELECT COUNT(*) FROM senses WHERE synset_rowid = ?",
            (synset_rowid,),
        ).fetchone()[0]

        if sense_count > 0 and not cascade:
            raise RelationError(
                f"Synset {synset_id} has {sense_count} senses; "
                "use cascade=True to force deletion"
            )

        if cascade:
            # Pre-fetch sense IDs for history
            sense_rows = self._conn.execute(
                "SELECT id FROM senses WHERE synset_rowid = ?",
                (synset_rowid,),
            ).fetchall()
            for sr in sense_rows:
                _hist.record_delete(self._conn, "sense", sr["id"])

        # Note: We rely on ON DELETE CASCADE in the database to remove
        # senses, relations (both sense and synset), definitions, etc.
        # This is much faster than deleting them one by one.

        # However, we still need to handle relation inverses for synset relations
        # where the target is this synset (or source is this synset).
        # _cleanup_synset_relations handles both directions and inverses.
        # If we just delete the synset, CASCADE removes relations where
        # source or target is this synset.
        # BUT, if we have a relation A -> B, and we delete A.
        # synset_relations table has FK on source_rowid and target_rowid with CASCADE.
        # So A->B is deleted.
        # If auto-inverse exists, B->A is also deleted because target_rowid (A) is deleted.
        # So we don't need to manually cleanup relations.

        # One edge case: unlexicalized_synsets logic in _remove_sense_internal.
        # If we delete a sense, we check if its synset becomes empty.
        # Here we are deleting the synset itself, so we don't care if it becomes empty.
        # But wait, what if we delete a sense that was the LAST sense of the synset?
        # The synset is being deleted anyway.

        _hist.record_delete(
            self._conn, "synset", synset_id, {"pos": row["pos"]}
        )
        self._conn.execute(
            "DELETE FROM synsets WHERE id = ?", (synset_id,)
        )

    def get_synset(self, synset_id: str) -> SynsetModel:
        """Retrieve a synset by its ID.

        Args:
            synset_id: Synset identifier.

        Returns:
            The matching synset.

        Raises:
            EntityNotFoundError: Synset not found.
        """
        model = self._build_synset_model(synset_id)
        if model is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")
        return model

    def find_synsets(
        self,
        *,
        lexicon_id: str | None = None,
        pos: str | None = None,
        ili: str | None = None,
        definition_contains: str | None = None,
    ) -> list[SynsetModel]:
        """Search for synsets matching all given criteria.

        Args:
            lexicon_id: Filter by parent lexicon.
            pos: Filter by part-of-speech.
            ili: Filter by ILI identifier.
            definition_contains: Filter by substring match in definitions.

        Returns:
            List of matching synsets (may be empty).
        """
        clauses: list[str] = []
        params: list[Any] = []

        if lexicon_id is not None:
            clauses.append(
                "s.lexicon_rowid = (SELECT rowid FROM lexicons WHERE id = ?)"
            )
            params.append(lexicon_id)
        if pos is not None:
            clauses.append("s.pos = ?")
            params.append(pos)
        if ili is not None:
            clauses.append(
                "s.ili_rowid = (SELECT rowid FROM ilis WHERE id = ?)"
            )
            params.append(ili)
        if definition_contains is not None:
            clauses.append(
                "s.rowid IN (SELECT synset_rowid FROM definitions "
                "WHERE definition LIKE ?)"
            )
            params.append(f"%{definition_contains}%")

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT s.id FROM synsets s WHERE {where}"
        rows = self._conn.execute(sql, params).fetchall()
        return [self._build_synset_model(r["id"]) for r in rows]

    def _build_synset_model(self, synset_id: str) -> SynsetModel:
        row = self._conn.execute(
            "SELECT s.rowid, s.id, s.pos, s.ili_rowid, s.lexfile_rowid, "
            "s.metadata, l.id as lexicon_id "
            "FROM synsets s JOIN lexicons l ON s.lexicon_rowid = l.rowid "
            "WHERE s.id = ?",
            (synset_id,),
        ).fetchone()
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        # Resolve ILI
        ili_str: str | None = None
        if row["ili_rowid"] is not None:
            ili_row = self._conn.execute(
                "SELECT id FROM ilis WHERE rowid = ?",
                (row["ili_rowid"],),
            ).fetchone()
            if ili_row:
                ili_str = ili_row["id"]
        # Check for proposed ILI
        proposed = self._conn.execute(
            "SELECT rowid FROM proposed_ilis WHERE synset_rowid = ?",
            (row["rowid"],),
        ).fetchone()
        if proposed is not None:
            ili_str = "in"

        # Resolve lexfile
        lexfile: str | None = None
        if row["lexfile_rowid"] is not None:
            lf_row = self._conn.execute(
                "SELECT name FROM lexfiles WHERE rowid = ?",
                (row["lexfile_rowid"],),
            ).fetchone()
            if lf_row:
                lexfile = lf_row["name"]

        # Check lexicalized
        unlex = self._conn.execute(
            "SELECT 1 FROM unlexicalized_synsets WHERE synset_rowid = ?",
            (row["rowid"],),
        ).fetchone()

        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)

        return SynsetModel(
            id=row["id"],
            lexicon_id=row["lexicon_id"],
            pos=row["pos"],
            ili=ili_str,
            lexicalized=unlex is None,
            lexfile=lexfile,
            metadata=meta,
        )

    def _generate_synset_id(
        self, lexicon_id: str, lex_rowid: int, pos: str
    ) -> str:
        prefix = f"{lexicon_id}-"
        prefix_len = len(prefix)
        row = self._conn.execute(
            "SELECT MAX(CAST(substr(id, ?, 8) AS INTEGER)) "
            "FROM synsets WHERE lexicon_rowid = ? AND id LIKE ?",
            (prefix_len + 1, lex_rowid, f"{prefix}________-%"),
        ).fetchone()
        counter = (row[0] or 0) + 1
        return f"{prefix}{counter:08d}-{pos}"

    def _cleanup_synset_relations(self, synset_rowid: int) -> None:
        """Remove all synset relations involving this synset and their inverses."""
        # Get all relations involving this synset
        rels = self._conn.execute(
            "SELECT sr.rowid, sr.source_rowid, sr.target_rowid, rt.type "
            "FROM synset_relations sr "
            "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
            "WHERE sr.source_rowid = ? OR sr.target_rowid = ?",
            (synset_rowid, synset_rowid),
        ).fetchall()

        for rel in rels:
            rel_type = rel["type"]
            inverse = SYNSET_RELATION_INVERSES.get(rel_type)
            if inverse:
                inv_type_row = self._conn.execute(
                    "SELECT rowid FROM relation_types WHERE type = ?",
                    (inverse,),
                ).fetchone()
                if inv_type_row:
                    self._conn.execute(
                        "DELETE FROM synset_relations "
                        "WHERE source_rowid = ? AND target_rowid = ? "
                        "AND type_rowid = ?",
                        (rel["target_rowid"], rel["source_rowid"],
                         inv_type_row["rowid"]),
                    )
            self._conn.execute(
                "DELETE FROM synset_relations WHERE rowid = ?",
                (rel["rowid"],),
            )

    # ------------------------------------------------------------------
    # Entry Operations (3.4)
    # ------------------------------------------------------------------

    @_modifies_db
    def create_entry(
        self,
        lexicon_id: str,
        lemma: str,
        pos: str,
        *,
        id: str | None = None,
        forms: list[str] | None = None,
        metadata: dict | None = None,
    ) -> EntryModel:
        """Create a new lexical entry.

        Args:
            lexicon_id: Parent lexicon ID.
            lemma: The lemma (canonical written form).
            pos: Part-of-speech tag.
            id: Explicit entry ID, or ``None`` to auto-generate.
            forms: Additional written forms (variants, inflections).
            metadata: Optional metadata dict.

        Returns:
            The newly created entry.

        Raises:
            ValidationError: Invalid POS or invalid ID prefix.
            EntityNotFoundError: Lexicon not found.
            DuplicateEntityError: Entry with *id* already exists.
        """
        if pos not in _VALID_POS:
            raise ValidationError(f"Invalid POS: {pos!r}")

        lex_rowid = _db.get_lexicon_rowid(self._conn, lexicon_id)
        if lex_rowid is None:
            raise EntityNotFoundError(f"Lexicon not found: {lexicon_id!r}")

        if id is None:
            id = self._generate_entry_id(lexicon_id, lemma, pos)
        else:
            if not id.startswith(f"{lexicon_id}-"):
                raise ValidationError(
                    f"ID must start with lexicon prefix: {lexicon_id}-"
                )

        if _db.get_entry_rowid(self._conn, id) is not None:
            raise DuplicateEntityError(f"Entry already exists: {id!r}")

        self._conn.execute(
            "INSERT INTO entries (id, lexicon_rowid, pos, metadata) "
            "VALUES (?, ?, ?, ?)",
            (id, lex_rowid, pos,
             json.dumps(metadata) if metadata else None),
        )
        entry_rowid = self._conn.execute(
            "SELECT rowid FROM entries WHERE id = ?", (id,)
        ).fetchone()[0]

        # Insert lemma as rank-0 form
        normalized = lemma.casefold() if lemma.casefold() != lemma else None
        self._conn.execute(
            "INSERT INTO forms "
            "(lexicon_rowid, entry_rowid, form, normalized_form, rank) "
            "VALUES (?, ?, ?, ?, 0)",
            (lex_rowid, entry_rowid, lemma, normalized),
        )

        # Insert entry_index
        self._conn.execute(
            "INSERT INTO entry_index (entry_rowid, lemma) VALUES (?, ?)",
            (entry_rowid, lemma),
        )

        # Insert additional forms
        if forms:
            for rank, form_text in enumerate(forms, start=1):
                cf = form_text.casefold()
                norm = cf if cf != form_text else None
                self._conn.execute(
                    "INSERT INTO forms "
                    "(lexicon_rowid, entry_rowid, form, normalized_form, rank) "
                    "VALUES (?, ?, ?, ?, ?)",
                    (lex_rowid, entry_rowid, form_text, norm, rank),
                )

        _hist.record_create(
            self._conn, "entry", id,
            {"lemma": lemma, "pos": pos, "lexicon_id": lexicon_id},
        )

        return self._build_entry_model(id)

    @_modifies_db
    def update_entry(
        self,
        entry_id: str,
        *,
        pos: str | None = None,
        metadata: Any = _UNSET,
    ) -> EntryModel:
        """Update mutable fields of an existing entry.

        Args:
            entry_id: ID of the entry to update.
            pos: New part-of-speech tag.
            metadata: New metadata dict, or ``None`` to clear.

        Returns:
            The updated entry.

        Raises:
            EntityNotFoundError: Entry not found.
            ValidationError: Invalid POS value.
        """
        row = _db.get_entry_row(self._conn, entry_id)
        if row is None:
            raise EntityNotFoundError(f"Entry not found: {entry_id!r}")

        if pos is not None:
            if pos not in _VALID_POS:
                raise ValidationError(f"Invalid POS: {pos!r}")
            _hist.record_update(
                self._conn, "entry", entry_id, "pos", row["pos"], pos
            )
            self._conn.execute(
                "UPDATE entries SET pos = ? WHERE id = ?",
                (pos, entry_id),
            )

        if metadata is not _UNSET:
            self._conn.execute(
                "UPDATE entries SET metadata = ? WHERE id = ?",
                (json.dumps(metadata) if metadata else None, entry_id),
            )

        return self._build_entry_model(entry_id)

    @_modifies_db
    def delete_entry(self, entry_id: str, cascade: bool = False) -> None:
        """Delete a lexical entry.

        Args:
            entry_id: ID of the entry to delete.
            cascade: If ``True``, also delete all attached senses.

        Raises:
            EntityNotFoundError: Entry not found.
            RelationError: Entry has senses and *cascade* is ``False``.
        """
        row = _db.get_entry_row(self._conn, entry_id)
        if row is None:
            raise EntityNotFoundError(f"Entry not found: {entry_id!r}")

        entry_rowid = row["rowid"]
        sense_count = self._conn.execute(
            "SELECT COUNT(*) FROM senses WHERE entry_rowid = ?",
            (entry_rowid,),
        ).fetchone()[0]

        if sense_count > 0 and not cascade:
            raise RelationError(
                f"Entry {entry_id} has {sense_count} senses; "
                "use cascade=True to force deletion"
            )

        if cascade:
            sense_rows = self._conn.execute(
                "SELECT id FROM senses WHERE entry_rowid = ?",
                (entry_rowid,),
            ).fetchall()
            for sr in sense_rows:
                self._remove_sense_internal(sr["id"])

        _hist.record_delete(
            self._conn, "entry", entry_id, {"pos": row["pos"]}
        )
        self._conn.execute("DELETE FROM entries WHERE id = ?", (entry_id,))

    def get_entry(self, entry_id: str) -> EntryModel:
        """Retrieve an entry by its ID.

        Args:
            entry_id: Entry identifier.

        Returns:
            The matching entry.

        Raises:
            EntityNotFoundError: Entry not found.
        """
        model = self._build_entry_model(entry_id)
        if model is None:
            raise EntityNotFoundError(f"Entry not found: {entry_id!r}")
        return model

    def find_entries(
        self,
        *,
        lexicon_id: str | None = None,
        lemma: str | None = None,
        pos: str | None = None,
    ) -> list[EntryModel]:
        """Search for entries matching all given criteria.

        Args:
            lexicon_id: Filter by parent lexicon.
            lemma: Filter by exact lemma match.
            pos: Filter by part-of-speech.

        Returns:
            List of matching entries (may be empty).
        """
        clauses: list[str] = []
        params: list[Any] = []

        if lexicon_id is not None:
            clauses.append(
                "e.lexicon_rowid = (SELECT rowid FROM lexicons WHERE id = ?)"
            )
            params.append(lexicon_id)
        if lemma is not None:
            clauses.append(
                "e.rowid IN (SELECT entry_rowid FROM forms "
                "WHERE form = ? AND rank = 0)"
            )
            params.append(lemma)
        if pos is not None:
            clauses.append("e.pos = ?")
            params.append(pos)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT e.id FROM entries e WHERE {where}"
        rows = self._conn.execute(sql, params).fetchall()
        return [self._build_entry_model(r["id"]) for r in rows]

    @_modifies_db
    def add_form(
        self,
        entry_id: str,
        written_form: str,
        *,
        id: str | None = None,
        script: str | None = None,
        tags: list[tuple[str, str]] | None = None,
    ) -> None:
        """Add an additional written form (variant/inflection) to an entry.

        Args:
            entry_id: ID of the parent entry.
            written_form: The form text to add.
            id: Optional explicit form ID.
            script: Optional ISO 15924 script tag.
            tags: Optional list of ``(tag, category)`` pairs.

        Raises:
            EntityNotFoundError: Entry not found.
            DuplicateEntityError: Form already exists for this entry.
        """
        row = _db.get_entry_row(self._conn, entry_id)
        if row is None:
            raise EntityNotFoundError(f"Entry not found: {entry_id!r}")

        entry_rowid = row["rowid"]
        lex_rowid = row["lexicon_rowid"]

        # Get max rank
        max_rank_row = self._conn.execute(
            "SELECT MAX(rank) FROM forms WHERE entry_rowid = ?",
            (entry_rowid,),
        ).fetchone()
        new_rank = (max_rank_row[0] or 0) + 1

        normalized = (
            written_form.casefold()
            if written_form.casefold() != written_form
            else None
        )
        try:
            self._conn.execute(
                "INSERT INTO forms "
                "(id, lexicon_rowid, entry_rowid, form, normalized_form, "
                "script, rank) VALUES (?, ?, ?, ?, ?, ?, ?)",
                (id, lex_rowid, entry_rowid, written_form, normalized,
                 script, new_rank),
            )
        except sqlite3.IntegrityError as e:
            raise DuplicateEntityError(
                f"Form {written_form!r} already exists for entry {entry_id!r}"
            ) from e

        if tags:
            form_rowid = self._conn.execute(
                "SELECT rowid FROM forms WHERE entry_rowid = ? AND form = ?",
                (entry_rowid, written_form),
            ).fetchone()[0]
            for tag, category in tags:
                self._conn.execute(
                    "INSERT INTO tags (form_rowid, lexicon_rowid, tag, category) "
                    "VALUES (?, ?, ?, ?)",
                    (form_rowid, lex_rowid, tag, category),
                )

        _hist.record_create(
            self._conn, "form", f"{entry_id}:{written_form}",
            {"written_form": written_form},
        )

    @_modifies_db
    def remove_form(self, entry_id: str, written_form: str) -> None:
        """Remove an additional form from an entry.

        The lemma form (rank 0) cannot be removed.

        Args:
            entry_id: ID of the parent entry.
            written_form: The form text to remove.

        Raises:
            EntityNotFoundError: Entry or form not found.
            ValidationError: Attempted to remove the lemma form.
        """
        row = _db.get_entry_row(self._conn, entry_id)
        if row is None:
            raise EntityNotFoundError(f"Entry not found: {entry_id!r}")

        entry_rowid = row["rowid"]
        form_row = self._conn.execute(
            "SELECT rowid, rank FROM forms "
            "WHERE entry_rowid = ? AND form = ?",
            (entry_rowid, written_form),
        ).fetchone()
        if form_row is None:
            raise EntityNotFoundError(
                f"Form {written_form!r} not found for entry {entry_id!r}"
            )
        if form_row["rank"] == 0:
            raise ValidationError("Cannot remove the lemma form")

        self._conn.execute(
            "DELETE FROM forms WHERE rowid = ?", (form_row["rowid"],)
        )
        _hist.record_delete(
            self._conn, "form", f"{entry_id}:{written_form}",
        )

    def get_forms(self, entry_id: str) -> list[FormModel]:
        """Return all forms of an entry, ordered by rank.

        The lemma is always at rank 0.

        Args:
            entry_id: ID of the entry.

        Returns:
            List of forms, starting with the lemma.

        Raises:
            EntityNotFoundError: Entry not found.
        """
        row = _db.get_entry_row(self._conn, entry_id)
        if row is None:
            raise EntityNotFoundError(f"Entry not found: {entry_id!r}")

        entry_rowid = row["rowid"]
        form_rows = self._conn.execute(
            "SELECT rowid, id, form, script, rank FROM forms "
            "WHERE entry_rowid = ? ORDER BY rank",
            (entry_rowid,),
        ).fetchall()

        result = []
        for fr in form_rows:
            # Get pronunciations
            pron_rows = self._conn.execute(
                "SELECT value, variety, notation, phonemic, audio "
                "FROM pronunciations WHERE form_rowid = ?",
                (fr["rowid"],),
            ).fetchall()
            pronunciations = tuple(
                PronunciationModel(
                    value=p["value"],
                    variety=p["variety"],
                    notation=p["notation"],
                    phonemic=bool(p["phonemic"]),
                    audio=p["audio"],
                )
                for p in pron_rows
            )

            # Get tags
            tag_rows = self._conn.execute(
                "SELECT tag, category FROM tags WHERE form_rowid = ?",
                (fr["rowid"],),
            ).fetchall()
            tags_tuple = tuple(
                TagModel(tag=t["tag"], category=t["category"])
                for t in tag_rows
            )

            result.append(FormModel(
                written_form=fr["form"],
                id=fr["id"],
                script=fr["script"],
                rank=fr["rank"],
                pronunciations=pronunciations,
                tags=tags_tuple,
            ))
        return result

    @_modifies_db
    def update_lemma(self, entry_id: str, new_lemma: str) -> None:
        """Change the lemma (canonical form) of an entry.

        Args:
            entry_id: ID of the entry.
            new_lemma: New lemma text.

        Raises:
            EntityNotFoundError: Entry not found.
        """
        row = _db.get_entry_row(self._conn, entry_id)
        if row is None:
            raise EntityNotFoundError(f"Entry not found: {entry_id!r}")

        entry_rowid = row["rowid"]
        old_form_row = self._conn.execute(
            "SELECT form FROM forms WHERE entry_rowid = ? AND rank = 0",
            (entry_rowid,),
        ).fetchone()
        old_lemma = old_form_row["form"] if old_form_row else ""

        normalized = new_lemma.casefold() if new_lemma.casefold() != new_lemma else None
        self._conn.execute(
            "UPDATE forms SET form = ?, normalized_form = ? "
            "WHERE entry_rowid = ? AND rank = 0",
            (new_lemma, normalized, entry_rowid),
        )
        self._conn.execute(
            "UPDATE entry_index SET lemma = ? WHERE entry_rowid = ?",
            (new_lemma, entry_rowid),
        )
        _hist.record_update(
            self._conn, "entry", entry_id, "lemma", old_lemma, new_lemma
        )

    def _build_entry_model(self, entry_id: str) -> EntryModel:
        row = self._conn.execute(
            "SELECT e.rowid, e.id, e.pos, e.metadata, l.id as lexicon_id "
            "FROM entries e JOIN lexicons l ON e.lexicon_rowid = l.rowid "
            "WHERE e.id = ?",
            (entry_id,),
        ).fetchone()
        if row is None:
            raise EntityNotFoundError(f"Entry not found: {entry_id!r}")

        # Get lemma
        lemma_row = self._conn.execute(
            "SELECT form FROM forms WHERE entry_rowid = ? AND rank = 0",
            (row["rowid"],),
        ).fetchone()
        lemma = lemma_row["form"] if lemma_row else ""

        # Get index
        idx_row = self._conn.execute(
            "SELECT lemma FROM entry_index WHERE entry_rowid = ?",
            (row["rowid"],),
        ).fetchone()

        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)

        return EntryModel(
            id=row["id"],
            lexicon_id=row["lexicon_id"],
            lemma=lemma,
            pos=row["pos"],
            index=idx_row["lemma"] if idx_row else None,
            metadata=meta,
        )

    def _generate_entry_id(
        self, lexicon_id: str, lemma: str, pos: str
    ) -> str:
        # Normalize: replace spaces with _, strip non-alnum except - and _
        normalized = lemma.lower()
        normalized = normalized.replace(" ", "_")
        normalized = _NORMALIZATION_REGEX.sub("", normalized)
        if not normalized:
            normalized = "entry"

        base_id = f"{lexicon_id}-{normalized}-{pos}"
        if _db.get_entry_rowid(self._conn, base_id) is None:
            return base_id

        # Get all existing IDs that match the base_id-{n} pattern
        # Escape special LIKE characters: \ -> \\, _ -> \_, % -> \%
        escaped_base = base_id.replace("\\", "\\\\").replace("_", r"\_").replace("%", r"\%")
        rows = self._conn.execute(
            "SELECT id FROM entries WHERE id LIKE ? ESCAPE '\\'",
            (f"{escaped_base}-%",),
        ).fetchall()

        existing_suffixes = set()
        prefix_len = len(base_id) + 1  # length of "base_id-"
        for row in rows:
            candidate_id = row["id"]
            # Double check prefix to be absolutely sure
            if not candidate_id.startswith(f"{base_id}-"):
                continue

            suffix = candidate_id[prefix_len:]
            if suffix.isdigit():
                existing_suffixes.add(int(suffix))

        n = 2
        while n in existing_suffixes:
            n += 1

        return f"{base_id}-{n}"

    # ------------------------------------------------------------------
    # Sense Operations (3.5)
    # ------------------------------------------------------------------

    @_modifies_db
    def add_sense(
        self,
        entry_id: str,
        synset_id: str,
        *,
        id: str | None = None,
        lexicalized: bool = True,
        adjposition: str | None = None,
        metadata: dict | None = None,
    ) -> SenseModel:
        """Link an entry to a synset by creating a new sense.

        If the target synset was unlexicalized, it becomes lexicalized.

        Args:
            entry_id: ID of the parent entry.
            synset_id: ID of the target synset.
            id: Explicit sense ID, or ``None`` to auto-generate.
            lexicalized: Whether the sense is lexicalized (default ``True``).
            adjposition: Adjective position (``"a"``, ``"ip"``, ``"p"``).
            metadata: Optional metadata dict.

        Returns:
            The newly created sense.

        Raises:
            EntityNotFoundError: Entry or synset not found.
            DuplicateEntityError: Entry already has a sense for this synset,
                or a sense with the given *id* already exists.
            ValidationError: Invalid ID prefix.
        """
        entry_row = _db.get_entry_row(self._conn, entry_id)
        if entry_row is None:
            raise EntityNotFoundError(f"Entry not found: {entry_id!r}")

        synset_row = _db.get_synset_row(self._conn, synset_id)
        if synset_row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        entry_rowid = entry_row["rowid"]
        synset_rowid = synset_row["rowid"]
        lex_rowid = entry_row["lexicon_rowid"]

        # Check duplicate: entry already has sense for this synset
        dup = self._conn.execute(
            "SELECT id FROM senses WHERE entry_rowid = ? AND synset_rowid = ?",
            (entry_rowid, synset_rowid),
        ).fetchone()
        if dup is not None:
            raise DuplicateEntityError(
                f"Entry {entry_id} already has a sense for synset {synset_id}"
            )

        # Determine entry_rank (1-based position)
        max_rank = self._conn.execute(
            "SELECT MAX(entry_rank) FROM senses WHERE entry_rowid = ?",
            (entry_rowid,),
        ).fetchone()[0]
        entry_rank = (max_rank or 0) + 1

        # Determine synset_rank
        max_srank = self._conn.execute(
            "SELECT MAX(synset_rank) FROM senses WHERE synset_rowid = ?",
            (synset_rowid,),
        ).fetchone()[0]
        synset_rank = (max_srank or 0) + 1

        if id is None:
            id = self._generate_sense_id(entry_id, synset_id, entry_rank)
        else:
            lex_id_row = self._conn.execute(
                "SELECT l.id FROM lexicons l WHERE l.rowid = ?",
                (lex_rowid,),
            ).fetchone()
            if lex_id_row and not id.startswith(f"{lex_id_row['id']}-"):
                raise ValidationError(
                    f"ID must start with lexicon prefix: {lex_id_row['id']}-"
                )

        # Check duplicate ID
        if _db.get_sense_rowid(self._conn, id) is not None:
            raise DuplicateEntityError(f"Sense already exists: {id!r}")

        self._conn.execute(
            "INSERT INTO senses "
            "(id, lexicon_rowid, entry_rowid, entry_rank, "
            "synset_rowid, synset_rank, metadata) "
            "VALUES (?, ?, ?, ?, ?, ?, ?)",
            (id, lex_rowid, entry_rowid, entry_rank,
             synset_rowid, synset_rank,
             json.dumps(metadata) if metadata else None),
        )

        sense_rowid = self._conn.execute(
            "SELECT rowid FROM senses WHERE id = ?", (id,)
        ).fetchone()[0]

        if not lexicalized:
            self._conn.execute(
                "INSERT INTO unlexicalized_senses (sense_rowid) VALUES (?)",
                (sense_rowid,),
            )

        if adjposition is not None:
            self._conn.execute(
                "INSERT INTO adjpositions (sense_rowid, adjposition) "
                "VALUES (?, ?)",
                (sense_rowid, adjposition),
            )

        # RULE-EMPTY-002: if synset was unlexicalized, make it lexicalized
        self._conn.execute(
            "DELETE FROM unlexicalized_synsets WHERE synset_rowid = ?",
            (synset_rowid,),
        )

        _hist.record_create(
            self._conn, "sense", id,
            {"entry_id": entry_id, "synset_id": synset_id},
        )

        return self._build_sense_model(id)

    @_modifies_db
    def remove_sense(self, sense_id: str) -> None:
        """Delete a sense and its relations, examples, and counts.

        If the synset has no remaining senses, it becomes unlexicalized.

        Args:
            sense_id: ID of the sense to delete.

        Raises:
            EntityNotFoundError: Sense not found.
        """
        self._remove_sense_internal(sense_id)

    def _remove_sense_internal(self, sense_id: str) -> None:
        """Internal: remove sense and handle unlexicalization."""
        row = _db.get_sense_row(self._conn, sense_id)
        if row is None:
            raise EntityNotFoundError(f"Sense not found: {sense_id!r}")

        sense_rowid = row["rowid"]
        synset_rowid = row["synset_rowid"]

        # Remove sense relations and their inverses
        self._cleanup_sense_relations(sense_rowid)

        # Remove sense-synset relations
        self._conn.execute(
            "DELETE FROM sense_synset_relations WHERE source_rowid = ?",
            (sense_rowid,),
        )

        _hist.record_delete(self._conn, "sense", sense_id)

        # Delete the sense (CASCADE handles examples, counts, adjpositions, etc.)
        self._conn.execute("DELETE FROM senses WHERE id = ?", (sense_id,))

        # RULE-EMPTY-001: check if synset now has zero senses
        remaining = self._conn.execute(
            "SELECT COUNT(*) FROM senses WHERE synset_rowid = ?",
            (synset_rowid,),
        ).fetchone()[0]
        if remaining == 0:
            self._conn.execute(
                "INSERT OR IGNORE INTO unlexicalized_synsets (synset_rowid) "
                "VALUES (?)",
                (synset_rowid,),
            )

    @_modifies_db
    def move_sense(self, sense_id: str, target_synset_id: str) -> SenseModel:
        """Move a sense from its current synset to a different synset.

        The source synset becomes unlexicalized if emptied.  The target
        synset becomes lexicalized if it was unlexicalized.

        Args:
            sense_id: ID of the sense to move.
            target_synset_id: ID of the destination synset.

        Returns:
            The updated sense.

        Raises:
            EntityNotFoundError: Sense or target synset not found.
            DuplicateEntityError: Entry already has a sense in the target
                synset.
        """
        sense_row = _db.get_sense_row(self._conn, sense_id)
        if sense_row is None:
            raise EntityNotFoundError(f"Sense not found: {sense_id!r}")

        target_row = _db.get_synset_row(self._conn, target_synset_id)
        if target_row is None:
            raise EntityNotFoundError(
                f"Synset not found: {target_synset_id!r}"
            )

        entry_rowid = sense_row["entry_rowid"]
        target_synset_rowid = target_row["rowid"]
        source_synset_rowid = sense_row["synset_rowid"]

        # RULE-MOVE-001: duplicate check
        dup = self._conn.execute(
            "SELECT id FROM senses WHERE entry_rowid = ? AND synset_rowid = ?",
            (entry_rowid, target_synset_rowid),
        ).fetchone()
        if dup is not None:
            raise DuplicateEntityError(
                "Entry already has a sense in target synset"
            )

        # Move the sense
        self._conn.execute(
            "UPDATE senses SET synset_rowid = ? WHERE id = ?",
            (target_synset_rowid, sense_id),
        )

        # RULE-EMPTY-002: remove target from unlexicalized
        self._conn.execute(
            "DELETE FROM unlexicalized_synsets WHERE synset_rowid = ?",
            (target_synset_rowid,),
        )

        # RULE-MOVE-003: check if source synset is now empty
        remaining = self._conn.execute(
            "SELECT COUNT(*) FROM senses WHERE synset_rowid = ?",
            (source_synset_rowid,),
        ).fetchone()[0]
        if remaining == 0:
            self._conn.execute(
                "INSERT OR IGNORE INTO unlexicalized_synsets (synset_rowid) "
                "VALUES (?)",
                (source_synset_rowid,),
            )

        _hist.record_update(
            self._conn, "sense", sense_id, "synset_rowid",
            str(source_synset_rowid), str(target_synset_rowid),
        )

        return self._build_sense_model(sense_id)

    @_modifies_db
    def reorder_senses(
        self, entry_id: str, sense_id_order: list[str]
    ) -> None:
        """Set the ordering of senses within an entry.

        Args:
            entry_id: ID of the entry whose senses to reorder.
            sense_id_order: Complete list of the entry's sense IDs in the
                desired order.

        Raises:
            EntityNotFoundError: Entry not found.
            ValidationError: *sense_id_order* does not exactly match the
                entry's current sense IDs.
        """
        entry_row = _db.get_entry_row(self._conn, entry_id)
        if entry_row is None:
            raise EntityNotFoundError(f"Entry not found: {entry_id!r}")

        entry_rowid = entry_row["rowid"]
        current = self._conn.execute(
            "SELECT id FROM senses WHERE entry_rowid = ? ORDER BY entry_rank",
            (entry_rowid,),
        ).fetchall()
        current_ids = {r["id"] for r in current}

        if set(sense_id_order) != current_ids:
            raise ValidationError(
                "sense_id_order must contain exactly the entry's sense IDs"
            )

        for rank, sid in enumerate(sense_id_order, start=1):
            self._conn.execute(
                "UPDATE senses SET entry_rank = ? WHERE id = ?",
                (rank, sid),
            )

    def get_sense(self, sense_id: str) -> SenseModel:
        """Retrieve a sense by its ID.

        Args:
            sense_id: Sense identifier.

        Returns:
            The matching sense.

        Raises:
            EntityNotFoundError: Sense not found.
        """
        model = self._build_sense_model(sense_id)
        if model is None:
            raise EntityNotFoundError(f"Sense not found: {sense_id!r}")
        return model

    def find_senses(
        self,
        *,
        entry_id: str | None = None,
        synset_id: str | None = None,
        lexicon_id: str | None = None,
    ) -> list[SenseModel]:
        """Search for senses matching all given criteria.

        Args:
            entry_id: Filter by parent entry.
            synset_id: Filter by target synset.
            lexicon_id: Filter by parent lexicon.

        Returns:
            List of matching senses ordered by entry rank (may be empty).
        """
        clauses: list[str] = []
        params: list[Any] = []

        if entry_id is not None:
            clauses.append(
                "s.entry_rowid = (SELECT rowid FROM entries WHERE id = ?)"
            )
            params.append(entry_id)
        if synset_id is not None:
            clauses.append(
                "s.synset_rowid = (SELECT rowid FROM synsets WHERE id = ?)"
            )
            params.append(synset_id)
        if lexicon_id is not None:
            clauses.append(
                "s.lexicon_rowid = (SELECT rowid FROM lexicons WHERE id = ?)"
            )
            params.append(lexicon_id)

        where = " AND ".join(clauses) if clauses else "1=1"
        sql = f"SELECT s.id FROM senses s WHERE {where} ORDER BY s.entry_rank"
        rows = self._conn.execute(sql, params).fetchall()
        return [self._build_sense_model(r["id"]) for r in rows]

    def _build_sense_model(self, sense_id: str) -> SenseModel:
        row = self._conn.execute(
            "SELECT s.rowid, s.id, s.entry_rank, s.synset_rank, s.metadata, "
            "e.id as entry_id, syn.id as synset_id, l.id as lexicon_id "
            "FROM senses s "
            "JOIN entries e ON s.entry_rowid = e.rowid "
            "JOIN synsets syn ON s.synset_rowid = syn.rowid "
            "JOIN lexicons l ON s.lexicon_rowid = l.rowid "
            "WHERE s.id = ?",
            (sense_id,),
        ).fetchone()
        if row is None:
            raise EntityNotFoundError(f"Sense not found: {sense_id!r}")

        # Check lexicalized
        unlex = self._conn.execute(
            "SELECT 1 FROM unlexicalized_senses WHERE sense_rowid = ?",
            (row["rowid"],),
        ).fetchone()

        # Get adjposition
        adj_row = self._conn.execute(
            "SELECT adjposition FROM adjpositions WHERE sense_rowid = ?",
            (row["rowid"],),
        ).fetchone()

        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)

        return SenseModel(
            id=row["id"],
            entry_id=row["entry_id"],
            synset_id=row["synset_id"],
            lexicon_id=row["lexicon_id"],
            entry_rank=row["entry_rank"],
            synset_rank=row["synset_rank"],
            lexicalized=unlex is None,
            adjposition=adj_row["adjposition"] if adj_row else None,
            metadata=meta,
        )

    def _generate_sense_id(
        self, entry_id: str, synset_id: str, position: int
    ) -> str:
        # Remove lexicon prefix from synset_id for the local part
        parts = synset_id.split("-", 1)
        local_part = parts[1] if len(parts) > 1 else synset_id
        return f"{entry_id}-{local_part}-{position:02d}"

    def _cleanup_sense_relations(self, sense_rowid: int) -> None:
        """Remove all sense relations involving this sense and their inverses."""
        rels = self._conn.execute(
            "SELECT sr.rowid, sr.source_rowid, sr.target_rowid, rt.type "
            "FROM sense_relations sr "
            "JOIN relation_types rt ON sr.type_rowid = rt.rowid "
            "WHERE sr.source_rowid = ? OR sr.target_rowid = ?",
            (sense_rowid, sense_rowid),
        ).fetchall()

        for rel in rels:
            rel_type = rel["type"]
            inverse = SENSE_RELATION_INVERSES.get(rel_type)
            if inverse:
                inv_type_row = self._conn.execute(
                    "SELECT rowid FROM relation_types WHERE type = ?",
                    (inverse,),
                ).fetchone()
                if inv_type_row:
                    self._conn.execute(
                        "DELETE FROM sense_relations "
                        "WHERE source_rowid = ? AND target_rowid = ? "
                        "AND type_rowid = ?",
                        (rel["target_rowid"], rel["source_rowid"],
                         inv_type_row["rowid"]),
                    )
            self._conn.execute(
                "DELETE FROM sense_relations WHERE rowid = ?",
                (rel["rowid"],),
            )

    # ------------------------------------------------------------------
    # Definition and Example Operations (3.6)
    # ------------------------------------------------------------------

    @_modifies_db
    def add_definition(
        self,
        synset_id: str,
        text: str,
        *,
        language: str | None = None,
        source_sense: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Add a definition to a synset.

        Args:
            synset_id: ID of the synset.
            text: Definition text.
            language: Optional BCP-47 language tag.
            source_sense: Optional sense ID this definition is derived from.
            metadata: Optional metadata dict.

        Raises:
            EntityNotFoundError: Synset (or *source_sense*) not found.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        sense_rowid = None
        if source_sense is not None:
            sr = _db.get_sense_rowid(self._conn, source_sense)
            if sr is None:
                raise EntityNotFoundError(
                    f"Sense not found: {source_sense!r}"
                )
            sense_rowid = sr

        self._conn.execute(
            "INSERT INTO definitions "
            "(lexicon_rowid, synset_rowid, definition, language, "
            "sense_rowid, metadata) VALUES (?, ?, ?, ?, ?, ?)",
            (row["lexicon_rowid"], row["rowid"], text, language,
             sense_rowid,
             json.dumps(metadata) if metadata else None),
        )
        _hist.record_create(
            self._conn, "definition", synset_id,
            {"text": text},
        )

    @_modifies_db
    def update_definition(
        self, synset_id: str, definition_index: int, text: str
    ) -> None:
        """Replace the text of a synset definition by its index.

        Args:
            synset_id: ID of the synset.
            definition_index: Zero-based index among the synset's definitions.
            text: New definition text.

        Raises:
            EntityNotFoundError: Synset not found.
            IndexError: *definition_index* out of range.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        defs = self._conn.execute(
            "SELECT rowid, definition FROM definitions "
            "WHERE synset_rowid = ? ORDER BY rowid",
            (row["rowid"],),
        ).fetchall()

        if definition_index < 0 or definition_index >= len(defs):
            raise IndexError(
                f"Definition index {definition_index} out of range "
                f"(synset has {len(defs)} definitions)"
            )

        target = defs[definition_index]
        _hist.record_update(
            self._conn, "definition", synset_id,
            "text", target["definition"], text,
        )
        self._conn.execute(
            "UPDATE definitions SET definition = ? WHERE rowid = ?",
            (text, target["rowid"]),
        )

    @_modifies_db
    def remove_definition(
        self, synset_id: str, definition_index: int
    ) -> None:
        """Remove a definition from a synset by its index.

        Args:
            synset_id: ID of the synset.
            definition_index: Zero-based index of the definition to remove.

        Raises:
            EntityNotFoundError: Synset not found.
            IndexError: *definition_index* out of range.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        defs = self._conn.execute(
            "SELECT rowid, definition FROM definitions "
            "WHERE synset_rowid = ? ORDER BY rowid",
            (row["rowid"],),
        ).fetchall()

        if definition_index < 0 or definition_index >= len(defs):
            raise IndexError(
                f"Definition index {definition_index} out of range"
            )

        target = defs[definition_index]
        _hist.record_delete(
            self._conn, "definition", synset_id,
            {"text": target["definition"]},
        )
        self._conn.execute(
            "DELETE FROM definitions WHERE rowid = ?", (target["rowid"],)
        )

    @_modifies_db
    def add_synset_example(
        self,
        synset_id: str,
        text: str,
        *,
        language: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Add a usage example to a synset.

        Args:
            synset_id: ID of the synset.
            text: Example text.
            language: Optional BCP-47 language tag.
            metadata: Optional metadata dict.

        Raises:
            EntityNotFoundError: Synset not found.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        self._conn.execute(
            "INSERT INTO synset_examples "
            "(lexicon_rowid, synset_rowid, example, language, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (row["lexicon_rowid"], row["rowid"], text, language,
             json.dumps(metadata) if metadata else None),
        )
        _hist.record_create(
            self._conn, "example", synset_id, {"text": text}
        )

    @_modifies_db
    def remove_synset_example(
        self, synset_id: str, example_index: int
    ) -> None:
        """Remove a usage example from a synset by its index.

        Args:
            synset_id: ID of the synset.
            example_index: Zero-based index of the example to remove.

        Raises:
            EntityNotFoundError: Synset not found.
            IndexError: *example_index* out of range.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        examples = self._conn.execute(
            "SELECT rowid, example FROM synset_examples "
            "WHERE synset_rowid = ? ORDER BY rowid",
            (row["rowid"],),
        ).fetchall()

        if example_index < 0 or example_index >= len(examples):
            raise IndexError(
                f"Example index {example_index} out of range"
            )

        target = examples[example_index]
        _hist.record_delete(
            self._conn, "example", synset_id,
            {"text": target["example"]},
        )
        self._conn.execute(
            "DELETE FROM synset_examples WHERE rowid = ?",
            (target["rowid"],),
        )

    @_modifies_db
    def add_sense_example(
        self,
        sense_id: str,
        text: str,
        *,
        language: str | None = None,
        metadata: dict | None = None,
    ) -> None:
        """Add a usage example to a sense.

        Args:
            sense_id: ID of the sense.
            text: Example text.
            language: Optional BCP-47 language tag.
            metadata: Optional metadata dict.

        Raises:
            EntityNotFoundError: Sense not found.
        """
        row = _db.get_sense_row(self._conn, sense_id)
        if row is None:
            raise EntityNotFoundError(f"Sense not found: {sense_id!r}")

        self._conn.execute(
            "INSERT INTO sense_examples "
            "(lexicon_rowid, sense_rowid, example, language, metadata) "
            "VALUES (?, ?, ?, ?, ?)",
            (row["lexicon_rowid"], row["rowid"], text, language,
             json.dumps(metadata) if metadata else None),
        )
        _hist.record_create(
            self._conn, "example", sense_id, {"text": text}
        )

    @_modifies_db
    def remove_sense_example(
        self, sense_id: str, example_index: int
    ) -> None:
        """Remove a usage example from a sense by its index.

        Args:
            sense_id: ID of the sense.
            example_index: Zero-based index of the example to remove.

        Raises:
            EntityNotFoundError: Sense not found.
            IndexError: *example_index* out of range.
        """
        row = _db.get_sense_row(self._conn, sense_id)
        if row is None:
            raise EntityNotFoundError(f"Sense not found: {sense_id!r}")

        examples = self._conn.execute(
            "SELECT rowid, example FROM sense_examples "
            "WHERE sense_rowid = ? ORDER BY rowid",
            (row["rowid"],),
        ).fetchall()

        if example_index < 0 or example_index >= len(examples):
            raise IndexError(
                f"Example index {example_index} out of range"
            )

        target = examples[example_index]
        _hist.record_delete(
            self._conn, "example", sense_id,
            {"text": target["example"]},
        )
        self._conn.execute(
            "DELETE FROM sense_examples WHERE rowid = ?",
            (target["rowid"],),
        )

    def get_definitions(self, synset_id: str) -> list[DefinitionModel]:
        """Return all definitions of a synset, ordered by insertion.

        Args:
            synset_id: ID of the synset.

        Returns:
            List of definitions (may be empty).

        Raises:
            EntityNotFoundError: Synset not found.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        defs = self._conn.execute(
            "SELECT d.definition, d.language, d.sense_rowid, d.metadata, "
            "s.id as sense_id "
            "FROM definitions d "
            "LEFT JOIN senses s ON d.sense_rowid = s.rowid "
            "WHERE d.synset_rowid = ? ORDER BY d.rowid",
            (row["rowid"],),
        ).fetchall()

        result = []
        for d in defs:
            meta = d["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta)
            result.append(DefinitionModel(
                text=d["definition"],
                language=d["language"],
                source_sense=d["sense_id"],
                metadata=meta,
            ))
        return result

    def get_synset_examples(self, synset_id: str) -> list[ExampleModel]:
        """Return all usage examples of a synset.

        Args:
            synset_id: ID of the synset.

        Returns:
            List of examples (may be empty).

        Raises:
            EntityNotFoundError: Synset not found.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        examples = self._conn.execute(
            "SELECT example, language, metadata FROM synset_examples "
            "WHERE synset_rowid = ? ORDER BY rowid",
            (row["rowid"],),
        ).fetchall()

        result = []
        for e in examples:
            meta = e["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta)
            result.append(ExampleModel(
                text=e["example"],
                language=e["language"],
                metadata=meta,
            ))
        return result

    def get_sense_examples(self, sense_id: str) -> list[ExampleModel]:
        """Return all usage examples of a sense.

        Args:
            sense_id: ID of the sense.

        Returns:
            List of examples (may be empty).

        Raises:
            EntityNotFoundError: Sense not found.
        """
        row = _db.get_sense_row(self._conn, sense_id)
        if row is None:
            raise EntityNotFoundError(f"Sense not found: {sense_id!r}")

        examples = self._conn.execute(
            "SELECT example, language, metadata FROM sense_examples "
            "WHERE sense_rowid = ? ORDER BY rowid",
            (row["rowid"],),
        ).fetchall()

        result = []
        for e in examples:
            meta = e["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta)
            result.append(ExampleModel(
                text=e["example"],
                language=e["language"],
                metadata=meta,
            ))
        return result

    # ------------------------------------------------------------------
    # Relation Operations (3.7)
    # ------------------------------------------------------------------

    @_modifies_db
    def add_synset_relation(
        self,
        source_id: str,
        relation_type: str,
        target_id: str,
        *,
        auto_inverse: bool = True,
        metadata: dict | None = None,
    ) -> None:
        """Add a directed relation between two synsets.

        When *auto_inverse* is ``True`` (the default), the corresponding
        inverse relation (e.g. ``hyponym`` for ``hypernym``) is also created
        automatically.  Duplicate relations are silently ignored.

        Args:
            source_id: Source synset ID.
            relation_type: Relation type string (see ``SynsetRelationType``).
            target_id: Target synset ID.
            auto_inverse: Create the inverse relation automatically.
            metadata: Optional metadata dict for the relation.

        Raises:
            ValidationError: Invalid relation type or self-referential.
            EntityNotFoundError: Source or target synset not found.
        """
        if not is_valid_synset_relation(relation_type):
            raise ValidationError(
                f"Invalid synset relation type: {relation_type!r}"
            )
        if source_id == target_id:
            raise ValidationError(
                f"Self-referential relations are not allowed: {source_id}"
            )

        src_row = _db.get_synset_row(self._conn, source_id)
        if src_row is None:
            raise EntityNotFoundError(f"Synset not found: {source_id!r}")
        tgt_row = _db.get_synset_row(self._conn, target_id)
        if tgt_row is None:
            raise EntityNotFoundError(f"Synset not found: {target_id!r}")

        type_rowid = _db.get_or_create_relation_type(
            self._conn, relation_type
        )

        with suppress(sqlite3.IntegrityError):
            self._conn.execute(
                "INSERT INTO synset_relations "
                "(lexicon_rowid, source_rowid, target_rowid, "
                "type_rowid, metadata) VALUES (?, ?, ?, ?, ?)",
                (src_row["lexicon_rowid"], src_row["rowid"],
                 tgt_row["rowid"], type_rowid,
                 json.dumps(metadata) if metadata else None),
            )

        _hist.record_create(
            self._conn, "relation",
            f"{source_id}->{relation_type}->{target_id}",
        )

        # Auto-inverse
        if auto_inverse:
            inverse = SYNSET_RELATION_INVERSES.get(relation_type)
            if inverse:
                inv_type_rowid = _db.get_or_create_relation_type(
                    self._conn, inverse
                )
                self._conn.execute(
                    "INSERT OR IGNORE INTO synset_relations "
                    "(lexicon_rowid, source_rowid, target_rowid, "
                    "type_rowid, metadata) "
                    "VALUES (?, ?, ?, ?, NULL)",
                    (tgt_row["lexicon_rowid"], tgt_row["rowid"],
                     src_row["rowid"], inv_type_rowid),
                )

    @_modifies_db
    def remove_synset_relation(
        self,
        source_id: str,
        relation_type: str,
        target_id: str,
        *,
        auto_inverse: bool = True,
    ) -> None:
        """Remove a directed relation between two synsets.

        When *auto_inverse* is ``True``, the inverse relation is also removed.
        No-op if the relation does not exist.

        Args:
            source_id: Source synset ID.
            relation_type: Relation type string.
            target_id: Target synset ID.
            auto_inverse: Also remove the inverse relation.
        """
        src_row = _db.get_synset_row(self._conn, source_id)
        tgt_row = _db.get_synset_row(self._conn, target_id)
        if src_row is None or tgt_row is None:
            return

        type_row = self._conn.execute(
            "SELECT rowid FROM relation_types WHERE type = ?",
            (relation_type,),
        ).fetchone()
        if type_row is None:
            return

        self._conn.execute(
            "DELETE FROM synset_relations "
            "WHERE source_rowid = ? AND target_rowid = ? AND type_rowid = ?",
            (src_row["rowid"], tgt_row["rowid"], type_row["rowid"]),
        )

        _hist.record_delete(
            self._conn, "relation",
            f"{source_id}->{relation_type}->{target_id}",
        )

        if auto_inverse:
            inverse = SYNSET_RELATION_INVERSES.get(relation_type)
            if inverse:
                inv_type_row = self._conn.execute(
                    "SELECT rowid FROM relation_types WHERE type = ?",
                    (inverse,),
                ).fetchone()
                if inv_type_row:
                    self._conn.execute(
                        "DELETE FROM synset_relations "
                        "WHERE source_rowid = ? AND target_rowid = ? "
                        "AND type_rowid = ?",
                        (tgt_row["rowid"], src_row["rowid"],
                         inv_type_row["rowid"]),
                    )

    @_modifies_db
    def add_sense_relation(
        self,
        source_id: str,
        relation_type: str,
        target_id: str,
        *,
        auto_inverse: bool = True,
        metadata: dict | None = None,
    ) -> None:
        """Add a directed relation between two senses.

        When *auto_inverse* is ``True``, the inverse relation is also created.
        Duplicate relations are silently ignored.

        Args:
            source_id: Source sense ID.
            relation_type: Relation type string (see ``SenseRelationType``).
            target_id: Target sense ID.
            auto_inverse: Create the inverse relation automatically.
            metadata: Optional metadata dict for the relation.

        Raises:
            ValidationError: Invalid relation type or self-referential.
            EntityNotFoundError: Source or target sense not found.
        """
        if not is_valid_sense_relation(relation_type):
            raise ValidationError(
                f"Invalid sense relation type: {relation_type!r}"
            )
        if source_id == target_id:
            raise ValidationError(
                f"Self-referential relations are not allowed: {source_id}"
            )

        src_row = _db.get_sense_row(self._conn, source_id)
        if src_row is None:
            raise EntityNotFoundError(f"Sense not found: {source_id!r}")
        tgt_row = _db.get_sense_row(self._conn, target_id)
        if tgt_row is None:
            raise EntityNotFoundError(f"Sense not found: {target_id!r}")

        type_rowid = _db.get_or_create_relation_type(
            self._conn, relation_type
        )

        with suppress(sqlite3.IntegrityError):
            self._conn.execute(
                "INSERT INTO sense_relations "
                "(lexicon_rowid, source_rowid, target_rowid, type_rowid, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                (src_row["lexicon_rowid"], src_row["rowid"],
                 tgt_row["rowid"], type_rowid,
                 json.dumps(metadata) if metadata else None),
            )

        _hist.record_create(
            self._conn, "relation",
            f"{source_id}->{relation_type}->{target_id}",
        )

        if auto_inverse:
            inverse = SENSE_RELATION_INVERSES.get(relation_type)
            if inverse:
                inv_type_rowid = _db.get_or_create_relation_type(
                    self._conn, inverse
                )
                self._conn.execute(
                    "INSERT OR IGNORE INTO sense_relations "
                    "(lexicon_rowid, source_rowid, target_rowid, "
                    "type_rowid, metadata) "
                    "VALUES (?, ?, ?, ?, NULL)",
                    (tgt_row["lexicon_rowid"], tgt_row["rowid"],
                     src_row["rowid"], inv_type_rowid),
                )

    @_modifies_db
    def remove_sense_relation(
        self,
        source_id: str,
        relation_type: str,
        target_id: str,
        *,
        auto_inverse: bool = True,
    ) -> None:
        """Remove a directed relation between two senses.

        When *auto_inverse* is ``True``, the inverse relation is also removed.
        No-op if the relation does not exist.

        Args:
            source_id: Source sense ID.
            relation_type: Relation type string.
            target_id: Target sense ID.
            auto_inverse: Also remove the inverse relation.
        """
        src_row = _db.get_sense_row(self._conn, source_id)
        tgt_row = _db.get_sense_row(self._conn, target_id)
        if src_row is None or tgt_row is None:
            return

        type_row = self._conn.execute(
            "SELECT rowid FROM relation_types WHERE type = ?",
            (relation_type,),
        ).fetchone()
        if type_row is None:
            return

        self._conn.execute(
            "DELETE FROM sense_relations "
            "WHERE source_rowid = ? AND target_rowid = ? AND type_rowid = ?",
            (src_row["rowid"], tgt_row["rowid"], type_row["rowid"]),
        )

        if auto_inverse:
            inverse = SENSE_RELATION_INVERSES.get(relation_type)
            if inverse:
                inv_type_row = self._conn.execute(
                    "SELECT rowid FROM relation_types WHERE type = ?",
                    (inverse,),
                ).fetchone()
                if inv_type_row:
                    self._conn.execute(
                        "DELETE FROM sense_relations "
                        "WHERE source_rowid = ? AND target_rowid = ? "
                        "AND type_rowid = ?",
                        (tgt_row["rowid"], src_row["rowid"],
                         inv_type_row["rowid"]),
                    )

    @_modifies_db
    def add_sense_synset_relation(
        self,
        source_sense_id: str,
        relation_type: str,
        target_synset_id: str,
        *,
        metadata: dict | None = None,
    ) -> None:
        """Add a relation from a sense to a synset.

        Duplicate relations are silently ignored.

        Args:
            source_sense_id: Source sense ID.
            relation_type: Relation type string (see
                ``SenseSynsetRelationType``).
            target_synset_id: Target synset ID.
            metadata: Optional metadata dict.

        Raises:
            ValidationError: Invalid relation type.
            EntityNotFoundError: Sense or synset not found.
        """
        if not is_valid_sense_synset_relation(relation_type):
            raise ValidationError(
                f"Invalid sense-synset relation type: {relation_type!r}"
            )

        src_row = _db.get_sense_row(self._conn, source_sense_id)
        if src_row is None:
            raise EntityNotFoundError(
                f"Sense not found: {source_sense_id!r}"
            )
        tgt_row = _db.get_synset_row(self._conn, target_synset_id)
        if tgt_row is None:
            raise EntityNotFoundError(
                f"Synset not found: {target_synset_id!r}"
            )

        type_rowid = _db.get_or_create_relation_type(
            self._conn, relation_type
        )

        with suppress(sqlite3.IntegrityError):
            self._conn.execute(
                "INSERT INTO sense_synset_relations "
                "(lexicon_rowid, source_rowid, target_rowid, type_rowid, metadata) "
                "VALUES (?, ?, ?, ?, ?)",
                (src_row["lexicon_rowid"], src_row["rowid"],
                 tgt_row["rowid"], type_rowid,
                 json.dumps(metadata) if metadata else None),
            )

    @_modifies_db
    def remove_sense_synset_relation(
        self,
        source_sense_id: str,
        relation_type: str,
        target_synset_id: str,
    ) -> None:
        """Remove a relation from a sense to a synset.

        No-op if the relation does not exist.

        Args:
            source_sense_id: Source sense ID.
            relation_type: Relation type string.
            target_synset_id: Target synset ID.
        """
        src_row = _db.get_sense_row(self._conn, source_sense_id)
        tgt_row = _db.get_synset_row(self._conn, target_synset_id)
        if src_row is None or tgt_row is None:
            return

        type_row = self._conn.execute(
            "SELECT rowid FROM relation_types WHERE type = ?",
            (relation_type,),
        ).fetchone()
        if type_row is None:
            return

        self._conn.execute(
            "DELETE FROM sense_synset_relations "
            "WHERE source_rowid = ? AND target_rowid = ? AND type_rowid = ?",
            (src_row["rowid"], tgt_row["rowid"], type_row["rowid"]),
        )

    def get_synset_relations(
        self,
        synset_id: str,
        *,
        relation_type: str | None = None,
    ) -> list[RelationModel]:
        """Return outgoing relations from a synset.

        Args:
            synset_id: ID of the source synset.
            relation_type: Optional filter by relation type.

        Returns:
            List of outgoing relations (may be empty).

        Raises:
            EntityNotFoundError: Synset not found.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        clauses = ["sr.source_rowid = ?"]
        params: list[Any] = [row["rowid"]]

        if relation_type is not None:
            clauses.append("rt.type = ?")
            params.append(relation_type)

        where = " AND ".join(clauses)
        rels = self._conn.execute(
            f"SELECT src.id as source_id, tgt.id as target_id, "
            f"rt.type as rel_type, sr.metadata "
            f"FROM synset_relations sr "
            f"JOIN synsets src ON sr.source_rowid = src.rowid "
            f"JOIN synsets tgt ON sr.target_rowid = tgt.rowid "
            f"JOIN relation_types rt ON sr.type_rowid = rt.rowid "
            f"WHERE {where}",
            params,
        ).fetchall()

        result = []
        for r in rels:
            meta = r["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta)
            result.append(RelationModel(
                source_id=r["source_id"],
                target_id=r["target_id"],
                relation_type=r["rel_type"],
                metadata=meta,
            ))
        return result

    def get_sense_relations(
        self,
        sense_id: str,
        *,
        relation_type: str | None = None,
    ) -> list[RelationModel]:
        """Return outgoing relations from a sense.

        Args:
            sense_id: ID of the source sense.
            relation_type: Optional filter by relation type.

        Returns:
            List of outgoing relations (may be empty).

        Raises:
            EntityNotFoundError: Sense not found.
        """
        row = _db.get_sense_row(self._conn, sense_id)
        if row is None:
            raise EntityNotFoundError(f"Sense not found: {sense_id!r}")

        clauses = ["sr.source_rowid = ?"]
        params: list[Any] = [row["rowid"]]

        if relation_type is not None:
            clauses.append("rt.type = ?")
            params.append(relation_type)

        where = " AND ".join(clauses)
        rels = self._conn.execute(
            f"SELECT src.id as source_id, tgt.id as target_id, "
            f"rt.type as rel_type, sr.metadata "
            f"FROM sense_relations sr "
            f"JOIN senses src ON sr.source_rowid = src.rowid "
            f"JOIN senses tgt ON sr.target_rowid = tgt.rowid "
            f"JOIN relation_types rt ON sr.type_rowid = rt.rowid "
            f"WHERE {where}",
            params,
        ).fetchall()

        result = []
        for r in rels:
            meta = r["metadata"]
            if isinstance(meta, str):
                meta = json.loads(meta)
            result.append(RelationModel(
                source_id=r["source_id"],
                target_id=r["target_id"],
                relation_type=r["rel_type"],
                metadata=meta,
            ))
        return result

    # ------------------------------------------------------------------
    # ILI Operations (3.8)
    # ------------------------------------------------------------------

    @_modifies_db
    def link_ili(self, synset_id: str, ili_id: str) -> None:
        """Link a synset to an existing ILI entry.

        Args:
            synset_id: ID of the synset.
            ili_id: ILI identifier (e.g. ``"i12345"``).

        Raises:
            EntityNotFoundError: Synset not found.
            ValidationError: Synset already has an ILI or proposed ILI.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        if row["ili_rowid"] is not None:
            raise ValidationError(
                f"Synset {synset_id} already has an ILI mapping"
            )
        # Also check proposed ILI
        proposed = self._conn.execute(
            "SELECT 1 FROM proposed_ilis WHERE synset_rowid = ?",
            (row["rowid"],),
        ).fetchone()
        if proposed is not None:
            raise ValidationError(
                f"Synset {synset_id} already has a proposed ILI"
            )

        ili_rowid = _db.get_or_create_ili(self._conn, ili_id)
        self._conn.execute(
            "UPDATE synsets SET ili_rowid = ? WHERE id = ?",
            (ili_rowid, synset_id),
        )
        _hist.record_update(
            self._conn, "synset", synset_id, "ili", None, ili_id
        )

    @_modifies_db
    def unlink_ili(self, synset_id: str) -> None:
        """Remove the ILI mapping (or proposed ILI) from a synset.

        Args:
            synset_id: ID of the synset.

        Raises:
            EntityNotFoundError: Synset not found.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        _hist.record_update(
            self._conn, "synset", synset_id, "ili",
            str(row["ili_rowid"]), None,
        )
        self._conn.execute(
            "UPDATE synsets SET ili_rowid = NULL WHERE id = ?",
            (synset_id,),
        )
        # Also remove proposed ILI if any
        self._conn.execute(
            "DELETE FROM proposed_ilis WHERE synset_rowid = ?",
            (row["rowid"],),
        )

    @_modifies_db
    def propose_ili(
        self,
        synset_id: str,
        definition: str,
        *,
        metadata: dict | None = None,
    ) -> None:
        """Propose a new ILI entry for a synset.

        Args:
            synset_id: ID of the synset.
            definition: ILI definition (minimum 20 characters).
            metadata: Optional metadata dict.

        Raises:
            EntityNotFoundError: Synset not found.
            ValidationError: Synset already has an ILI or proposed ILI, or
                definition is too short.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        if row["ili_rowid"] is not None:
            raise ValidationError(
                f"Synset {synset_id} already has an ILI mapping"
            )

        if len(definition) < 20:
            raise ValidationError(
                "ILI definition must be at least 20 characters"
            )

        # Check for existing proposed ILI
        existing = self._conn.execute(
            "SELECT 1 FROM proposed_ilis WHERE synset_rowid = ?",
            (row["rowid"],),
        ).fetchone()
        if existing is not None:
            raise ValidationError(
                f"Synset {synset_id} already has a proposed ILI"
            )

        self._conn.execute(
            "INSERT INTO proposed_ilis (synset_rowid, definition, metadata) "
            "VALUES (?, ?, ?)",
            (row["rowid"], definition,
             json.dumps(metadata) if metadata else None),
        )
        _hist.record_create(
            self._conn, "ili", synset_id,
            {"definition": definition, "type": "proposed"},
        )

    def get_ili(self, synset_id: str) -> ILIModel | None:
        """Get the ILI mapping for a synset.

        Args:
            synset_id: ID of the synset.

        Returns:
            The ILI mapping, or ``None`` if the synset has no ILI.

        Raises:
            EntityNotFoundError: Synset not found.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        if row["ili_rowid"] is not None:
            ili_row = self._conn.execute(
                "SELECT i.id, i.definition, i.metadata, s.status "
                "FROM ilis i JOIN ili_statuses s ON i.status_rowid = s.rowid "
                "WHERE i.rowid = ?",
                (row["ili_rowid"],),
            ).fetchone()
            if ili_row:
                meta = ili_row["metadata"]
                if isinstance(meta, str):
                    meta = json.loads(meta)
                return ILIModel(
                    id=ili_row["id"],
                    status=ili_row["status"],
                    definition=ili_row["definition"],
                    metadata=meta,
                )
        return None

    # ------------------------------------------------------------------
    # Metadata Operations (3.9)
    # ------------------------------------------------------------------

    @_modifies_db
    def set_metadata(
        self,
        entity_type: str,
        entity_id: str,
        key: str,
        value: str | float | None,
    ) -> None:
        """Set or delete a single metadata key on any entity.

        Pass ``None`` as *value* to delete the key.

        Args:
            entity_type: One of ``"lexicon"``, ``"synset"``, ``"entry"``,
                ``"sense"``.
            entity_id: ID of the entity.
            key: Metadata key.
            value: Value to set, or ``None`` to delete the key.

        Raises:
            EntityNotFoundError: Entity not found.
            ValidationError: Unknown *entity_type*.
        """
        table, id_col = self._resolve_entity_table(entity_type)
        row = self._conn.execute(
            f"SELECT rowid, metadata FROM {table} WHERE {id_col} = ?",
            (entity_id,),
        ).fetchone()
        if row is None:
            raise EntityNotFoundError(
                f"{entity_type} not found: {entity_id!r}"
            )

        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)
        if meta is None:
            meta = {}

        if value is None:
            meta.pop(key, None)
        else:
            meta[key] = value

        self._conn.execute(
            f"UPDATE {table} SET metadata = ? WHERE rowid = ?",
            (json.dumps(meta) if meta else None, row["rowid"]),
        )

    def get_metadata(self, entity_type: str, entity_id: str) -> dict:
        """Return the full metadata dict for an entity.

        Args:
            entity_type: One of ``"lexicon"``, ``"synset"``, ``"entry"``,
                ``"sense"``.
            entity_id: ID of the entity.

        Returns:
            Metadata dict (empty dict if no metadata is set).

        Raises:
            EntityNotFoundError: Entity not found.
            ValidationError: Unknown *entity_type*.
        """
        table, id_col = self._resolve_entity_table(entity_type)
        row = self._conn.execute(
            f"SELECT metadata FROM {table} WHERE {id_col} = ?",
            (entity_id,),
        ).fetchone()
        if row is None:
            raise EntityNotFoundError(
                f"{entity_type} not found: {entity_id!r}"
            )
        meta = row["metadata"]
        if isinstance(meta, str):
            meta = json.loads(meta)
        return meta or {}

    @_modifies_db
    def set_confidence(
        self, entity_type: str, entity_id: str, score: float
    ) -> None:
        """Set the ``confidenceScore`` metadata key on an entity.

        Args:
            entity_type: One of ``"lexicon"``, ``"synset"``, ``"entry"``,
                ``"sense"``.
            entity_id: ID of the entity.
            score: Confidence score (typically 0.0 to 1.0).

        Raises:
            EntityNotFoundError: Entity not found.
            ValidationError: Unknown *entity_type*.
        """
        self.set_metadata(entity_type, entity_id, "confidenceScore", score)

    def _resolve_entity_table(
        self, entity_type: str
    ) -> tuple[str, str]:
        """Map entity type name to (table, id_column)."""
        mapping: dict[str, tuple[str, str]] = {
            "lexicon": ("lexicons", "id"),
            "synset": ("synsets", "id"),
            "entry": ("entries", "id"),
            "sense": ("senses", "id"),
        }
        if entity_type not in mapping:
            raise ValidationError(f"Unknown entity type: {entity_type!r}")
        return mapping[entity_type]

    # ------------------------------------------------------------------
    # Compound Operations: Merge (3.3)
    # ------------------------------------------------------------------

    @_modifies_db
    def merge_synsets(
        self, source_id: str, target_id: str
    ) -> SynsetModel:
        """Merge two synsets atomically.

        Moves all senses, definitions, examples, and relations from the
        source synset into the target synset, then deletes the source.
        Duplicate definitions and self-loop relations are removed.

        Args:
            source_id: ID of the synset to merge from (will be deleted).
            target_id: ID of the synset to merge into (will be kept).

        Returns:
            The updated target synset.

        Raises:
            EntityNotFoundError: Source or target synset not found.
            ConflictError: Both synsets have ILI mappings.
        """
        src = _db.get_synset_row(self._conn, source_id)
        if src is None:
            raise EntityNotFoundError(f"Synset not found: {source_id!r}")
        tgt = _db.get_synset_row(self._conn, target_id)
        if tgt is None:
            raise EntityNotFoundError(f"Synset not found: {target_id!r}")

        src_rowid = src["rowid"]
        tgt_rowid = tgt["rowid"]

        # RULE-MERGE-006: ILI handling
        src_has_ili = src["ili_rowid"] is not None
        tgt_has_ili = tgt["ili_rowid"] is not None
        src_has_proposed = self._conn.execute(
            "SELECT 1 FROM proposed_ilis WHERE synset_rowid = ?",
            (src_rowid,),
        ).fetchone() is not None
        tgt_has_proposed = self._conn.execute(
            "SELECT 1 FROM proposed_ilis WHERE synset_rowid = ?",
            (tgt_rowid,),
        ).fetchone() is not None

        if (src_has_ili or src_has_proposed) and (tgt_has_ili or tgt_has_proposed):
            raise ConflictError("Both synsets have ILI mappings")

        # Transfer ILI if source has it and target doesn't
        if src_has_ili and not tgt_has_ili:
            self._conn.execute(
                "UPDATE synsets SET ili_rowid = ? WHERE rowid = ?",
                (src["ili_rowid"], tgt_rowid),
            )
        if src_has_proposed and not tgt_has_proposed:
            self._conn.execute(
                "UPDATE proposed_ilis SET synset_rowid = ? "
                "WHERE synset_rowid = ?",
                (tgt_rowid, src_rowid),
            )

        # RULE-MERGE-001: Sense transfer
        senses = self._conn.execute(
            "SELECT rowid, id, entry_rowid FROM senses "
            "WHERE synset_rowid = ?",
            (src_rowid,),
        ).fetchall()

        for s in senses:
            # Check for duplicate (same entry already has sense in target)
            dup = self._conn.execute(
                "SELECT id FROM senses "
                "WHERE entry_rowid = ? AND synset_rowid = ?",
                (s["entry_rowid"], tgt_rowid),
            ).fetchone()
            if dup:
                # Delete redundant sense from source
                self._conn.execute(
                    "DELETE FROM senses WHERE rowid = ?", (s["rowid"],)
                )
            else:
                self._conn.execute(
                    "UPDATE senses SET synset_rowid = ? WHERE rowid = ?",
                    (tgt_rowid, s["rowid"]),
                )

        # RULE-MERGE-002/003: Relation redirect
        # Outgoing relations from source -> update to from target
        out_rels = self._conn.execute(
            "SELECT rowid, target_rowid, type_rowid FROM synset_relations "
            "WHERE source_rowid = ?",
            (src_rowid,),
        ).fetchall()
        for rel in out_rels:
            if rel["target_rowid"] == tgt_rowid:
                # Would create self-loop, remove
                self._conn.execute(
                    "DELETE FROM synset_relations WHERE rowid = ?",
                    (rel["rowid"],),
                )
            else:
                try:
                    self._conn.execute(
                        "UPDATE synset_relations "
                        "SET source_rowid = ? WHERE rowid = ?",
                        (tgt_rowid, rel["rowid"]),
                    )
                except sqlite3.IntegrityError:
                    # Duplicate, remove
                    self._conn.execute(
                        "DELETE FROM synset_relations WHERE rowid = ?",
                        (rel["rowid"],),
                    )

        # Incoming relations to source -> redirect to target
        in_rels = self._conn.execute(
            "SELECT rowid, source_rowid, type_rowid FROM synset_relations "
            "WHERE target_rowid = ?",
            (src_rowid,),
        ).fetchall()
        for rel in in_rels:
            if rel["source_rowid"] == tgt_rowid:
                self._conn.execute(
                    "DELETE FROM synset_relations WHERE rowid = ?",
                    (rel["rowid"],),
                )
            else:
                try:
                    self._conn.execute(
                        "UPDATE synset_relations "
                        "SET target_rowid = ? WHERE rowid = ?",
                        (tgt_rowid, rel["rowid"]),
                    )
                except sqlite3.IntegrityError:
                    self._conn.execute(
                        "DELETE FROM synset_relations WHERE rowid = ?",
                        (rel["rowid"],),
                    )

        # RULE-MERGE-004: Definition merge
        tgt_defs = {
            r["definition"].strip()
            for r in self._conn.execute(
                "SELECT definition FROM definitions "
                "WHERE synset_rowid = ?",
                (tgt_rowid,),
            ).fetchall()
            if r["definition"]
        }
        src_defs = self._conn.execute(
            "SELECT rowid, definition FROM definitions "
            "WHERE synset_rowid = ?",
            (src_rowid,),
        ).fetchall()
        for d in src_defs:
            if d["definition"] and d["definition"].strip() not in tgt_defs:
                self._conn.execute(
                    "UPDATE definitions SET synset_rowid = ? WHERE rowid = ?",
                    (tgt_rowid, d["rowid"]),
                )
            else:
                self._conn.execute(
                    "DELETE FROM definitions WHERE rowid = ?",
                    (d["rowid"],),
                )

        # RULE-MERGE-005: Example merge
        self._conn.execute(
            "UPDATE synset_examples SET synset_rowid = ? "
            "WHERE synset_rowid = ?",
            (tgt_rowid, src_rowid),
        )

        # Remove target from unlexicalized
        self._conn.execute(
            "DELETE FROM unlexicalized_synsets WHERE synset_rowid = ?",
            (tgt_rowid,),
        )

        # RULE-MERGE-007: Delete source
        self._conn.execute(
            "DELETE FROM synsets WHERE rowid = ?", (src_rowid,)
        )

        _hist.record_update(
            self._conn, "synset", target_id, "merge_from",
            None, source_id,
        )

        return self._build_synset_model(target_id)

    # ------------------------------------------------------------------
    # Compound Operations: Split (3.3)
    # ------------------------------------------------------------------

    @_modifies_db
    def split_synset(
        self, synset_id: str, sense_groups: list[list[str]]
    ) -> list[SynsetModel]:
        """Split a synset into multiple synsets atomically.

        The first group keeps the original synset.  Each subsequent group
        creates a new synset and moves its senses there.  Outgoing relations
        are copied to all new synsets.

        Args:
            synset_id: ID of the synset to split.
            sense_groups: List of sense-ID lists.  Must partition the synset's
                senses exactly and contain at least 2 groups.

        Returns:
            List of resulting synsets (original first, then new ones).

        Raises:
            EntityNotFoundError: Synset not found.
            ValidationError: Groups don't partition the senses exactly, or
                fewer than 2 groups provided.
        """
        row = _db.get_synset_row(self._conn, synset_id)
        if row is None:
            raise EntityNotFoundError(f"Synset not found: {synset_id!r}")

        synset_rowid = row["rowid"]
        lex_rowid = row["lexicon_rowid"]
        lex_id = self._conn.execute(
            "SELECT id FROM lexicons WHERE rowid = ?",
            (lex_rowid,),
        ).fetchone()["id"]

        # RULE-SPLIT-001: Validate sense groups
        current_senses = self._conn.execute(
            "SELECT id FROM senses WHERE synset_rowid = ?",
            (synset_rowid,),
        ).fetchall()
        current_ids = {s["id"] for s in current_senses}
        provided_ids: set[str] = set()
        for group in sense_groups:
            for sid in group:
                if sid in provided_ids:
                    raise ValidationError(f"Duplicate sense in groups: {sid}")
                provided_ids.add(sid)

        if provided_ids != current_ids:
            raise ValidationError(
                "sense_groups must partition the synset's senses exactly"
            )

        if len(sense_groups) < 2:
            raise ValidationError(
                "Need at least 2 sense groups to split"
            )

        result = []

        # First group stays with original synset (no change needed)
        result.append(self._build_synset_model(synset_id))

        # Get outgoing relations for copying
        outgoing = self._conn.execute(
            "SELECT type_rowid, target_rowid, metadata "
            "FROM synset_relations WHERE source_rowid = ?",
            (synset_rowid,),
        ).fetchall()

        # Create new synsets for subsequent groups
        for group in sense_groups[1:]:
            new_id = self._generate_synset_id(lex_id, lex_rowid, row["pos"])
            self._conn.execute(
                "INSERT INTO synsets "
                "(id, lexicon_rowid, pos, metadata) VALUES (?, ?, ?, NULL)",
                (new_id, lex_rowid, row["pos"]),
            )
            new_rowid = self._conn.execute(
                "SELECT rowid FROM synsets WHERE id = ?", (new_id,)
            ).fetchone()[0]

            # Move senses
            for sid in group:
                self._conn.execute(
                    "UPDATE senses SET synset_rowid = ? WHERE id = ?",
                    (new_rowid, sid),
                )

            # RULE-SPLIT-004: Copy outgoing relations
            for rel in outgoing:
                with suppress(sqlite3.IntegrityError):
                    self._conn.execute(
                        "INSERT INTO synset_relations "
                        "(lexicon_rowid, source_rowid, target_rowid, "
                        "type_rowid, metadata) VALUES (?, ?, ?, ?, ?)",
                        (lex_rowid, new_rowid, rel["target_rowid"],
                         rel["type_rowid"], rel["metadata"]),
                    )

            _hist.record_create(
                self._conn, "synset", new_id,
                {"split_from": synset_id},
            )

            result.append(self._build_synset_model(new_id))

        return result

    # ------------------------------------------------------------------
    # Change Tracking (3.12)
    # ------------------------------------------------------------------

    def get_history(
        self,
        *,
        entity_type: str | None = None,
        entity_id: str | None = None,
        since: str | None = None,
        operation: str | None = None,
    ) -> list[EditRecord]:
        """Query the edit history log.

        All parameters are optional; when omitted the full history is returned.

        Args:
            entity_type: Filter by entity type (e.g. ``"synset"``).
            entity_id: Filter by entity ID.
            since: ISO-8601 timestamp; return only records after this time.
            operation: Filter by operation (``"CREATE"``, ``"UPDATE"``,
                ``"DELETE"``).

        Returns:
            List of edit records matching the filters.
        """
        return _hist.query_history(
            self._conn,
            entity_type=entity_type,
            entity_id=entity_id,
            since=since,
            operation=operation,
        )

    def get_changes_since(self, timestamp: str) -> list[EditRecord]:
        """Return all edit records after the given timestamp.

        Args:
            timestamp: ISO-8601 timestamp.

        Returns:
            List of edit records since *timestamp*.
        """
        return self.get_history(since=timestamp)

    # ------------------------------------------------------------------
    # Validation (3.10) — stub, full implementation in Phase 6
    # ------------------------------------------------------------------

    def validate(
        self, *, lexicon_id: str | None = None
    ) -> list[ValidationResult]:
        """Run all 22 validation rules and return any findings.

        Args:
            lexicon_id: Optionally restrict validation to one lexicon.

        Returns:
            List of validation results (errors and warnings).
        """
        from wordnet_editor.validator import validate_all
        return validate_all(self._conn, lexicon_id=lexicon_id)

    def validate_synset(self, synset_id: str) -> list[ValidationResult]:
        """Run validation rules scoped to a single synset.

        Args:
            synset_id: ID of the synset to validate.

        Returns:
            List of validation results for this synset.
        """
        from wordnet_editor.validator import validate_synset
        return validate_synset(self._conn, synset_id)

    def validate_entry(self, entry_id: str) -> list[ValidationResult]:
        """Run validation rules scoped to a single entry.

        Args:
            entry_id: ID of the entry to validate.

        Returns:
            List of validation results for this entry.
        """
        from wordnet_editor.validator import validate_entry
        return validate_entry(self._conn, entry_id)

    def validate_relations(
        self, *, lexicon_id: str | None = None
    ) -> list[ValidationResult]:
        """Run relation-specific validation rules (e.g. missing inverses).

        Args:
            lexicon_id: Optionally restrict to one lexicon.

        Returns:
            List of validation results for relations.
        """
        from wordnet_editor.validator import validate_relations
        return validate_relations(self._conn, lexicon_id=lexicon_id)

    # ------------------------------------------------------------------
    # Import/Export (3.11) — stubs, full implementation in Phase 5
    # ------------------------------------------------------------------

    @classmethod
    def from_wn(
        cls,
        lexicon: str,
        db_path: str | Path = ":memory:",
        *,
        record_history: bool = True,
        version: str | None = None,
        label: str | None = None,
        lexicon_id: str | None = None,
        email: str | None = None,
        license: str | None = None,
        url: str | None = None,
        citation: str | None = None,
    ) -> WordnetEditor:
        """Create an editor pre-loaded from the ``wn`` library.

        Args:
            lexicon: Lexicon specifier understood by ``wn`` (e.g.
                ``"ewn:2024"``).
            db_path: Path for the editor's own database.
            record_history: Record import operations in edit history.
            version: Override the imported lexicon's version.
            label: Override the imported lexicon's label.
            lexicon_id: Override the imported lexicon's ID.
            email: Override the imported lexicon's email.
            license: Override the imported lexicon's license.
            url: Override the imported lexicon's URL.
            citation: Override the imported lexicon's citation.

        Returns:
            A new editor instance with the imported data.

        Raises:
            DataImportError: Import failed.
        """
        from wordnet_editor.importer import import_from_wn

        editor = cls(db_path)
        import_from_wn(
            editor._conn,
            lexicon,
            record_history=record_history,
            overrides={
                "version": version,
                "label": label,
                "lexicon_id": lexicon_id,
                "email": email,
                "license": license,
                "url": url,
                "citation": citation,
            },
        )
        return editor

    @classmethod
    def from_lmf(
        cls,
        source: str | Path,
        db_path: str | Path = ":memory:",
        *,
        record_history: bool = True,
    ) -> WordnetEditor:
        """Create an editor pre-loaded from a WN-LMF XML file.

        Args:
            source: Path to the WN-LMF XML file.
            db_path: Path for the editor's own database.
            record_history: Record import operations in edit history.

        Returns:
            A new editor instance with the imported data.

        Raises:
            DataImportError: Import failed (e.g. malformed XML).
        """
        from wordnet_editor.importer import import_from_lmf

        editor = cls(db_path)
        import_from_lmf(editor._conn, source, record_history=record_history)
        return editor

    @_modifies_db
    def import_lmf(self, source: str | Path) -> None:
        """Import additional data from a WN-LMF XML file into this editor.

        Args:
            source: Path to the WN-LMF XML file.

        Raises:
            DataImportError: Import failed.
        """
        from wordnet_editor.importer import import_from_lmf
        import_from_lmf(self._conn, source, record_history=True)

    def export_lmf(
        self,
        destination: str | Path,
        *,
        lexicon_ids: list[str] | None = None,
        lmf_version: str = "1.4",
    ) -> None:
        """Export the database to a WN-LMF XML file.

        Args:
            destination: Output file path.
            lexicon_ids: Optionally export only specific lexicons.
            lmf_version: LMF schema version (default ``"1.4"``).

        Raises:
            ExportError: Validation errors found in output data.
        """
        from wordnet_editor.exporter import export_to_lmf
        export_to_lmf(
            self._conn, destination,
            lexicon_ids=lexicon_ids, lmf_version=lmf_version,
        )

    def commit_to_wn(
        self,
        *,
        db_path: str | Path | None = None,
        lexicon_ids: list[str] | None = None,
    ) -> None:
        """Push changes back into the ``wn`` library's database.

        Exports to a temporary LMF file and imports it via ``wn.add()``.

        Args:
            db_path: Optional ``wn`` database path (uses default if omitted).
            lexicon_ids: Optionally export only specific lexicons.

        Raises:
            ExportError: Validation errors found in output data.
        """
        from wordnet_editor.exporter import commit_to_wn
        commit_to_wn(
            self._conn, db_path=db_path, lexicon_ids=lexicon_ids,
        )
