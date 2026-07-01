from datetime import UTC, datetime
from pathlib import Path

from scbounty.analyzers.aderyn import AderynAdapter
from scbounty.analyzers.foundry import FoundryAdapter
from scbounty.analyzers.runner import _create_run_directory
from scbounty.analyzers.slither import SlitherAdapter
from scbounty.config.loader import load_target
from scbounty.config.models import ToolExecution


def test_missing_optional_adapter_returns_structured_skip(monkeypatch) -> None:
    adapter = AderynAdapter()
    monkeypatch.setattr(adapter, "is_available", lambda: False)

    result = adapter.run(load_target("arbitrum"), Path.cwd())

    assert result.status == "skipped"
    assert result.execution.available is False
    assert "degraded mode" in result.warnings[0]


def test_detected_campaign_stub_is_explicitly_skipped(monkeypatch) -> None:
    adapter = AderynAdapter()
    monkeypatch.setattr(adapter, "is_available", lambda: True)
    monkeypatch.setattr(adapter, "version", lambda: "1.0")

    result = adapter.run(load_target("arbitrum"), Path.cwd())

    assert result.status == "skipped"
    assert result.execution.available is True
    assert "not enabled" in result.warnings[0]


def test_foundry_adapter_records_success(monkeypatch) -> None:
    adapter = FoundryAdapter()
    monkeypatch.setattr(adapter, "is_available", lambda: True)
    monkeypatch.setattr(adapter, "version", lambda: "forge 1")
    monkeypatch.setattr(
        "scbounty.analyzers.foundry.run_command",
        lambda *args, **kwargs: ToolExecution(
            tool="foundry",
            available=True,
            exit_code=0,
        ),
    )

    result = adapter.run(load_target("arbitrum"), Path.cwd())

    assert result.status == "completed"
    assert result.execution.version == "forge 1"


def test_slither_json_is_preserved_even_with_detector_exit_code(monkeypatch) -> None:
    adapter = SlitherAdapter()
    monkeypatch.setattr(adapter, "is_available", lambda: True)
    monkeypatch.setattr(adapter, "version", lambda: "slither 1")
    captured: dict[str, object] = {}

    def fake_run_command(*args, **kwargs):
        captured["args"] = args
        captured["kwargs"] = kwargs
        return ToolExecution(
            tool="slither",
            available=True,
            exit_code=255,
            stdout='{"success": true, "results": {}}',
        )

    monkeypatch.setattr(
        "scbounty.analyzers.slither.run_command",
        fake_run_command,
    )

    result = adapter.run(
        load_target("arbitrum"),
        Path.cwd(),
        ["contracts/A.sol", "contracts/nested/B.sol", "README.md"],
    )

    assert result.status == "completed"
    command = captured["args"][1]  # type: ignore[index]
    assert "--include-paths" in command
    include_filter = command[command.index("--include-paths") + 1]
    assert "contracts/A\\.sol" in include_filter
    assert "contracts/nested/B\\.sol" in include_filter
    assert "README" not in include_filter
    extra_env = captured["kwargs"]["extra_env"]  # type: ignore[index]
    assert extra_env["GIT_CONFIG_KEY_0"] == "safe.directory"  # type: ignore[index]


def test_run_directory_allocation_tolerates_same_timestamp(tmp_path: Path) -> None:
    started = datetime(2026, 7, 1, 8, 0, 28, 123456, tzinfo=UTC)

    first_id, first_dir = _create_run_directory("arbitrum", started, "abcdef012345", tmp_path)
    second_id, second_dir = _create_run_directory("arbitrum", started, "abcdef012345", tmp_path)

    assert first_id != second_id
    assert first_dir.is_dir()
    assert second_dir.is_dir()
