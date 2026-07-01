from __future__ import annotations

from datetime import UTC, datetime
from pathlib import Path

from scbounty.analyzers import (
    AderynAdapter,
    EchidnaAdapter,
    FoundryAdapter,
    HalmosAdapter,
    MedusaAdapter,
    MythrilAdapter,
    SemgrepAdapter,
    SlitherAdapter,
    SolhintAdapter,
)
from scbounty.analyzers.base import AnalyzerAdapter
from scbounty.analyzers.evidence import (
    semgrep_findings_from_execution,
    slither_findings_from_execution,
)
from scbounty.config.models import (
    AnalyzerResult,
    Finding,
    RunManifest,
    TargetConfig,
    ToolExecution,
)
from scbounty.config.scope_gate import ScopeGate
from scbounty.detectors import (
    AccountingDetector,
    ArbitrumBridgeDetector,
    CrossChainMessagingDetector,
    GasGriefingDetector,
    UnsafeERC20Detector,
    UpgradeabilityDetector,
)
from scbounty.detectors.base import Detector
from scbounty.source.fetcher import SourceFetcher
from scbounty.utils.hashing import stable_json_hash
from scbounty.utils.paths import artifacts_root, safe_child
from scbounty.utils.serialization import write_model, write_models


def _adapter_registry() -> dict[str, AnalyzerAdapter]:
    adapters: list[AnalyzerAdapter] = [
        FoundryAdapter(),
        SlitherAdapter(),
        SemgrepAdapter(),
        AderynAdapter(),
        MythrilAdapter(),
        EchidnaAdapter(),
        MedusaAdapter(),
        HalmosAdapter(),
        SolhintAdapter(),
    ]
    return {adapter.name: adapter for adapter in adapters}


def _detectors() -> list[Detector]:
    return [
        ArbitrumBridgeDetector(),
        CrossChainMessagingDetector(),
        AccountingDetector(),
        UnsafeERC20Detector(),
        UpgradeabilityDetector(),
        GasGriefingDetector(),
    ]


def _merge_findings(findings: list[Finding]) -> list[Finding]:
    merged: dict[str, Finding] = {}
    for finding in findings:
        semantic_key = _semantic_deduplication_key(finding)
        current = merged.get(semantic_key)
        if current is None:
            merged[semantic_key] = finding
            continue
        known = {(item.kind, item.summary, item.source) for item in current.evidence}
        current.evidence.extend(
            item for item in finding.evidence if (item.kind, item.summary, item.source) not in known
        )
    return sorted(merged.values(), key=lambda finding: finding.finding_id)


def _semantic_deduplication_key(finding: Finding) -> str:
    location = finding.source_locations[0] if finding.source_locations else None
    location_path = location.path if location else ""
    functions = ",".join(sorted(finding.affected_functions))
    return "|".join((finding.target_id, location_path, functions, finding.category))


def _filter_findings_to_selected_paths(
    findings: list[Finding],
    repository: str,
    selected_paths: list[str],
) -> list[Finding]:
    allowed = {(Path(repository) / Path(path)).as_posix() for path in selected_paths}
    return [
        finding
        for finding in findings
        if any(location.path in allowed for location in finding.source_locations)
    ]


def _findings_from_analyzer_result(
    target: TargetConfig,
    repository: str,
    workspace: Path,
    selected_paths: list[str],
    result: AnalyzerResult,
) -> list[Finding]:
    if result.analyzer == "semgrep":
        findings = semgrep_findings_from_execution(
            target_id=target.target_id,
            repository=repository,
            workspace=workspace,
            execution=result.execution,
        )
    elif result.analyzer == "slither":
        findings = slither_findings_from_execution(
            target_id=target.target_id,
            repository=repository,
            workspace=workspace,
            execution=result.execution,
        )
    else:
        return []
    return _filter_findings_to_selected_paths(findings, repository, selected_paths)


def _create_run_directory(
    target_id: str,
    started: datetime,
    config_hash: str,
    root: Path | None,
) -> tuple[str, Path]:
    base_run_id = f"{target_id}-{started.strftime('%Y%m%dT%H%M%S%fZ')}-{config_hash[:8]}"
    for attempt in range(100):
        run_id = base_run_id if attempt == 0 else f"{base_run_id}-{attempt}"
        run_dir = safe_child(artifacts_root(root), "runs", run_id)
        try:
            run_dir.mkdir(parents=True, exist_ok=False)
        except FileExistsError:
            continue
        return run_id, run_dir
    raise RuntimeError(f"Could not allocate a unique run directory for {base_run_id}")


class AnalysisRunner:
    def __init__(
        self,
        scope_gate: ScopeGate | None = None,
        source_fetcher: SourceFetcher | None = None,
    ) -> None:
        self.scope_gate = scope_gate or ScopeGate()
        self.source_fetcher = source_fetcher or SourceFetcher()

    def run(
        self,
        target: TargetConfig,
        *,
        tool: str | None = None,
        root: Path | None = None,
    ) -> tuple[RunManifest, list[Finding], Path]:
        started = datetime.now(UTC)
        config_hash = stable_json_hash(target.model_dump(mode="json"))
        run_id, run_dir = _create_run_directory(target.target_id, started, config_hash, root)
        manifest_path = run_dir / "run.json"
        manifest = RunManifest(
            run_id=run_id,
            target_id=target.target_id,
            started_at_utc=started,
            status="running",
            config_hash=config_hash,
        )
        write_model(manifest_path, manifest)

        attestation = self.scope_gate.verify(
            target,
            root=root,
            output_path=run_dir / "scope-attestation.json",
        )
        manifest.scope_attestation = attestation
        source_manifest = self.source_fetcher.fetch(
            target,
            root=root,
            output_path=run_dir / "source-manifest.json",
        )
        manifest.source_manifest_path = "source-manifest.json"
        write_model(manifest_path, manifest)

        registry = _adapter_registry()
        if tool is not None and tool not in registry:
            raise ValueError(f"Unknown analyzer '{tool}'. Available: {', '.join(sorted(registry))}")
        selected_adapters = (
            [registry[tool]]
            if tool
            else [
                registry["foundry"],
                registry["slither"],
                registry["semgrep"],
                registry["aderyn"],
                registry["mythril"],
                registry["echidna"],
                registry["medusa"],
                registry["halmos"],
                registry["solhint"],
            ]
        )

        results: list[AnalyzerResult] = []
        all_findings: list[Finding] = []
        for artifact in source_manifest.artifacts:
            workspace = Path(artifact.checkout_path)
            analyzer_findings: list[Finding] = []
            for adapter in selected_adapters:
                result = adapter.run(target, workspace, artifact.selected_paths)
                result.findings = _findings_from_analyzer_result(
                    target,
                    artifact.repository,
                    workspace,
                    artifact.selected_paths,
                    result,
                )
                analyzer_findings.extend(result.findings)
                results.append(result)
            for relative in artifact.selected_paths:
                source_file = workspace / relative
                source = source_file.read_text(encoding="utf-8", errors="replace")
                display_path = Path(artifact.repository) / relative
                for detector in _detectors():
                    all_findings.extend(detector.analyze(target.target_id, display_path, source))
            all_findings.extend(analyzer_findings)

        findings = _merge_findings(all_findings)
        internal_result = AnalyzerResult(
            analyzer="scbounty",
            status="completed",
            execution=ToolExecution(
                tool="scbounty",
                available=True,
                version="0.1.0",
                started_at_utc=started,
                ended_at_utc=datetime.now(UTC),
                exit_code=0,
            ),
            findings=findings,
        )
        results.append(internal_result)
        findings_path = run_dir / "findings.json"
        write_models(findings_path, findings)
        manifest.analyzer_results = results
        manifest.findings_path = "findings.json"
        manifest.completed_at_utc = datetime.now(UTC)
        manifest.status = "completed"
        write_model(manifest_path, manifest)
        return manifest, findings, run_dir
