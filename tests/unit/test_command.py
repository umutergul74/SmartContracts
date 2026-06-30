import sys
from pathlib import Path

import pytest

from scbounty.utils.command import UnsafeCommandError, assert_safe_command, redact, run_command


@pytest.mark.parametrize(
    "command",
    [
        ["forge", "script", "--broadcast"],
        ["cast", "send", "0x0"],
        ["forge", "create", "Contract"],
        ["tool", "--private-key", "secret"],
    ],
)
def test_dangerous_command_capabilities_are_rejected(command: list[str]) -> None:
    with pytest.raises(UnsafeCommandError):
        assert_safe_command(command)


def test_runner_uses_argument_list_and_captures_output() -> None:
    result = run_command(
        "python",
        [sys.executable, "-c", "print('safe-local-run')"],
        cwd=Path.cwd(),
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == "safe-local-run"


def test_redaction_hides_url_credentials_and_query_secrets() -> None:
    text = "https://user:pass@example.test api_key=abc token=def"

    redacted = redact(text)

    assert "pass" not in redacted
    assert "abc" not in redacted
    assert "def" not in redacted


def test_redaction_accepts_missing_streams() -> None:
    assert redact(None) == ""
