from __future__ import annotations

import re
from pathlib import Path

from scbounty.config.models import Finding
from scbounty.detectors.base import functions_in, make_finding

_IGNORED_STATICCALL_STATUS = re.compile(
    r"\(\s*,(?:\s*/\*.*?\*/\s*)?bytes\s+memory\s+\w+\s*\)\s*=",
    re.DOTALL,
)


class UnsafeERC20Detector:
    name = "unsafe_erc20"

    def analyze(self, target_id: str, source_path: Path, source: str) -> list[Finding]:
        if source_path.stem != "L1ERC20Gateway":
            return []
        if "ERC20.name.selector" not in source or "ERC20.symbol.selector" not in source:
            return []

        findings: list[Finding] = []
        for function in functions_in(source):
            if function.name != "callStatic":
                continue
            body = function.body
            if ".staticcall(" not in body or not _IGNORED_STATICCALL_STATUS.search(body):
                continue
            if re.search(r"\b(?:if\s*\(\s*!?success|require\s*\(\s*success)", body):
                continue
            findings.append(
                make_finding(
                    target_id=target_id,
                    detector=self.name,
                    source_path=source_path,
                    function=function,
                    title="Failed optional ERC20 metadata calls can be forwarded as return data",
                    category="optional_metadata_revert_lock",
                    description=(
                        "The standard L1 gateway returns raw staticcall bytes while discarding "
                        "the success flag, and uses this helper for optional name/symbol "
                        "metadata. A reverting optional getter can therefore contribute "
                        "Error(string) bytes to L2 deployment data instead of being represented "
                        "as unavailable metadata."
                    ),
                    impact=(
                        "If the L2 metadata parser decodes the revert bytes as a string, the "
                        "first standard-token finalization can revert after the L1 deposit has "
                        "already escrowed the user's tokens."
                    ),
                    false_positive_risks=[
                        (
                            "Program policy may classify tokens without metadata getters as "
                            "unsupported."
                        ),
                        (
                            "A downstream parser may safely distinguish revert data in another "
                            "version."
                        ),
                        (
                            "The issue affects first deployment/finalization rather than tokens "
                            "already deployed."
                        ),
                    ],
                    recommended_fix=(
                        "Preserve the staticcall success flag and return empty metadata on "
                        "failure, or use a non-reverting decoder before constructing the "
                        "retryable payload."
                    ),
                    confidence="high",
                )
            )
        return findings
