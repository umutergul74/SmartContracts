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
