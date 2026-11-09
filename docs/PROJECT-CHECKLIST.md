# 项目清单

记录这个项目要做哪些事、哪些已经做完、哪些要你自己做。

---

## 一、项目结构树

```
ai-contract-auditor/
├─ README.md                 仓库首页。面试官打开仓库第一眼看的说明：工具干什么、怎么跑、五种状态定义
├─ requirements.txt          声明"本项目零依赖"，Slither 要单独装
├─ .gitignore                排除 build/、密钥、临时产物
├─ .gitattributes            统一换行符为 LF，避免 WSL 里脚本带 \r 报错
├─ run_pipeline.py           入口：一条命令串起四步
│
├─ src/                      核心代码（简历第 3 条的证据）
│  ├─ scan.py                第 1 步：扫 .sol 文件，输出文件/合约/函数/可见性/修饰器 → build/scan.json
│  ├─ convert_slither.py     第 2 步：把 Slither 原始 JSON 压平成统一格式 → build/slither.json
│  ├─ build_input.py         第 3 步：一个对外函数一个分析单元，附源码片段和告警 → build/analysis_input.json
│  └─ analyze.py             第 4 步：填提示词、调 LLM、解析 JSON → build/llm_findings.json
│
├─ prompts/
│  └─ risk_analysis.md       提示词模板。中文，$file/$source 这些是占位符，由代码替换
│
├─ schema/
│  └─ finding.schema.json    五状态定义：tool_alert / unconfirmed / confirmed / false_positive / unverifiable
│
├─ review/                   人工复核（简历第 3 条的"人工复核"部分）
│  ├─ template.md            裁决表空表。你要往这里填每条假设的结论
│  └─ README.md              复核规则：怎么判误报、测试放哪、怎么命名
│
├─ eval/                     效果评估（简历第 3 条的最后一句话）
│  ├─ cases.csv              5 个案例，每个填 slither/llm/人工三列。现在全是 TODO
│  ├─ run_eval.py            算检出率、误报、漏报 → eval/eval_result.md
│  ├─ README.md              评估规则：调试集和评估集为什么要分开
│  └─ eval_result.md         跑出来的报告（本地有，被 .gitignore 排除）
│
└─ docs/                     给你自己看的学习材料，不是简历证据
   ├─ PYTHON-101.md          Python 语法速成，全部对照 C
   ├─ WALKTHROUGH.md         每个脚本在干嘛、你要敲什么命令
   └─ PROJECT-CHECKLIST.md   本文件
```

---

## 二、每个文件对应简历哪一句

| 简历原话 | 靠这些文件 | 产物 |
|---|---|---|
| 整理 Solidity 源码、编译配置和静态分析结果…构建结构化分析输入 | `scan.py`、`convert_slither.py`、`build_input.py` | `build/scan.json`、`build/slither.json`、`build/analysis_input.json` |
| 设计 LLM 提示词与输出格式，生成风险假设…区分四类结果 | `prompts/risk_analysis.md`、`schema/finding.schema.json`、`analyze.py` | `build/prompts/*.txt`、`build/llm_findings.json` |
| 人工复核…编写 Foundry 测试…生成审查辅助报告 | `review/template.md`、`review/README.md` | `review/review.md`、`test/audit/*.t.sol` |
| 使用已知漏洞样例评估…对比基线…记录检出、误报、漏报 | `eval/cases.csv`、`eval/run_eval.py`、`eval/README.md` | `eval/eval_result.md` |

---

## 三、已完成（✅ 已跑过，有输出为证）

| # | 任务 | 证据 | 状态 |
|---|---|---|---|
| 1 | 建项目骨架，19 个文件 | git 提交 `02aea50`、`22487a5`、`5bad231` | ✅ |
| 2 | `scan.py` 能扫真实项目 | `files=15 contracts=35 functions=251 external=196 low_level=1` | ✅ |
| 3 | 修掉"returns 变量名被当修饰器"的 bug | 重跑后 `modifiers: onlyVault, nonReentrant` | ✅ |
| 4 | `build_input.py` 能生成分析单元 | `units=196 alerts_assigned=0` | ✅ |
| 5 | `analyze.py` 的 dry-run 能出提示词 | `dry-run: wrote 3 prompts` | ✅ |
| 6 | `run_eval.py` 能算指标 | 输出表头 + `pending cases: C-01...C-05` | ✅ |
| 7 | 提示词模板改成中文 | dry-run 验证，占位符替换正常 | ✅ |
| 8 | 两个教学文档 | `docs/PYTHON-101.md`、`docs/WALKTHROUGH.md` | ✅ |
| 9 | `convert_slither.py` 代码写完 | 已用真实 Slither 输出验证（17 条告警归一化成功） | ✅ |
| 10 | 用 staking 作样本跑通扫描 | `files=4 contracts=4 functions=21 external=15 low_level=0` | ✅ |
| 11 | 生成分析单元（含告警挂载） | `units=15 alerts_assigned=14`，3 条命名规范类落空 | ✅ |
| 12 | DeepSeek 真调全量 15 条 | `findings=15 failed=0` | ✅ |
| 13 | 人工逐条复核 | `review/review.md`：6 条成立、8 条误报、精确率 42.9% | ✅ |
| 14 | 评估跑出真实数字 | `eval/eval_result.md`：基线 1/5、LLM 累计 3/5、两边都漏 2 | ✅ |
| 15 | 修两个真实 bug | `"no"` 被当成真值；Slither 路径 `src/x.sol` 与扫描 `x.sol` 对不上 | ✅ |

---

## 四、操作步骤（先看状态总览）

| 步骤 | 状态 | 说明 |
|---|---|---|
| 1 装 Slither | ✅ 已装 | WSL 里 Slither 0.11.5（`~/.local/bin/slither`） |
| 2 生成 Slither JSON | ✅ 已做 | 复制到 `/tmp` 跑，原目录零改动；29 合约 / 17 条告警 |
| 3 归一化 | ✅ 已做 | `alerts=17 by_impact={'Medium': 4, 'Low': 9, 'Informational': 3, 'Optimization': 1}` |
| 4 跑流水线 | ✅ 已做 | staking：`units=15` |
| 5 拿 API key | ✅ 已做 | DeepSeek |
| 6 真调 | ✅ 已做 | 15 条全部成功 |
| 7 人工复核 | ✅ 已做 | 4 条成立、9 条误报 |
| 8 Foundry 测试 | ✅ 已做 | `evidence/AuditF005PrecisionBound.t.sol` 跑通，实测截断误差 556 wei |
| 9 填评估表 | ✅ 已做 | 基线 1/5、LLM 累计 3/5、两边都漏 2 |
| 10 推 GitHub | ⬜ 未做 | **唯一必须做的收尾** |

下面各节保留原始操作说明。已完成的可以当参考，未完成的照着做。

**样本已从 vault 改为 staking。** 涉及 Slither 的命令要把目录换成 `staking`：

```bash
cd /mnt/d/Solidity-Projects/staking
slither . --filter-paths "lib/" --exclude-dependencies --json /mnt/d/Solidity-Projects/ai-contract-auditor/slither_raw.json
```

**注意**：Slither 会往被测项目里写 `crytic-export/`、`cache/` 等产物。如果不想让 staking 出现任何新文件，就在副本目录里跑，别在原目录跑。

### ⬜ 1. 在 WSL 里装 Slither（15 分钟）

```bash
cd ~/Adaptive-Self-Rebalance-Lp-Vault
python3 -m pip install slither-analyzer
slither --version
```

**验收**：`slither --version` 打印出版本号，不是 `command not found`。

**卡住**：`pip` 权限报错就加 `--user`；装完还找不到命令，把 `~/.local/bin` 加进 PATH。

---

### ⬜ 2. 生成 Slither 原始输出（10 分钟）

```bash
cd ~/Adaptive-Self-Rebalance-Lp-Vault
forge build
slither . --json /mnt/d/Solidity-Projects/ai-contract-auditor/slither_raw.json
```

**验收**：Windows 侧能看到 `D:\Solidity-Projects\ai-contract-auditor\slither_raw.json`，文件不是 0 字节。

**卡住**：报 `compile` 相关错误就加 `--compile-force-framework foundry`。Slither 会自己 `forge clean` 再 build，可能跑几分钟，别以为卡死了。

---

### ⬜ 3. 归一化，看看有多少 High（10 分钟）

```powershell
cd D:\Solidity-Projects\ai-contract-auditor
python src\convert_slither.py --input slither_raw.json
```

**验收**：输出类似 `alerts=23 by_impact={'High': 3, 'Medium': 8, 'Low': 12}`。

这一步同时验证了 `convert_slither.py`（清单里的 ⚠️ 项）。

**把 High 的数量记下来**，面试会问。

---

### ⬜ 4. 跑完整流水线（5 分钟）

```powershell
python run_pipeline.py --target "\\wsl.localhost\Ubuntu\home\gintoki\Adaptive-Self-Rebalance-Lp-Vault\src" --slither slither_raw.json
```

**验收**：`units=196 alerts_assigned=XX`，XX 不再是 0。

如果还是 0，说明告警行号没落进任何函数范围，去 `build/analysis_input.json` 的 `unassigned_alerts` 里看为什么。

---

### ⬜ 5. 拿一个 LLM API key（20 分钟）

DeepSeek（便宜）：`platform.deepseek.com` → 注册 → 充值 10 块 → API keys → 创建 → 复制 `sk-` 开头的字符串。

```powershell
$env:LLM_API_KEY="sk-你的key"
$env:LLM_BASE_URL="https://api.deepseek.com/v1"
$env:LLM_MODEL="deepseek-chat"
```

**验收**：`echo $env:LLM_API_KEY` 能打印出来。

**注意**：这个变量只在当前 PowerShell 窗口有效。

---

### ⬜ 6. 真调 10 条，看输出质量（15 分钟）

```powershell
python run_pipeline.py --target "\\wsl.localhost\...\src" --slither slither_raw.json --analyze --limit 10
```

**验收**：输出 `findings=10 failed=0`，`build/llm_findings.json` 里有 10 条假设。

**然后你要做判断**：这 10 条里，有几条看起来像真的？

- 0 条 → 提示词有问题，改 `prompts/risk_analysis.md` 后重跑
- 3 条以上 → 提示词可用，放开跑更多

---

### ⬜ 7. 人工复核，填 `review/review.md`（1–2 小时，最重的一步）

打开 `build/llm_findings.json`，逐条：

1. 按 `code_evidence` 给的行号，打开源码核对
2. 判断：
   - 有 `require` 或修饰器挡住 → `false_positive`，写清是哪一行挡的
   - 确实有问题 → 写 Foundry 测试复现 → `confirmed`
   - 依赖链上状态构造不了 → `unverifiable`
3. 把结果抄进 `review/template.md`，另存为 `review/review.md`

**验收**：`review/review.md` 里至少 10 行有明确裁决，没有空着的格子。

**这是简历里"人工复核"四个字的唯一证据。**

---

### ⬜ 8. 至少写 1 个 Foundry 测试（1 小时）

放在被测项目的 `test/audit/` 下：

```bash
# 在 vault 项目里
mkdir -p test/audit
```

命名：`test_Audit_F001_ReentrancyOnWithdraw.t.sol`

**验收**：`forge test --match-path "test/audit/*"` 通过，且这个测试**真的复现了前面确认的问题**（不是写个必然通过的测试凑数）。

---

### ⬜ 9. 填评估表，跑出数字（1 小时）

打开 `eval/cases.csv`，5 行全部填完：

| 列 | 怎么填 |
|---|---|
| `slither_detected` | 在 `build/slither.json` 里搜这个问题的关键词，有就 yes |
| `llm_flagged` | 在 `build/llm_findings.json` 里搜，有就 yes |
| `human_confirmed` | 你复核后是否成立 |

案例可以从你自己 vault 项目里挑：F-01（burn 无授权）、F-02（setMinter 设零地址）、F-8（单边闲置）等。不一定要用外部靶场。

```powershell
python eval\run_eval.py
```

**验收**：`eval/eval_result.md` 里有非零数字，`pending` 列表为空。

---

### ⬜ 10. 推到 GitHub（20 分钟）

先在 GitHub 建空仓库 `ai-contract-auditor`（不要勾选 README）。

```powershell
cd D:\Solidity-Projects\ai-contract-auditor
git config user.name "你的名字"
git config user.email "你的邮箱"
git remote add origin git@github.com:sktgtk051010-pixel/ai-contract-auditor.git
git push -u origin main
```

**验收**：浏览器打开仓库能看到 README 和 `src/` 目录。

**注意**：`slither_raw.json` 和 `build/` 被 gitignore，不会上传，这是对的 —— 里面有源码路径，而且太大。

---

## 五、可选加分项（⭐ 有空再做）

| 项 | 时间 | 价值 |
|---|---|---|
| 全跑 196 个函数 | 30 分钟 + 十几块 | 数据更完整，能说"全项目覆盖" |
| 写 `src/report.py`，把 findings 生成 markdown 报告 | 1 小时 | 对应简历"生成审查辅助报告" |
| 加 GitHub Actions 自动跑 scan | 1 小时 | 简历能写 CI |
| 用两个模型（DeepSeek + 豆包）对比结果 | 1 小时 | 能讲"模型差异" |
| 补 `docs/` 里的示例输出截图 | 30 分钟 | 面试演示更直观 |

---

## 六、卡住对照表

| 现象 | 看哪里 |
|---|---|
| `slither: command not found` | WSL 里没装成功，回第 1 步 |
| `slither` 报编译错误 | 加 `--compile-force-framework foundry`，先手动 `forge build` 一遍 |
| `alerts_assigned=0` | 看 `build/analysis_input.json` 的 `unassigned_alerts` |
| `LLM_API_KEY not set` | 环境变量没设，或者换了 PowerShell 窗口 |
| `findings=0 failed=10` | key 无效、余额不足、或 base_url 写错 |
| `pending` 一直不减少 | `cases.csv` 里还有 `TODO` 没替换成 `yes`/`no` |

---

## 七、完成后简历能写成什么样

全部打勾后，第 3 条可以改成：

> **AI 辅助智能合约审计工具**｜Python / Slither / LLM / Foundry
> · 代码与告警处理：用正则解析 Solidity 源码结构（15 文件 / 35 合约 / 251 函数），将 Slither 告警归一化并按函数合并为 196 个分析单元。
> · 风险分析流程：设计中文提示词与 JSON 输出契约，约束行号必须落在给定片段内，输出风险假设、代码依据、前置条件与验证建议；结果按五状态分类。
> · 人工与测试验证：逐条复核模型假设，对确认问题编写 Foundry 测试复现；误报按权限、重入、返回值三类固定依据判定。
> · 效果评估：以 5 个已知问题构建评估集，对比 Slither 基线，统计检出率 X%、LLM 新增检出 Y 条、误报 Z 条。

**X/Y/Z 必须是你跑出来的真实数字，不能编。**
