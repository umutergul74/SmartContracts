from __future__ import annotations

from pathlib import Path
from typing import Literal

from scbounty.analyzers.base import ExternalToolAdapter
from scbounty.config.models import AnalyzerResult, TargetConfig
from scbounty.utils.command import run_command
from scbounty.utils.paths import cache_root, repository_root


class SemgrepAdapter(ExternalToolAdapter):
    name = "semgrep"
    executable = "semgrep"

    def _safe_log_environment(self) -> dict[str, str]:
        log_directory = cache_root() / "semgrep"
        log_directory.mkdir(parents=True, exist_ok=True)
        return {
            "SEMGREP_LOG_FILE": str(log_directory / "semgrep.log"),
            "SEMGREP_VERSION_CACHE_PATH": str(log_directory / "version-cache.json"),
            "XDG_CACHE_HOME": str(log_directory),
        }

    def version(self) -> str | None:
        if not self.is_available():
            return None
        execution = run_command(
            self.name,
            [self.resolved_executable(), "--version"],
            cwd=repository_root(),
            timeout_seconds=30,
            extra_env=self._safe_log_environment(),
        )
        output = (execution.stdout or execution.stderr).strip()
        return output.splitlines()[0] if output else None

    def run(
        self,
        target: TargetConfig,
        workspace: Path,
        selected_paths: list[str] | None = None,
    ) -> AnalyzerResult:
        del target
        if not self.is_available():
            return self.missing_result()
        candidates = [
            str(workspace / path) for path in (selected_paths or []) if (workspace / path).is_file()
        ]
        if not candidates:
            candidates = [str(workspace)]
        rules = repository_root() / "semgrep" / "solidity"
        execution = run_command(
            self.name,
            [
                self.resolved_executable(),
                "scan",
                "--config",
                str(rules),
                "--json",
                "--metrics=off",
                "--no-git-ignore",
                *candidates,
            ],
            cwd=workspace,
            timeout_seconds=180,
            extra_env=self._safe_log_environment(),
        )
        execution.version = self.version()
        has_json = execution.stdout.lstrip().startswith("{")
        status: Literal["completed", "failed"] = (
            "completed" if execution.exit_code == 0 and has_json else "failed"
        )
        if status == "completed":
            warnings = []
        elif execution.timed_out:
            warnings = ["Semgrep timed out before producing valid JSON output."]
        else:
            warnings = ["Semgrep did not produce valid JSON output."]
        return AnalyzerResult(
            analyzer=self.name,
            status=status,
            execution=execution,
            warnings=warnings,
        )
