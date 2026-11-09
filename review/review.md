# 人工复核记录

**样本**：`D:\Solidity-Projects\staking`（TimeBoostStaking 质押激励协议）
**扫描范围**：`src/` 4 个合约、15 个对外函数
**模型**：DeepSeek `deepseek-chat`（2026-11-10 实跑）
**输入条件**：提示词中包含真实 Slither 告警（17 条，挂上 14 条、落空 3 条）
**产出**：15 条 LLM 风险假设，逐条复核

每条假设必须给出明确裁决，不允许留空。`F-` 为 LLM 假设，`SL-` 为 Slither 告警。

## 裁决表

| ID | 文件 | 函数 | 风险假设 | 裁决 | 代码依据 | Foundry 测试 | 结论 |
|---|---|---|---|---|---|---|---|
| F-001 | BoostCredential.sol | mintBoostCredential | owner 私钥泄露可被滥用铸造 | confirmed | L21-L25 | 无需 | 属 owner 信任假设，与 SR-05 同类 |
| F-002 | TimeBoostStaking.sol | userHasBoost | `balanceOf` 对零地址/异常输入返回非预期值 | false_positive | L180-L181、BoostCredential L31-L33 | 无需 | OZ ERC1155 的 `balanceOf` 对零地址返回 0，不存在误判路径 |
| F-003 | StakeToken.sol | mint | owner 无上限增发，稀释持有者 | confirmed | L15-L17 | 无需 | 设计如此，与 SR-05 同一问题 |
| F-004 | RewardToken.sol | mint | owner 无上限增发，稀释持有者 | confirmed | L15-L17 | 无需 | 同上 |
| F-005 | TimeBoostStaking.sol | stake | `rewardDebt` 先除后乘，截断偏小导致多领 | confirmed | L109、L287 | **已写并跑通** | 机制真实、方向也对；但误差不是固定 2 wei，第一层残差被 `rpt` 放大，实测 556 wei、上界约 `rpt/1e18`，对 1000 ether 仍可忽略 |
| F-006 | TimeBoostStaking.sol | getReward | 时间边界处理不当导致重复领取 | false_positive | L130、L276-L289 | 无需 | `nonReentrant` + 每次结算全量刷新 `rewardDebt`，无重复计算路径 |
| F-007 | TimeBoostStaking.sol | unstake | 用 `block.timestamp` 判断解锁可能被操纵 | false_positive | L144 | 已有测试 | 锁仓协议必须用时间；PoS 下偏移秒级，`test_Unstake_RevertWhen_StillLocked` 覆盖 |
| F-008 | TimeBoostStaking.sol | earned | 模型未产出假设 | unverifiable | - | - | 只读函数，模型判为无风险 |
| F-009 | TimeBoostStaking.sol | getUserStakeIds | 返回 storage 数组引用可被篡改 | false_positive | L173-L175 | 无需 | 返回值声明为 `uint256[] memory`，自动拷贝 |
| F-010 | TimeBoostStaking.sol | notifyRewardAmount | `leftover` 计算漏乘 `boostMultiplier` | false_positive | L202-L206 | 无需 | 新速率与初始速率都除以 `boostMultiplier`，口径一致 |
| F-011 | TimeBoostStaking.sol | setRewardsDuration | 仅用时间判断周期结束 | false_positive | L216-L221 | 已有测试 | 业务设计如此，不影响已发奖励 |
| F-012 | TimeBoostStaking.sol | setLockTier | 改档位影响已质押用户 | false_positive | L110-L111 | 已有测试 | 倍率与解锁时间在 `stake` 时快照进 `UserStake` |
| F-013 | TimeBoostStaking.sol | setBoostMultiplier | 用时间比较限制调整有边界漏洞 | false_positive | L239、L243-L251 | 已有测试 | 时间判断是业务必需；切点分段保证历史不被追溯 |
| F-014 | TimeBoostStaking.sol | boostPageCount | `cutBoost` 无上限增长，view 可能 gas 耗尽 | confirmed（弱） | L258-L260、L246-L251 | 无需 | 对应 SR-02 段数增长；模型自己标置信度 0.2，方向偏到 view 而非结算循环 |
| F-015 | TimeBoostStaking.sol | setEarlyMintDeadline | owner 可将窗口设为立即关闭 | confirmed | L264-L267 | 无需 | 属 owner 权限范围，与 SR-05 同类 |

## 统计

| 项 | 数值 |
|---|---|
| LLM 假设总数 | 14（CH-008 空输出） |
| 人工确认成立 | 6（F-001、F-003、F-004、F-005、F-014、F-015） |
| 判为误报 | 8 |
| 精确率 | 6 / 14 ≈ 42.9% |

## 一个值得记住的观察

6 条成立的假设里，**4 条是 owner 权限类**（F-001、F-003、F-004、F-015），1 条精度类（F-005），1 条效率类（F-014）。

也就是说：**模型很会抓"管理员能干什么"，但对记账语义（空池沉淀、凭证资格按时段判定）基本抓不到。** 这是这个工具的边界。

## 与评估案例的对应

| 案例 | 对应发现 | LLM 是否提出 | 说明 |
|---|---|---|---|
| C-01 定点数先除后乘 | F-005 | 是 | 带告警后模型直接命中，置信度 0.7，方向（多领）也说对 |
| C-02 owner 单点增发 | F-003、F-004 | 是 | 直接命中 |
| C-03 空池期预算沉淀 | 无 | 否 | 模型未涉及 `totalStaked == 0` 时的预算沉淀 |
| C-04 凭证资格实时判定 | 无 | 否 | F-002 转向了 `balanceOf` 零地址，未提出"按实时余额判定" |
| C-05 段数线性增长 | F-014 | 是 | 机制命中，但方向是 view 调用，未指出结算循环 gas |

## Foundry 复核测试

以下测试真的跑过，源码在 `evidence/`：

| 测试 | 对应发现 | 结果 |
|---|---|---|
| `AuditF005PrecisionBound.t.sol` | F-005 | PASS；实测截断误差 556 wei，上界 `rpt/1e18 + 2` |

跑法见 `evidence/README.md`。测试写在 staking 的**副本**里（`/tmp/staking-audit-copy/test/audit/`），原项目零写入。

**这个测试的价值不在于"通过"，而在于它校正了报告的口径**：报告写"单笔单次截断 ≤ 2 wei"，实测是 556 wei —— 第一层截断的残差会被奖励指数放大，上界随 `rewardPerTokenStored` 增长。结论仍是"可忽略"，但依据变了。

## 复核方法

每条都按三步走：

1. **定位原文**：按 LLM 给的行号打开源码，确认它说的代码确实存在
2. **找阻挡条件**：看有没有 `require`、修饰器、快照机制挡住这条路
3. **判成立与否**：挡住了就是 `false_positive` 并写明挡在哪一行；没挡住就是 `confirmed`

误报的典型原因有两个：

- 模型只看了单个函数，看不到跨函数的约束（如 `setLockTier` 的上限校验在另一个函数里）
- 把"业务必需的设计"当成缺陷（`block.timestamp` 在锁仓协议里不可能不用）
