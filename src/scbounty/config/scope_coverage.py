from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from urllib.parse import urlsplit

from scbounty.config.models import ScopeAttestation, TargetConfig
from scbounty.utils.paths import artifacts_root, safe_child


@dataclass(frozen=True)
class ScopeAssetKey:
    repository: str
    path: str


@dataclass(frozen=True)
class ScopeCoverage:
    observed_asset_count: int
    github_blob_asset_count: int
    configured_path_count: int
    exact_match_count: int
    observed_not_configured: list[ScopeAssetKey]
    configured_not_observed: list[ScopeAssetKey]
    repositories: dict[str, tuple[int, int, int]]


def github_blob_asset_key(url: str) -> ScopeAssetKey | None:
    parsed = urlsplit(url)
    if parsed.netloc.lower() != "github.com":
        return None
    parts = [part for part in parsed.path.split("/") if part]
    if len(parts) < 5 or parts[2] != "blob":
        return None
    repository = f"{parts[0]}/{parts[1]}"
    return ScopeAssetKey(repository=repository, path="/".join(parts[4:]))


def latest_attestation_path(target_id: str) -> Path:
    scope_dir = safe_child(artifacts_root(), "scope", target_id)
    candidates = sorted(scope_dir.glob("*.json"))
    if not candidates:
        raise FileNotFoundError(
            f"No scope attestation found for {target_id}; "
            f"run `scbounty scope check {target_id}` first."
        )
    return candidates[-1]


def load_scope_attestation(path: Path) -> ScopeAttestation:
    return ScopeAttestation.model_validate_json(path.read_bytes())


def compare_target_scope_coverage(
    target: TargetConfig,
    attestation: ScopeAttestation,
) -> ScopeCoverage:
    observed = {
        key
        for url in attestation.observed_asset_urls
        if (key := github_blob_asset_key(str(url))) is not None
    }
    configured = {
        ScopeAssetKey(repository=repository.name, path=path)
        for repository in target.source_repositories
        for path in repository.analysis_paths
    }
    exact_matches = observed.intersection(configured)

    repositories: dict[str, list[int]] = defaultdict(lambda: [0, 0, 0])
    for key in observed:
        repositories[key.repository][0] += 1
    for key in configured:
        repositories[key.repository][1] += 1
    for key in exact_matches:
        repositories[key.repository][2] += 1

    return ScopeCoverage(
        observed_asset_count=len(attestation.observed_asset_urls),
        github_blob_asset_count=len(observed),
        configured_path_count=len(configured),
        exact_match_count=len(exact_matches),
        observed_not_configured=sorted(
            observed.difference(configured), key=lambda item: (item.repository, item.path)
        ),
        configured_not_observed=sorted(
            configured.difference(observed), key=lambda item: (item.repository, item.path)
        ),
        repositories={
            repository: (counts[0], counts[1], counts[2])
            for repository, counts in sorted(repositories.items())
        },
    )
