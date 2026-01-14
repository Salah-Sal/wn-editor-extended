"""
Tests for batch change request functionality.
"""
import pytest
import tempfile
from pathlib import Path

import wn
from wn_editor.batch import (
    load_change_request,
    validate_change_request,
    execute_change_request,
    ParseError,
    ChangeRequest,
    Change,
    ValidationResult,
    BatchResult,
    OperationType,
    RELATION_TYPES,
)


class TestParser:
    """Tests for YAML parsing."""

    def test_load_from_file(self, tmp_path):
        """Test loading a change request from a file."""
        yaml_content = """
lexicon: ewn
session:
  name: Test Session
changes:
  - operation: add_word
    synset: ewn-00001740-n
    word: testword
"""
        yaml_file = tmp_path / "test.yaml"
        yaml_file.write_text(yaml_content)

        request = load_change_request(yaml_file)

        assert request.lexicon == "ewn"
        assert request.session_name == "Test Session"
        assert len(request.changes) == 1
        assert request.changes[0].operation == "add_word"

    def test_load_from_string(self):
        """Test loading a change request from a YAML string."""
        yaml_content = """
lexicon: ewn
changes:
  - operation: create_synset
    words:
      - word: newword
        pos: n
    definition: A test definition
"""
        request = load_change_request(yaml_content)

        assert request.lexicon == "ewn"
        assert len(request.changes) == 1
        assert request.changes[0].operation == "create_synset"

    def test_load_from_dict(self):
        """Test loading a change request from a dictionary."""
        data = {
            "lexicon": "ewn",
            "changes": [
                {
                    "operation": "add_word",
                    "synset": "ewn-00001740-n",
                    "word": "testword",
                }
            ],
        }

        request = load_change_request(data)

        assert request.lexicon == "ewn"
        assert len(request.changes) == 1

    def test_parse_error_missing_lexicon(self):
        """Test that missing lexicon raises ParseError."""
        yaml_content = """
changes:
  - operation: add_word
    synset: ewn-00001740-n
    word: test
"""
        with pytest.raises(ParseError, match="lexicon"):
            load_change_request(yaml_content)

    def test_parse_error_missing_changes(self):
        """Test that missing changes raises ParseError."""
        yaml_content = """
lexicon: ewn
"""
        with pytest.raises(ParseError, match="changes"):
            load_change_request(yaml_content)

    def test_parse_error_empty_changes(self):
        """Test that empty changes raises ParseError."""
        yaml_content = """
lexicon: ewn
changes: []
"""
        with pytest.raises(ParseError, match="empty"):
            load_change_request(yaml_content)

    def test_parse_error_invalid_yaml(self, tmp_path):
        """Test that invalid YAML raises ParseError."""
        yaml_file = tmp_path / "invalid.yaml"
        yaml_file.write_text("lexicon: [invalid yaml")

        with pytest.raises(ParseError, match="Invalid YAML"):
            load_change_request(yaml_file)

    def test_file_not_found(self):
        """Test that non-existent file raises FileNotFoundError."""
        with pytest.raises(FileNotFoundError):
            load_change_request(Path("/nonexistent/file.yaml"))


class TestValidation:
    """Tests for validation."""

    def test_validate_valid_request(self):
        """Test validating a well-formed request."""
        request = ChangeRequest(
            lexicon="ewn",
            changes=[
                Change(
                    operation="add_word",
                    params={"synset": "ewn-00001740-n", "word": "testword"},
                )
            ],
        )

        # Skip reference checking for this test
        result = validate_change_request(request, check_references=False)

        assert result.is_valid
        assert len(result.errors) == 0

    def test_validate_unknown_operation(self):
        """Test that unknown operation is flagged."""
        request = ChangeRequest(
            lexicon="ewn",
            changes=[
                Change(
                    operation="unknown_op",
                    params={},
                )
            ],
        )

        result = validate_change_request(request, check_references=False)

        assert not result.is_valid
        assert any("unknown" in e.message.lower() for e in result.errors)

    def test_validate_missing_required_field(self):
        """Test that missing required field is flagged."""
        request = ChangeRequest(
            lexicon="ewn",
            changes=[
                Change(
                    operation="add_word",
                    params={"synset": "ewn-00001740-n"},  # Missing 'word'
                )
            ],
        )

        result = validate_change_request(request, check_references=False)

        assert not result.is_valid
        assert any("word" in e.field for e in result.errors)

    def test_validate_invalid_pos(self):
        """Test that invalid POS is flagged."""
        request = ChangeRequest(
            lexicon="ewn",
            changes=[
                Change(
                    operation="set_pos",
                    params={"synset": "ewn-00001740-n", "pos": "invalid"},
                )
            ],
        )

        result = validate_change_request(request, check_references=False)

        assert not result.is_valid
        assert any("pos" in e.field.lower() for e in result.errors)

    def test_validate_invalid_relation_type(self):
        """Test that invalid relation type is flagged."""
        request = ChangeRequest(
            lexicon="ewn",
            changes=[
                Change(
                    operation="add_relation",
                    params={
                        "source": "ewn-00001740-n",
                        "target": "ewn-00002000-n",
                        "type": "invalid_relation",
                    },
                )
            ],
        )

        result = validate_change_request(request, check_references=False)

        assert not result.is_valid
        assert any("type" in e.field.lower() for e in result.errors)

    def test_validate_create_synset_words(self):
        """Test validation of create_synset words field."""
        # Empty words
        request = ChangeRequest(
            lexicon="ewn",
            changes=[
                Change(
                    operation="create_synset",
                    params={"words": [], "definition": "test"},
                )
            ],
        )

        result = validate_change_request(request, check_references=False)
        assert not result.is_valid
        assert any("empty" in e.message.lower() for e in result.errors)

    def test_validate_all_operations_schema(self):
        """Test schema validation for all operation types."""
        operations_with_valid_params = [
            ("create_synset", {"words": [{"word": "test", "pos": "n"}], "definition": "test"}),
            ("add_word", {"synset": "s1", "word": "test"}),
            ("delete_word", {"synset": "s1", "word": "test"}),
            ("add_definition", {"synset": "s1", "definition": "test"}),
            ("modify_definition", {"synset": "s1", "definition": "test"}),
            ("delete_definition", {"synset": "s1"}),
            ("add_example", {"synset": "s1", "example": "test"}),
            ("delete_example", {"synset": "s1", "example": "test"}),
            ("set_pos", {"synset": "s1", "pos": "n"}),
            ("add_relation", {"source": "s1", "target": "s2", "type": "hypernym"}),
            ("delete_relation", {"source": "s1", "target": "s2", "type": "hypernym"}),
            ("set_ili", {"synset": "s1", "ili": "i12345"}),
            ("delete_ili", {"synset": "s1"}),
        ]

        for op, params in operations_with_valid_params:
            request = ChangeRequest(
                lexicon="ewn",
                changes=[Change(operation=op, params=params)],
            )
            result = validate_change_request(request, check_references=False)
            assert result.is_valid, f"Operation {op} should be valid with params {params}"


class TestExecutor:
    """Tests for change execution."""

    def test_dry_run(self, test_lexicon):
        """Test dry run mode doesn't make changes."""
        request = ChangeRequest(
            lexicon=test_lexicon.lex_rowid,
            session_name="Dry run test",
            changes=[
                Change(
                    operation="create_synset",
                    params={
                        "words": [{"word": "dryruntest", "pos": "n"}],
                        "definition": "A test word",
                    },
                )
            ],
        )

        # Need to get the lexicon name for the request
        from wn._db import connect
        with connect() as conn:
            res = conn.cursor().execute(
                "SELECT id FROM lexicons WHERE rowid = ?",
                (test_lexicon.lex_rowid,)
            ).fetchone()
            request.lexicon = res[0]

        result = execute_change_request(request, dry_run=True, enable_tracking=False)

        assert result.success_count == 1
        assert result.failure_count == 0

        # Word should NOT exist
        synsets = wn.synsets("dryruntest")
        assert len(synsets) == 0

    def test_execute_create_synset(self, test_lexicon):
        """Test executing create_synset operation."""
        # Get lexicon name
        from wn._db import connect
        with connect() as conn:
            res = conn.cursor().execute(
                "SELECT id FROM lexicons WHERE rowid = ?",
                (test_lexicon.lex_rowid,)
            ).fetchone()
            lex_name = res[0]

        request = ChangeRequest(
            lexicon=lex_name,
            session_name="Create synset test",
            changes=[
                Change(
                    operation="create_synset",
                    params={
                        "words": [{"word": "batchcreatetest", "pos": "n"}],
                        "definition": "A test word for batch create",
                    },
                )
            ],
        )

        result = execute_change_request(request, enable_tracking=False)

        assert result.success_count == 1
        assert result.failure_count == 0
        assert result.changes[0].created_id is not None

        # Word should exist
        synsets = wn.synsets("batchcreatetest")
        assert len(synsets) >= 1

    def test_execute_add_word(self, test_lexicon):
        """Test executing add_word operation."""
        # First create a synset
        synset = test_lexicon.create_synset()
        synset.add_word("batchaddwordbase", pos="n")
        synset.add_definition("Base synset for add_word test")
        synset_id = synset.as_synset().id

        # Get lexicon name
        from wn._db import connect
        with connect() as conn:
            res = conn.cursor().execute(
                "SELECT id FROM lexicons WHERE rowid = ?",
                (test_lexicon.lex_rowid,)
            ).fetchone()
            lex_name = res[0]

        request = ChangeRequest(
            lexicon=lex_name,
            changes=[
                Change(
                    operation="add_word",
                    params={
                        "synset": synset_id,
                        "word": "batchaddwordnew",
                    },
                )
            ],
        )

        result = execute_change_request(request, enable_tracking=False)

        assert result.success_count == 1
        assert result.failure_count == 0

    def test_execute_continues_on_error(self, test_lexicon):
        """Test that execution continues after an error."""
        # Get lexicon name
        from wn._db import connect
        with connect() as conn:
            res = conn.cursor().execute(
                "SELECT id FROM lexicons WHERE rowid = ?",
                (test_lexicon.lex_rowid,)
            ).fetchone()
            lex_name = res[0]

        request = ChangeRequest(
            lexicon=lex_name,
            changes=[
                # This will fail - non-existent synset
                Change(
                    operation="add_word",
                    params={
                        "synset": "nonexistent-synset-id",
                        "word": "test1",
                    },
                ),
                # This should succeed
                Change(
                    operation="create_synset",
                    params={
                        "words": [{"word": "continueontest", "pos": "n"}],
                        "definition": "Test continue on error",
                    },
                ),
            ],
        )

        result = execute_change_request(request, enable_tracking=False)

        # Should have one failure and one success
        assert result.failure_count >= 1
        assert result.success_count >= 1
        assert result.total_count == 2


class TestRelationTypes:
    """Tests for relation type mapping."""

    def test_all_relation_types_present(self):
        """Test that all expected relation types are in the mapping."""
        expected = [
            "also", "antonym", "attribute", "causes", "derivation",
            "domain_region", "domain_topic", "entails", "exemplifies",
            "has_domain_region", "has_domain_topic", "holo_member",
            "holo_part", "holo_substance", "hypernym", "hyponym",
            "instance_hypernym", "instance_hyponym", "is_exemplified_by",
            "mero_member", "mero_part", "mero_substance", "participle",
            "pertainym", "similar", "is_caused_by", "is_entailed_by",
            "other",  # Added to match database
        ]

        for rel in expected:
            assert rel in RELATION_TYPES, f"Missing relation type: {rel}"

    def test_relation_type_ids(self):
        """Test some known relation type IDs match database."""
        assert RELATION_TYPES["hypernym"] == 15
        assert RELATION_TYPES["hyponym"] == 16
        assert RELATION_TYPES["antonym"] == 2
        assert RELATION_TYPES["similar"] == 28
        assert RELATION_TYPES["mero_part"] == 23
        assert RELATION_TYPES["holo_member"] == 12


class TestOperationTypes:
    """Tests for operation type enum."""

    def test_all_operations_have_required_fields(self):
        """Test that all operations are documented in REQUIRED_FIELDS."""
        from wn_editor.batch.schema import REQUIRED_FIELDS

        for op in OperationType:
            assert op.value in REQUIRED_FIELDS, f"Missing required fields for: {op.value}"


class TestBatchResult:
    """Tests for BatchResult dataclass."""

    def test_skipped_count(self):
        """Test skipped_count calculation."""
        result = BatchResult(
            session_id=1,
            total_count=10,
            success_count=7,
            failure_count=2,
            changes=[],
            duration_seconds=1.0,
        )

        assert result.skipped_count == 1


class TestIntegration:
    """Integration tests for full batch workflow."""

    def test_full_workflow(self, test_lexicon, tmp_path):
        """Test complete workflow: load -> validate -> execute."""
        # Get lexicon name
        from wn._db import connect
        with connect() as conn:
            res = conn.cursor().execute(
                "SELECT id FROM lexicons WHERE rowid = ?",
                (test_lexicon.lex_rowid,)
            ).fetchone()
            lex_name = res[0]

        yaml_content = f"""
lexicon: {lex_name}
session:
  name: Integration Test
  description: Testing full batch workflow
changes:
  - operation: create_synset
    words:
      - word: integrationtest1
        pos: n
      - word: integrationtest2
    definition: A test synset for integration testing
    examples:
      - "This is an integration test example."
"""
        yaml_file = tmp_path / "integration.yaml"
        yaml_file.write_text(yaml_content)

        # Load
        request = load_change_request(yaml_file)
        assert request.session_name == "Integration Test"

        # Validate (skip reference checks since we're using test lexicon)
        validation = validate_change_request(request, check_references=False)
        assert validation.is_valid

        # Execute
        result = execute_change_request(request, enable_tracking=False)
        assert result.success_count == 1
        assert result.failure_count == 0

        # Verify
        synsets = wn.synsets("integrationtest1")
        assert len(synsets) >= 1


class TestEWNGroundTruth:
    """
    Comprehensive validation tests using real English WordNet data.

    Ground truth data from ewn:2020:

    ewn-02086723-n (dog):
        - Words: ['dog', 'Canis familiaris', 'domestic dog']
        - POS: n
        - Definition: "a member of the genus Canis..."
        - Example: "the dog barked all night"
        - ILI: i46360
        - hypernym: ewn-02085998-n (canine)
        - hyponym: ewn-01325095-n (puppy)
        - holo_member: ewn-02086515-n (Canis)

    ewn-01126910-a (good):
        - Sense: ewn-good-a-01126910-01
        - Antonym sense: ewn-bad-a-01129296-01
    """

    @pytest.fixture
    def ewn_lexicon(self):
        """Get English WordNet lexicon."""
        return wn.Wordnet('ewn:2020')

    def test_validate_existing_synset_reference(self, ewn_lexicon):
        """Test validation with real EWN synset IDs."""
        request = ChangeRequest(
            lexicon="ewn",
            changes=[
                Change(
                    operation="add_word",
                    params={
                        "synset": "ewn-02086723-n",  # Real dog synset
                        "word": "validationtest",
                    },
                )
            ],
        )

        # With reference checking - should pass
        result = validate_change_request(request, check_references=True)
        assert result.is_valid, f"Validation failed: {[e.message for e in result.errors]}"

    def test_validate_nonexistent_synset_reference(self):
        """Test validation catches non-existent synset references."""
        request = ChangeRequest(
            lexicon="ewn",
            changes=[
                Change(
                    operation="add_word",
                    params={
                        "synset": "ewn-99999999-n",  # Non-existent
                        "word": "test",
                    },
                )
            ],
        )

        result = validate_change_request(request, check_references=True)
        # Should have a warning or error about non-existent synset
        assert not result.is_valid or result.warning_count > 0

    def test_validate_real_hypernym_relation(self, ewn_lexicon):
        """Test validation of real hypernym relation from EWN."""
        # Verify ground truth: dog (ewn-02086723-n) has hypernym canine (ewn-02085998-n)
        dog = ewn_lexicon.synsets('dog', pos='n')[0]
        assert dog.id == "ewn-02086723-n"

        hypernyms = dog.relations().get('hypernym', [])
        hypernym_ids = [h.id for h in hypernyms]
        assert "ewn-02085998-n" in hypernym_ids, "Ground truth: dog should have canine as hypernym"

        # Now test our validation accepts this relation type
        request = ChangeRequest(
            lexicon="ewn",
            changes=[
                Change(
                    operation="add_relation",
                    params={
                        "source": "ewn-02086723-n",  # dog
                        "target": "ewn-02085998-n",  # canine
                        "type": "hypernym",
                    },
                )
            ],
        )

        result = validate_change_request(request, check_references=True)
        assert result.is_valid

    def test_validate_all_ewn_relation_types(self, ewn_lexicon):
        """Test validation accepts all relation types found in EWN."""
        from wn._db import connect

        # Get all relation types actually used in EWN
        with connect() as conn:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT DISTINCT rt.type
                FROM synset_relations sr
                JOIN relation_types rt ON sr.type_rowid = rt.rowid
                JOIN lexicons l ON sr.lexicon_rowid = l.rowid
                WHERE l.id = 'ewn'
            ''')
            ewn_synset_relations = [row[0] for row in cursor.fetchall()]

        # Each relation type should be valid in our schema
        for rel_type in ewn_synset_relations:
            assert rel_type in RELATION_TYPES, f"EWN relation type '{rel_type}' not in RELATION_TYPES"

    def test_validate_real_ili_value(self, ewn_lexicon):
        """Test validation with real ILI value from EWN."""
        # Verify ground truth: dog synset has ILI i46360
        dog = ewn_lexicon.synsets('dog', pos='n')[0]
        assert str(dog.ili) == "ILI('i46360')"

        request = ChangeRequest(
            lexicon="ewn",
            changes=[
                Change(
                    operation="set_ili",
                    params={
                        "synset": "ewn-02086723-n",
                        "ili": "i46360",
                    },
                )
            ],
        )

        result = validate_change_request(request, check_references=True)
        assert result.is_valid

    def test_validate_real_pos_values(self, ewn_lexicon):
        """Test validation with real POS values from EWN."""
        # Verify ground truth: dog is noun, good is adjective
        dog = ewn_lexicon.synsets('dog', pos='n')[0]
        assert dog.pos == 'n'

        good = ewn_lexicon.synsets('good', pos='a')[0]
        assert good.pos == 'a'

        # Test all valid POS values
        for pos in ['n', 'v', 'a', 'r', 's']:
            request = ChangeRequest(
                lexicon="ewn",
                changes=[
                    Change(
                        operation="set_pos",
                        params={
                            "synset": "ewn-02086723-n",
                            "pos": pos,
                        },
                    )
                ],
            )

            result = validate_change_request(request, check_references=False)
            assert result.is_valid, f"POS '{pos}' should be valid"

    def test_validate_invalid_pos_rejected(self):
        """Test validation rejects invalid POS values."""
        for invalid_pos in ['x', 'noun', 'verb', 'adj', '']:
            request = ChangeRequest(
                lexicon="ewn",
                changes=[
                    Change(
                        operation="set_pos",
                        params={
                            "synset": "ewn-02086723-n",
                            "pos": invalid_pos,
                        },
                    )
                ],
            )

            result = validate_change_request(request, check_references=False)
            assert not result.is_valid, f"POS '{invalid_pos}' should be invalid"

    def test_verify_dog_synset_words(self, ewn_lexicon):
        """Verify ground truth: dog synset has expected words."""
        dog = ewn_lexicon.synsets('dog', pos='n')[0]
        words = [w.lemma() for w in dog.words()]

        # Ground truth from EWN
        assert 'dog' in words
        assert 'domestic dog' in words
        assert 'Canis familiaris' in words

    def test_verify_dog_synset_definition(self, ewn_lexicon):
        """Verify ground truth: dog synset has expected definition."""
        dog = ewn_lexicon.synsets('dog', pos='n')[0]
        definitions = dog.definitions()

        assert len(definitions) >= 1
        assert "genus Canis" in definitions[0]
        assert "domesticated" in definitions[0]

    def test_verify_dog_synset_examples(self, ewn_lexicon):
        """Verify ground truth: dog synset has expected example."""
        dog = ewn_lexicon.synsets('dog', pos='n')[0]
        examples = dog.examples()

        assert len(examples) >= 1
        assert "barked" in examples[0]

    def test_verify_dog_synset_relations(self, ewn_lexicon):
        """Verify ground truth: dog synset has expected relations."""
        dog = ewn_lexicon.synsets('dog', pos='n')[0]
        relations = dog.relations()

        # Hypernyms
        assert 'hypernym' in relations
        hypernym_ids = [s.id for s in relations['hypernym']]
        assert 'ewn-02085998-n' in hypernym_ids  # canine

        # Hyponyms
        assert 'hyponym' in relations
        hyponym_ids = [s.id for s in relations['hyponym']]
        assert 'ewn-01325095-n' in hyponym_ids  # puppy

        # Holonyms
        assert 'holo_member' in relations
        holo_ids = [s.id for s in relations['holo_member']]
        assert 'ewn-02086515-n' in holo_ids  # Canis

    def test_verify_good_bad_antonym(self, ewn_lexicon):
        """Verify ground truth: good/bad have antonym sense relation."""
        good = ewn_lexicon.synsets('good', pos='a')[0]
        good_sense = good.senses()[0]
        sense_rels = good_sense.relations()

        assert 'antonym' in sense_rels
        antonym_sense = sense_rels['antonym'][0]
        assert antonym_sense.word().lemma() == 'bad'

    def test_relation_type_ids_match_database(self):
        """Test RELATION_TYPES IDs match actual database values."""
        from wn._db import connect

        with connect() as conn:
            cursor = conn.cursor()
            cursor.execute('SELECT rowid, type FROM relation_types')
            db_relations = {row[1]: row[0] for row in cursor.fetchall()}

        # Every relation in our mapping should match the database
        for rel_name, rel_id in RELATION_TYPES.items():
            assert rel_name in db_relations, f"Relation '{rel_name}' not in database"
            assert db_relations[rel_name] == rel_id, \
                f"Relation '{rel_name}' ID mismatch: expected {rel_id}, got {db_relations[rel_name]}"

    def test_execute_all_operations_dry_run(self, test_lexicon):
        """Test dry run execution of all operations."""
        from wn._db import connect

        # Get lexicon name
        with connect() as conn:
            res = conn.cursor().execute(
                "SELECT id FROM lexicons WHERE rowid = ?",
                (test_lexicon.lex_rowid,)
            ).fetchone()
            lex_name = res[0]

        # First create a synset to work with
        synset = test_lexicon.create_synset()
        synset.add_word("dryrunbaseword", pos="n")
        synset.add_definition("Base definition for dry run tests")
        synset.add_example("An example sentence.")
        synset_id = synset.as_synset().id

        # Create another synset for relation tests
        synset2 = test_lexicon.create_synset()
        synset2.add_word("dryrunrelationword", pos="n")
        synset2.add_definition("Target synset for relation tests")
        synset2_id = synset2.as_synset().id

        # Test all operations in dry run mode
        all_operations = [
            Change(operation="create_synset", params={
                "words": [{"word": "dryruntest", "pos": "n"}],
                "definition": "Test synset",
            }),
            Change(operation="add_word", params={
                "synset": synset_id,
                "word": "newword",
            }),
            Change(operation="delete_word", params={
                "synset": synset_id,
                "word": "dryrunbaseword",
            }),
            Change(operation="add_definition", params={
                "synset": synset_id,
                "definition": "Another definition",
            }),
            Change(operation="modify_definition", params={
                "synset": synset_id,
                "definition": "Modified definition",
            }),
            Change(operation="add_example", params={
                "synset": synset_id,
                "example": "Another example.",
            }),
            Change(operation="delete_example", params={
                "synset": synset_id,
                "example": "An example sentence.",
            }),
            Change(operation="set_pos", params={
                "synset": synset_id,
                "pos": "v",
            }),
            Change(operation="add_relation", params={
                "source": synset_id,
                "target": synset2_id,
                "type": "hypernym",
            }),
            Change(operation="delete_relation", params={
                "source": synset_id,
                "target": synset2_id,
                "type": "hypernym",
            }),
            Change(operation="set_ili", params={
                "synset": synset_id,
                "ili": "i99999",
            }),
            Change(operation="delete_ili", params={
                "synset": synset_id,
            }),
        ]

        request = ChangeRequest(
            lexicon=lex_name,
            changes=all_operations,
        )

        # Validate
        validation = validate_change_request(request, check_references=False)
        assert validation.is_valid, f"Validation errors: {[e.message for e in validation.errors]}"

        # Execute in dry run
        result = execute_change_request(request, dry_run=True, enable_tracking=False)

        # All should succeed in dry run
        assert result.success_count == len(all_operations), \
            f"Expected {len(all_operations)} successes, got {result.success_count}"
        assert result.failure_count == 0, \
            f"Unexpected failures: {[c.message for c in result.changes if not c.success]}"
