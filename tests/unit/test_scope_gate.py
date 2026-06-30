from datetime import UTC, datetime

from scbounty.config.models import ScopeSnapshot
from scbounty.config.scope_gate import (
    KNOWN_ARBITRUM_IMPACTS,
    compare_live_scope,
)
from scbounty.utils.hashing import sha256_text


def _page_and_snapshot() -> tuple[str, ScopeSnapshot]:
    assets = sorted(
        [
            "https://github.com/OffchainLabs/token-bridge-contracts/blob/main/A.sol",
            "https://github.com/OffchainLabs/nitro-contracts/blob/main/B.sol",
        ]
    )
    impacts = sorted(f"{severity}|{title}" for severity, title in KNOWN_ARBITRUM_IMPACTS)
    markers = [
        "Any testing on mainnet or public testnet deployed code",
        "all testing should be done on local-forks",
        "Public disclosure of an unpatched vulnerability",
    ]
    page = "<script>" + "\n".join(
        [*assets, *(title for _, title in KNOWN_ARBITRUM_IMPACTS), *markers]
    )
    snapshot = ScopeSnapshot(
        target_id="test",
        captured_at_utc=datetime.now(UTC),
        source_url="https://example.test/scope",
        program_last_updated="today",
        asset_count=2,
        asset_urls_sha256=sha256_text("\n".join(assets)),
        impact_count=len(impacts),
        impacts_sha256=sha256_text("\n".join(impacts)),
        seed_assets=["A.sol", "B.sol"],
        repositories=[
            "https://github.com/OffchainLabs/token-bridge-contracts",
            "https://github.com/OffchainLabs/nitro-contracts",
        ],
        prohibited_activity_markers=markers,
    )
    return page, snapshot


def test_scope_comparison_passes_only_for_exact_reviewed_fingerprint() -> None:
    page, snapshot = _page_and_snapshot()

    diff = compare_live_scope(page, snapshot)

    assert diff.passed is True
    assert diff.observed_asset_count == 2
    assert diff.observed_impact_count == 13


def test_scope_comparison_fails_when_safety_marker_disappears() -> None:
    page, snapshot = _page_and_snapshot()

    diff = compare_live_scope(
        page.replace("all testing should be done on local-forks", ""),
        snapshot,
    )

    assert diff.passed is False
    assert diff.missing_safety_markers == ["all testing should be done on local-forks"]


def test_scope_comparison_counts_duplicate_rows() -> None:
    page, snapshot = _page_and_snapshot()

    diff = compare_live_scope(
        page.replace("</script>", "")
        + "\nhttps://github.com/OffchainLabs/token-bridge-contracts/blob/main/A.sol",
        snapshot,
    )

    assert diff.passed is False
    assert diff.observed_asset_count == 3
