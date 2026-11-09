# 人工复核记录

**样本**：`D:\Solidity-Projects\staking`（TimeBoostStaking 质押激励协议）
**扫描范围**：`src/` 4 个合约、15 个对外函数
**模型**：DeepSeek `deepseek-chat`（2026-11-10 实跑）
**产出**：15 条 LLM 风险假设，逐条复核

每条假设必须给出明确裁决，不允许留空。`F-` 为 LLM 假设，`SL-` 为 Slither 告警。

## 裁决表

| ID | 文件 | 函数 | 风险假设 | 裁决 | 代码依据 | Foundry 测试 | 结论 |
|---|---|---|---|---|---|---|---|
| F-001 | BoostCredential.sol | mintBoostCredential | `_mint` 回调可重入绕过 `hasMinted` | false_positive | L21-L25 | 未写 | `mintBoostCredential` 带 `onlyOwner`，回调方不是 owner，二次调用被拒 |
| F-002 | TimeBoostStaking.sol | userHasBoost | 资格按实时余额判定，可临时持有刷历史加成 | confirmed | L180-L181、L281、BoostCredential L31-L33 | 建议补 | 未结算区间全部按当前 `boosted` 计算，先质押后买凭证可追溯加成；预算不超发，属预算内再分配 |
| F-003 | StakeToken.sol | mint | owner 可无限增发，稀释持有者 | confirmed | L15-L17 | 无需 | 设计如此，与 SR-05 同一问题 |
| F-004 | RewardToken.sol | mint | owner 可无限增发，稀释持有者 | confirmed | L15-L17 | 无需 | 同上 |
| F-005 | TimeBoostStaking.sol | stake | 档位倍率未校验上限，可能溢出 | false_positive | L230-L231 | 无需 | `setLockTier` 限制 `1e18 <= m <= 5e18` |
| F-006 | TimeBoostStaking.sol | getReward | 未更新债务前转账，可重复领取 | false_positive | L130、L146-L159、L276-L289 | 无需 | `nonReentrant` + 严格 CEI：先改 `rewardDebt` 再转账 |
| F-007 | TimeBoostStaking.sol | unstake | `totalStaked` 扣减口径与质押不一致 | false_positive | L115、L150 | 无需 | 两侧都按 `amount * lockMultiplier / 1e18` 计算 |
| F-008 | TimeBoostStaking.sol | earned | 模型未产出假设 | unverifiable | - | - | 只读函数，模型判为无风险，无假设可裁 |
| F-009 | TimeBoostStaking.sol | getUserStakeIds | 返回 storage 数组引用可被篡改 | false_positive | L173-L175 | 无需 | 返回值声明为 `uint256[] memory`，Solidity 自动拷贝 |
| F-010 | TimeBoostStaking.sol | notifyRewardAmount | `leftover` 计算漏乘 `boostMultiplier` | false_positive | L202-L206 | 无需 | 新速率与初始速率都除以 `boostMultiplier`，口径一致 |
| F-011 | TimeBoostStaking.sol | setRewardsDuration | 改周期与已发奖励不兼容 | false_positive | L216-L221 | 已有测试 | 仅影响下个周期折算；`test_SetRewardsDuration_*` 覆盖 |
| F-012 | TimeBoostStaking.sol | setLockTier | 改档位影响已质押用户 | false_positive | L110-L111 | 已有测试 | 倍率与解锁时间在 `stake` 时快照进 `UserStake` |
| F-013 | TimeBoostStaking.sol | setBoostMultiplier | 新倍率追溯计算历史奖励 | false_positive | L243-L251、L309-L319 | 已有测试 | 切点分段：历史区间用旧 `cutBoost`，新倍率只作用于新段 |
| F-014 | TimeBoostStaking.sol | boostPageCount | 模型未产出假设 | unverifiable | - | - | view 函数，无假设可裁 |
| F-015 | TimeBoostStaking.sol | setEarlyMintDeadline | owner 可任意缩短或延长凭证窗口 | confirmed | L264-L267 | 无需 | 属 owner 权限范围，与 SR-05 同类的中心化风险 |

## 统计

| 项 | 数值 |
|---|---|
| LLM 假设总数 | 13（另有 2 条空输出） |
| 人工确认成立 | 4（F-002、F-003、F-004、F-015） |
| 判为误报 | 9 |
| 精确率 | 4 / 13 ≈ 30.8% |

## 与评估案例的对应

| 案例 | 对应发现 | LLM 是否提出 | 说明 |
|---|---|---|---|
| C-01 定点数先除后乘 | 无 | 否 | F-005、F-007 提到精度，但指的是「倍率上限」和「记账口径」，不是截断误差 |
| C-02 owner 单点增发 | F-003、F-004 | 是 | 直接命中「owner 无限增发稀释」 |
| C-03 空池期预算沉淀 | 无 | 否 | F-010 讲 leftover 缩放，与空池沉淀无关 |
| C-04 凭证资格实时判定 | F-002 | 是 | 机制相同（按当前余额判定），利用方向不同（临时买入 vs 转让丢失） |
| C-05 段数线性增长 gas | 无 | 否 | 工具与模型都不看 gas 增长趋势 |

## 复核方法

每条都按三步走：

1. **定位原文**：按 LLM 给的行号打开源码，确认它说的代码确实存在
2. **找阻挡条件**：看有没有 `require`、修饰器、快照机制挡住这条路
3. **判成立与否**：挡住了就是 `false_positive` 并写明挡在哪一行；没挡住就是 `confirmed`

误报的典型原因：模型只看了单个函数，看不到跨函数的约束（如 `setLockTier` 的上限校验在另一个函数里）。
