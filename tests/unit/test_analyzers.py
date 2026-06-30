from pathlib import Path

from scbounty.analyzers.aderyn import AderynAdapter
from scbounty.analyzers.foundry import FoundryAdapter
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
    monkeypatch.setattr(
        "scbounty.analyzers.slither.run_command",
        lambda *args, **kwargs: ToolExecution(
            tool="slither",
            available=True,
            exit_code=255,
            stdout='{"success": true, "results": {}}',
        ),
    )

    result = adapter.run(load_target("arbitrum"), Path.cwd())

    assert result.status == "completed"
