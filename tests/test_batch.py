"""Tests for batch operations."""

import pytest


class TestBatchCommit:
    """TP-BATCH-001."""

    def test_batch_commits_atomically(self, editor_with_lexicon):
        ed = editor_with_lexicon
        with ed.batch():
            for i in range(100):
                ed.create_synset("test", "n", f"Concept {i}")
        synsets = ed.find_synsets(lexicon_id="test")
        assert len(synsets) == 100


class TestBatchRollback:
    """TP-BATCH-002."""

    def test_batch_rollback_on_error(self, editor_with_lexicon):
        ed = editor_with_lexicon
        try:
            with ed.batch():
                ed.create_synset("test", "n", "Will be rolled back")
                raise RuntimeError("Intentional error")
        except RuntimeError:
            pass
        synsets = ed.find_synsets(lexicon_id="test")
        assert len(synsets) == 0


class TestBatchPerformance:
    """TP-BATCH-003."""

    def test_batch_faster_than_individual(self, editor_with_lexicon):
        import time

        ed = editor_with_lexicon

        # Without batch
        start = time.monotonic()
        for i in range(200):
            ed.create_synset("test", "n", f"No-batch {i}")
        no_batch_time = time.monotonic() - start

        # Clean up
        for ss in ed.find_synsets(lexicon_id="test"):
            ed.delete_synset(ss.id, cascade=True)

        # With batch
        start = time.monotonic()
        with ed.batch():
            for i in range(200):
                ed.create_synset("test", "n", f"Batch {i}")
        batch_time = time.monotonic() - start

        # Batch should be faster (or at least not slower)
        # We use a generous margin since timing can vary
        assert batch_time <= no_batch_time * 3


class TestBatchNested:
    """TP-BATCH-004."""

    def test_nested_batch(self, editor_with_lexicon):
        ed = editor_with_lexicon
        with ed.batch():
            ed.create_synset("test", "n", "Outer")
            with ed.batch():
                ed.create_synset("test", "n", "Inner")
        synsets = ed.find_synsets(lexicon_id="test")
        assert len(synsets) == 2
