"""
Pytest configuration and fixtures for wn-editor tests.
"""
import pytest
import wn
from wn._db import connect
from wn_editor.editor import LexiconEditor


@pytest.fixture(scope="session", autouse=True)
def ensure_wordnet_downloaded():
    """Ensure English WordNet is available for tests."""
    lexicons = [lex.id for lex in wn.lexicons()]
    if "ewn" not in lexicons and "omw-en" not in lexicons:
        wn.download("ewn:2020")


@pytest.fixture
def test_lexicon():
    """
    Create a fresh test lexicon for each test.
    Cleanup after the test completes.
    """
    import uuid
    unique_id = f"test-{uuid.uuid4().hex[:8]}"

    lex = LexiconEditor.create_new_lexicon(
        lex_id=unique_id,
        label="Test Lexicon",
        language="en",
        email="test@test.com",
        lex_license="MIT",
        version="1.0"
    )

    yield lex

    # Cleanup: remove the test lexicon
    try:
        wn.remove(f"{unique_id}:1.0")
    except Exception:
        pass


@pytest.fixture
def existing_synset():
    """Get an existing synset from the installed WordNet for relation tests."""
    synsets = wn.synsets('dog', lang='en')
    if synsets:
        return synsets[0]
    # Fallback to any synset
    synsets = wn.synsets('car', lang='en')
    return synsets[0] if synsets else None


def cleanup_test_lexicons():
    """Remove all test lexicons created during tests."""
    for lex in wn.lexicons():
        if lex.id.startswith("test-"):
            try:
                wn.remove(f"{lex.id}:{lex.version}")
            except Exception:
                pass
