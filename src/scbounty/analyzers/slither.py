from __future__ import annotations

import re
from pathlib import Path
from typing import Literal

from scbounty.analyzers.base import ExternalToolAdapter
from scbounty.config.models import AnalyzerResult, TargetConfig
from scbounty.utils.command import run_command


class SlitherAdapter(ExternalToolAdapter):
    name = "slither"
    executable = "slither"

    def run(
        self,
        target: TargetConfig,
        workspace: Path,
        selected_paths: list[str] | None = None,
    ) -> AnalyzerResult:
        del target
        if not self.is_available():
            return self.missing_result()
        command = [
            self.resolved_executable(),
            str(workspace),
            "--json",
            "-",
            "--disable-color",
        ]
        include_filter = _include_filter(selected_paths or [])
        if include_filter:
            command.extend(["--include-paths", include_filter])
        execution = run_command(
            self.name,
            command,
            cwd=workspace,
            timeout_seconds=60,
            extra_env={
                "GIT_CONFIG_COUNT": "1",
                "GIT_CONFIG_KEY_0": "safe.directory",
                "GIT_CONFIG_VALUE_0": workspace.resolve().as_posix(),
            },
        )
        execution.version = self.version()
        # Slither may use non-zero status when detectors emit results. A parseable JSON payload
        # still counts as a completed analyzer run and is preserved as evidence.
        has_json = execution.stdout.lstrip().startswith("{")
        status: Literal["completed", "failed"] = (
            "completed" if execution.exit_code == 0 or has_json else "failed"
        )
        if status == "completed":
            warnings = []
        elif execution.timed_out:
            warnings = ["Slither timed out before producing JSON output."]
        else:
            warnings = ["Slither failed before producing JSON output."]
        return AnalyzerResult(
            analyzer=self.name,
            status=status,
            execution=execution,
            warnings=warnings,
        )


def _include_filter(selected_paths: list[str]) -> str | None:
    files = [Path(path).as_posix() for path in selected_paths if path.endswith(".sol")]
    if not files:
        return None
    return "|".join(re.escape(path) for path in files)
