from datetime import UTC, datetime

from typer.testing import CliRunner

from scbounty.cli import app
from scbounty.config.models import ScopeAttestation, ScopeDiff
from scbounty.utils.serialization import write_model

runner = CliRunner()


def test_targets_list_smoke() -> None:
    result = runner.invoke(app, ["targets", "list"])

    assert result.exit_code == 0
    assert "arbitrum" in result.stdout


def test_env_doctor_never_prints_secret_values(monkeypatch) -> None:
    monkeypatch.setenv("ARBITRUM_ONE_RPC_URL", "https://token@example.test")

    result = runner.invoke(app, ["env", "doctor"])

    assert result.exit_code == 0
    assert "https://token@example.test" not in result.stdout
    assert "Private keys are neither required nor loaded." in result.stdout


def test_test_command_requires_local_only_flag() -> None:
    result = runner.invoke(app, ["test", "arbitrum", "--kind", "invariant"])

    assert result.exit_code == 2
    assert "Tests require --local-only" in result.stdout


def test_scope_coverage_uses_attestation_file(tmp_path) -> None:
    attestation_path = tmp_path / "scope.json"
    write_model(
        attestation_path,
        ScopeAttestation(
            attestation_id="scope-test",
            target_id="arbitrum",
            verified_at_utc=datetime.now(UTC),
            scope_url="https://immunefi.com/bug-bounty/arbitrum/scope/",
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
            observed_asset_urls=[
                "https://github.com/OffchainLabs/token-bridge-contracts/blob/main/"
                "contracts/tokenbridge/arbitrum/gateway/L2GatewayRouter.sol"
            ],
            observed_impacts=["Direct theft of user funds"],
        ),
    )

    result = runner.invoke(
        app,
        ["scope", "coverage", "arbitrum", "--attestation", str(attestation_path)],
    )

    assert result.exit_code == 0
    assert "GitHub blob assets" in result.stdout
    assert "1/1 GitHub blob assets" in result.stdout
