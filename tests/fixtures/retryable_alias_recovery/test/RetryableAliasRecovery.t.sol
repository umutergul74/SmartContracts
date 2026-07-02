// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

import "../src/RetryableAliasRecoveryModel.sol";

interface Vm {
    function deal(address account, uint256 newBalance) external;
    function etch(address target, bytes calldata newRuntimeBytecode) external;
    function prank(address msgSender) external;
}

contract RetryableAliasRecoveryTest {
    Vm internal constant vm = Vm(address(uint160(uint256(keccak256("hevm cheat code")))));

    address internal constant DELEGATED_EOA = address(0xA11CE);
    address internal constant DELEGATE_TARGET = address(0xBEEF);
    address internal constant PLAIN_EOA = address(0xB0B);

    DelayedInboxAliasModel internal inbox;

    function setUp() public {
        inbox = new DelayedInboxAliasModel();
        vm.etch(DELEGATED_EOA, abi.encodePacked(hex"ef0100", DELEGATE_TARGET));
        vm.deal(DELEGATED_EOA, 2 ether);
        vm.deal(PLAIN_EOA, 2 ether);
    }

    function testDelegationIndicatorIsObservedAsCode() public view {
        require(DELEGATED_EOA.code.length == 23, "delegation indicator must be 23 bytes");
        require(PLAIN_EOA.code.length == 0, "negative control must remain codeless");
    }

    function testDelegatedEoaRefundAliasIsRecoverableThroughDelayedMessage() public {
        RetryableAliasModel retryable = new RetryableAliasModel(address(inbox));
        address expectedAlias = LocalAddressAliasHelper.applyL1ToL2Alias(DELEGATED_EOA);

        vm.prank(DELEGATED_EOA);
        inbox.createRetryable{value: 1 ether}(retryable, DELEGATED_EOA);

        require(retryable.beneficiary() == expectedAlias, "refund beneficiary was not aliased");

        vm.prank(DELEGATED_EOA);
        try retryable.cancelDirect() {
            revert("original L1 address unexpectedly passed the L2 beneficiary check");
        } catch {}

        vm.prank(DELEGATED_EOA);
        inbox.depositEth{value: 1 wei}();
        require(inbox.l2GasBalance(expectedAlias) == 1 wei, "alias gas deposit was not modeled");

        vm.prank(DELEGATED_EOA);
        inbox.sendContractTransaction(retryable);

        require(retryable.cancelled(), "delayed alias transaction did not cancel the ticket");
        require(retryable.refundedTo() == expectedAlias, "refund destination changed unexpectedly");
        require(retryable.escrow() == 0, "escrow was not released");
    }

    function testCodelessEoaKeepsDirectBeneficiaryControl() public {
        RetryableAliasModel retryable = new RetryableAliasModel(address(inbox));

        vm.prank(PLAIN_EOA);
        inbox.createRetryable{value: 1 ether}(retryable, PLAIN_EOA);

        require(retryable.beneficiary() == PLAIN_EOA, "codeless EOA was unexpectedly aliased");

        vm.prank(PLAIN_EOA);
        retryable.cancelDirect();

        require(retryable.cancelled(), "plain EOA could not cancel directly");
        require(retryable.refundedTo() == PLAIN_EOA, "plain EOA refund destination changed");
    }
}
