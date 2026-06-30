from __future__ import annotations

import re
from datetime import UTC, datetime
from pathlib import Path

from scbounty.config.models import SourceArtifact, SourceManifest, TargetConfig
from scbounty.utils.command import run_command
from scbounty.utils.hashing import hash_paths
from scbounty.utils.paths import cache_root, repository_root, safe_child
from scbounty.utils.serialization import write_model


class SourceFetchError(RuntimeError):
    """Raised when a configured source cannot be pinned safely."""


def _directory_name(repository_name: str) -> str:
    return re.sub(r"[^A-Za-z0-9_.-]", "-", repository_name)


def _git_in_checkout(checkout: Path, *args: str) -> list[str]:
    return [
        "git",
        "-c",
        f"safe.directory={checkout.resolve().as_posix()}",
        "-C",
        str(checkout),
        *args,
    ]


class SourceFetcher:
    def fetch(
        self,
        target: TargetConfig,
        *,
        root: Path | None = None,
        output_path: Path | None = None,
    ) -> SourceManifest:
        base = safe_child(cache_root(root), "sources", target.target_id)
        base.mkdir(parents=True, exist_ok=True)
        artifacts: list[SourceArtifact] = []
        for repository in target.source_repositories:
            if repository.local_path is not None:
                checkout = safe_child(repository_root(root), *Path(repository.local_path).parts)
                if not checkout.is_dir():
                    raise SourceFetchError(
                        f"Local fixture source does not exist for {repository.name}: {checkout}"
                    )
                selected = [
                    path for path in repository.analysis_paths if (checkout / path).is_file()
                ]
                if not selected:
                    raise SourceFetchError(
                        f"None of the reviewed local analysis paths exist in {repository.name}"
                    )
                content_hash = hash_paths(checkout, selected)
                artifacts.append(
                    SourceArtifact(
                        repository=repository.name,
                        url=repository.url,
                        commit_sha=f"local-fixture-{content_hash[:16]}",
                        checkout_path=str(checkout),
                        selected_paths=selected,
                        selected_content_hash=content_hash,
                    )
                )
                continue
            checkout = safe_child(base, _directory_name(repository.name))
            url = str(repository.url)
            if not (checkout / ".git").is_dir():
                checkout.parent.mkdir(parents=True, exist_ok=True)
                execution = run_command(
                    "git",
                    [
                        "git",
                        "clone",
                        "--depth",
                        "1",
                        "--filter=blob:none",
                        "--branch",
                        repository.default_branch,
                        url,
                        str(checkout),
                    ],
                    cwd=checkout.parent,
                    timeout_seconds=300,
                )
            else:
                execution = run_command(
                    "git",
                    _git_in_checkout(
                        checkout,
                        "fetch",
                        "--depth",
                        "1",
                        "origin",
                        repository.default_branch,
                    ),
                    cwd=base,
                    timeout_seconds=300,
                )
                if execution.exit_code == 0:
                    execution = run_command(
                        "git",
                        _git_in_checkout(checkout, "checkout", "--detach", "FETCH_HEAD"),
                        cwd=base,
                    )
            if execution.exit_code != 0:
                raise SourceFetchError(
                    f"Failed to acquire {repository.name}: {execution.stderr or execution.stdout}"
                )
            revision = run_command(
                "git",
                _git_in_checkout(checkout, "rev-parse", "HEAD"),
                cwd=base,
            )
            if revision.exit_code != 0:
                raise SourceFetchError(f"Could not pin commit for {repository.name}")
            commit = revision.stdout.strip()
            selected = [path for path in repository.analysis_paths if (checkout / path).is_file()]
            if not selected:
                raise SourceFetchError(
                    f"None of the reviewed analysis paths exist in {repository.name} at {commit}"
                )
            artifacts.append(
                SourceArtifact(
                    repository=repository.name,
                    url=repository.url,
                    commit_sha=commit,
                    checkout_path=str(checkout),
                    selected_paths=selected,
                    selected_content_hash=hash_paths(checkout, selected),
                )
            )
        manifest = SourceManifest(
            target_id=target.target_id,
            created_at_utc=datetime.now(UTC),
            artifacts=artifacts,
        )
        if output_path is not None:
            write_model(output_path, manifest)
        return manifest
