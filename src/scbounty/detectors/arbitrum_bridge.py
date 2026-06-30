from __future__ import annotations

from pathlib import Path

from scbounty.config.models import Finding
from scbounty.detectors.base import functions_in, has_caller_guard, make_finding


class ArbitrumBridgeDetector:
    name = "arbitrum_bridge"

    def analyze(self, target_id: str, source_path: Path, source: str) -> list[Finding]:
        findings: list[Finding] = []
        for function in functions_in(source):
            lowered = function.name.casefold()
            if lowered in {"bridgemint", "bridgeburn"} and not has_caller_guard(function):
                findings.append(
                    make_finding(
                        target_id=target_id,
                        detector=self.name,
                        source_path=source_path,
                        function=function,
                        title="Bridge mint/burn entry point lacks an explicit caller guard",
                        category="bridge_access_control",
                        description=(
                            "The bridge supply mutation entry point does not expose an explicit "
                            "gateway, router, bridge, role, or sender check in its "
                            "declaration/body."
                        ),
                        impact=(
                            "If no inherited or indirect guard exists, bridge supply may be "
                            "mutable."
                        ),
                        false_positive_risks=[
                            "The guard may be inherited through an unresolved modifier.",
                            "An internal callee may enforce the expected gateway.",
                        ],
                        recommended_fix=(
                            "Enforce and test the canonical gateway/counterpart caller at the "
                            "state-changing entry point."
                        ),
                    )
                )
            if lowered == "setgateway" and "=" in function.body and not has_caller_guard(function):
                findings.append(
                    make_finding(
                        target_id=target_id,
                        detector=self.name,
                        source_path=source_path,
                        function=function,
                        title="Gateway mapping mutation lacks an explicit authorization guard",
                        category="gateway_mapping",
                        description=(
                            "A gateway mapping appears mutable without a visible caller guard."
                        ),
                        impact=(
                            "Unauthorized remapping could route bridge operations to an "
                            "unsafe gateway."
                        ),
                        false_positive_risks=[
                            "Authorization may be enforced by an inherited modifier."
                        ],
                        recommended_fix=(
                            "Restrict remapping and test zero-address and replacement cases."
                        ),
                    )
                )
        return findings
