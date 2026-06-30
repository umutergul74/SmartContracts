from __future__ import annotations

from pathlib import Path
from typing import Protocol

from scbounty.config.models import AnalyzerResult, TargetConfig, ToolExecution
from scbounty.utils.versions import executable_path, tool_version


class AnalyzerAdapter(Protocol):
    name: str

    def is_available(self) -> bool: ...

    def version(self) -> str | None: ...

    def run(
        self,
        target: TargetConfig,
        workspace: Path,
        selected_paths: list[str] | None = None,
    ) -> AnalyzerResult: ...


class ExternalToolAdapter:
    name = "external"
    executable = ""
    version_args: tuple[str, ...] = ("--version",)

    def is_available(self) -> bool:
        return executable_path(self.executable) is not None

    def version(self) -> str | None:
        return tool_version(self.executable, self.version_args)

    def resolved_executable(self) -> str:
        return executable_path(self.executable) or self.executable

    def missing_result(self) -> AnalyzerResult:
        return AnalyzerResult(
            analyzer=self.name,
            status="skipped",
            execution=ToolExecution(tool=self.name, available=False),
            warnings=[f"{self.name} is not installed; analysis continued in degraded mode."],
        )


class AvailabilityOnlyAdapter(ExternalToolAdapter):
    def run(
        self,
        target: TargetConfig,
        workspace: Path,
        selected_paths: list[str] | None = None,
    ) -> AnalyzerResult:
        del target, workspace, selected_paths
        if not self.is_available():
            return self.missing_result()
        return AnalyzerResult(
            analyzer=self.name,
            status="skipped",
            execution=ToolExecution(
                tool=self.name,
                available=True,
                version=self.version(),
            ),
            warnings=[
                f"{self.name} was detected, but its campaign profile is intentionally "
                "not enabled in the first bridge/gateway vertical slice."
            ],
        )
