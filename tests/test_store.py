"""Tests for the Chroma index settings."""

import pytest

import store


def test_chroma_telemetry_is_off(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "CHROMA_PATH", tmp_path / "chroma_db")

    assert store._client().get_settings().anonymized_telemetry is False


def test_missing_index_has_a_clear_error(monkeypatch, tmp_path):
    monkeypatch.setattr(store, "CHROMA_PATH", tmp_path / "empty_chroma_db")

    with pytest.raises(RuntimeError, match="python src/store.py"):
        store.search("What is the BOD5 limit?")
