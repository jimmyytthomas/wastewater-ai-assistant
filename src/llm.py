"""The only module that talks to Claude.

ask_claude() is the only thing to change to switch to the Anthropic API later.
"""

import os
import subprocess
import tempfile
from pathlib import Path

from dotenv import load_dotenv

ROOT = Path(__file__).resolve().parents[1]
TIMEOUT_SECONDS = 120


def ask_claude(prompt: str) -> str:
    """Send a prompt to Claude Code and return the reply text.

    This function is the only thing to change to switch to the Anthropic API later.
    It shells out to `claude -p` and passes the prompt on stdin so a long prompt
    is not limited by the operating system's argument length.
    """
    load_dotenv(ROOT / ".env")

    # Copy the environment, keep the subscription token, and drop an API key
    # so Claude Code authenticates with the OAuth subscription.
    env = os.environ.copy()
    env.pop("ANTHROPIC_API_KEY", None)
    token = env.get("CLAUDE_CODE_OAUTH_TOKEN")
    if not token:
        raise RuntimeError(
            "Claude call failed: CLAUDE_CODE_OAUTH_TOKEN is not set. Add it to .env."
        )
    env["CLAUDE_CODE_OAUTH_TOKEN"] = token

    # A throwaway directory keeps Claude Code from reading this project's files.
    with tempfile.TemporaryDirectory() as temp_dir:
        try:
            completed = subprocess.run(
                ["claude", "-p"],
                input=prompt,
                text=True,
                capture_output=True,
                timeout=TIMEOUT_SECONDS,
                cwd=temp_dir,
                env=env,
            )
        except subprocess.TimeoutExpired as exc:
            raise RuntimeError(
                f"Claude call failed: timed out after {TIMEOUT_SECONDS} seconds."
            ) from exc
        except FileNotFoundError as exc:
            raise RuntimeError(
                "Claude call failed: the `claude` command was not found on PATH."
            ) from exc

    if completed.returncode != 0:
        detail = (completed.stderr or completed.stdout or "").strip()
        raise RuntimeError(
            f"Claude call failed (exit code {completed.returncode}): {detail}"
        )

    return completed.stdout.strip()
