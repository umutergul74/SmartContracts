from __future__ import annotations

from pathlib import Path

from scbounty.config.models import Finding
from scbounty.detectors.base import functions_in, has_caller_guard, is_reverting_stub, make_finding


class CrossChainMessagingDetector:
    name = "cross_chain_messaging"

    def analyze(self, target_id: str, source_path: Path, source: str) -> list[Finding]:
        findings: list[Finding] = []
        for function in functions_in(source):
            lowered = function.name.casefold()
            if (
                lowered in {"finalizeinboundtransfer", "executemessage"}
                and not is_reverting_stub(function.body)
                and not has_caller_guard(function)
            ):
                findings.append(
                    make_finding(
                        target_id=target_id,
                        detector=self.name,
                        source_path=source_path,
                        function=function,
                        title="Cross-chain finalization lacks a visible sender/counterpart check",
                        category="cross_chain_sender_validation",
                        description=(
                            "A message finalization entry point has no visible gateway, outbox, "
                            "router, alias, or msg.sender validation."
                        ),
                        impact=(
                            "Forged local calls may be mistaken for authenticated "
                            "cross-chain messages."
                        ),
                        false_positive_risks=[
                            "Authentication may be performed in a parent contract or "
                            "internal callee."
                        ],
                        recommended_fix=(
                            "Validate the canonical cross-domain sender and test aliased "
                            "and replayed calls."
                        ),
                    )
                )
        return findings
