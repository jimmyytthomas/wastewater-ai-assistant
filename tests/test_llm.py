"""Tests for the Claude call. subprocess.run is faked, so Claude is never called."""

import subprocess

import pytest

import llm

TOKEN = "sk-ant-oat01-test-token-value"


@pytest.fixture(autouse=True)
def token_env(monkeypatch):
    monkeypatch.setattr(llm, "load_dotenv", lambda *args, **kwargs: None)
    monkeypatch.setenv("CLAUDE_CODE_OAUTH_TOKEN", TOKEN)


def _fake_run(monkeypatch, returncode=0, stdout="", stderr=""):
    def fake_run(command, **kwargs):
        return subprocess.CompletedProcess(command, returncode, stdout, stderr)

    monkeypatch.setattr(llm.subprocess, "run", fake_run)


def test_failure_message_never_contains_the_token(monkeypatch):
    _fake_run(monkeypatch, returncode=1, stderr=f"auth failed for token {TOKEN}")

    with pytest.raises(RuntimeError) as error:
        llm.ask_claude("prompt")

    assert TOKEN not in str(error.value)
    assert "[TOKEN]" in str(error.value)


def test_empty_reply_is_an_error(monkeypatch):
    _fake_run(monkeypatch, stdout="   \n")

    with pytest.raises(RuntimeError, match="empty reply"):
        llm.ask_claude("prompt")


def test_timeout_is_reported(monkeypatch):
    def fake_run(command, **kwargs):
        raise subprocess.TimeoutExpired(command, llm.TIMEOUT_SECONDS)

    monkeypatch.setattr(llm.subprocess, "run", fake_run)

    with pytest.raises(RuntimeError, match="timed out"):
        llm.ask_claude("prompt")


def test_missing_token_is_reported(monkeypatch):
    monkeypatch.delenv("CLAUDE_CODE_OAUTH_TOKEN")

    with pytest.raises(RuntimeError, match="CLAUDE_CODE_OAUTH_TOKEN is not set"):
        llm.ask_claude("prompt")
