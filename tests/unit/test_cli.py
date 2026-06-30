from typer.testing import CliRunner

from scbounty.cli import app

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
