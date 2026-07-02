import re
from pathlib import Path

import yaml


def _bridge_mint_rule_patterns() -> list[str]:
    rules = yaml.safe_load(
        Path("semgrep/solidity/arbitrum-cross-chain.yml").read_text(encoding="utf-8")
    )["rules"]
    rule = next(item for item in rules if item["id"] == "scbounty.solidity.bridge-mint-entry-point")
    return [
        pattern["pattern-not-regex"]
        for pattern in rule["patterns"]
        if "pattern-not-regex" in pattern
    ]


def _initializer_rule_patterns() -> list[str]:
    rules = yaml.safe_load(Path("semgrep/solidity/upgradeability.yml").read_text(encoding="utf-8"))[
        "rules"
    ]
    rule = next(item for item in rules if item["id"] == "scbounty.solidity.initializer-review")
    return [
        pattern["pattern-not-regex"]
        for pattern in rule["patterns"]
        if "pattern-not-regex" in pattern
    ]


def test_bridge_mint_semgrep_rule_suppresses_named_gateway_modifier() -> None:
    guarded = """
    function bridgeMint(address account, uint256 amount)
        public
        onlyArbOneGateway
    {
        _mint(account, amount);
    }
    """
    unguarded = """
    function bridgeMint(address account, uint256 amount) public {
        _mint(account, amount);
    }
    """
    guard_exclusion = _bridge_mint_rule_patterns()[0]

    assert re.search(guard_exclusion, guarded)
    assert not re.search(guard_exclusion, unguarded)


def test_initializer_semgrep_rule_suppresses_read_only_and_internal_entrypoints() -> None:
    read_only = """
    function initialize(address stakeToken) external view onlyProxy {
        require(stakeToken != address(0), "NEED_STAKE_TOKEN");
    }
    """
    internal = """
    function initializeCore(bytes32 genesisHash) internal {
        latestConfirmed = genesisHash;
    }
    """
    unguarded = """
    function initialize(address owner) external {
        admin = owner;
    }
    """
    visibility_exclusion = _initializer_rule_patterns()[0]

    assert re.search(visibility_exclusion, read_only)
    assert re.search(visibility_exclusion, internal)
    assert not re.search(visibility_exclusion, unguarded)


def test_initializer_semgrep_rule_suppresses_double_logic_empty_slot_guard() -> None:
    guarded = """
    function initializeProxy(Config memory config) external {
        if (
            _getAdmin() == address(0) && _getImplementation() == address(0)
                && _getSecondaryImplementation() == address(0)
        ) {
            _initialize(config.owner);
        } else {
            _fallback();
        }
    }
    """
    unguarded = """
    function initializeProxy(Config memory config) external {
        _initialize(config.owner);
    }
    """
    empty_slot_exclusion = _initializer_rule_patterns()[-1]

    assert re.search(empty_slot_exclusion, guarded)
    assert not re.search(empty_slot_exclusion, unguarded)
