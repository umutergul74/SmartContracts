from __future__ import annotations

import os
import re
import subprocess
import sys
from collections.abc import Mapping, Sequence
from datetime import UTC, datetime
from pathlib import Path

from scbounty.config.models import ToolExecution

_FORBIDDEN_SEQUENCES = (
    "--broadcast",
    "cast send",
    "forge create",
    "private-key",
    "private_key",
    "mnemonic",
    "wallet import",
    "wallet new",
)
_SAFE_ENV_KEYS = {
    "COMSPEC",
    "HOME",
    "LANG",
    "LOCALAPPDATA",
    "PATH",
    "PATHEXT",
    "PROGRAMDATA",
    "SYSTEMDRIVE",
    "SYSTEMROOT",
    "TEMP",
    "TMP",
    "USERPROFILE",
    "VIRTUAL_ENV",
    "WINDIR",
}
_MAX_CAPTURE = 200_000


class UnsafeCommandError(ValueError):
    """Raised when an adapter attempts to invoke a prohibited capability."""


def assert_safe_command(command: Sequence[str]) -> None:
    if not command:
        raise UnsafeCommandError("Empty commands are not allowed")
    rendered = " ".join(command).lower()
    for marker in _FORBIDDEN_SEQUENCES:
        if marker in rendered:
            raise UnsafeCommandError(f"Prohibited command capability detected: {marker}")


def _clean_environment(extra: Mapping[str, str] | None = None) -> dict[str, str]:
    environment = {key: value for key, value in os.environ.items() if key.upper() in _SAFE_ENV_KEYS}
    tool_directories = [
        str(Path(sys.executable).resolve().parent),
        str(Path.home() / ".foundry" / "bin"),
    ]
    environment["PATH"] = os.pathsep.join([*tool_directories, environment.get("PATH", "")])
    if sys.prefix != sys.base_prefix:
        environment.setdefault("VIRTUAL_ENV", sys.prefix)
    if extra:
        for key, value in extra.items():
            lowered = key.lower()
            if any(secret in lowered for secret in ("key", "mnemonic", "secret", "wallet")):
                raise UnsafeCommandError(f"Secret-bearing environment variable rejected: {key}")
            environment[key] = value
    return environment


def redact(value: str | None, sensitive_values: Sequence[str] = ()) -> str:
    redacted = value or ""
    for secret in sensitive_values:
        if secret:
            redacted = redacted.replace(secret, "<redacted>")
    redacted = re.sub(
        r"(https?://)([^/\s:@]+):([^@\s/]+)@",
        r"\1<redacted>@",
        redacted,
    )
    redacted = re.sub(
        r"(?i)(api[_-]?key|token|secret|private[_-]?key)=([^&\s]+)",
        r"\1=<redacted>",
        redacted,
    )
    return redacted[:_MAX_CAPTURE]


def run_command(
    tool: str,
    command: Sequence[str],
    cwd: Path,
    *,
    timeout_seconds: int = 300,
    extra_env: Mapping[str, str] | None = None,
    sensitive_values: Sequence[str] = (),
) -> ToolExecution:
    command_list = [str(part) for part in command]
    assert_safe_command(command_list)
    started = datetime.now(UTC)
    try:
        completed = subprocess.run(
            command_list,
            cwd=cwd,
            env=_clean_environment(extra_env),
            check=False,
            capture_output=True,
            encoding="utf-8",
            errors="replace",
            text=True,
            timeout=timeout_seconds,
            shell=False,
        )
        ended = datetime.now(UTC)
        return ToolExecution(
            tool=tool,
            available=True,
            command=[redact(item, sensitive_values) for item in command_list],
            started_at_utc=started,
            ended_at_utc=ended,
            exit_code=completed.returncode,
            stdout=redact(completed.stdout, sensitive_values),
            stderr=redact(completed.stderr, sensitive_values),
        )
    except subprocess.TimeoutExpired as exc:
        ended = datetime.now(UTC)
        stdout = (
            exc.stdout.decode("utf-8", errors="replace")
            if isinstance(exc.stdout, bytes)
            else (exc.stdout or "")
        )
        stderr = (
            exc.stderr.decode("utf-8", errors="replace")
            if isinstance(exc.stderr, bytes)
            else (exc.stderr or "")
        )
        return ToolExecution(
            tool=tool,
            available=True,
            command=[redact(item, sensitive_values) for item in command_list],
            started_at_utc=started,
            ended_at_utc=ended,
            timed_out=True,
            stdout=redact(stdout, sensitive_values),
            stderr=redact(stderr, sensitive_values),
        )
    except OSError as exc:
        ended = datetime.now(UTC)
        return ToolExecution(
            tool=tool,
            available=False,
            command=[redact(item, sensitive_values) for item in command_list],
            started_at_utc=started,
            ended_at_utc=ended,
            stderr=redact(str(exc), sensitive_values),
        )
