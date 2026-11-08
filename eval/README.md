# 效果评估

## 两个集合分开

| 集合 | 用途 | 规则 |
|---|---|---|
| `debug` | 调提示词、改输出格式 | 可以反复跑，改动后回来重测 |
| `eval` | 最终结论 | 提示词定稿后才能跑，只跑一次，不回头调 |

先跑 `debug`，把提示词改到稳定；再跑 `eval`，`eval` 的结果才写进报告。混着跑等于自己给自己泄题。

## 三个对比项

| 项 | 定义 | CSV 列 |
|---|---|---|
| 基线检出 | 只有 Slither 时能否发现 | `slither_detected` |
| LLM 提出 | LLM 是否提出相关假设 | `llm_flagged` |
| 人工确认 | 复核后是否成立 | `human_confirmed` |

## 填表口径

- `slither_detected`：该案例在 Slither 输出里是否有对应告警（`build/slither.json` 里搜得到）
- `llm_flagged`：LLM 输出里是否提到该案例的问题点（`build/llm_findings.json` 里搜得到）
- `human_confirmed`：你复核后是否确认为真问题
- 三者都是 `yes` / `no`，没跑就是 `TODO`

## 计算

```bash
python eval/run_eval.py
```

输出 `eval/eval_result.md`，含基线检出率、LLM 新增、误报、漏报、LLM 精确率。

## 案例怎么选

- 至少 5 个，其中 3 个可以来自自己项目里已知的问题（F-01/F-02/F-08），2 个来自公开靶场
- 每个案例要有明确答案，否则无法判断检出
- 有修复版本更好：修复版应当检不出，用来验证工具不会乱报
