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

```bash
# 1. 只跑结构和告警，不调 LLM
python run_pipeline.py --target <your-project>/src --slither slither_raw.json

# 2. 看将要发给 LLM 的提示词（不花钱）
python run_pipeline.py --target <your-project>/src --dry-run

# 3. 真调 LLM
export LLM_API_KEY=sk-xxx          # PowerShell: $env:LLM_API_KEY="sk-xxx"
export LLM_BASE_URL=https://api.openai.com/v1   # 兼容其他 OpenAI 格式服务
export LLM_MODEL=gpt-4o-mini
python run_pipeline.py --target <your-project>/src --slither slither_raw.json --analyze --limit 5
```

Slither 原始输出这样产生：

```bash
slither . --json slither_raw.json
```

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
