import pytest
from pydantic import ValidationError

from scbounty.detectors.arbitrum_bridge import ArbitrumBridgeDetector


def _finding():
    source = """
    contract Token {
        function bridgeMint(address to, uint256 amount) external {
            balances[to] += amount;
        }
    }
    """
    return ArbitrumBridgeDetector().analyze(
        "fixture", __import__("pathlib").Path("Token.sol"), source
    )[0]


def test_automatic_finding_is_low_and_requires_review() -> None:
    finding = _finding()

    assert finding.severity == "low"
    assert finding.scope_status == "possibly_in_scope"
    assert finding.triage_status == "needs_review"
    assert finding.shareable is False


def test_high_severity_requires_confirmed_human_triage() -> None:
    finding = _finding()
    payload = finding.model_dump(mode="python")
    payload["severity"] = "high"

    with pytest.raises(ValidationError, match="confirmed human triage"):
        type(finding).model_validate(payload)
