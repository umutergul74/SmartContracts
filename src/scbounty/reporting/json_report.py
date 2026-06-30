from __future__ import annotations

import orjson

from scbounty.config.models import Finding


def render_json(findings: list[Finding]) -> bytes:
    payload = {
        "schema_version": "1",
        "draft": any(not finding.shareable for finding in findings),
        "findings": [finding.model_dump(mode="json") for finding in findings],
    }
    return orjson.dumps(payload, option=orjson.OPT_INDENT_2 | orjson.OPT_SORT_KEYS) + b"\n"
