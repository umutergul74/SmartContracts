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
    deployed = {contract.name: contract for contract in target.deployed_contracts}
    assert len(deployed) == 19
    assert deployed["arb_one_bridge"].network == "ethereum_l1"
    assert deployed["arb_one_bridge"].proxy_kind == "eip1967"
    assert deployed["arb_one_l2_gateway_router"].network == "arbitrum_one"
    fast_confirmer = deployed["arb_one_rollup"].read_only_calls[0]
    assert fast_confirmer.name == "any_trust_fast_confirmer"
    assert fast_confirmer.result_type == "address"


def test_scope_snapshot_is_complete_fingerprint() -> None:
    target = load_target("arbitrum")
    snapshot = load_scope_snapshot(target)

    assert snapshot.asset_count == 181
    assert snapshot.impact_count == 13
    assert len(snapshot.asset_urls_sha256) == 64
    assert len(snapshot.impacts_sha256) == 64
