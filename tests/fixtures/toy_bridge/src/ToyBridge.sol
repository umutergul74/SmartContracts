// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @notice Deliberately vulnerable educational fixture. Not Arbitrum production code.
contract ToyToken {
    mapping(address => uint256) public balanceOf;
    uint256 public totalSupply;

    function seed(address account, uint256 amount) external {
        balanceOf[account] += amount;
        totalSupply += amount;
    }

    // Deliberately unsafe: no gateway authorization.
    function bridgeMint(address account, uint256 amount) external {
        balanceOf[account] += amount;
        totalSupply += amount;
    }

    // Deliberately unsafe: no gateway authorization.
    function bridgeBurn(address account, uint256 amount) external {
        balanceOf[account] -= amount;
        totalSupply -= amount;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

/// @notice Contains four intentional bugs for detector and local-PoC tests.
contract ToyBridge {
    mapping(address => address) public gateways;
    mapping(address => uint256) public escrowed;

    // Deliberately unsafe: anyone can remap a token.
    function setGateway(address token, address gateway) external {
        gateways[token] = gateway;
    }

    // Deliberately unsafe: missing router/counterpart validation.
    function finalizeInboundTransfer(address token, address to, uint256 amount) external {
        ToyToken(token).bridgeMint(to, amount);
    }

    // Deliberately unsafe: token moves and representation mints, but escrow is not updated.
    function deposit(address token, address representation, uint256 amount) external {
        ToyToken(token).transferFrom(msg.sender, address(this), amount);
        ToyToken(representation).bridgeMint(msg.sender, amount);
    }
}

