from __future__ import annotations

from pathlib import Path

from scbounty.config.models import Finding
from scbounty.detectors.base import (
    functions_in,
    has_admin_guard,
    has_caller_guard,
    is_double_logic_proxy_admin_source,
    is_initializer,
    is_publicly_callable,
    is_read_only,
    make_finding,
)


class GasGriefingDetector:
    name = "gas_griefing"

    def analyze(self, target_id: str, source_path: Path, source: str) -> list[Finding]:
        findings: list[Finding] = []
        proxy_admin_routed = is_double_logic_proxy_admin_source(source)
        for function in functions_in(source):
            if (
                not is_publicly_callable(function)
                or is_read_only(function)
                or is_initializer(function)
                or has_admin_guard(function)
                or proxy_admin_routed
            ):
                continue
            body = function.body.casefold()
            user_array = "calldata" in function.tail.casefold() or "[]" in function.parameters
            has_loop = "for (" in body or "for(" in body or "while (" in body or "while(" in body
            committed_collection = (
                "hashaddresses(" in body
                and "currentrecipientgroup" in body
                and "hashweights(" in body
                and "currentrecipientweights" in body
            )
            if committed_collection:
                continue
            if user_array and has_loop and ".length" in body:
                caller_guarded = has_caller_guard(function)
                findings.append(
                    make_finding(
                        target_id=target_id,
                        detector=self.name,
                        source_path=source_path,
                        function=function,
                        title=(
                            "Counterpart-gated collection processing needs liveness review"
                            if caller_guarded
                            else "User-sized collection is processed in a loop"
                        ),
                        category="gas_griefing",
                        description=(
                            "A counterpart-gated bridge entry point loops over a collection whose "
                            "bound is not visible locally."
                            if caller_guarded
                            else "A public entry point loops over a caller-sized collection."
                        ),
                        impact=(
                            "Large inputs may make a required bridge/finalization path unusable."
                        ),
                        false_positive_risks=[
                            "The authorized counterpart may enforce a practical upper bound."
                            if caller_guarded
                            else "The caller may not control the collection size.",
                            "Protocol or ABI constraints may enforce a small bound.",
                        ],
                        recommended_fix="Enforce a proven bound or make progress resumable.",
                        confidence="low" if caller_guarded else "medium",
                    )
                )
        return findings
