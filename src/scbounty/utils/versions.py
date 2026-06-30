from __future__ import annotations

import os
import shutil
import subprocess
import sys
from pathlib import Path


def executable_path(name: str) -> str | None:
    discovered = shutil.which(name)
    if discovered:
        return discovered
    suffix = ".exe" if sys.platform == "win32" else ""
    candidates = [
        Path(sys.executable).resolve().parent / f"{name}{suffix}",
        Path.home() / ".foundry" / "bin" / f"{name}{suffix}",
    ]
    return next((str(path) for path in candidates if path.is_file()), None)


def tool_version(name: str, args: tuple[str, ...] = ("--version",)) -> str | None:
    executable = executable_path(name)
    if executable is None:
        return None
    try:
        environment = os.environ.copy()
        if sys.prefix != sys.base_prefix:
            environment.setdefault("VIRTUAL_ENV", sys.prefix)
        result = subprocess.run(
            [executable, *args],
            check=False,
            capture_output=True,
            text=True,
            timeout=10,
            shell=False,
            env=environment,
        )
    except (OSError, subprocess.TimeoutExpired):
        return None
    output = (result.stdout or result.stderr).strip()
    return output.splitlines()[0] if output else None
