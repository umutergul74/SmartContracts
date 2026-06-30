from __future__ import annotations

from pathlib import Path


def repository_root(start: Path | None = None) -> Path:
    current = (start or Path.cwd()).resolve()
    for candidate in (current, *current.parents):
        if (candidate / "pyproject.toml").is_file() and (candidate / "targets").is_dir():
            return candidate
    package_root = Path(__file__).resolve().parents[3]
    if (package_root / "pyproject.toml").is_file():
        return package_root
    raise RuntimeError("Unable to locate repository root")


def artifacts_root(root: Path | None = None) -> Path:
    path = (root or repository_root()) / "artifacts"
    path.mkdir(parents=True, exist_ok=True)
    return path


def cache_root(root: Path | None = None) -> Path:
    path = (root or repository_root()) / ".scbounty" / "cache"
    path.mkdir(parents=True, exist_ok=True)
    return path


def safe_child(base: Path, *parts: str) -> Path:
    root = base.resolve()
    candidate = root.joinpath(*parts).resolve()
    if not candidate.is_relative_to(root):
        raise ValueError(f"Refusing path outside {root}: {candidate}")
    return candidate
