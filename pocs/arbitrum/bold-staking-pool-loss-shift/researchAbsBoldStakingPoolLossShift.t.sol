// SPDX-License-Identifier: UNLICENSED
pragma solidity ^0.8.13;

import "forge-std/Test.sol";

import "../../src/assertionStakingPool/AbsBoldStakingPool.sol";
import "../../src/mocks/TestWETH9.sol";

contract ResearchLossSink {
    // Intentionally no withdrawal path. This models a losing protocol move whose stake is not
    // returned to the pool.
}

contract ResearchLossShiftPool is AbsBoldStakingPool {
    ResearchLossSink public immutable sink;
    uint256 public immutable requiredStake;

    constructor(address stakeToken_, uint256 requiredStake_)
        AbsBoldStakingPool(stakeToken_)
    {
        sink = new ResearchLossSink();
        requiredStake = requiredStake_;
    }

    function createLosingMove() external {
        IERC20(stakeToken).transfer(address(sink), requiredStake);
    }
}

contract ResearchAbsBoldStakingPoolLossShiftTest is Test {
    uint256 internal constant BASE_STAKE = 10 ether;

    address internal stakerA = address(0xA11CE);
    address internal stakerB = address(0xB0B);
    address internal excessStaker = address(0xECCE55);

    TestWETH9 internal token;
    ResearchLossShiftPool internal pool;

    function setUp() public {
        token = new TestWETH9("Test", "TEST");
        pool = new ResearchLossShiftPool(address(token), BASE_STAKE);

        token.deposit{value: 11 ether}();
        token.transfer(stakerA, 6 ether);
        token.transfer(stakerB, 4 ether);
        token.transfer(excessStaker, 1 ether);

        vm.prank(stakerA);
        token.approve(address(pool), type(uint256).max);
        vm.prank(stakerB);
        token.approve(address(pool), type(uint256).max);
        vm.prank(excessStaker);
        token.approve(address(pool), type(uint256).max);
    }

    function testExcessWithdrawerCanAvoidPoolLossWhileRequiredStakersRemainUnpaid() public {
        vm.prank(stakerA);
        pool.depositIntoPool(6 ether);
        vm.prank(stakerB);
        pool.depositIntoPool(4 ether);
        vm.prank(excessStaker);
        pool.depositIntoPool(1 ether);

        pool.createLosingMove();
        assertEq(token.balanceOf(address(pool)), 1 ether, "only excess remains in pool");

        vm.prank(excessStaker);
        pool.withdrawFromPool();
        assertEq(token.balanceOf(excessStaker), 1 ether, "excess staker recovered");
        assertEq(token.balanceOf(address(pool)), 0, "pool is empty after excess withdrawal");

        vm.expectRevert("ERC20: transfer amount exceeds balance");
        vm.prank(stakerA);
        pool.withdrawFromPool();

        vm.expectRevert("ERC20: transfer amount exceeds balance");
        vm.prank(stakerB);
        pool.withdrawFromPool();

        assertEq(pool.depositBalance(stakerA), 6 ether, "staker A still has accounting balance");
        assertEq(pool.depositBalance(stakerB), 4 ether, "staker B still has accounting balance");
    }
}
