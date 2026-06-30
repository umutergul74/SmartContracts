from __future__ import annotations

import hashlib
from collections.abc import Iterable
from pathlib import Path

import orjson


def sha256_bytes(value: bytes) -> str:
    return hashlib.sha256(value).hexdigest()


def sha256_text(value: str) -> str:
    return sha256_bytes(value.encode("utf-8"))


def stable_json_hash(value: object) -> str:
    return sha256_bytes(orjson.dumps(value, option=orjson.OPT_SORT_KEYS))


def hash_paths(root: Path, paths: Iterable[str]) -> str:
    digest = hashlib.sha256()
    for relative in sorted(set(paths)):
        candidate = (root / relative).resolve()
        if not candidate.is_file() or not candidate.is_relative_to(root.resolve()):
            continue
        digest.update(relative.replace("\\", "/").encode())
        digest.update(b"\0")
        digest.update(candidate.read_bytes())
        digest.update(b"\0")
    return digest.hexdigest()
