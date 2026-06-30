from __future__ import annotations

from urllib.parse import urlsplit


def github_blob_path(url: str) -> tuple[str, str, str] | None:
    """Return repository, ref, and path for a canonical GitHub blob URL."""
    parts = [part for part in urlsplit(url).path.split("/") if part]
    if len(parts) < 5 or parts[2] not in {"blob", "tree"}:
        return None
    repository = f"{parts[0]}/{parts[1]}"
    return repository, parts[3], "/".join(parts[4:])
