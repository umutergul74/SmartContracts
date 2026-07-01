from __future__ import annotations

from pathlib import Path

from scbounty.config.models import Finding
from scbounty.detectors.base import SolidityFunction, functions_in, make_finding


class UpgradeabilityDetector:
    name = "upgradeability"

    def analyze(self, target_id: str, source_path: Path, source: str) -> list[Finding]:
        findings: list[Finding] = []
        functions = functions_in(source)
        for function in functions:
            if function.name.casefold().startswith("initialize"):
                if _has_initializer_guard(function) or _delegates_to_known_guarded_initializer(
                    function
                ):
                    continue
                delegates_to_internal_initializer = "_initialize(" in function.body.casefold()
                if delegates_to_internal_initializer:
                    title = "Initializer-like entry point delegates to an internal initializer"
                    description = (
                        "An initializer-named function lacks a standard initializer modifier, "
                        "but delegates to an internal initializer that may enforce a custom "
                        "one-time guard."
                    )
                    false_positive_risks = [
                        "The internal initializer may contain a proven ALREADY_INIT-style guard.",
                        "The deployed proxy may have been initialized atomically at deployment.",
                    ]
                    recommended_fix = (
                        "Trace the internal initializer and deployed proxy initialization path; "
                        "add a regression proving repeated calls revert before privileged "
                        "state changes."
                    )
                    confidence = "low"
                else:
                    title = "Initializer-like entry point lacks an initializer modifier"
                    description = "An initializer-named function lacks a visible one-time guard."
                    false_positive_risks = ["A custom guard may exist inside the function body."]
                    recommended_fix = "Use a tested initializer/reinitializer guard."
                    confidence = "medium"
                findings.append(
                    make_finding(
                        target_id=target_id,
                        detector=self.name,
                        source_path=source_path,
                        function=function,
                        title=title,
                        category="upgradeability_initialization",
                        description=description,
                        impact="Repeated initialization can alter privileged state.",
                        false_positive_risks=false_positive_risks,
                        recommended_fix=recommended_fix,
                        confidence=confidence,
                    )
                )
        return findings


def _has_initializer_guard(function: SolidityFunction) -> bool:
    # Keep this textual and conservative; deeper inheritance tracing belongs in the Slither-backed
    # phase. These markers cover standard OpenZeppelin modifiers plus explicit one-time guards.
    tail = function.tail.casefold()
    body = function.body.casefold()
    combined = f"{tail}\n{body}"
    return any(
        marker in combined
        for marker in (
            "initializer",
            "reinitializer",
            "alreadyinit",
            "already init",
            "already_init",
            "already initialized",
            "already_initialized",
            "!= address(0)) revert",
            "!= ibridge(address(0))) revert",
            "counterpartgateway == address(0)",
            "_initialized",
        )
    )


def _delegates_to_known_guarded_initializer(function: SolidityFunction) -> bool:
    # These are Arbitrum bridge/gateway initializer chains whose internal implementation
    # terminates in TokenGateway._initialize, which enforces counterpartGateway == address(0).
    # Keep the list explicit and narrow; unknown internal initializers should still produce
    # a review signal until Slither inheritance tracing proves the guard.
    body = function.body.casefold()
    return any(
        marker in body
        for marker in (
            "tokengateway._initialize(",
            "l1arbitrumgateway._initialize(",
            "l2arbitrumgateway._initialize(",
            "l2gatewaytoken._initialize(",
            "gatewayrouter._initialize(",
        )
    )
