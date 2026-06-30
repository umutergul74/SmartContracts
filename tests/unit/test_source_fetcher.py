from pathlib import Path

from scbounty.config.loader import load_target
from scbounty.config.models import ToolExecution
from scbounty.source.fetcher import SourceFetcher


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
    monkeypatch.setattr(
        "scbounty.source.fetcher.run_command",
        lambda *args, **kwargs: next(calls),
    )

    manifest = SourceFetcher().fetch(target, root=tmp_path)

    assert manifest.artifacts[0].commit_sha == "a" * 40
    assert manifest.artifacts[0].selected_paths == ["contracts/A.sol"]
    assert len(manifest.artifacts[0].selected_content_hash) == 64
