from pathlib import Path

import pytest

from scbounty.config.loader import load_target
from scbounty.detectors.arbitrum_bridge import ArbitrumBridgeDetector
from scbounty.reporting.immunefi_template import (
    ReportNotShareableError,
    render_immunefi,
)
from scbounty.reporting.json_report import render_json
from scbounty.reporting.markdown import render_markdown


def _finding():
    source = "contract T { function bridgeMint(address a, uint x) external { x; a; } }"
    return ArbitrumBridgeDetector().analyze("arbitrum", Path("T.sol"), source)[0]


def test_draft_reports_label_unvalidated_findings() -> None:
    target = load_target("arbitrum")
    finding = _finding()

    markdown = render_markdown(target, [finding])
    json_report = render_json([finding])

    assert "DRAFT / NOT A VALIDATED BOUNTY FINDING" in markdown
    assert b'"draft": true' in json_report


def test_immunefi_report_refuses_unconfirmed_finding() -> None:
    target = load_target("arbitrum")

    with pytest.raises(ReportNotShareableError):
        render_immunefi(target, [_finding()])
