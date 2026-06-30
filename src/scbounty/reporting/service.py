from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path
from typing import Literal

from pydantic import TypeAdapter

from scbounty.config.models import Finding, ReportManifest, RunManifest, TargetConfig, TriageRecord
from scbounty.reporting.immunefi_template import render_immunefi
from scbounty.reporting.json_report import render_json
from scbounty.reporting.markdown import render_markdown
from scbounty.utils.paths import artifacts_root, safe_child
from scbounty.utils.serialization import write_model, write_models

_FINDINGS = TypeAdapter(list[Finding])


class ReportError(RuntimeError):
    """Raised when a run or report artifact cannot be resolved."""


def latest_run(target_id: str, root: Path | None = None) -> Path:
    base = safe_child(artifacts_root(root), "runs")
    if not base.is_dir():
        raise ReportError(f"No runs exist for target '{target_id}'")
    candidates: list[tuple[datetime, Path]] = []
    for directory in base.iterdir():
        manifest_path = directory / "run.json"
        if not manifest_path.is_file():
            continue
        manifest = RunManifest.model_validate_json(manifest_path.read_bytes())
        if manifest.target_id == target_id and manifest.status == "completed":
            candidates.append((manifest.started_at_utc, directory))
    if not candidates:
        raise ReportError(f"No completed runs exist for target '{target_id}'")
    return max(candidates, key=lambda item: item[0])[1]


def resolve_run(target_id: str, run_id: str | None, root: Path | None = None) -> Path:
    if run_id is None:
        return latest_run(target_id, root)
    directory = safe_child(artifacts_root(root), "runs", run_id)
    if not (directory / "run.json").is_file():
        raise ReportError(f"Unknown run: {run_id}")
    return directory


def load_findings(run_dir: Path) -> list[Finding]:
    path = run_dir / "findings.json"
    if not path.is_file():
        raise ReportError(f"Findings are missing from {run_dir.name}")
    return _FINDINGS.validate_json(path.read_bytes())


def triage_finding(
    run_dir: Path,
    finding_id: str,
    status: Literal["needs_review", "confirmed", "rejected"],
    note: str,
    *,
    scope_confirmed: bool = False,
    poc_status: Literal["local_fixture", "local_fork"] | None = None,
) -> Finding:
    findings = load_findings(run_dir)
    selected = next((finding for finding in findings if finding.finding_id == finding_id), None)
    if selected is None:
        raise ReportError(f"Finding does not exist in run {run_dir.name}: {finding_id}")
    if status == "confirmed":
        if not scope_confirmed:
            raise ReportError("Confirmed triage requires an explicit reviewed in-scope mapping")
        if poc_status is None:
            raise ReportError(
                "Confirmed triage requires a local fixture or local fork reproduction"
            )
        selected.scope_status = "in_scope"
        selected.safe_poc_status = poc_status
        selected.scope_evidence.append(note)
    selected.triage_status = status
    write_models(run_dir / "findings.json", findings)
    record = TriageRecord(
        finding_id=finding_id,
        run_id=run_dir.name,
        status=status,
        note=note,
        reviewed_at_utc=datetime.now(UTC),
    )
    write_model(run_dir / "triage" / f"{finding_id}.json", record)
    return selected


def generate_report(
    target: TargetConfig,
    run_dir: Path,
    report_format: Literal["markdown", "json", "immunefi"],
) -> ReportManifest:
    findings = load_findings(run_dir)
    report_dir = run_dir / "reports"
    report_dir.mkdir(parents=True, exist_ok=True)
    if report_format == "json":
        output = report_dir / "report.json"
        output.write_bytes(render_json(findings))
    elif report_format == "markdown":
        output = report_dir / "report.md"
        output.write_text(render_markdown(target, findings), encoding="utf-8")
    else:
        output = report_dir / "immunefi-draft.md"
        output.write_text(render_immunefi(target, findings), encoding="utf-8")
    manifest = ReportManifest(
        run_id=run_dir.name,
        target_id=target.target_id,
        generated_at_utc=datetime.now(UTC),
        format=report_format,
        output_path=str(output),
        included_findings=[finding.finding_id for finding in findings],
        draft=any(not finding.shareable for finding in findings),
    )
    write_model(report_dir / f"{report_format}-manifest.json", manifest)
    return manifest
