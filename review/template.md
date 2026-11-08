# 人工复核记录

每条 LLM 风险假设都必须在“裁决”列给出明确结论，不允许留空。

| ID | 文件 | 函数 | 风险假设 | 裁决 | 代码依据 | Foundry 测试 | 结论 |
|---|---|---|---|---|---|---|---|
| F-001 |  |  |  | confirmed / false_positive / unverifiable | L__-L__ | test/ | 已复现 / 已修复 / 不成立 |

## 裁决标准

| 裁决 | 什么情况下用 | 必须附带 |
|---|---|---|
| `confirmed` | 读完代码确认缺陷成立，或 Foundry 测试复现 | 代码行号 + 测试文件，缺一不可 |
| `false_positive` | 读完代码确认不成立（有校验、不可达、工具误报） | 指出哪一行 `require` 或哪个修饰器挡住了 |
| `unverifiable` | 证据不足、依赖外部状态无法在测试中构造 | 写清缺什么证据 |

## 与 Slither 告警的关系

工具告警先进 `tool_alert`，人工裁决后改为 `confirmed` 或 `false_positive`。LLM 产生的假设从 `unconfirmed` 开始。两类来源在表里用 ID 前缀区分：`SL-` 为工具告警，`F-` 为 LLM 假设。
