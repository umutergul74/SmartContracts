from scbounty.config.loader import load_scope_snapshot, load_target


def test_arbitrum_config_loads_with_required_safety_boundaries() -> None:
    target = load_target("arbitrum")

    assert target.authorization.must_reverify_before_run is True
    assert target.local_only_poc is True
    assert "mainnet_transactions" in target.prohibited_testing
    assert "public_testnet_transactions" in target.prohibited_testing
    assert target.disclosure.channel == "Immunefi submission portal"


def test_scope_snapshot_is_complete_fingerprint() -> None:
    target = load_target("arbitrum")
    snapshot = load_scope_snapshot(target)

    assert snapshot.asset_count == 181
    assert snapshot.impact_count == 13
    assert len(snapshot.asset_urls_sha256) == 64
    assert len(snapshot.impacts_sha256) == 64
