from datetime import UTC, datetime
from pathlib import Path

import pytest

from scbounty.config.loader import load_target
from scbounty.config.models import RunManifest
from scbounty.detectors.arbitrum_bridge import ArbitrumBridgeDetector
from scbounty.reporting.service import (
    ReportError,
    generate_report,
    latest_run,
    load_findings,
    resolve_run,
    triage_finding,
)
from scbounty.utils.serialization import write_model, write_models


def _completed_run(tmp_path: Path) -> tuple[Path, object]:
    run_dir = tmp_path / "artifacts" / "runs" / "arbitrum-run"
    finding = ArbitrumBridgeDetector().analyze(
        "arbitrum",
        Path("Token.sol"),
        "contract T { function bridgeMint(address a, uint x) external { a; x; } }",
    )[0]
    write_models(run_dir / "findings.json", [finding])
    write_model(
        run_dir / "run.json",
        RunManifest(
            run_id="arbitrum-run",
            target_id="arbitrum",
            started_at_utc=datetime.now(UTC),
            completed_at_utc=datetime.now(UTC),
            status="completed",
            config_hash="a" * 64,
            findings_path="findings.json",
        ),
    )
    return run_dir, finding


def test_run_resolution_triage_and_reports(tmp_path: Path) -> None:
    run_dir, finding = _completed_run(tmp_path)

    assert latest_run("arbitrum", tmp_path) == run_dir
    assert resolve_run("arbitrum", "arbitrum-run", tmp_path) == run_dir
    updated = triage_finding(
        run_dir,
        finding.finding_id,  # type: ignore[attr-defined]
        "confirmed",
        "Reviewed current scope and local fixture evidence.",
        scope_confirmed=True,
        poc_status="local_fixture",
    )
    assert updated.shareable is True
    assert load_findings(run_dir)[0].triage_status == "confirmed"

    target = load_target("arbitrum")
    assert generate_report(target, run_dir, "markdown").draft is False
    assert generate_report(target, run_dir, "json").output_path.endswith("report.json")
    assert generate_report(target, run_dir, "immunefi").draft is False


def test_confirmed_triage_requires_scope_and_poc(tmp_path: Path) -> None:
    run_dir, finding = _completed_run(tmp_path)

    with pytest.raises(ReportError, match="in-scope mapping"):
        triage_finding(
            run_dir,
            finding.finding_id,  # type: ignore[attr-defined]
            "confirmed",
            "note",
        )
