from __future__ import annotations

from pathlib import Path

import yaml

from scbounty.config.models import ScopeSnapshot, TargetConfig
from scbounty.utils.paths import repository_root


class ConfigError(RuntimeError):
    """Raised when a committed target configuration cannot be loaded."""


def target_config_path(target_id: str, root: Path | None = None) -> Path:
    base = root or repository_root()
    return base / "targets" / target_id / f"{target_id}.yaml"


def load_target(target_id: str, root: Path | None = None) -> TargetConfig:
    path = target_config_path(target_id, root)
    if not path.is_file():
        raise ConfigError(f"Unknown target '{target_id}': {path} does not exist")
    try:
        raw = yaml.safe_load(path.read_text(encoding="utf-8"))
        return TargetConfig.model_validate(raw)
    except Exception as exc:
        raise ConfigError(f"Invalid target configuration at {path}: {exc}") from exc


def load_scope_snapshot(target: TargetConfig, root: Path | None = None) -> ScopeSnapshot:
    base = root or repository_root()
    path = base / "targets" / target.target_id / target.scope_snapshot_file
    if not path.is_file():
        raise ConfigError(f"Scope snapshot is missing: {path}")
    try:
        return ScopeSnapshot.model_validate_json(path.read_bytes())
    except Exception as exc:
        raise ConfigError(f"Invalid scope snapshot at {path}: {exc}") from exc
