# 人工复核

LLM 只产出“风险假设”，是否成立由人和测试决定。

## 流程

1. `build/llm_findings.json` 里每条 `status` 都是 `unconfirmed`
2. 逐条打开源码，核对 `code_evidence` 的行号是否真的支撑假设
3. 判定：
   - 代码里有 `require` / 修饰器挡住 → `false_positive`
   - 缺陷成立 → 写 Foundry 测试复现，标 `confirmed`
   - 依赖链上状态无法构造 → `unverifiable`
4. 把结果填进 `template.md` 的表格，测试文件路径写进“Foundry 测试”列

## 输出

- `review.md`：复核后的完整表（从 template 复制）
- 测试放在被测项目的 `test/audit/` 下，命名 `test_Audit_<FindingID>_<Scenario>.t.sol`

## 判断“误报”的三个固定依据

| 类型 | 检查什么 |
|---|---|
| 权限误报 | 函数是否有 `onlyOwner` / `onlyGovernance` / 角色校验 |
| 重入误报 | 是否有 `nonReentrant`，或状态更新是否在外部调用之前（CEI） |
| 返回值误报 | 是否用了 `SafeERC20`，或是否检查了返回值 |
