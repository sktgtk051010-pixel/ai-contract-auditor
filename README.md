# ai-contract-auditor

Python + Slither + LLM 的智能合约审计辅助工具：扫描源码结构、归并静态分析告警、生成风险假设，再由人工复核并用 Foundry 测试验证。

LLM 只负责提假设，不下结论。每条假设的状态由人裁决。

## 流水线

```
Solidity 源码
   │
   ├─ scan.py          结构提取（合约/函数/可见性/修饰器/低层调用）
   │
   ├─ convert_slither.py   Slither JSON 归一化（按 impact 排序）
   │
   ├─ build_input.py   按函数合并源码片段 + 告警 → 分析单元
   │
   ├─ analyze.py       LLM 生成风险假设（JSON 输出）
   │
   ├─ review/          人工裁决：confirmed / false_positive / unverifiable
   │
   └─ eval/            基线 vs LLM 的检出对比
```

## 快速开始

样本用 `D:\Solidity-Projects\staking`（**只读，不改它**）。

```powershell
# 1. 结构扫描
python src\scan.py --target "D:\Solidity-Projects\staking\src"

# 2. 合并源码与告警，生成分析单元
python src\build_input.py --scan build\scan.json

# 3. 先看提示词长什么样，不发请求
python src\analyze.py --input build\analysis_input.json --dry-run --limit 3

# 4. 真调 LLM（先设环境变量，见下）
python src\analyze.py --input build\analysis_input.json

# 5. 算对比指标
python eval\run_eval.py
```

环境变量三件套（DeepSeek 为例，PowerShell 里设一次即可）：

```powershell
setx LLM_API_KEY "sk-xxx"
setx LLM_BASE_URL "https://api.deepseek.com/v1"
setx LLM_MODEL "deepseek-chat"
```

`LLM_BASE_URL` 只要兼容 OpenAI 格式就能换其他服务商。

Slither 原始输出这样产生：

```bash
slither . --json slither_raw.json
```

## 实测结果（staking 样本，2026-11-10）

| 阶段 | 结果 |
|---|---|
| 扫描 | 4 文件 / 4 合约 / 21 函数 / 15 个对外函数 |
| Slither | 29 合约 / 101 detectors / 17 条告警（Medium 4、Low 9、Info 3、Opt 1） |
| 告警挂载 | 14 条挂到 7 个函数；3 条命名规范类落在状态变量上，挂不上 |
| 分析单元 | 15 个 |
| LLM 假设 | 15 条（14 条有内容，1 条空输出） |
| 人工复核成立 | 6 条 |
| 误报 | 8 条 |
| 全量精确率 | 6 / 14 ≈ 42.9% |
| 基线（Slither）检出 | 1 / 5 个已知问题（20%） |
| LLM 累计检出 | 3 / 5（60%） |
| LLM 新增 | 2 / 5（owner 增发、段数增长） |
| 两边都漏 | 2 / 5（空池预算沉淀、凭证资格实时判定） |

**结论**：Slither 擅长精度类模式匹配，业务语义问题（权限设计、记账资格）它看不到；LLM 能补上一部分，但误报率高，必须人工逐条裁决。

**一个观察**：6 条成立的假设里 4 条是 owner 权限类。模型很会抓"管理员能干什么"，但对记账语义（空池沉淀、凭证资格按时段判定）基本抓不到 —— 这是工具的边界。

## 产物

| 文件 | 内容 |
|---|---|
| `build/scan.json` | 文件、合约、函数、可见性、修饰器、低层调用标记 |
| `build/slither.json` | 归一化告警（id / detector / impact / 行号） |
| `build/analysis_input.json` | 每个对外函数一个分析单元，含源码片段与关联告警 |
| `build/prompts/` | dry-run 模式生成的提示词 |
| `build/llm_findings.json` | LLM 风险假设，全部 `unconfirmed` |
| `review/review.md` | 人工裁决后的结论表 |
| `eval/eval_result.md` | 检出率、误报、漏报对比 |

## 状态定义

| status | 含义 | 谁写入 |
|---|---|---|
| `tool_alert` | 只有静态分析告警 | Slither |
| `unconfirmed` | LLM 假设，未复核 | analyze.py |
| `confirmed` | 人工确认或测试复现 | 人工 |
| `false_positive` | 复核后不成立 | 人工 |
| `unverifiable` | 证据不足，无法判定 | 人工 / API 失败 |

## 局限

- Solidity 解析基于正则，不处理宏式继承展开，跨文件函数归属只按同文件行号
- LLM 输出可能行号越界，必须人工核对
- 评估集需要自己准备案例，工具不内置漏洞样本
- 不做自动修复，不生成报告正文，只产出结构化线索
- **实测误报率 57.1%**（14 条假设里 8 条不成立），所以每条都必须人工复核，不能直接当结论用
- LLM 只看单个函数，跨函数的约束看不到，典型的误报来源就是"校验写在别的函数里"

## 目录

```
src/        扫描、转换、合并、分析
prompts/    提示词模板
schema/     finding 的 JSON schema
review/     人工裁决模板
eval/       案例表与指标计算
docs/       学习文档
```

## 文档

- `docs/PYTHON-101.md`：Python 语法速成，全部对照 C
- `docs/WALKTHROUGH.md`：每个脚本在干什么、你要执行什么、怎么核对结果
