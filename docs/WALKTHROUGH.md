# 逐文件讲解：每个脚本在干嘛，你要做什么

配合 `docs/PYTHON-101.md` 一起看。那份讲语法，这份讲"这个文件为什么存在"。

---

## 0. 整个项目在解决什么问题

你之前手工读 vault 代码找漏洞：一页页看，记下来，写测试验证。慢，而且会漏。

这个项目把这件事拆成机器能做的部分：

```
源码 ──► 切成"一个函数一块" ──► 让大模型提可疑点 ──► 你来判断真假 ──► 统计准不准
```

**关键的边界**：大模型只负责"提假设"，不负责"下结论"。它说"这里可能重入"，不代表真的重入，要你看代码、写测试。

为什么这么设计：模型会一本正经地胡说，所以它的输出只能当线索，不能当结论。这就是简历里"人工复核"四个字的实际含义。

---

## 1. `src/scan.py` —— 把源码变成表格

### 它干什么

输入一堆 `.sol` 文件，输出一个 JSON，里面记着：

- 有哪些文件、每个文件多少行、用的 Solidity 版本
- 有哪些合约（contract / library / interface）
- 有哪些函数，每个函数的：
  - 名字、起止行号
  - 可见性（external / public / internal / private）
  - 修饰器（onlyOwner、nonReentrant 这些）
  - 有没有低层调用（`.call` / `.delegatecall`）
  - 有没有用 SafeERC20
  - 有没有读 `balanceOf`

### 为什么要这一步

大模型一次读不完一整个项目（上下文有限，而且按 token 收费）。所以要先把项目切成"一个函数一块"，后面每次只喂一块。

### 你在这一步要做什么

```powershell
python3 src\scan.py --target "你的项目\src" --out build\scan.json
```

看终端输出的那行数字：

```
files=15 contracts=35 functions=251 external=196 low_level=1
```

**你要判断的是**：这些数字对不对？

- `functions=251` 但你觉得项目只有几十个函数 → 解析漏了，去看正则
- `external=196` 占比特别高 → 可能把 internal 也当成 external 了
- `low_level=1` → 只有 1 个函数用了低层调用，可以去 JSON 里搜出来核对

数字不对，后面全错。这一步是地基。

### 里面的关键技术点（对应代码注释）

| 代码 | 在干嘛 | 为什么这么做 |
|---|---|---|
| `strip_comments` | 把 `//` 和 `/* */` 换成空格 | 注释里的 `function xxx(` 会干扰正则；换成空格而不是删掉，是为了**行号不变** |
| `match_paren` / `match_brace` | 数括号，找到配对的那个 | 函数参数里可能有嵌套括号，不能简单找下一个 `)` |
| `attach_contracts` | 按行号把函数归到最近的合约 | Solidity 一个文件可以有多个合约，函数得知道属于谁 |
| `SKIP_MODIFIERS` | 排除 `external` `returns` 这些词 | 不然 `returns (uint256 amount)` 里的变量名会被当成修饰器 |

---

## 2. `src/convert_slither.py` —— 把 Slither 的输出压平

### 它干什么

Slither 的 JSON 长这样（简化）：

```json
{"results": {"detectors": [
  {"check": "reentrancy-eth", "impact": "High",
   "elements": [{"source_mapping": {"filename_relative": "src/Vault.sol", "lines": [120]}}]}
]}}
```

嵌套很深，字段名也不统一。这个脚本把它压成：

```json
{"alerts": [
  {"id": "SL-001", "detector": "reentrancy-eth", "impact": "High",
   "file": "src/Vault.sol", "lines": [120], "status": "tool_alert"}
]}
```

并且**按严重度排序后重新编号**，让 `SL-001` 永远是最严重的。

### 你在这一步要做什么

```bash
# 先在被测项目里跑 Slither
cd ~/你的项目
slither . --json /mnt/d/Solidity-Projects/ai-contract-auditor/slither_raw.json

# 再回来转换
cd /mnt/d/Solidity-Projects/ai-contract-auditor
python src/convert_slither.py --input slither_raw.json
```

看输出：

```
alerts=23 by_impact={'High': 3, 'Medium': 8, 'Low': 12}
```

**你要判断的是**：High 有几条？这些是不是你项目里真实存在的问题？后面人工复核就从 High 开始看。

### 为什么需要"归一化"这一步

Slither 升级会改字段名（`check` 有时叫 `detector`，`filename_relative` 有时叫 `filename_absolute`）。中间加一层转换，后面所有脚本只认一种格式，Slither 升级不会把整条流水线带崩。

---

## 3. `src/build_input.py` —— 组装"给模型看的那一块"

### 它干什么

把 scan 的结构 + Slither 的告警合起来，**每个对外函数生成一个分析单元**：

```json
{
  "id": "CH-001",
  "file": "adapters/UniswapV2Adapter.sol",
  "contract": "UniswapV2Adapter",
  "function": "addLiquidity",
  "visibility": "external",
  "modifiers": ["onlyVault", "nonReentrant"],
  "line_start": 87,
  "line_end": 141,
  "alerts": [...],
  "source": "   87|     function addLiquidity(...\n   88| ..."
}
```

`source` 是原始源码的片段，**每行前面加了行号**。

### 为什么要加行号

模型说"第 97 行有问题"，你得能立刻翻到第 97 行核对。没行号就只能靠它描述，容易对不上。

这也是为什么 `strip_comments` 要用空格替换而不是删除——行号必须和原文件一致。

### 你在这一步要做什么

```powershell
python src\build_input.py --scan build\scan.json --slither build\slither.json
```

输出：

```
units=196 alerts_assigned=0
```

`units=196` 表示有 196 个对外函数要分析。`alerts_assigned=0` 表示没有告警挂到函数上（因为你还没跑 Slither）。

**你要抽查**：打开 `build/analysis_input.json`，找一个熟悉的函数，看它的 `source` 是不是真的那段代码、`modifiers` 对不对。

### 只分析对外函数的原因

`internal` / `private` 函数攻击者调不到，除非被对外函数间接调用。先只看对外入口，是审计的标准做法。

---

## 4. `src/analyze.py` —— 真正调用大模型

### 它干什么

对每个分析单元：

1. 把模板 `prompts/risk_analysis.md` 里的 `$file` `$source` 这些占位符替换成真实内容
2. 发给 LLM（OpenAI 兼容接口）
3. 从回复里抠出 JSON
4. 存成 `build/llm_findings.json`，状态统一写 `unconfirmed`

### 两种模式

| 模式 | 命令 | 花钱 | 用途 |
|---|---|---|---|
| dry-run | 不加 `--analyze` | 不花钱 | 只看提示词长什么样 |
| 真跑 | 加 `--analyze` | 按 token 收费 | 拿真实结果 |

**先 dry-run**。提示词写错了，真跑就是浪费钱。

### 你在这一步要做什么

```powershell
# 第一步：看看提示词
python run_pipeline.py --target "你的项目\src" --limit 2

# 打开 build\prompts\CH-001.txt 读一遍
# 确认：源码片段对不对、修饰器对不对、告警有没有带上

# 第二步：配 key，真跑 10 条
$env:LLM_API_KEY="sk-xxx"
$env:LLM_BASE_URL="https://api.deepseek.com/v1"
$env:LLM_MODEL="deepseek-chat"
python run_pipeline.py --target "你的项目\src" --slither slither_raw.json --analyze --limit 10
```

为什么先 `--limit 10`：196 个函数全跑一遍要花不少钱。先跑 10 个看输出质量，质量不行就改提示词，别一上来全跑。

### 里面的关键技术点

| 代码 | 在干嘛 | 为什么 |
|---|---|---|
| `string.Template` | 把 `$xxx` 替换成值 | 比 `str.replace` 安全，不会误替换 |
| `extract_json` | 找第一个 `{` 和最后一个 `}` | 模型常在 JSON 外面加"好的，结果如下"或代码块 |
| 重试 3 次 | 失败后隔 1.5 秒再试 | 网络抖动、限流是常态 |
| 失败标 `unverifiable` | 保留 error 字段 | 失败也是结果，不能假装成功 |

---

## 5. `run_pipeline.py` —— 一条命令跑完

### 它干什么

按顺序调用上面四个脚本，任何一步失败就停。

相当于 C 里的：

```c
system("python src/scan.py ...");
if (ret != 0) exit(1);
system("python src/build_input.py ...");
```

### 你在这一步要做什么

平时只用这一条：

```powershell
python run_pipeline.py --target "你的项目\src" --slither slither_raw.json
```

它会依次打印每一步的输出。**哪一步数字不对，就去看那一步对应的脚本。**

---

## 6. `eval/run_eval.py` —— 算准确率

### 它干什么

读 `eval/cases.csv`，算：

- 基线（只有 Slither）检出几个
- LLM 提出几个
- LLM 补上了几个基线没发现的
- 误报几个（提了但不成立）
- 漏报几个（两边都没发现）
- 两个比率：基线检出率、LLM 精确率

### 你在这一步要做什么

**手填 `eval/cases.csv`**，每行一个已知案例：

| 列 | 填什么 |
|---|---|
| `case_id` | C-01、C-02…… |
| `case_name` | 一句话描述，如 "burn without allowance" |
| `slither_detected` | Slither 输出里有没有这条 → yes/no |
| `llm_flagged` | LLM 输出里有没有提 → yes/no |
| `human_confirmed` | 你复核后是否成立 → yes/no |
| `split` | `debug`（调提示词用）或 `eval`（最终结论） |

填完跑：

```powershell
python eval\run_eval.py
```

结果写到 `eval/eval_result.md`。

**这一步的意义**：简历上"对比基线和引入 LLM 后的结果"这句话，就靠这张表撑着。没有数字，这句话就是空的。

---

## 7. 你的完整操作顺序

| 步骤 | 命令 | 产物 | 对应简历哪条 |
|---|---|---|---|
| 1 | `python src\scan.py --target ...` | `build/scan.json` | 代码与告警处理 |
| 2 | 项目里 `slither . --json ...` | `slither_raw.json` | 代码与告警处理 |
| 3 | `python src\convert_slither.py` | `build/slither.json` | 代码与告警处理 |
| 4 | `python src\build_input.py` | `build/analysis_input.json` | 代码与告警处理 |
| 5 | `python run_pipeline.py ... --limit 2` | `build/prompts/*.txt` | 风险分析流程 |
| 6 | 配 key，`--analyze --limit 10` | `build/llm_findings.json` | 风险分析流程 |
| 7 | 人工看代码，填 `review/review.md` | 裁决表 | 人工与测试验证 |
| 8 | 写 Foundry 测试 | `test/audit/*.t.sol` | 人工与测试验证 |
| 9 | 填 `eval/cases.csv` | 案例表 | 效果评估 |
| 10 | `python eval\run_eval.py` | `eval/eval_result.md` | 效果评估 |

**1-4 已经跑通了，5-6 差一个 API key，7-10 要你自己动手。**

---

## 8. 报错怎么读

| 报错 | 意思 | 怎么办 |
|---|---|---|
| `ModuleNotFoundError` | 缺库 | `pip install 库名` |
| `FileNotFoundError: build/scan.json` | 上一步没跑 | 按顺序重跑 |
| `IndentationError` | 缩进错了 | 检查是不是混了 Tab |
| `KeyError: 'xxx'` | 字典里没这个键 | 用 `.get("xxx", 默认值)` 或先打印看有哪些键 |
| `UnicodeDecodeError` | 编码不对 | 读文件加 `encoding="utf-8"` |
| `json.decoder.JSONDecodeError` | 不是合法 JSON | 打印出问题的那段文本看 |

---

## 9. 怎么练 Python（别只看不写）

按这个顺序，每个 10 分钟：

1. **改数字**：把 `MAX_SOURCE_LINES = 120` 改成 60，重跑，看 prompt 变短
2. **加一个字段**：在 `scan.py` 里给每个函数加 `"is_view"`（判断签名里有没有 `view`），跑完看 JSON
3. **加一个统计**：在 `scan.py` 的 summary 里加"有多少函数带 nonReentrant"
4. **改输出格式**：把终端那行 `files=15 contracts=35` 改成中文
5. **自己写一个**：写 `count_lines.py`，统计一个目录下所有 .sol 多少行

每改一次都跑一遍，报错就查 `PYTHON-101.md`。改坏了大不了用 `git checkout 文件名` 还原（本项目已提交过）。
