from __future__ import annotations

from pathlib import Path

from scbounty.config.models import Finding
from scbounty.detectors.base import functions_in, make_finding


class GasGriefingDetector:
    name = "gas_griefing"

    def analyze(self, target_id: str, source_path: Path, source: str) -> list[Finding]:
        findings: list[Finding] = []
        for function in functions_in(source):
            body = function.body.casefold()
            user_array = "calldata" in function.tail.casefold() or "[]" in function.parameters
            has_loop = "for (" in body or "for(" in body or "while (" in body or "while(" in body
            if user_array and has_loop and ".length" in body:
                findings.append(
                    make_finding(
                        target_id=target_id,
                        detector=self.name,
                        source_path=source_path,
                        function=function,
                        title="User-sized collection is processed in a loop",
                        category="gas_griefing",
                        description="A public entry point loops over a caller-sized collection.",
                        impact=(
                            "Large inputs may make a required bridge/finalization path unusable."
                        ),
                        false_positive_risks=[
                            "Protocol or ABI constraints may enforce a small bound."
                        ],
                        recommended_fix="Enforce a proven bound or make progress resumable.",
                    )
                )
        return findings
