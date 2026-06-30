from __future__ import annotations

import json
import shutil
from pathlib import Path

from scbounty.analyzers.evidence import (
    semgrep_findings_from_execution,
    slither_findings_from_execution,
)
from scbounty.analyzers.runner import _merge_findings
from scbounty.config.models import ToolExecution
from scbounty.detectors.arbitrum_bridge import ArbitrumBridgeDetector


def _copy_toy_bridge(tmp_path: Path) -> Path:
    workspace = tmp_path / "toy_bridge"
    shutil.copytree("tests/fixtures/toy_bridge", workspace)
    return workspace


def test_semgrep_results_become_review_findings(tmp_path: Path) -> None:
    workspace = _copy_toy_bridge(tmp_path)
    source_path = workspace / "src" / "ToyBridge.sol"
    payload = {
        "results": [
            {
                "check_id": "semgrep.solidity.scbounty.solidity.bridge-mint-entry-point",
                "path": str(source_path),
                "start": {"line": 15},
                "end": {"line": 18},
                "extra": {
                    "message": (
                        "Bridge supply mutation requires manual gateway authorization review."
                    )
                },
            }
        ]
    }
    execution = ToolExecution(
        tool="semgrep",
        available=True,
        exit_code=0,
        stdout=json.dumps(payload),
    )

    findings = semgrep_findings_from_execution(
        target_id="toy_bridge",
        repository="scbounty/toy_bridge_fixture",
        workspace=workspace,
        execution=execution,
    )

    assert len(findings) == 1
    assert findings[0].tool == "semgrep"
    assert findings[0].category == "bridge_access_control"
    assert findings[0].affected_functions == ["bridgeMint"]
    assert findings[0].source_locations[0].path.endswith("src/ToyBridge.sol")
    assert findings[0].evidence[0].kind == "semgrep_signal"


def test_semgrep_parser_handles_invalid_payloads(tmp_path: Path) -> None:
    workspace = _copy_toy_bridge(tmp_path)

    assert (
        semgrep_findings_from_execution(
            target_id="toy_bridge",
            repository="scbounty/toy_bridge_fixture",
            workspace=workspace,
            execution=ToolExecution(
                tool="semgrep",
                available=True,
                exit_code=1,
                stdout="not-json",
            ),
        )
        == []
    )


def test_semgrep_rule_mapping_covers_accounting_and_initializer(tmp_path: Path) -> None:
    workspace = _copy_toy_bridge(tmp_path)
    initializer_source = workspace / "src" / "Initializer.sol"
    initializer_source.write_text(
        "contract Initializer { function initialize(address owner) external { owner; } }",
        encoding="utf-8",
    )
    payload = {
        "results": [
            {
                "check_id": "semgrep.solidity.scbounty.solidity.bridge-accounting-review",
                "path": str(workspace / "src" / "ToyBridge.sol"),
                "start": {"line": 49},
                "extra": {"message": "Accounting review"},
            },
            {
                "check_id": "semgrep.solidity.scbounty.solidity.initializer-review",
                "path": str(initializer_source),
                "start": {"line": 1},
                "extra": {"message": "Initializer review"},
            },
        ]
    }

    findings = semgrep_findings_from_execution(
        target_id="toy_bridge",
        repository="scbounty/toy_bridge_fixture",
        workspace=workspace,
        execution=ToolExecution(
            tool="semgrep",
            available=True,
            exit_code=0,
            stdout=json.dumps(payload),
        ),
    )

    assert [finding.category for finding in findings] == [
        "bridge_accounting",
        "upgradeability_initialization",
    ]
    assert [finding.affected_functions for finding in findings] == [["deposit"], ["initialize"]]


def test_cross_tool_merge_keeps_one_finding_with_multiple_evidence_items(tmp_path: Path) -> None:
    workspace = _copy_toy_bridge(tmp_path)
    source_path = workspace / "src" / "ToyBridge.sol"
    source = source_path.read_text(encoding="utf-8")
    internal = ArbitrumBridgeDetector().analyze(
        "toy_bridge",
        Path("scbounty/toy_bridge_fixture/src/ToyBridge.sol"),
        source,
    )[0]
    payload = {
        "results": [
            {
                "check_id": "semgrep.solidity.scbounty.solidity.bridge-mint-entry-point",
                "path": str(source_path),
                "start": {"line": 15},
                "end": {"line": 18},
                "extra": {"message": "Bridge mint review"},
            }
        ]
    }
    semgrep = semgrep_findings_from_execution(
        target_id="toy_bridge",
        repository="scbounty/toy_bridge_fixture",
        workspace=workspace,
        execution=ToolExecution(
            tool="semgrep",
            available=True,
            exit_code=0,
            stdout=json.dumps(payload),
        ),
    )[0]

    merged = _merge_findings([internal, semgrep])

    assert len(merged) == 1
    assert merged[0].finding_id == internal.finding_id
    assert {item.kind for item in merged[0].evidence} == {"source_pattern", "semgrep_signal"}


def test_slither_results_become_review_findings(tmp_path: Path) -> None:
    workspace = _copy_toy_bridge(tmp_path)
    source_path = workspace / "src" / "ToyBridge.sol"
    payload = {
        "results": {
            "detectors": [
                {
                    "check": "unprotected-upgrade",
                    "description": "Toy Slither signal",
                    "elements": [
                        {
                            "source_mapping": {
                                "filename_absolute": str(source_path),
                                "lines": [15],
                            }
                        }
                    ],
                }
            ]
        }
    }
    execution = ToolExecution(
        tool="slither",
        available=True,
        exit_code=0,
        stdout=json.dumps(payload),
    )

    findings = slither_findings_from_execution(
        target_id="toy_bridge",
        repository="scbounty/toy_bridge_fixture",
        workspace=workspace,
        execution=execution,
    )

    assert len(findings) == 1
    assert findings[0].tool == "slither"
    assert findings[0].affected_functions == ["bridgeMint"]
    assert findings[0].evidence[0].kind == "slither_signal"


def test_slither_parser_handles_missing_json_or_detector_elements(tmp_path: Path) -> None:
    workspace = _copy_toy_bridge(tmp_path)

    assert (
        slither_findings_from_execution(
            target_id="toy_bridge",
            repository="scbounty/toy_bridge_fixture",
            workspace=workspace,
            execution=ToolExecution(tool="slither", available=True, stdout=""),
        )
        == []
    )
    assert (
        slither_findings_from_execution(
            target_id="toy_bridge",
            repository="scbounty/toy_bridge_fixture",
            workspace=workspace,
            execution=ToolExecution(
                tool="slither",
                available=True,
                stdout=json.dumps({"results": {"detectors": [{"check": "x"}]}}),
            ),
        )
        == []
    )
