// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.24;

/// @notice Local semantic model only. This is not Arbitrum production code.
library LocalAddressAliasHelper {
    uint160 internal constant OFFSET = uint160(0x1111000000000000000000000000000000001111);

    function applyL1ToL2Alias(address l1Address) internal pure returns (address l2Address) {
        unchecked {
            l2Address = address(uint160(l1Address) + OFFSET);
        }
    }
}

/// @notice Models the beneficiary check performed by the ArbRetryableTx precompile.
contract RetryableAliasModel {
    address public immutable delayedExecutor;
    address public beneficiary;
    address public refundedTo;
    uint256 public escrow;
    bool public cancelled;

    constructor(address delayedExecutor_) {
        delayedExecutor = delayedExecutor_;
    }

    function create(address requestedRefundAddress) external payable {
        require(beneficiary == address(0), "ALREADY_CREATED");
        beneficiary = requestedRefundAddress.code.length > 0
            ? LocalAddressAliasHelper.applyL1ToL2Alias(requestedRefundAddress)
            : requestedRefundAddress;
        escrow = msg.value;
    }

    function cancelDirect() external {
        _cancel(msg.sender);
    }

    function cancelFromDelayedMessage(address l2Sender) external {
        require(msg.sender == delayedExecutor, "ONLY_DELAYED_EXECUTOR");
        _cancel(l2Sender);
    }

    function _cancel(address caller) internal {
        require(caller == beneficiary, "ONLY_BENEFICIARY");
        cancelled = true;
        refundedTo = beneficiary;
        escrow = 0;
    }
}

/// @notice Models Inbox aliasing and the L1 delayed contract-transaction recovery route.
contract DelayedInboxAliasModel {
    uint256 public constant DELAYED_MESSAGE_GAS_COST = 1 wei;

    mapping(address => uint256) public l2GasBalance;

    function createRetryable(
        RetryableAliasModel retryable,
        address requestedRefundAddress
    ) external payable {
        retryable.create{value: msg.value}(requestedRefundAddress);
    }

    function depositEth() external payable {
        address recipient = msg.sender.code.length > 0
            ? LocalAddressAliasHelper.applyL1ToL2Alias(msg.sender)
            : msg.sender;
        l2GasBalance[recipient] += msg.value;
    }

    function sendContractTransaction(RetryableAliasModel retryable) external {
        address l2Sender = LocalAddressAliasHelper.applyL1ToL2Alias(msg.sender);
        require(l2GasBalance[l2Sender] >= DELAYED_MESSAGE_GAS_COST, "INSUFFICIENT_L2_GAS");
        l2GasBalance[l2Sender] -= DELAYED_MESSAGE_GAS_COST;
        retryable.cancelFromDelayedMessage(l2Sender);
    }
}
