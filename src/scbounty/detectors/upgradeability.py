from __future__ import annotations

from pathlib import Path

from scbounty.config.models import Finding
from scbounty.detectors.base import functions_in, make_finding


class UpgradeabilityDetector:
    name = "upgradeability"

    def analyze(self, target_id: str, source_path: Path, source: str) -> list[Finding]:
        findings: list[Finding] = []
        for function in functions_in(source):
            if function.name.casefold().startswith("initialize"):
                tail = function.tail.casefold()
                if "initializer" not in tail and "reinitializer" not in tail:
                    findings.append(
                        make_finding(
                            target_id=target_id,
                            detector=self.name,
                            source_path=source_path,
                            function=function,
                            title="Initializer-like entry point lacks an initializer modifier",
                            category="upgradeability_initialization",
                            description=(
                                "An initializer-named function lacks a visible one-time guard."
                            ),
                            impact="Repeated initialization can alter privileged state.",
                            false_positive_risks=[
                                "A custom guard may exist inside the function body."
                            ],
                            recommended_fix="Use a tested initializer/reinitializer guard.",
                        )
                    )
        return findings
