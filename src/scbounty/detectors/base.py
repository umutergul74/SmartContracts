from __future__ import annotations

import re
from dataclasses import dataclass
from datetime import UTC, datetime
from pathlib import Path
from typing import Protocol

from scbounty.config.models import EvidenceItem, Finding, SourceLocation
from scbounty.utils.hashing import sha256_text

_FUNCTION_HEADER = re.compile(
    r"\bfunction\s+(?P<name>[A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\((?P<params>.*?)\)\s*(?P<tail>[^{;]*)\{",
    re.DOTALL,
)


@dataclass(frozen=True)
class SolidityFunction:
    name: str
    parameters: str
    tail: str
    body: str
    start_line: int
    end_line: int


class Detector(Protocol):
    name: str

    def analyze(self, target_id: str, source_path: Path, source: str) -> list[Finding]: ...


def functions_in(source: str) -> list[SolidityFunction]:
    functions: list[SolidityFunction] = []
    for match in _FUNCTION_HEADER.finditer(source):
        depth = 1
        cursor = match.end()
        while cursor < len(source) and depth:
            if source[cursor] == "{":
                depth += 1
            elif source[cursor] == "}":
                depth -= 1
            cursor += 1
        if depth:
            continue
        start_line = source.count("\n", 0, match.start()) + 1
        end_line = source.count("\n", 0, cursor) + 1
        functions.append(
            SolidityFunction(
                name=match.group("name"),
                parameters=match.group("params"),
                tail=match.group("tail"),
                body=source[match.end() : cursor - 1],
                start_line=start_line,
                end_line=end_line,
            )
        )
    return functions


def has_caller_guard(function: SolidityFunction) -> bool:
    combined = f"{function.tail}\n{function.body}".casefold()
    if re.search(r"\bonly[a-z0-9_]*(gateway|router|bridge|counterpart|timelock)\b", combined):
        return True
    markers = (
        "onlycounterpartgateway",
        "onlygateway",
        "onlyrouter",
        "onlybridge",
        "onlyowner",
        "onlyrole",
        "not_from_bridge",
        "only_counterpart_gateway",
        "getl2tol1sender",
        "msg.sender ==",
        "msg.sender!=",
        "msg.sender !=",
        "_msgsender() ==",
        "addressaliashelper",
    )
    return any(marker in combined for marker in markers)


def has_admin_guard(function: SolidityFunction) -> bool:
    combined = f"{function.tail}\n{function.body}".casefold()
    return any(
        marker in combined
        for marker in (
            "onlyowner",
            "onlyrole",
            "proxyadmin",
            "msg.sender == owner",
            "msg.sender==owner",
            "not_from_admin",
            "onlyrole(default_admin_role",
        )
    )


def is_initializer(function: SolidityFunction) -> bool:
    return function.name.casefold() in {"initialize", "initializer"} or " initializer" in (
        f" {function.tail.casefold()}"
    )


def is_publicly_callable(function: SolidityFunction) -> bool:
    tail = function.tail.casefold()
    return "external" in tail or "public" in tail


def is_read_only(function: SolidityFunction) -> bool:
    tail = function.tail.casefold()
    return " view" in f" {tail}" or " pure" in f" {tail}"


def is_double_logic_proxy_admin_source(source: str) -> bool:
    lowered = source.casefold()
    return (
        "doublelogicuupsupgradeable" in lowered
        and "function _authorizeupgrade" in lowered
        and "function _authorizesecondaryupgrade" in lowered
    )


def body_without_string_literals(body: str) -> str:
    return re.sub(r'"[^"]*"|\'[^\']*\'', '""', body)


def is_reverting_stub(body: str) -> bool:
    lowered = body_without_string_literals(body).casefold()
    mutation_markers = (
        "_mint",
        "_burn",
        "totalsupply",
        "balanceof",
        ".mint",
        ".burn",
        "transfer(",
        "call{",
    )
    return "revert(" in lowered and not any(marker in lowered for marker in mutation_markers)


def make_finding(
    *,
    target_id: str,
    detector: str,
    source_path: Path,
    function: SolidityFunction,
    title: str,
    category: str,
    description: str,
    impact: str,
    false_positive_risks: list[str],
    recommended_fix: str,
    confidence: str = "medium",
) -> Finding:
    normalized_path = source_path.as_posix()
    dedup = sha256_text(
        "|".join((target_id, detector, normalized_path, function.name, category, title))
    )
    return Finding(
        finding_id=f"SCB-{dedup[:12].upper()}",
        target_id=target_id,
        title=title,
        severity="low",
        confidence=confidence,  # type: ignore[arg-type]
        category=category,
        detector=detector,
        affected_contracts=[source_path.stem],
        affected_functions=[function.name],
        source_locations=[
            SourceLocation(
                path=normalized_path,
                start_line=function.start_line,
                end_line=function.end_line,
            )
        ],
        description=description,
        impact=impact,
        impact_category="requires_manual_mapping",
        severity_rationale=(
            "Automated signals are capped at low severity until scope, exploitability, "
            "and concrete program impact are confirmed by a human."
        ),
        exploitability_notes="No production exploitability claim has been made.",
        safe_poc_status="needs_manual_triage",
        reproduction_steps=["Review the cited function in an isolated local workspace."],
        evidence=[
            EvidenceItem(
                kind="source_pattern",
                summary=f"{detector} matched {function.name} at {normalized_path}.",
                source=detector,
            )
        ],
        false_positive_risks=false_positive_risks,
        recommended_fix=recommended_fix,
        references=[],
        scope_status="possibly_in_scope",
        scope_evidence=[],
        deduplication_key=dedup,
        created_at_utc=datetime.now(UTC),
    )
