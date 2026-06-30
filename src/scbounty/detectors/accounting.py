from __future__ import annotations

from pathlib import Path

from scbounty.config.models import Finding
from scbounty.detectors.base import functions_in, make_finding


class AccountingDetector:
    name = "accounting"

    def analyze(self, target_id: str, source_path: Path, source: str) -> list[Finding]:
        findings: list[Finding] = []
        for function in functions_in(source):
            body = function.body.casefold()
            moves_tokens = "transferfrom" in body
            mints = "bridgemint" in body or "_mint" in body
            tracks_escrow = "escrow" in body or "locked" in body
            if moves_tokens and mints and not tracks_escrow:
                findings.append(
                    make_finding(
                        target_id=target_id,
                        detector=self.name,
                        source_path=source_path,
                        function=function,
                        title="Token movement and minting lack a visible escrow accounting update",
                        category="bridge_accounting",
                        description=(
                            "The function appears to move tokens and mint bridge representation "
                            "without updating a visible escrow/locked-balance invariant."
                        ),
                        impact="A real mismatch could create unbacked supply or insolvency.",
                        false_positive_risks=[
                            "The token balance itself may be the intended escrow ledger.",
                            "Accounting may be updated in a called contract.",
                        ],
                        recommended_fix=(
                            "Document and assert escrow == outstanding bridge supply "
                            "across deposits, "
                            "withdrawals, fee tokens, and failed messages."
                        ),
                    )
                )
        return findings
