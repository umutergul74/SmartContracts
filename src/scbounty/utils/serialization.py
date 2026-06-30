from __future__ import annotations

from collections.abc import Sequence
from pathlib import Path

import orjson
from pydantic import BaseModel


def write_model(path: Path, model: BaseModel) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(
        orjson.dumps(
            model.model_dump(mode="json"),
            option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS,
        )
        + b"\n"
    )


def write_models(path: Path, models: Sequence[BaseModel]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    payload = [model.model_dump(mode="json") for model in models]
    path.write_bytes(
        orjson.dumps(payload, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS) + b"\n"
    )
