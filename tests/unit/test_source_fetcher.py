from pathlib import Path

import pytest

from scbounty.config.loader import load_target
from scbounty.config.models import ToolExecution
from scbounty.source.fetcher import SourceFetcher, SourceFetchError


def test_source_fetcher_records_pinned_selected_content(tmp_path: Path, monkeypatch) -> None:
    target = load_target("arbitrum")
    target.source_repositories = target.source_repositories[:1]
    repository = target.source_repositories[0]
    repository.analysis_paths = ["contracts/A.sol"]
    checkout = (
        tmp_path
        / ".scbounty"
        / "cache"
        / "sources"
        / "arbitrum"
        / "OffchainLabs-token-bridge-contracts"
    )
    (checkout / ".git").mkdir(parents=True)
    source = checkout / "contracts" / "A.sol"
    source.parent.mkdir(parents=True)
    source.write_text("contract A {}", encoding="utf-8")
    calls = iter(
        [
            ToolExecution(tool="git", available=True, exit_code=0),
            ToolExecution(tool="git", available=True, exit_code=0),
            ToolExecution(tool="git", available=True, exit_code=0, stdout="a" * 40),
        ]
    )
    commands: list[list[str]] = []

    def fake_run_command(*args, **kwargs):
        commands.append(args[1])
        return next(calls)

    monkeypatch.setattr(
        "scbounty.source.fetcher.run_command",
        fake_run_command,
    )

    manifest = SourceFetcher().fetch(target, root=tmp_path)

    assert manifest.artifacts[0].commit_sha == "a" * 40
    assert manifest.artifacts[0].selected_paths == ["contracts/A.sol"]
    assert len(manifest.artifacts[0].selected_content_hash) == 64
    assert all("-c" in command for command in commands)
    assert all(any(part.startswith("safe.directory=") for part in command) for command in commands)


def test_source_fetcher_records_local_fixture_without_git_clone() -> None:
    target = load_target("toy_bridge")

    manifest = SourceFetcher().fetch(target)

    artifact = manifest.artifacts[0]
    assert manifest.target_id == "toy_bridge"
    assert artifact.repository == "scbounty/toy_bridge_fixture"
    assert artifact.commit_sha.startswith("local-fixture-")
    assert artifact.selected_paths == ["src/ToyBridge.sol", "src/SafeToyBridge.sol"]
    assert len(artifact.selected_content_hash) == 64


def test_source_fetcher_rejects_partially_missing_reviewed_scope(
    tmp_path: Path, monkeypatch
) -> None:
    target = load_target("arbitrum")
    target.source_repositories = target.source_repositories[:1]
    repository = target.source_repositories[0]
    repository.analysis_paths = ["contracts/A.sol", "contracts/Missing.sol"]
    checkout = (
        tmp_path
        / ".scbounty"
        / "cache"
        / "sources"
        / "arbitrum"
        / "OffchainLabs-token-bridge-contracts"
    )
    (checkout / ".git").mkdir(parents=True)
    source = checkout / "contracts" / "A.sol"
    source.parent.mkdir(parents=True)
    source.write_text("contract A {}", encoding="utf-8")
    calls = iter(
        [
            ToolExecution(tool="git", available=True, exit_code=0),
            ToolExecution(tool="git", available=True, exit_code=0),
            ToolExecution(tool="git", available=True, exit_code=0, stdout="b" * 40),
        ]
    )
    monkeypatch.setattr(
        "scbounty.source.fetcher.run_command",
        lambda *args, **kwargs: next(calls),
    )

    with pytest.raises(SourceFetchError, match="contracts/Missing.sol"):
        SourceFetcher().fetch(target, root=tmp_path)
