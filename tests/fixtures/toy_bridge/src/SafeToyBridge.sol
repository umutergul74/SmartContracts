// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

contract SafeToyToken {
    address public immutable gateway;
    mapping(address => uint256) public balanceOf;
    uint256 public totalSupply;

    constructor(address gateway_) {
        gateway = gateway_;
    }

    function seed(address account, uint256 amount) external {
        balanceOf[account] += amount;
        totalSupply += amount;
    }

    function bridgeMint(address account, uint256 amount) external {
        require(msg.sender == gateway, "ONLY_GATEWAY");
        balanceOf[account] += amount;
        totalSupply += amount;
    }

    function transferFrom(address from, address to, uint256 amount) external returns (bool) {
        balanceOf[from] -= amount;
        balanceOf[to] += amount;
        return true;
    }
}

contract SafeToyBridge {
    address public immutable router;
    mapping(address => address) public gateways;
    mapping(address => uint256) public escrowed;

    constructor(address router_) {
        router = router_;
    }

    function setGateway(address token, address gateway) external {
        require(msg.sender == router, "ONLY_ROUTER");
        gateways[token] = gateway;
    }

    function finalizeInboundTransfer(address token, address to, uint256 amount) external {
        require(msg.sender == router, "ONLY_ROUTER");
        SafeToyToken(token).bridgeMint(to, amount);
    }

    function deposit(address token, address representation, uint256 amount) external {
        SafeToyToken(token).transferFrom(msg.sender, address(this), amount);
        escrowed[token] += amount;
        SafeToyToken(representation).bridgeMint(msg.sender, amount);
    }
}

