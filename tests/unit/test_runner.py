from datetime import UTC, datetime
from pathlib import Path

from scbounty.analyzers.runner import AnalysisRunner
from scbounty.config.loader import load_target
from scbounty.config.models import (
    ScopeAttestation,
    ScopeDiff,
    SourceArtifact,
    SourceManifest,
)


class FakeScopeGate:
    def verify(self, target, *, root=None, output_path=None):
        del root, output_path
        return ScopeAttestation(
            attestation_id="test-attestation",
            target_id=target.target_id,
            verified_at_utc=datetime.now(UTC),
            scope_url=target.authorization.scope_url,
            snapshot_hash="a" * 64,
            live_content_hash="b" * 64,
            diff=ScopeDiff(
                passed=True,
                expected_asset_count=1,
                observed_asset_count=1,
                expected_asset_digest="c" * 64,
                observed_asset_digest="c" * 64,
                expected_impact_count=1,
                observed_impact_count=1,
                expected_impact_digest="d" * 64,
                observed_impact_digest="d" * 64,
            ),
        )


class FakeSourceFetcher:
    def __init__(self, fixture: Path) -> None:
        self.fixture = fixture

    def fetch(self, target, *, root=None, output_path=None):
        del root, output_path
        return SourceManifest(
            target_id=target.target_id,
            created_at_utc=datetime.now(UTC),
            artifacts=[
                SourceArtifact(
                    repository="fixture/toy-bridge",
                    url="https://example.test/toy-bridge",
                    commit_sha="f" * 40,
                    checkout_path=str(self.fixture),
                    selected_paths=["src/ToyBridge.sol", "src/SafeToyBridge.sol"],
                    selected_content_hash="e" * 64,
                )
            ],
        )


def test_runner_completes_safe_fixture_vertical_slice(tmp_path: Path) -> None:
    fixture = Path("tests/fixtures/toy_bridge").resolve()
    runner = AnalysisRunner(
        scope_gate=FakeScopeGate(),  # type: ignore[arg-type]
        source_fetcher=FakeSourceFetcher(fixture),  # type: ignore[arg-type]
    )

    manifest, findings, run_dir = runner.run(
        load_target("arbitrum"),
        tool="aderyn",
        root=tmp_path,
    )

    assert manifest.status == "completed"
    assert manifest.scope_attestation is not None
    assert len(findings) == 5
    assert (run_dir / "run.json").is_file()
    assert (run_dir / "findings.json").is_file()
    assert {result.analyzer for result in manifest.analyzer_results} == {"aderyn", "scbounty"}
