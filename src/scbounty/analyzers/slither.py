from __future__ import annotations

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
        del target, selected_paths
        if not self.is_available():
            return self.missing_result()
        execution = run_command(
            self.name,
            [
                self.resolved_executable(),
                str(workspace),
                "--json",
                "-",
                "--disable-color",
            ],
            cwd=workspace,
            timeout_seconds=900,
        )
        execution.version = self.version()
        # Slither may use non-zero status when detectors emit results. A parseable JSON payload
        # still counts as a completed analyzer run and is preserved as evidence.
        has_json = execution.stdout.lstrip().startswith("{")
        status: Literal["completed", "failed"] = (
            "completed" if execution.exit_code == 0 or has_json else "failed"
        )
        warnings = [] if status == "completed" else ["Slither failed before producing JSON output."]
        return AnalyzerResult(
            analyzer=self.name,
            status=status,
            execution=execution,
            warnings=warnings,
        )
