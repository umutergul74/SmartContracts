from pathlib import Path

from scbounty.detectors.arbitrum_bridge import ArbitrumBridgeDetector
from scbounty.detectors.cross_chain_messaging import CrossChainMessagingDetector
from scbounty.detectors.gas_griefing import GasGriefingDetector
from scbounty.detectors.unsafe_erc20 import UnsafeERC20Detector
from scbounty.detectors.upgradeability import UpgradeabilityDetector


def test_upgradeability_and_gas_detectors_are_conservative() -> None:
    source = """
    contract Review {
        function initialize(address admin) external { owner = admin; }
        function process(address[] calldata users) external {
            for (uint i = 0; i < users.length; i++) { seen[users[i]] = true; }
        }
    }
    """
    path = Path("Review.sol")

    upgrade = UpgradeabilityDetector().analyze("fixture", path, source)
    gas = GasGriefingDetector().analyze("fixture", path, source)

    assert upgrade[0].severity == "low"
    assert gas[0].triage_status == "needs_review"


def test_counterpart_gateway_guard_suppresses_sender_and_mapping_findings() -> None:
    source = """
    contract L2Gateway {
        modifier onlyCounterpartGateway() { require(msg.sender == counterpart); _; }
        function finalizeInboundTransfer(
            address token,
            address from,
            address to,
            uint256 amount,
            bytes calldata data
        )
            external
            onlyCounterpartGateway
        {
            token; from; to; amount; data;
        }
        function setGateway(address[] memory tokens, address[] memory gateways)
            external
            onlyCounterpartGateway
        {
            for (uint i = 0; i < tokens.length; i++) { l1TokenToGateway[tokens[i]] = gateways[i]; }
        }
    }
    """
    path = Path("L2Gateway.sol")

    assert CrossChainMessagingDetector().analyze("fixture", path, source) == []
    assert ArbitrumBridgeDetector().analyze("fixture", path, source) == []


def test_admin_and_internal_loops_are_not_public_gas_griefing_signals() -> None:
    source = """
    contract AdminBatching {
        modifier onlyOwner() { require(msg.sender == owner, "ONLY_OWNER"); _; }

        function setWhitelist(address[] memory users, bool[] memory values) external onlyOwner {
            for (uint256 i = 0; i < users.length; i++) { allowed[users[i]] = values[i]; }
        }

        function _setGateways(address[] memory tokens, address[] memory gateways) internal {
            for (uint256 i = 0; i < tokens.length; i++) { gateway[tokens[i]] = gateways[i]; }
        }
    }
    """

    assert GasGriefingDetector().analyze("fixture", Path("AdminBatching.sol"), source) == []


def test_double_logic_proxy_admin_loops_are_not_public_gas_griefing_signals() -> None:
    source = """
    contract RollupAdminLogic is DoubleLogicUUPSUpgradeable {
        function setValidator(address[] calldata validators, bool[] calldata values) external {
            for (uint256 i = 0; i < validators.length; i++) { values[i]; }
        }

        function forceRefundStaker(address[] calldata stakers) external {
            for (uint256 i = 0; i < stakers.length; i++) { stakers[i]; }
        }

        function _authorizeUpgrade(address) internal override {}
        function _authorizeSecondaryUpgrade(address) internal override {}
    }
    """

    assert GasGriefingDetector().analyze("arbitrum", Path("RollupAdminLogic.sol"), source) == []


def test_read_only_initializer_and_role_guarded_loops_are_not_gas_griefing_signals() -> None:
    source = """
    contract GovernanceHelpers {
        modifier onlyRole(bytes32 role) { role; _; }

        function initialize(address[] memory members) external initializer {
            for (uint256 i = 0; i < members.length; i++) { seen[members[i]] = true; }
        }

        function selectTopNominees(address[] memory nominees, uint240[] memory weights)
            public
            pure
            returns (address[] memory)
        {
            for (uint256 i = 0; i < nominees.length; i++) { weights[i]; }
            return nominees;
        }

        function replaceCohort(address[] memory newCohort)
            external
            onlyRole(keccak256("COHORT_REPLACER_ROLE"))
        {
            for (uint256 i = 0; i < newCohort.length; i++) { seen[newCohort[i]] = true; }
        }
    }
    """

    assert GasGriefingDetector().analyze("fixture", Path("GovernanceHelpers.sol"), source) == []


def test_committed_recipient_hash_loop_is_not_gas_griefing_signal() -> None:
    source = """
    contract RewardDistributor {
        bytes32 public currentRecipientGroup;
        bytes32 public currentRecipientWeights;

        function distributeRewards(address[] memory recipients, uint256[] memory weights) public {
            bytes32 recipientGroup = hashAddresses(recipients);
            if (recipientGroup != currentRecipientGroup) revert InvalidRecipientGroup();
            bytes32 recipientWeights = hashWeights(weights);
            if (recipientWeights != currentRecipientWeights) revert InvalidRecipientWeights();
            for (uint256 i = 0; i < recipients.length; i++) { recipients[i].call(""); }
        }
    }
    """

    assert GasGriefingDetector().analyze("arbitrum", Path("RewardDistributor.sol"), source) == []


def test_reverting_cross_chain_router_stub_is_not_sender_validation_signal() -> None:
    source = """
    contract GatewayRouter {
        function finalizeInboundTransfer(address, address, address, uint256, bytes calldata)
            external
            payable
        {
            revert("ONLY_OUTBOUND_ROUTER");
        }
    }
    """

    assert CrossChainMessagingDetector().analyze("fixture", Path("GatewayRouter.sol"), source) == []


def test_internal_initializer_delegation_is_low_confidence_review_signal() -> None:
    source = """
    contract Gateway {
        function initialize(address counterpart, address router) external {
            CustomBase._initialize(counterpart, router);
            beacon = router;
        }
    }
    """

    findings = UpgradeabilityDetector().analyze("fixture", Path("Gateway.sol"), source)

    assert findings[0].confidence == "low"
    assert "delegates to an internal initializer" in findings[0].title


def test_known_arbitrum_guarded_initializer_delegation_is_suppressed() -> None:
    source = """
    contract L2ERC20Gateway {
        function initialize(
            address l1Counterpart,
            address router,
            address beaconProxyFactory
        ) public {
            L2ArbitrumGateway._initialize(l1Counterpart, router);
            require(beaconProxyFactory != address(0), "INVALID_BEACON");
            beacon = beaconProxyFactory;
        }
    }
    """

    assert UpgradeabilityDetector().analyze("fixture", Path("L2ERC20Gateway.sol"), source) == []


def test_read_only_and_internal_initializers_are_not_upgradeability_signals() -> None:
    source = """
    contract Rollup {
        function initialize(address stakeToken) external view onlyProxy {
            require(stakeToken != address(0), "NEED_STAKE_TOKEN");
        }

        function initializeCore(bytes32 genesisHash) internal {
            latestConfirmed = genesisHash;
        }
    }
    """

    assert UpgradeabilityDetector().analyze("arbitrum", Path("Rollup.sol"), source) == []


def test_double_logic_proxy_empty_slot_guard_suppresses_initializer_signal() -> None:
    source = """
    contract RollupProxy {
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
    }
    """

    assert UpgradeabilityDetector().analyze("arbitrum", Path("RollupProxy.sol"), source) == []


def test_known_arbitrum_guarded_token_initializer_delegation_is_suppressed() -> None:
    source = """
    contract aeWETH {
        function initialize(
            string memory name_,
            string memory symbol_,
            uint8 decimals_,
            address l2Gateway_,
            address l1Address_
        ) external {
            L2GatewayToken._initialize(name_, symbol_, decimals_, l2Gateway_, l1Address_);
        }
    }
    """

    assert UpgradeabilityDetector().analyze("fixture", Path("aeWETH.sol"), source) == []


def test_visible_custom_initializer_guard_suppresses_signal() -> None:
    source = """
    contract Gateway {
        address public counterpartGateway;
        function initialize(address counterpart) external {
            require(counterpartGateway == address(0), "ALREADY_INIT");
            counterpartGateway = counterpart;
        }
    }
    """

    assert UpgradeabilityDetector().analyze("fixture", Path("Gateway.sol"), source) == []


def test_typed_already_init_guard_suppresses_initializer_signal() -> None:
    source = """
    contract SequencerInbox {
        IBridge public bridge;
        function initialize(IBridge bridge_) external onlyDelegated {
            if (bridge != IBridge(address(0))) revert AlreadyInit();
            bridge = bridge_;
        }
    }
    """

    assert UpgradeabilityDetector().analyze("fixture", Path("SequencerInbox.sol"), source) == []


def test_reverting_bridge_token_stubs_are_not_access_control_findings() -> None:
    source = """
    contract ReverseArbToken {
        function bridgeMint(address, uint256) public {
            revert("BRIDGE_MINT_NOT_IMPLEMENTED");
        }

        function bridgeBurn(address, uint256) public {
            revert("BRIDGE_BURN_NOT_IMPLEMENTED");
        }
    }
    """

    assert ArbitrumBridgeDetector().analyze("fixture", Path("ReverseArbToken.sol"), source) == []


def test_named_gateway_modifier_suppresses_bridge_access_control_signal() -> None:
    source = """
    contract L1ArbitrumToken {
        modifier onlyArbOneGateway() { _; }

        function bridgeMint(address account, uint256 amount)
            public
            onlyArbOneGateway
        {
            _mint(account, amount);
        }

        function _mint(address account, uint256 amount) internal {}
    }
    """

    assert ArbitrumBridgeDetector().analyze("arbitrum", Path("L1ArbitrumToken.sol"), source) == []


def test_ignored_optional_metadata_staticcall_status_is_detected() -> None:
    source = """
    contract L1ERC20Gateway {
        function callStatic(address targetContract, bytes4 targetFunction)
            internal
            view
            returns (bytes memory)
        {
            (, /* bool success */ bytes memory res) =
                targetContract.staticcall(abi.encodeWithSelector(targetFunction));
            return res;
        }

        function getOutboundCalldata(address token) external view returns (bytes memory) {
            return abi.encode(
                callStatic(token, ERC20.name.selector),
                callStatic(token, ERC20.symbol.selector)
            );
        }
    }
    """

    findings = UnsafeERC20Detector().analyze(
        "arbitrum",
        Path(
            "OffchainLabs/token-bridge-contracts/contracts/tokenbridge/ethereum/gateway/"
            "L1ERC20Gateway.sol"
        ),
        source,
    )

    assert len(findings) == 1
    assert findings[0].category == "optional_metadata_revert_lock"
    assert findings[0].confidence == "high"


def test_checked_optional_metadata_staticcall_status_is_suppressed() -> None:
    source = """
    contract L1ERC20Gateway {
        function callStatic(address targetContract, bytes4 targetFunction)
            internal
            view
            returns (bytes memory)
        {
            (bool success, bytes memory res) =
                targetContract.staticcall(abi.encodeWithSelector(targetFunction));
            if (!success) return "";
            return res;
        }

        function getOutboundCalldata(address token) external view returns (bytes memory) {
            return abi.encode(
                callStatic(token, ERC20.name.selector),
                callStatic(token, ERC20.symbol.selector)
            );
        }
    }
    """

    assert (
        UnsafeERC20Detector().analyze(
            "arbitrum",
            Path(
                "OffchainLabs/token-bridge-contracts/contracts/tokenbridge/ethereum/gateway/"
                "L1ERC20Gateway.sol"
            ),
            source,
        )
        == []
    )
