from __future__ import annotations

from collections import defaultdict
from dataclasses import dataclass
from pathlib import Path
from typing import Any
from urllib.parse import urlsplit

from pydantic import ValidationError

from scbounty.config.models import ScopeAttestation, TargetConfig
from scbounty.utils.paths import artifacts_root, safe_child


@dataclass(frozen=True)
class ScopeAssetKey:
    repository: str
    path: str

    def as_string(self) -> str:
        return f"{self.repository}/{self.path}"


@dataclass(frozen=True)
class ScopeCoverage:
    observed_asset_count: int
    github_blob_asset_count: int
    configured_path_count: int
    exact_match_count: int
    observed_not_configured: list[ScopeAssetKey]
    configured_not_observed: list[ScopeAssetKey]
    repositories: dict[str, tuple[int, int, int]]

    def to_payload(self, *, target_id: str, attestation_path: Path) -> dict[str, Any]:
        return {
            "schema_version": "scope_coverage.v1",
            "target_id": target_id,
            "attestation_path": str(attestation_path),
            "summary": {
                "observed_asset_count": self.observed_asset_count,
                "github_blob_asset_count": self.github_blob_asset_count,
                "configured_path_count": self.configured_path_count,
                "exact_match_count": self.exact_match_count,
                "observed_not_configured_count": len(self.observed_not_configured),
                "configured_not_observed_count": len(self.configured_not_observed),
            },
            "repositories": [
                {
                    "repository": repository,
                    "live_assets": counts[0],
                    "configured_paths": counts[1],
                    "exact_matches": counts[2],
                }
                for repository, counts in self.repositories.items()
            ],
            "observed_not_configured": [key.as_string() for key in self.observed_not_configured],
            "configured_not_observed": [key.as_string() for key in self.configured_not_observed],
        }


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
    for candidate in reversed(candidates):
        try:
            ScopeAttestation.model_validate_json(candidate.read_bytes())
        except (OSError, ValidationError, ValueError):
            continue
        return candidate
    raise FileNotFoundError(
        f"No scope attestation found for {target_id}; run `scbounty scope check {target_id}` first."
    )


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


def render_scope_coverage_markdown(
    coverage: ScopeCoverage,
    *,
    target_id: str,
    attestation_path: Path,
) -> str:
    lines = [
        f"# Scope coverage for `{target_id}`",
        "",
        "> DRAFT / INTERNAL RESEARCH QUEUE. This is not a vulnerability finding.",
        "",
        f"- Attestation: `{attestation_path}`",
        f"- Total observed scope assets: {coverage.observed_asset_count}",
        f"- GitHub blob assets: {coverage.github_blob_asset_count}",
        f"- Configured analysis paths: {coverage.configured_path_count}",
        f"- Exact live-scope/profile matches: {coverage.exact_match_count}",
        f"- Live assets outside this profile: {len(coverage.observed_not_configured)}",
        f"- Configured paths not observed in live scope: {len(coverage.configured_not_observed)}",
        "",
        "## Repository coverage",
        "",
        "| Repository | Live assets | Configured paths | Exact matches |",
        "| --- | ---: | ---: | ---: |",
    ]
    for repository, counts in coverage.repositories.items():
        observed_count, configured_count, exact_count = counts
        lines.append(f"| `{repository}` | {observed_count} | {configured_count} | {exact_count} |")

    if coverage.observed_not_configured:
        lines.extend(["", "## Live assets outside this analysis profile", ""])
        lines.extend(f"- `{key.as_string()}`" for key in coverage.observed_not_configured)

    if coverage.configured_not_observed:
        lines.extend(["", "## Configured paths not observed in live scope", ""])
        lines.extend(f"- `{key.as_string()}`" for key in coverage.configured_not_observed)

    lines.append("")
    return "\n".join(lines)
