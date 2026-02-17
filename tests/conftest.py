"""Shared test fixtures for wordnet-editor."""

import pytest

from wordnet_editor import WordnetEditor


@pytest.fixture
def editor():
    """Create an in-memory editor for testing."""
    with WordnetEditor(":memory:") as ed:
        yield ed


@pytest.fixture
def editor_with_lexicon(editor):
    """Editor with one lexicon 'test' pre-created."""
    editor.create_lexicon(
        "test", "Test Lexicon", "en", "test@test.com",
        "https://opensource.org/licenses/MIT", "1.0",
    )
    return editor


@pytest.fixture
def editor_with_data(editor_with_lexicon):
    """Editor with a lexicon, synsets, entries, and senses."""
    ed = editor_with_lexicon
    ss1 = ed.create_synset("test", "n", "A large feline animal")
    ss2 = ed.create_synset("test", "n", "A small domestic animal")
    e1 = ed.create_entry("test", "cat", "n")
    e2 = ed.create_entry("test", "dog", "n")
    s1 = ed.add_sense(e1.id, ss1.id)
    s2 = ed.add_sense(e2.id, ss2.id)
    return ed, ss1, ss2, e1, e2, s1, s2
