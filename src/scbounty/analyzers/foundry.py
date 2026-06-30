from __future__ import annotations

from pathlib import Path
from typing import Literal

from scbounty.analyzers.base import ExternalToolAdapter
from scbounty.config.models import AnalyzerResult, TargetConfig
from scbounty.utils.command import run_command


class FoundryAdapter(ExternalToolAdapter):
    name = "foundry"
    executable = "forge"

    def run(
        self,
        target: TargetConfig,
        workspace: Path,
        selected_paths: list[str] | None = None,
    ) -> AnalyzerResult:
        del target, selected_paths
        if not self.is_available():
            return self.missing_result()
        execution = run_command(
            self.name,
            [self.resolved_executable(), "build", "--root", str(workspace)],
            cwd=workspace,
            timeout_seconds=600,
        )
        execution.version = self.version()
        status: Literal["completed", "failed"] = (
            "completed" if execution.exit_code == 0 else "failed"
        )
        warnings = [] if status == "completed" else ["Foundry build did not complete successfully."]
        return AnalyzerResult(
            analyzer=self.name,
            status=status,
            execution=execution,
            warnings=warnings,
        )

    def test(self, workspace: Path, match_test: str | None = None) -> AnalyzerResult:
        if not self.is_available():
            return self.missing_result()
        command = [self.resolved_executable(), "test", "--root", str(workspace)]
        if match_test:
            command.extend(["--match-test", match_test])
        execution = run_command(
            self.name,
            command,
            cwd=workspace,
            timeout_seconds=600,
        )
        execution.version = self.version()
        return AnalyzerResult(
            analyzer=self.name,
            status="completed" if execution.exit_code == 0 else "failed",
            execution=execution,
            warnings=[] if execution.exit_code == 0 else ["Foundry tests failed."],
        )
