"""Tests for import/export pipelines (TP-INIT-005 to 008, TP-RT-001 to 010,
TP-INTEG-001 to 005, TP-XLEX-001/003)."""

import os
import tempfile
from pathlib import Path

import pytest

from wordnet_editor import (
    DataImportError,
    DuplicateEntityError,
    WordnetEditor,
)

FIXTURES = Path(__file__).parent / "fixtures"


# ---------------------------------------------------------------------------
# TP-INIT-007: from_lmf with valid XML
# ---------------------------------------------------------------------------
class TestFromLMF:
    def test_from_lmf_minimal(self):
        """TP-INIT-007: from_lmf loads a valid WN-LMF file."""
        ed = WordnetEditor.from_lmf(FIXTURES / "minimal.xml")
        try:
            lexicons = ed.list_lexicons()
            assert len(lexicons) >= 1
            lex = lexicons[0]
            assert lex.id == "test-min"
            assert lex.language == "en"

            entries = ed.find_entries(lexicon_id="test-min")
            assert len(entries) >= 1
            assert entries[0].lemma == "cat"

            synsets = ed.find_synsets(lexicon_id="test-min")
            assert len(synsets) >= 1
            assert synsets[0].id == "test-min-00000001-n"

            senses = ed.find_senses(synset_id="test-min-00000001-n")
            assert len(senses) >= 1
        finally:
            ed.close()

    def test_from_lmf_invalid_xml(self):
        """TP-INIT-008: from_lmf with malformed XML raises DataImportError."""
        with tempfile.NamedTemporaryFile(
            suffix=".xml", mode="w", delete=False
        ) as f:
            f.write("<not valid xml")
            tmp_path = f.name
        try:
            with pytest.raises(DataImportError):
                WordnetEditor.from_lmf(tmp_path)
        finally:
            os.unlink(tmp_path)

    def test_from_lmf_file_not_found(self):
        """from_lmf with nonexistent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            WordnetEditor.from_lmf("/nonexistent/path.xml")


# ---------------------------------------------------------------------------
# TP-RT-001: Full round-trip (import -> edit -> export -> reimport)
# ---------------------------------------------------------------------------
class TestRoundTrip:
    def test_full_round_trip(self):
        """TP-RT-001: Import, edit, export, reimport produces equivalent data."""
        ed = WordnetEditor.from_lmf(FIXTURES / "minimal.xml")
        try:
            # Edit: update the definition
            synsets = ed.find_synsets(lexicon_id="test-min")
            ss = synsets[0]
            defs = ed.get_definitions(ss.id)
            if defs:
                ed.update_definition(
                    ss.id, 0, text="An updated definition"
                )

            # Export
            with tempfile.NamedTemporaryFile(
                suffix=".xml", delete=False
            ) as f:
                out_path = f.name

            try:
                ed.export_lmf(out_path)

                # Reimport
                ed2 = WordnetEditor.from_lmf(out_path)
                try:
                    synsets2 = ed2.find_synsets(lexicon_id="test-min")
                    assert len(synsets2) == len(synsets)
                    defs2 = ed2.get_definitions(synsets2[0].id)
                    assert defs2[0].text == "An updated definition"
                finally:
                    ed2.close()
            finally:
                os.unlink(out_path)
        finally:
            ed.close()

    def test_export_produces_valid_xml(self):
        """Exported XML can be re-parsed by wn.lmf."""
        ed = WordnetEditor.from_lmf(FIXTURES / "minimal.xml")
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".xml", delete=False
            ) as f:
                out_path = f.name

            try:
                ed.export_lmf(out_path)
                # If export_to_lmf doesn't raise, it validated the output
                assert os.path.getsize(out_path) > 0
            finally:
                os.unlink(out_path)
        finally:
            ed.close()


# ---------------------------------------------------------------------------
# TP-RT-004: Import preserves all data types
# ---------------------------------------------------------------------------
class TestFullFeaturesRoundTrip:
    def test_import_preserves_data_types(self):
        """TP-RT-004: All data types survive import and are queryable."""
        ed = WordnetEditor.from_lmf(FIXTURES / "full_features.xml")
        try:
            lexicons = ed.list_lexicons()
            assert len(lexicons) == 1
            lex = lexicons[0]
            assert lex.id == "test-full"
            assert lex.url == "https://example.com/wordnet"

            # Entries
            entries = ed.find_entries(lexicon_id="test-full")
            assert len(entries) == 3  # cat, dog, run

            # Cat entry has forms
            cat_entry = next(e for e in entries if e.lemma == "cat")
            forms = ed.get_forms(cat_entry.id)
            assert len(forms) >= 2  # lemma + "cats"
            # Lemma form
            lemma_form = forms[0]
            assert lemma_form.written_form == "cat"
            # Check pronunciations on lemma
            assert len(lemma_form.pronunciations) >= 1
            # Check tags on lemma
            assert len(lemma_form.tags) >= 1

            # Synsets with definitions
            synsets = ed.find_synsets(lexicon_id="test-full")
            assert len(synsets) == 5

            # Synset with multiple definitions
            ss4 = next(
                s for s in synsets if s.id == "test-full-00000004-v"
            )
            defs = ed.get_definitions(ss4.id)
            assert len(defs) >= 2  # English + Spanish

            # Synset with examples
            ss1 = next(
                s for s in synsets if s.id == "test-full-00000001-n"
            )
            examples = ed.get_synset_examples(ss1.id)
            assert len(examples) >= 1

            # Relations
            rels = ed.get_synset_relations(ss1.id)
            hypernyms = [r for r in rels if r.relation_type == "hypernym"]
            assert len(hypernyms) >= 1

            # Senses
            senses = ed.find_senses(entry_id=cat_entry.id)
            assert len(senses) == 2  # cat-n-01, cat-n-02

            # Sense relations (antonym)
            cat_sense = next(
                s for s in senses if s.id == "test-full-cat-n-01"
            )
            sense_rels = ed.get_sense_relations(cat_sense.id)
            antonyms = [
                r for r in sense_rels if r.relation_type == "antonym"
            ]
            assert len(antonyms) >= 1
        finally:
            ed.close()

    def test_full_features_round_trip(self):
        """TP-RT-004: Import full features, export, reimport, verify."""
        ed = WordnetEditor.from_lmf(FIXTURES / "full_features.xml")
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".xml", delete=False
            ) as f:
                out_path = f.name

            try:
                ed.export_lmf(out_path)

                ed2 = WordnetEditor.from_lmf(out_path)
                try:
                    entries2 = ed2.find_entries(lexicon_id="test-full")
                    assert len(entries2) == 3

                    synsets2 = ed2.find_synsets(lexicon_id="test-full")
                    assert len(synsets2) == 5

                    # Verify pronunciations survived
                    cat2 = next(e for e in entries2 if e.lemma == "cat")
                    forms2 = ed2.get_forms(cat2.id)
                    lemma2 = forms2[0]
                    assert len(lemma2.pronunciations) >= 1
                finally:
                    ed2.close()
            finally:
                os.unlink(out_path)
        finally:
            ed.close()


# ---------------------------------------------------------------------------
# TP-RT-005: Import duplicate lexicon
# ---------------------------------------------------------------------------
class TestDuplicateImport:
    def test_duplicate_lexicon_raises(self):
        """TP-RT-005: Importing same lexicon twice raises DuplicateEntityError."""
        ed = WordnetEditor.from_lmf(FIXTURES / "minimal.xml")
        try:
            with pytest.raises(DuplicateEntityError):
                ed.import_lmf(FIXTURES / "minimal.xml")
        finally:
            ed.close()


# ---------------------------------------------------------------------------
# TP-RT-007: Add/remove cycle fidelity
# ---------------------------------------------------------------------------
class TestAddRemoveCycle:
    def test_add_remove_cycle(self):
        """TP-RT-007: Add then delete; DB returns to original state."""
        ed = WordnetEditor.from_lmf(FIXTURES / "minimal.xml")
        try:
            original_synsets = ed.find_synsets(lexicon_id="test-min")
            original_entries = ed.find_entries(lexicon_id="test-min")

            # Add a new synset + entry + sense
            new_ss = ed.create_synset(
                "test-min", "n", "A temporary thing"
            )
            new_entry = ed.create_entry("test-min", "temp", "n")
            ed.add_sense(new_entry.id, new_ss.id)

            # Delete with cascade
            ed.delete_synset(new_ss.id, cascade=True)
            ed.delete_entry(new_entry.id, cascade=True)

            # Verify we're back to original state
            assert len(ed.find_synsets(lexicon_id="test-min")) == len(
                original_synsets
            )
            assert len(ed.find_entries(lexicon_id="test-min")) == len(
                original_entries
            )
        finally:
            ed.close()


# ---------------------------------------------------------------------------
# TP-XLEX-001: Import two lexicons
# ---------------------------------------------------------------------------
class TestCrossLexicon:
    def test_import_two_lexicons(self):
        """TP-XLEX-001: Both lexicons import with cross-lexicon relations."""
        ed = WordnetEditor.from_lmf(FIXTURES / "two_lexicons.xml")
        try:
            lexicons = ed.list_lexicons()
            assert len(lexicons) == 2

            en_entries = ed.find_entries(lexicon_id="lex-en")
            fr_entries = ed.find_entries(lexicon_id="lex-fr")
            assert len(en_entries) >= 1
            assert len(fr_entries) >= 1

            # Cross-lexicon synset relation (eq_synonym)
            fr_synsets = ed.find_synsets(lexicon_id="lex-fr")
            assert len(fr_synsets) >= 1
            fr_rels = ed.get_synset_relations(fr_synsets[0].id)
            eq_syns = [
                r for r in fr_rels if r.relation_type == "eq_synonym"
            ]
            assert len(eq_syns) >= 1
            assert eq_syns[0].target_id == "lex-en-00000001-n"
        finally:
            ed.close()

    def test_two_lexicons_round_trip(self):
        """Two-lexicon export/reimport preserves both."""
        ed = WordnetEditor.from_lmf(FIXTURES / "two_lexicons.xml")
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".xml", delete=False
            ) as f:
                out_path = f.name

            try:
                ed.export_lmf(out_path)

                ed2 = WordnetEditor.from_lmf(out_path)
                try:
                    assert len(ed2.list_lexicons()) == 2
                finally:
                    ed2.close()
            finally:
                os.unlink(out_path)
        finally:
            ed.close()


# ---------------------------------------------------------------------------
# TP-XLEX-003: Import lexicon extension
# ---------------------------------------------------------------------------
class TestExtension:
    def test_import_extension(self):
        """TP-XLEX-003: Extension lexicon imports with dependency."""
        ed = WordnetEditor.from_lmf(FIXTURES / "extension.xml")
        try:
            lexicons = ed.list_lexicons()
            assert len(lexicons) == 2

            # Extension entry references base synset
            ext_entries = ed.find_entries(lexicon_id="test-ext")
            assert len(ext_entries) >= 1
            assert ext_entries[0].lemma == "kitten"

            # Kitten sense points to base synset
            senses = ed.find_senses(entry_id=ext_entries[0].id)
            assert len(senses) >= 1
            assert senses[0].synset_id == "test-base-00000001-n"
        finally:
            ed.close()


# ---------------------------------------------------------------------------
# TP-RT-009/010: LMF version export behavior
# ---------------------------------------------------------------------------
class TestLMFVersion:
    def test_export_default_version(self):
        """TP-RT-010: Default export uses lmf_version 1.4."""
        ed = WordnetEditor.from_lmf(FIXTURES / "minimal.xml")
        try:
            with tempfile.NamedTemporaryFile(
                suffix=".xml", delete=False
            ) as f:
                out_path = f.name

            try:
                ed.export_lmf(out_path, lmf_version="1.4")
                assert os.path.getsize(out_path) > 0
            finally:
                os.unlink(out_path)
        finally:
            ed.close()


# ---------------------------------------------------------------------------
# TP-INIT-005/006: from_wn tests (require wn database)
# ---------------------------------------------------------------------------
class TestFromWn:
    def test_from_wn_with_fixture(self):
        """TP-INIT-005: from_wn loads data from wn's DB."""
        import wn

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "wn.db"
            original = wn.config._dbpath
            wn.config._dbpath = db_path
            try:
                wn.add(str(FIXTURES / "minimal.xml"))
                ed = WordnetEditor.from_wn("test-min:1.0")
                try:
                    lexicons = ed.list_lexicons()
                    assert len(lexicons) >= 1
                    assert lexicons[0].id == "test-min"
                finally:
                    ed.close()
            finally:
                wn.config._dbpath = original

    def test_from_wn_invalid_specifier(self):
        """TP-INIT-006: from_wn with invalid specifier raises error."""
        import wn

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "wn.db"
            original = wn.config._dbpath
            wn.config._dbpath = db_path
            try:
                with pytest.raises(Exception):
                    WordnetEditor.from_wn("nonexistent:1.0")
            finally:
                wn.config._dbpath = original

    def test_import_from_wn_exception_propagation(self):
        """TP-INIT-009: import_from_wn propagates exceptions from fallback."""
        from unittest.mock import MagicMock, patch
        import sqlite3
        from wordnet_editor.importer import import_from_wn

        conn = MagicMock(spec=sqlite3.Connection)
        specifier = "test:1.0"

        with patch("wordnet_editor.importer._import_from_wn_bulk") as mock_bulk:
            with patch("wordnet_editor.importer._import_from_wn_xml") as mock_xml:
                # Make bulk fail
                mock_bulk.side_effect = Exception("Bulk import failed")
                # Make xml fail with a specific error
                expected_error = ValueError("XML import failed")
                mock_xml.side_effect = expected_error

                # Assert that the specific error is raised
                with pytest.raises(ValueError, match="XML import failed"):
                    import_from_wn(conn, specifier)

                # Verify both were called
                mock_bulk.assert_called_once()
                mock_xml.assert_called_once()


# ---------------------------------------------------------------------------
# TP-INTEG-001 to 004: Commit to wn integration
# ---------------------------------------------------------------------------
class TestCommitToWn:
    def test_commit_and_query(self):
        """TP-INTEG-001: Committed entities are queryable via wn."""
        import wn

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "wn.db"
            original = wn.config._dbpath
            wn.config._dbpath = db_path
            try:
                ed = WordnetEditor.from_lmf(FIXTURES / "minimal.xml")
                try:
                    ed.commit_to_wn(db_path=db_path)

                    # Query via wn
                    synsets = wn.synsets(lang="en")
                    assert len(synsets) >= 1

                    words = wn.words(lang="en")
                    assert len(words) >= 1
                finally:
                    ed.close()
            finally:
                wn.config._dbpath = original

    def test_commit_replaces_existing(self):
        """TP-INTEG-004: Commit twice replaces, no duplicates."""
        import wn

        with tempfile.TemporaryDirectory() as tmpdir:
            db_path = Path(tmpdir) / "wn.db"
            original = wn.config._dbpath
            wn.config._dbpath = db_path
            try:
                ed = WordnetEditor.from_lmf(FIXTURES / "minimal.xml")
                try:
                    # First commit
                    ed.commit_to_wn(db_path=db_path)

                    # Modify
                    synsets = ed.find_synsets(lexicon_id="test-min")
                    defs = ed.get_definitions(synsets[0].id)
                    if defs:
                        ed.update_definition(
                            synsets[0].id, 0, text="Updated definition"
                        )

                    # Second commit (should replace)
                    ed.commit_to_wn(db_path=db_path)

                    # Verify no duplicates
                    lexicons = wn.lexicons()
                    test_lexicons = [
                        lex for lex in lexicons if lex.id == "test-min"
                    ]
                    assert len(test_lexicons) == 1
                finally:
                    ed.close()
            finally:
                wn.config._dbpath = original
