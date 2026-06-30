from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from scbounty.config.models import EvidenceItem, Finding, ToolExecution
from scbounty.detectors.base import SolidityFunction, functions_in, make_finding


def _function_at_line(source: str, line: int) -> SolidityFunction:
    for function in functions_in(source):
        if function.start_line <= line <= function.end_line:
            return function
    return SolidityFunction(
        name=f"line_{line}",
        parameters="",
        tail="",
        body="",
        start_line=max(line, 1),
        end_line=max(line, 1),
    )


def _display_path(repository: str, workspace: Path, raw_path: str) -> tuple[Path, Path] | None:
    candidate = Path(raw_path)
    source_file = candidate if candidate.is_absolute() else workspace / candidate
    source_file = source_file.resolve()
    workspace = workspace.resolve()
    if not source_file.is_file() or not source_file.is_relative_to(workspace):
        return None
    relative = source_file.relative_to(workspace)
    return source_file, Path(repository) / relative


def _semgrep_rule_metadata(check_id: str) -> tuple[str, str, str, str, list[str], str]:
    rule = check_id.split(".")[-1]
    if rule == "bridge-mint-entry-point":
        return (
            "bridge_access_control",
            "Bridge mint/burn entry point lacks an explicit caller guard",
            "Semgrep matched a bridge supply mutation entry point for authorization review.",
            (
                "If no stronger guard exists, bridge supply mutation may be reachable by "
                "an unexpected caller."
            ),
            [
                "Semgrep is syntax-oriented and cannot prove inherited authorization.",
                "A guard may exist in a modifier, parent contract, or internal callee.",
            ],
            "Validate the canonical bridge/gateway/router caller in semantic analysis and tests.",
        )
    if rule == "bridge-accounting-review":
        return (
            "bridge_accounting",
            "Token movement and minting lack a visible escrow accounting update",
            "Semgrep matched token movement near bridge minting for escrow invariant review.",
            "A real accounting mismatch could create unbacked representation supply.",
            [
                "Token balance may be the intended escrow ledger.",
                "Accounting may happen in a called contract or inherited function.",
            ],
            "Add or document escrow/supply invariants and cover fee-token edge cases.",
        )
    if rule == "initializer-review":
        return (
            "upgradeability_initialization",
            "Initializer-like entry point requires one-time guard review",
            "Semgrep matched an initializer-like entry point for one-time guard review.",
            "Repeated initialization can alter privileged state if no effective guard exists.",
            [
                "The initializer guard may be implemented by a modifier or custom state check.",
                "The function may only be callable during deployment in the upstream workflow.",
            ],
            "Confirm initializer/reinitializer semantics and add regression coverage.",
        )
    return (
        f"semgrep_{rule}",
        f"Semgrep rule {rule} requires manual review",
        "Semgrep emitted a local Solidity rule signal.",
        "The impact depends on manual scope and exploitability review.",
        ["Semgrep results are review signals and not standalone bounty evidence."],
        "Manually review the cited source and add a stronger semantic detector if useful.",
    )


def semgrep_findings_from_execution(
    *,
    target_id: str,
    repository: str,
    workspace: Path,
    execution: ToolExecution,
) -> list[Finding]:
    if not execution.stdout.strip():
        return []
    try:
        payload = json.loads(execution.stdout)
    except json.JSONDecodeError:
        return []
    findings: list[Finding] = []
    for result in payload.get("results", []):
        if not isinstance(result, dict):
            continue
        raw_path = str(result.get("path", ""))
        resolved = _display_path(repository, workspace, raw_path)
        if resolved is None:
            continue
        source_file, display_path = resolved
        raw_start = result.get("start")
        start = raw_start if isinstance(raw_start, dict) else {}
        start_line = int(start.get("line") or 1)
        source = source_file.read_text(encoding="utf-8", errors="replace")
        function = _function_at_line(source, start_line)
        raw_extra = result.get("extra")
        extra = raw_extra if isinstance(raw_extra, dict) else {}
        check_id = str(result.get("check_id", "semgrep.unknown"))
        message = str(extra.get("message") or check_id)
        category, title, description, impact, risks, fix = _semgrep_rule_metadata(check_id)
        finding = make_finding(
            target_id=target_id,
            detector="semgrep",
            source_path=display_path,
            function=function,
            title=title,
            category=category,
            description=description,
            impact=impact,
            false_positive_risks=risks,
            recommended_fix=fix,
            confidence="low",
        )
        finding.tool = "semgrep"
        finding.evidence = [
            EvidenceItem(
                kind="semgrep_signal",
                summary=message,
                artifact_path="run.json",
                source=check_id,
            )
        ]
        findings.append(finding)
    return findings


def slither_findings_from_execution(
    *,
    target_id: str,
    repository: str,
    workspace: Path,
    execution: ToolExecution,
) -> list[Finding]:
    if not execution.stdout.strip().startswith("{"):
        return []
    try:
        payload: dict[str, Any] = json.loads(execution.stdout)
    except json.JSONDecodeError:
        return []
    detectors = payload.get("results", {}).get("detectors", [])
    if not isinstance(detectors, list):
        return []
    findings: list[Finding] = []
    for detector_result in detectors:
        if not isinstance(detector_result, dict):
            continue
        elements = detector_result.get("elements")
        if not isinstance(elements, list) or not elements:
            continue
        element = next((item for item in elements if isinstance(item, dict)), None)
        if element is None:
            continue
        mapping = element.get("source_mapping")
        if not isinstance(mapping, dict):
            continue
        raw_path = str(mapping.get("filename_absolute") or mapping.get("filename") or "")
        resolved = _display_path(repository, workspace, raw_path)
        if resolved is None:
            continue
        source_file, display_path = resolved
        lines = mapping.get("lines") if isinstance(mapping.get("lines"), list) else []
        start_line = int(lines[0]) if lines else 1
        source = source_file.read_text(encoding="utf-8", errors="replace")
        function = _function_at_line(source, start_line)
        check = str(detector_result.get("check") or "slither-review")
        description = str(detector_result.get("description") or check).strip()
        finding = make_finding(
            target_id=target_id,
            detector="slither",
            source_path=display_path,
            function=function,
            title=f"Slither {check} requires manual review",
            category=f"slither_{check.replace('-', '_')}",
            description=description,
            impact="Slither emitted a semantic analysis signal requiring human triage.",
            false_positive_risks=[
                "Slither findings can be informational or context-dependent.",
                "Scope and exploitability must be confirmed manually.",
            ],
            recommended_fix=(
                "Review the Slither finding and add a local PoC or invariant if relevant."
            ),
            confidence="medium",
        )
        finding.tool = "slither"
        finding.evidence = [
            EvidenceItem(
                kind="slither_signal",
                summary=description.splitlines()[0],
                artifact_path="run.json",
                source=check,
            )
        ]
        findings.append(finding)
    return findings
