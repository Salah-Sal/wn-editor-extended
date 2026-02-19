import pytest
from wordnet_editor import WordnetEditor

def test_entry_id_gap_filling(tmp_path):
    db_path = tmp_path / "test.db"
    editor = WordnetEditor(str(db_path))
    editor.create_lexicon("test", "Test", "en", "email", "lic", "1.0")

    # Create base
    # id: test-cat-n
    e1 = editor.create_entry("test", "cat", "n")
    assert e1.id == "test-cat-n"

    # Create second (collision)
    # id: test-cat-n-2
    e2 = editor.create_entry("test", "cat", "n")
    assert e2.id == "test-cat-n-2"

    # Create third
    # id: test-cat-n-3
    e3 = editor.create_entry("test", "cat", "n")
    assert e3.id == "test-cat-n-3"

    # Delete the middle one
    editor.delete_entry(e2.id)

    # Create another one, should reuse gap
    # id: test-cat-n-2
    e4 = editor.create_entry("test", "cat", "n")
    assert e4.id == "test-cat-n-2"

    # Create another one, should append
    # id: test-cat-n-4
    e5 = editor.create_entry("test", "cat", "n")
    assert e5.id == "test-cat-n-4"

def test_entry_id_normalization_wildcards(tmp_path):
    """Test that underscores in ID don't cause false matches if we use LIKE without escaping."""
    db_path = tmp_path / "wildcard.db"
    editor = WordnetEditor(str(db_path))
    editor.create_lexicon("test", "Test", "en", "email", "lic", "1.0")

    # Lemma "foo bar" -> normalized "foo_bar"
    # Base ID: test-foo_bar-n
    e1 = editor.create_entry("test", "foo bar", "n")
    assert e1.id == "test-foo_bar-n"

    # Lemma "foo-bar" -> normalized "foo-bar"
    # Base ID: test-foo-bar-n
    # If we had test-foo-bar-n-2, it should NOT affect test-foo_bar-n generation

    # Create test-foo-bar-n
    e2 = editor.create_entry("test", "foo-bar", "n")
    assert e2.id == "test-foo-bar-n"

    # Create test-foo-bar-n-2
    e3 = editor.create_entry("test", "foo-bar", "n")
    assert e3.id == "test-foo-bar-n-2"

    # Now create another "foo bar" entry.
    # Base ID: test-foo_bar-n. Exists.
    # Should look for test-foo_bar-n-X.
    # Should NOT see test-foo-bar-n-2 as a conflict.

    # If we used LIKE 'test-foo_bar-n-%' without escaping _, it would match test-foo-bar-n-2
    # because _ matches -.
    # If it matched, it would see '2' is taken, and might skip to 3?
    # Wait, if it sees '2' is taken, it would try to use '2' (if we fill gaps) or '3' (if we take max).
    # If we fill gaps:
    #   existing_suffixes = {2} (from foo-bar-n-2)
    #   We want to generate for foo_bar.
    #   n=2. 2 is in existing_suffixes? Yes. n becomes 3.
    #   Result: test-foo_bar-n-3.
    #   But we expected test-foo_bar-n-2.

    e4 = editor.create_entry("test", "foo bar", "n")
    assert e4.id == "test-foo_bar-n-2"
