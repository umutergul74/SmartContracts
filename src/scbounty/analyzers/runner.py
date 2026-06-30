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
        UpgradeabilityDetector(),
        GasGriefingDetector(),
    ]


def _merge_findings(findings: list[Finding]) -> list[Finding]:
    merged: dict[str, Finding] = {}
    for finding in findings:
        current = merged.get(finding.deduplication_key)
        if current is None:
            merged[finding.deduplication_key] = finding
            continue
        known = {(item.kind, item.summary, item.source) for item in current.evidence}
        current.evidence.extend(
            item for item in finding.evidence if (item.kind, item.summary, item.source) not in known
        )
    return sorted(merged.values(), key=lambda finding: finding.finding_id)


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
        run_id = f"{target.target_id}-{started.strftime('%Y%m%dT%H%M%SZ')}-{config_hash[:8]}"
        run_dir = safe_child(artifacts_root(root), "runs", run_id)
        run_dir.mkdir(parents=True, exist_ok=False)
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
            for adapter in selected_adapters:
                result = adapter.run(target, workspace, artifact.selected_paths)
                results.append(result)
            for relative in artifact.selected_paths:
                source_file = workspace / relative
                source = source_file.read_text(encoding="utf-8", errors="replace")
                display_path = Path(artifact.repository) / relative
                for detector in _detectors():
                    all_findings.extend(detector.analyze(target.target_id, display_path, source))

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
