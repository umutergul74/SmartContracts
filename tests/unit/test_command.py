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


def test_runner_reports_timeout_without_crashing() -> None:
    result = run_command(
        "python",
        [sys.executable, "-c", "import time; time.sleep(5)"],
        cwd=Path.cwd(),
        timeout_seconds=1,
    )

    assert result.timed_out is True
    assert result.exit_code is None


def test_redaction_hides_url_credentials_and_query_secrets() -> None:
    text = "https://user:pass@example.test api_key=abc token=def"

    redacted = redact(text)

    assert "pass" not in redacted
    assert "abc" not in redacted
    assert "def" not in redacted


def test_redaction_accepts_missing_streams() -> None:
    assert redact(None) == ""


def test_git_safe_directory_env_is_allowed_without_allowing_secret_env() -> None:
    result = run_command(
        "python",
        [
            sys.executable,
            "-c",
            "import os; print(os.environ['GIT_CONFIG_KEY_0'])",
        ],
        cwd=Path.cwd(),
        extra_env={
            "GIT_CONFIG_COUNT": "1",
            "GIT_CONFIG_KEY_0": "safe.directory",
            "GIT_CONFIG_VALUE_0": Path.cwd().as_posix(),
        },
    )

    assert result.exit_code == 0
    assert result.stdout.strip() == "safe.directory"


def test_secret_bearing_extra_env_is_rejected() -> None:
    with pytest.raises(UnsafeCommandError):
        run_command(
            "python",
            [sys.executable, "-c", "print('nope')"],
            cwd=Path.cwd(),
            extra_env={"PRIVATE_KEY": "secret"},
        )
