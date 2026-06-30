import os

import pytest

from scbounty.config.loader import load_target
from scbounty.config.scope_gate import ScopeGate


@pytest.mark.integration
@pytest.mark.skipif(
    os.getenv("SCBOUNTY_LIVE_SCOPE") != "1",
    reason="live scope test is opt-in to avoid routine third-party traffic",
)
def test_live_arbitrum_scope_matches_reviewed_snapshot() -> None:
    attestation = ScopeGate().verify(load_target("arbitrum"))

    assert attestation.diff.passed is True
    assert attestation.diff.observed_asset_count == 181
