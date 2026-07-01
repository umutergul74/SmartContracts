from scbounty.config.loader import load_scope_snapshot, load_target


def test_arbitrum_config_loads_with_required_safety_boundaries() -> None:
    target = load_target("arbitrum")

    assert target.authorization.must_reverify_before_run is True
    assert target.local_only_poc is True
    assert "mainnet_transactions" in target.prohibited_testing
    assert "public_testnet_transactions" in target.prohibited_testing
    assert target.disclosure.channel == "Immunefi submission portal"
    repositories = {repository.name: repository for repository in target.source_repositories}
    token_bridge_paths = repositories["OffchainLabs/token-bridge-contracts"].analysis_paths
    nitro_paths = repositories["OffchainLabs/nitro-contracts"].analysis_paths
    assert len(token_bridge_paths) == 43
    assert "contracts/tokenbridge/ethereum/gateway/L1ERC20Gateway.sol" in token_bridge_paths
    assert "contracts/tokenbridge/libraries/BytesParser.sol" in token_bridge_paths
    assert "contracts/tokenbridge/libraries/ClonableBeaconProxy.sol" in token_bridge_paths
    assert "src/bridge/SequencerInbox.sol" in nitro_paths
    assert "src/bridge/DelayBuffer.sol" in nitro_paths
    assert "src/libraries/MerkleLib.sol" in nitro_paths


def test_scope_snapshot_is_complete_fingerprint() -> None:
    target = load_target("arbitrum")
    snapshot = load_scope_snapshot(target)

    assert snapshot.asset_count == 181
    assert snapshot.impact_count == 13
    assert len(snapshot.asset_urls_sha256) == 64
    assert len(snapshot.impacts_sha256) == 64
