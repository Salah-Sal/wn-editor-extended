"""Tests for the validation engine."""

import pytest


class TestValidateClean:
    """TP-VAL-001."""

    def test_validate_clean(self, editor_with_data):
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        results = ed.validate()
        # A clean setup should have no ERRORs
        errors = [r for r in results if r.severity == "ERROR"]
        assert len(errors) == 0


class TestMissingInverse:
    """TP-VAL-002."""

    def test_missing_inverse_detected(self, editor_with_data):
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_synset_relation(
            ss1.id, "hypernym", ss2.id, auto_inverse=False
        )
        results = ed.validate_relations()
        assert any(r.rule_id == "VAL-REL-004" for r in results)


class TestEmptySynset:
    """TP-VAL-003."""

    def test_empty_synset_detected(self, editor_with_lexicon):
        ed = editor_with_lexicon
        ss = ed.create_synset("test", "n", "Test", lexicalized=False)
        results = ed.validate_synset(ss.id)
        assert any(r.rule_id == "VAL-SYN-001" for r in results)


class TestBlankDefinition:
    """TP-VAL-004."""

    def test_blank_definition_detected(self, editor_with_lexicon):
        ed = editor_with_lexicon
        ss = ed.create_synset("test", "n", "Valid definition")
        # Add a blank definition
        ed.add_definition(ss.id, "")
        results = ed.validate()
        assert any(r.rule_id == "VAL-SYN-005" for r in results)


class TestIDPrefixValidation:
    """TP-VAL-005."""

    def test_id_prefix_validation(self, editor_with_lexicon):
        ed = editor_with_lexicon
        # Manually insert a synset with wrong prefix (bypass API)
        lex_rowid = ed._conn.execute(
            "SELECT rowid FROM lexicons WHERE id = 'test'"
        ).fetchone()[0]
        ed._conn.execute(
            "INSERT INTO synsets (id, lexicon_rowid, pos) "
            "VALUES ('wrong-prefix-n', ?, 'n')",
            (lex_rowid,),
        )
        results = ed.validate()
        assert any(r.rule_id == "VAL-EDT-001" for r in results)


class TestValidateEntry:
    """TP-VAL-006."""

    def test_orphan_entry(self, editor_with_lexicon):
        ed = editor_with_lexicon
        entry = ed.create_entry("test", "orphan", "n")
        results = ed.validate_entry(entry.id)
        assert any(r.rule_id == "VAL-ENT-001" for r in results)


class TestDanglingRelation:
    """TP-VAL-007."""

    def test_dangling_relation_target(self, editor_with_data):
        ed, ss1, ss2, e1, e2, s1, s2 = editor_with_data
        ed.add_synset_relation(ss1.id, "hypernym", ss2.id)
        # Disable FK checks, delete the target synset to create a dangling ref
        ed._conn.execute("PRAGMA foreign_keys = OFF")
        ss2_rowid = ed._conn.execute(
            "SELECT rowid FROM synsets WHERE id = ?", (ss2.id,)
        ).fetchone()[0]
        ed._conn.execute(
            "DELETE FROM senses WHERE synset_rowid = ?", (ss2_rowid,)
        )
        # Delete inverse relations pointing FROM ss2
        ed._conn.execute(
            "DELETE FROM synset_relations WHERE source_rowid = ?",
            (ss2_rowid,),
        )
        ed._conn.execute(
            "DELETE FROM definitions WHERE synset_rowid = ?",
            (ss2_rowid,),
        )
        ed._conn.execute(
            "DELETE FROM synsets WHERE id = ?", (ss2.id,)
        )
        ed._conn.execute("PRAGMA foreign_keys = ON")
        results = ed.validate()
        assert any(r.rule_id == "VAL-REL-001" for r in results)
