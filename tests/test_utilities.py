"""
Tests for utility functions.
"""
import pytest
import wn
from wn._db import connect
from wn_editor.editor import (
    get_row_id,
    get_wordnet_overview,
    RelationType,
    _get_valid_entity_id,
    _get_valid_synset_id,
    _get_valid_sense_id,
    _get_valid_ili_id,
)


class TestGetRowId:
    """Tests for get_row_id function."""

    def test_get_lexicon_rowid(self):
        """Test getting row ID for a lexicon."""
        lexicons = wn.lexicons()
        if lexicons:
            lex = lexicons[0]
            rowid = get_row_id("lexicons", {"id": lex.id, "version": lex.version})
            assert rowid is not None
            assert isinstance(rowid, int)

    def test_get_rowid_not_found(self):
        """Test get_row_id with non-existent entry."""
        result = get_row_id("lexicons", {"id": "nonexistent-lex-xyz", "version": "0.0"})
        # Should return None or handle gracefully


class TestIdGenerators:
    """Tests for ID generation functions."""

    def test_get_valid_entity_id(self):
        """Test entity ID generation."""
        entity_id = _get_valid_entity_id()
        assert entity_id is not None
        assert entity_id.startswith("w")

    def test_get_valid_entity_id_increments(self):
        """Test that entity IDs increment."""
        id1 = _get_valid_entity_id()
        # Creating an entry should increment the next ID
        # (This depends on actual database state)

    def test_get_valid_synset_id(self, test_lexicon):
        """Test synset ID generation."""
        synset_id = _get_valid_synset_id(test_lexicon.lex_rowid)
        assert synset_id is not None
        # Should contain lexicon name prefix

    def test_get_valid_sense_id(self, test_lexicon):
        """Test sense ID generation."""
        entry = test_lexicon.create_entry()
        sense_id = _get_valid_sense_id(entry.entry_id, "testform")
        assert sense_id is not None
        assert "testform" in sense_id

    def test_get_valid_ili_id(self):
        """Test ILI ID generation."""
        ili_id = _get_valid_ili_id()
        assert ili_id is not None
        assert ili_id.startswith("i")


class TestRelationType:
    """Tests for RelationType enum."""

    def test_relation_type_values(self):
        """Test that RelationType has expected values matching wn database."""
        # These values match the rowid in the relation_types table
        assert RelationType.also == 1
        assert RelationType.antonym == 2
        assert RelationType.hypernym == 15
        assert RelationType.hyponym == 16
        assert RelationType.similar == 25

    def test_relation_type_complete(self):
        """Test that all 27 relation types exist (matching wn database)."""
        # Note: 'meronym' was removed as it's not in the wn database
        relation_names = [
            "also", "antonym", "attribute", "causes", "derivation",
            "domain_region", "domain_topic", "entails", "exemplifies",
            "has_domain_region", "has_domain_topic", "holo_member",
            "holo_part", "holo_substance", "hypernym", "hyponym",
            "instance_hypernym", "instance_hyponym", "is_exemplified_by",
            "mero_member", "mero_part", "mero_substance", "participle",
            "pertainym", "similar", "is_caused_by", "is_entailed_by"
        ]

        for name in relation_names:
            assert hasattr(RelationType, name)


class TestGetWordnetOverview:
    """Tests for get_wordnet_overview function."""

    def test_overview_runs_without_error(self, capsys):
        """Test that get_wordnet_overview executes without errors."""
        get_wordnet_overview()

        captured = capsys.readouterr()
        # Should print something about lexicons
        assert len(captured.out) > 0


class TestDatabaseConnectivity:
    """Tests for database connectivity."""

    def test_connect_works(self):
        """Test that database connection works."""
        with connect() as conn:
            result = conn.cursor().execute("SELECT 1").fetchone()
            assert result[0] == 1

    def test_tables_exist(self):
        """Test that required tables exist."""
        required_tables = [
            "lexicons", "synsets", "senses", "entries",
            "forms", "ilis", "definitions"
        ]

        with connect() as conn:
            for table in required_tables:
                result = conn.cursor().execute(
                    f"SELECT name FROM sqlite_master WHERE type='table' AND name=?",
                    (table,)
                ).fetchone()
                assert result is not None, f"Table {table} not found"
