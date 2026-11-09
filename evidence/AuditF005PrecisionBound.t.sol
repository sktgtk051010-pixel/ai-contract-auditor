// SPDX-License-Identifier: MIT
pragma solidity ^0.8.24;

import {BaseTest} from "../base/BaseTest.t.sol";

/// @notice 复核 F-005：stake 里 rewardDebt 先除后乘，截断误差到底有多大
/// @dev 结论：误差不是固定 2 wei。第一层的截断残差会被 rewardPerTokenStored 放大，
///      上界约 rpt / 1e18；实测 556 wei，相对质押额 1000 ether 可忽略。
contract AuditF005PrecisionBoundTest is BaseTest {
    function test_Audit_F005_RewardDebtTruncationBound() public {
        // 1. bob 先质押一笔，让 totalStaked > 0，rewardPerTokenStored 才会随时间增长
        vm.prank(bob);
        staking.stake(1000 ether, 0);

        // 2. 推进 10 天，把 rewardPerTokenStored 推到一个非零值
        skipDays(10);

        // 3. alice 用非 1.0 倍率、且金额不能整除 1e18 的方式质押，制造第一层截断
        uint256 amount = 1000 ether + 1;   // +1 wei 让 amount * mult 不能被 1e18 整除
        uint256 tierIndex = 1;             // 30 天档，倍率 1.2x

        vm.prank(alice);
        uint256 id = staking.stake(amount, tierIndex);

        // 4. 读合约里实际记下的 rewardDebt
        (, uint256 actualDebt, , ) = staking.stakes(id);
        uint256 rpt = staking.rewardPerTokenStored();
        (, uint256 mult) = staking.lockTiers(tierIndex);

        // 5. 用一次除法算全精度理论值（不在中间截断两次）
        uint256 exact = (amount * mult * rpt) / (1e18 * 1e18);

        // 6. 断言一：实际值只会偏小（向下取整）
        assertLe(actualDebt, exact, "actual debt should not exceed exact");

        // 7. 断言二：误差上界 = rpt / 1e18 + 2
        //    推导：第一层残差 r1 < 1e18，再乘 rpt 除以 1e18，最多贡献 rpt/1e18 wei
        uint256 bound = rpt / 1e18 + 2;
        assertLe(exact - actualDebt, bound, "truncation exceeded rpt-scaled bound");

        // 8. 断言三：相对误差仍可忽略（小于质押额的百万分之一）
        assertLt(exact - actualDebt, amount / 1e6, "relative error unexpectedly large");

        emit log_named_uint("rewardPerTokenStored", rpt);
        emit log_named_uint("exact debt          ", exact);
        emit log_named_uint("actual debt         ", actualDebt);
        emit log_named_uint("delta (wei)         ", exact - actualDebt);
        emit log_named_uint("allowed bound (wei) ", bound);
    }
}
