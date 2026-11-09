# 复核测试证据

这个目录放"人工复核时真的跑过的 Foundry 测试"，用来证明复核不是只靠眼睛看的。

## 为什么不能放进 staking 项目

`staking` 是只读样本，整轮工作没有向它写入任何文件（`git status` 全程为空）。所以测试写在**副本**里跑：把 staking 复制到 `/tmp/staking-audit-copy`，再把测试放到副本的 `test/audit/` 下。

## 怎么复现

```bash
# 1. 复制样本（排除 .git 和 .env）
rsync -a --exclude='.git' --exclude='.env' --exclude='out' --exclude='cache' \
  /mnt/d/Solidity-Projects/staking/ /tmp/staking-audit-copy/

# 2. 放测试
mkdir -p /tmp/staking-audit-copy/test/audit
cp evidence/AuditF005PrecisionBound.t.sol /tmp/staking-audit-copy/test/audit/

# 3. 跑
export PATH="$HOME/.foundry/bin:$PATH"
cd /tmp/staking-audit-copy
forge test --match-contract AuditF005 -vv
```

## AuditF005PrecisionBound.t.sol —— 验证 F-005 的截断误差

**对应假设**：`stake` 里 `rewardDebt` 先除后乘，截断会让 debt 偏小、用户多领。
**对应案例**：C-01（SR-06，Slither 唯一检出的那条）。

**测试做了什么**：

1. bob 先质押，让 `totalStaked > 0`，奖励指数才会随时间增长
2. 推进 10 天
3. alice 用 `1000 ether + 1 wei`、30 天档（1.2x）质押，故意制造第一层不能整除
4. 读合约里实际写入的 `rewardDebt`
5. 用一次除法算全精度理论值
6. 断言：实际值只偏小、误差 ≤ `rpt/1e18 + 2`、相对误差可忽略

**实测输出**：

```
rewardPerTokenStored: 2777777777777777777088
exact debt          : 3333333333333333332508933
actual debt         : 3333333333333333332508377
delta (wei)         : 556
allowed bound (wei) : 2779
[PASS]
```

**结论**：

- 模型说的"先除后乘导致精度损失"**成立**，方向（debt 偏小 → 多领）也对
- 但 staking 自审报告写的"单笔单次截断 ≤ 2 wei"**不准确**：第一层截断的残差会被 `rewardPerTokenStored` 放大，上界约 `rpt / 1e18`。本场景实测 556 wei
- 556 wei 相对 1000 ether（1e21 wei）是 5.6e-19 量级，**仍然可以忽略**，不构成可利用漏洞

这就是"人工复核 + Foundry 测试验证"的实际产出：不是复述报告结论，而是把报告的量化口径校正了一遍。
