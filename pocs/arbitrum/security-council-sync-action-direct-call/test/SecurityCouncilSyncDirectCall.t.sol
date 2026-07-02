// SPDX-License-Identifier: Apache-2.0
pragma solidity ^0.8.20;

contract KeyValueStore {
    mapping(uint256 => uint256) public store;

    function set(uint256 key, uint256 value) external {
        store[computeKey(msg.sender, key)] = value;
    }

    function get(address owner, uint256 key) external view returns (uint256) {
        return store[computeKey(owner, key)];
    }

    function computeKey(address owner, uint256 key) public pure returns (uint256) {
        return uint256(keccak256(abi.encode(owner, key)));
    }
}

contract ActionExecutionRecord {
    KeyValueStore public immutable store;
    bytes32 public immutable actionContractId;

    constructor(KeyValueStore _store, string memory _uniqueActionName) {
        store = _store;
        actionContractId = keccak256(bytes(_uniqueActionName));
    }

    function _set(uint256 key, uint256 value) internal {
        store.set(computeKey(key), value);
    }

    function _get(uint256 key) internal view returns (uint256) {
        return store.get(address(this), computeKey(key));
    }

    function computeKey(uint256 key) public view returns (uint256) {
        return uint256(keccak256(abi.encode(actionContractId, key)));
    }
}

contract MiniSafe {
    enum Operation {
        Call,
        DelegateCall
    }

    mapping(address => bool) public modules;
    address[] internal owners;
    uint256 internal threshold;

    constructor(address[] memory _owners, uint256 _threshold, address module) {
        owners = _owners;
        threshold = _threshold;
        modules[module] = true;
    }

    function getOwners() external view returns (address[] memory) {
        return owners;
    }

    function getThreshold() external view returns (uint256) {
        return threshold;
    }

    function isOwner(address owner) external view returns (bool) {
        for (uint256 i = 0; i < owners.length; i++) {
            if (owners[i] == owner) return true;
        }
        return false;
    }

    function addOwnerWithThreshold(address owner, uint256 newThreshold) external {
        require(msg.sender == address(this), "only safe self-call");
        owners.push(owner);
        threshold = newThreshold;
    }

    function removeOwner(address, address owner, uint256 newThreshold) external {
        require(msg.sender == address(this), "only safe self-call");
        require(owners.length - 1 >= newThreshold, "below threshold");
        for (uint256 i = 0; i < owners.length; i++) {
            if (owners[i] == owner) {
                owners[i] = owners[owners.length - 1];
                owners.pop();
                threshold = newThreshold;
                return;
            }
        }
        revert("owner not found");
    }

    function execTransactionFromModule(
        address to,
        uint256,
        bytes memory data,
        Operation operation
    ) external returns (bool success) {
        require(modules[msg.sender], "sender is not an enabled module");
        if (operation == Operation.Call) {
            (success,) = to.call(data);
        } else {
            (success,) = to.delegatecall(data);
        }
    }
}

contract MiniUpgradeExecutor {
    mapping(address => bool) public executors;

    constructor(address executor) {
        executors[executor] = true;
    }

    function execute(address upgrade, bytes memory upgradeCallData) external {
        require(executors[msg.sender], "not executor");
        (bool success, bytes memory returnData) = upgrade.delegatecall(upgradeCallData);
        if (!success) {
            assembly {
                revert(add(returnData, 0x20), mload(returnData))
            }
        }
    }
}

contract SecurityCouncilMemberSyncAction is ActionExecutionRecord {
    error ExecFromModuleError(bytes data, address securityCouncil);

    address public constant SENTINEL_OWNERS = address(0x1);

    constructor(KeyValueStore _store)
        ActionExecutionRecord(_store, "SecurityCouncilMemberSyncAction")
    {}

    function perform(address _securityCouncil, address[] memory _updatedMembers, uint256 _nonce)
        external
        returns (bool res)
    {
        uint256 updateNonce = getUpdateNonce(_securityCouncil);
        if (_nonce <= updateNonce) return false;
        _setUpdateNonce(_securityCouncil, _nonce);

        MiniSafe securityCouncil = MiniSafe(_securityCouncil);
        uint256 threshold = securityCouncil.getThreshold();
        address[] memory previousOwners = securityCouncil.getOwners();

        for (uint256 i = 0; i < _updatedMembers.length; i++) {
            address member = _updatedMembers[i];
            if (!securityCouncil.isOwner(member)) {
                _execFromModule(
                    securityCouncil,
                    abi.encodeWithSelector(MiniSafe.addOwnerWithThreshold.selector, member, threshold)
                );
            }
        }

        for (uint256 i = 0; i < previousOwners.length; i++) {
            address owner = previousOwners[i];
            if (!_isInArray(owner, _updatedMembers)) {
                _execFromModule(
                    securityCouncil,
                    abi.encodeWithSelector(
                        MiniSafe.removeOwner.selector, SENTINEL_OWNERS, owner, threshold
                    )
                );
            }
        }
        return true;
    }

    function getUpdateNonce(address securityCouncil) public view returns (uint256) {
        return _get(uint160(securityCouncil));
    }

    function _setUpdateNonce(address securityCouncil, uint256 nonce) internal {
        _set(uint160(securityCouncil), nonce);
    }

    function _execFromModule(MiniSafe securityCouncil, bytes memory data) internal {
        if (!securityCouncil.execTransactionFromModule(address(securityCouncil), 0, data, MiniSafe.Operation.Call)) {
            revert ExecFromModuleError({data: data, securityCouncil: address(securityCouncil)});
        }
    }

    function _isInArray(address needle, address[] memory values) internal pure returns (bool) {
        for (uint256 i = 0; i < values.length; i++) {
            if (values[i] == needle) return true;
        }
        return false;
    }
}

contract SecurityCouncilSyncDirectCallTest {
    address internal constant EXECUTOR = address(0xEEC);
    address internal constant ATTACKER = address(0xBAD);

    function testExecutorDelegatecallCanUpdateOwners() public {
        Fixture memory fixture = _fixture();
        address[] memory updated = _updatedOwners();

        fixture.executor.execute(
            address(fixture.action),
            abi.encodeWithSelector(
                SecurityCouncilMemberSyncAction.perform.selector,
                address(fixture.safe),
                updated,
                1
            )
        );

        _assertOwnerSet(fixture.safe.getOwners(), updated);
    }

    function testDirectActionCallCannotUpdateOwners() public {
        Fixture memory fixture = _fixture();
        address[] memory beforeOwners = fixture.safe.getOwners();
        address[] memory updated = _updatedOwners();

        try fixture.action.perform(address(fixture.safe), updated, 1) returns (bool) {
            revert("direct call unexpectedly succeeded");
        } catch {}

        _assertOwnerSet(fixture.safe.getOwners(), beforeOwners);
    }

    struct Fixture {
        MiniUpgradeExecutor executor;
        MiniSafe safe;
        SecurityCouncilMemberSyncAction action;
    }

    function _fixture() internal returns (Fixture memory) {
        MiniUpgradeExecutor executor = new MiniUpgradeExecutor(address(this));
        address[] memory owners = _initialOwners();
        MiniSafe safe = new MiniSafe(owners, 2, address(executor));
        SecurityCouncilMemberSyncAction action =
            new SecurityCouncilMemberSyncAction(new KeyValueStore());
        return Fixture({executor: executor, safe: safe, action: action});
    }

    function _initialOwners() internal pure returns (address[] memory owners) {
        owners = new address[](3);
        owners[0] = address(0xA1);
        owners[1] = address(0xA2);
        owners[2] = address(0xA3);
    }

    function _updatedOwners() internal pure returns (address[] memory owners) {
        owners = new address[](3);
        owners[0] = address(0xA1);
        owners[1] = address(0xA2);
        owners[2] = ATTACKER;
    }

    function _assertOwnerSet(address[] memory actual, address[] memory expected) internal pure {
        require(actual.length == expected.length, "owner length mismatch");
        for (uint256 i = 0; i < expected.length; i++) {
            bool found;
            for (uint256 j = 0; j < actual.length; j++) {
                if (actual[j] == expected[i]) found = true;
            }
            require(found, "missing expected owner");
        }
    }
}

