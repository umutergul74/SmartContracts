from pathlib import Path

from scbounty.detectors.gas_griefing import GasGriefingDetector
from scbounty.detectors.upgradeability import UpgradeabilityDetector


def test_upgradeability_and_gas_detectors_are_conservative() -> None:
    source = """
    contract Review {
        function initialize(address admin) external { owner = admin; }
        function process(address[] calldata users) external {
            for (uint i = 0; i < users.length; i++) { seen[users[i]] = true; }
        }
    }
    """
    path = Path("Review.sol")

    upgrade = UpgradeabilityDetector().analyze("fixture", path, source)
    gas = GasGriefingDetector().analyze("fixture", path, source)

    assert upgrade[0].severity == "low"
    assert gas[0].triage_status == "needs_review"
