from datetime import UTC, datetime

from scbounty.config.loader import load_target
from scbounty.config.models import ScopeAttestation, ScopeDiff
from scbounty.config.scope_coverage import (
    compare_target_scope_coverage,
    github_blob_asset_key,
    latest_attestation_path,
    render_scope_coverage_markdown,
)
from scbounty.utils.serialization import write_model


def _attestation(urls: list[str]) -> ScopeAttestation:
    return ScopeAttestation(
        attestation_id="scope-test",
        target_id="arbitrum",
        verified_at_utc=datetime.now(UTC),
        scope_url="https://immunefi.com/bug-bounty/arbitrum/scope/",
        snapshot_hash="a" * 64,
        live_content_hash="b" * 64,
        diff=ScopeDiff(
            passed=True,
            expected_asset_count=len(urls),
            observed_asset_count=len(urls),
            expected_asset_digest="c" * 64,
            observed_asset_digest="c" * 64,
            expected_impact_count=1,
            observed_impact_count=1,
            expected_impact_digest="d" * 64,
            observed_impact_digest="d" * 64,
        ),
        observed_asset_urls=urls,
        observed_impacts=["Direct theft of user funds"],
    )


def test_github_blob_asset_key_extracts_repository_path() -> None:
    key = github_blob_asset_key(
        "https://github.com/OffchainLabs/token-bridge-contracts/blob/main/"
        "contracts/tokenbridge/arbitrum/gateway/L2GatewayRouter.sol"
    )

    assert key is not None
    assert key.repository == "OffchainLabs/token-bridge-contracts"
    assert key.path == "contracts/tokenbridge/arbitrum/gateway/L2GatewayRouter.sol"


def test_compare_target_scope_coverage_counts_exact_profile_matches() -> None:
    target = load_target("arbitrum")
    coverage = compare_target_scope_coverage(
        target,
        _attestation(
            [
                "https://github.com/OffchainLabs/token-bridge-contracts/blob/main/"
                "contracts/tokenbridge/arbitrum/gateway/L2GatewayRouter.sol",
                "https://github.com/OffchainLabs/nitro-contracts/blob/main/src/rollup/RollupCore.sol",
            ]
        ),
    )

    assert coverage.observed_asset_count == 2
    assert coverage.github_blob_asset_count == 2
    assert coverage.exact_match_count == 1
    assert coverage.repositories["OffchainLabs/token-bridge-contracts"] == (1, 43, 1)
    assert coverage.repositories["OffchainLabs/nitro-contracts"] == (1, 15, 0)


def test_scope_coverage_payload_and_markdown_include_gap_queue(tmp_path) -> None:
    target = load_target("arbitrum")
    attestation_path = tmp_path / "scope.json"
    coverage = compare_target_scope_coverage(
        target,
        _attestation(
            [
                "https://github.com/OffchainLabs/token-bridge-contracts/blob/main/"
                "contracts/tokenbridge/arbitrum/gateway/L2GatewayRouter.sol",
                "https://github.com/OffchainLabs/nitro-contracts/blob/main/src/rollup/RollupCore.sol",
            ]
        ),
    )

    payload = coverage.to_payload(target_id="arbitrum", attestation_path=attestation_path)
    markdown = render_scope_coverage_markdown(
        coverage,
        target_id="arbitrum",
        attestation_path=attestation_path,
    )

    assert payload["schema_version"] == "scope_coverage.v1"
    assert payload["summary"]["observed_not_configured_count"] == 1
    assert (
        "OffchainLabs/nitro-contracts/src/rollup/RollupCore.sol"
        in payload["observed_not_configured"]
    )
    assert "DRAFT / INTERNAL RESEARCH QUEUE" in markdown
    assert "`OffchainLabs/nitro-contracts/src/rollup/RollupCore.sol`" in markdown


def test_latest_attestation_path_ignores_coverage_artifacts(tmp_path, monkeypatch) -> None:
    scope_dir = tmp_path / "scope" / "arbitrum"
    scope_dir.mkdir(parents=True)
    (scope_dir / "coverage.json").write_text('{"schema_version":"scope_coverage.v1"}')
    attestation_path = scope_dir / "20260702T100000Z.json"
    write_model(
        attestation_path,
        _attestation(
            [
                "https://github.com/OffchainLabs/token-bridge-contracts/blob/main/"
                "contracts/tokenbridge/arbitrum/gateway/L2GatewayRouter.sol"
            ]
        ),
    )
    monkeypatch.setattr("scbounty.config.scope_coverage.artifacts_root", lambda: tmp_path)

    assert latest_attestation_path("arbitrum") == attestation_path
