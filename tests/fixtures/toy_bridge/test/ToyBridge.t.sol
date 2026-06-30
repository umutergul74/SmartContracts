// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import "../src/ToyBridge.sol";
import "../src/SafeToyBridge.sol";

contract ToyBridgeLocalReproductionTest {
    function testUnauthorizedMintIsLocallyReproducible() public {
        ToyToken token = new ToyToken();
        token.bridgeMint(address(this), 10 ether);
        require(token.balanceOf(address(this)) == 10 ether, "unsafe mint was not reproduced");
    }

    function testMissingRouterCheckIsLocallyReproducible() public {
        ToyToken representation = new ToyToken();
        ToyBridge bridge = new ToyBridge();
        bridge.finalizeInboundTransfer(address(representation), address(this), 5 ether);
        require(representation.balanceOf(address(this)) == 5 ether, "missing router check not shown");
    }

    function testGatewayCanBeRemappedByAnyone() public {
        ToyBridge bridge = new ToyBridge();
        bridge.setGateway(address(1), address(2));
        require(bridge.gateways(address(1)) == address(2), "unsafe remap not shown");
    }

    function testAccountingMismatchIsLocallyReproducible() public {
        ToyToken canonical = new ToyToken();
        ToyToken representation = new ToyToken();
        ToyBridge bridge = new ToyBridge();
        canonical.seed(address(this), 7 ether);
        bridge.deposit(address(canonical), address(representation), 7 ether);
        require(bridge.escrowed(address(canonical)) == 0, "fixture unexpectedly tracked escrow");
        require(representation.totalSupply() == 7 ether, "representation was not minted");
    }
}

contract SafeToyBridgeInvariantTest {
    SafeToyBridge internal bridge;
    SafeToyToken internal canonical;
    SafeToyToken internal representation;

    function setUp() public {
        bridge = new SafeToyBridge(address(this));
        canonical = new SafeToyToken(address(bridge));
        representation = new SafeToyToken(address(bridge));
        canonical.seed(address(this), type(uint128).max);
    }

    function targetContracts() public view returns (address[] memory targets) {
        targets = new address[](1);
        targets[0] = address(bridge);
    }

    function testFuzz_EscrowCoversRepresentation(uint96 rawAmount) public {
        uint256 amount = uint256(rawAmount) + 1;
        bridge.deposit(address(canonical), address(representation), amount);
        require(
            bridge.escrowed(address(canonical)) == representation.totalSupply(),
            "safe fixture accounting invariant failed"
        );
    }

    function invariant_EscrowNeverFallsBelowRepresentationSupply() public view {
        require(
            bridge.escrowed(address(canonical)) >= representation.totalSupply(),
            "escrow coverage invariant failed"
        );
    }
}
