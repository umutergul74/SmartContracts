from pathlib import Path

from scbounty.detectors import (
    AccountingDetector,
    ArbitrumBridgeDetector,
    CrossChainMessagingDetector,
)

FIXTURE = Path("tests/fixtures/toy_bridge/src")


def test_vulnerable_fixture_produces_expected_bridge_signals() -> None:
    source = (FIXTURE / "ToyBridge.sol").read_text(encoding="utf-8")
    path = Path("toy/ToyBridge.sol")

    bridge = ArbitrumBridgeDetector().analyze("fixture", path, source)
    messaging = CrossChainMessagingDetector().analyze("fixture", path, source)
    accounting = AccountingDetector().analyze("fixture", path, source)

    assert {finding.affected_functions[0] for finding in bridge} == {
        "bridgeMint",
        "bridgeBurn",
        "setGateway",
    }
    assert [finding.affected_functions[0] for finding in messaging] == ["finalizeInboundTransfer"]
    assert [finding.affected_functions[0] for finding in accounting] == ["deposit"]


def test_safe_control_suppresses_same_signals() -> None:
    source = (FIXTURE / "SafeToyBridge.sol").read_text(encoding="utf-8")
    path = Path("toy/SafeToyBridge.sol")

    assert ArbitrumBridgeDetector().analyze("fixture", path, source) == []
    assert CrossChainMessagingDetector().analyze("fixture", path, source) == []
    assert AccountingDetector().analyze("fixture", path, source) == []
