from __future__ import annotations

from pathlib import Path

from scbounty.config.loader import load_target
from scbounty.config.models import TargetConfig
from scbounty.utils.paths import repository_root


def list_target_ids(root: Path | None = None) -> list[str]:
    base = (root or repository_root()) / "targets"
    return sorted(
        path.name
        for path in base.iterdir()
        if path.is_dir() and (path / f"{path.name}.yaml").is_file()
    )


def get_target(target_id: str, root: Path | None = None) -> TargetConfig:
    return load_target(target_id, root)
