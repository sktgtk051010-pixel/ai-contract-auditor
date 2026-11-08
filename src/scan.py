"""扫描 Solidity 源码，提取结构信息与风险标记，输出 JSON。

这是流水线第 1 步：把一堆 .sol 文件变成结构化数据（build/scan.json）。
后面 build_input.py 和 analyze.py 都依赖它。
"""

import argparse            # 解析命令行参数，相当于 C 里自己遍历 argv
import json                # 读写 JSON，Python 自带
import re                  # 正则表达式，相当于 C 的 regex.h
from pathlib import Path   # 路径处理，避免手拼字符串

# 匹配 "contract Xxx" / "library Xxx" / "interface Xxx"，括号里是要抓的部分
CONTRACT_RE = re.compile(r"\b(contract|library|interface)\s+(\w+)")
# 匹配 "function foo("，抓函数名
FUNCTION_RE = re.compile(r"\bfunction\s+(\w+)\s*\(")
# 匹配 "pragma solidity 0.8.24;"
PRAGMA_RE = re.compile(r"pragma\s+solidity\s+([^;]+);")

# 函数可见性关键字，用来判断一个函数对外还是对内
VISIBILITY = ("external", "public", "internal", "private")
# 这些词出现在函数签名末尾时不算修饰器，要跳过
SKIP_MODIFIERS = set(VISIBILITY) | {"returns", "override", "virtual", "payable"}

# 函数体里出现这些片段，说明做了低层调用（容易出问题的地方）
LOW_LEVEL_PATTERNS = {
    ".call{": "call",
    ".call(": "call",
    ".delegatecall": "delegatecall",
    ".staticcall": "staticcall",
    ".send(": "send",
}
# 用了这些说明走的是 SafeERC20，返回值有人检查
SAFE_ERC20 = ("safeTransfer(", "safeTransferFrom(", "safeApprove(", "safeIncreaseAllowance(")


def strip_comments(text):
    """把注释挖掉，但保留换行，这样行号不会错位。

    C 里没有现成函数干这事，得自己扫字符；Python 用正则一行搞定。
    """
    # 内部函数：把匹配到的注释字符换成等长空格（换行保留）
    def blank(match):
        return re.sub(r"[^\n]", " ", match.group(0))

    # 先处理 /* ... */ 块注释，re.S 让 . 能匹配换行
    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.S)
    # 再处理 // 行注释
    text = re.sub(r"//[^\n]*", blank, text)
    return text


def line_number(text, offset):
    """字符位置 -> 行号：数字符串里 offset 之前有几个换行，再加 1。"""
    return text.count("\n", 0, offset) + 1


def match_paren(text, start):
    """从 start 位置的 '(' 开始，找到配对的 ')'，返回它后面的位置。

    用来处理函数参数里嵌套括号的情况，比如 foo(uint256(a), b)。
    """
    depth = 0                       # 括号深度，遇到 ( 加 1，遇到 ) 减 1
    i = start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:          # 回到 0 说明配对完成
                return i + 1
        i += 1
    return len(text)                # 没找到配对就返回末尾，不让程序崩


def match_brace(text, start):
    """从 start 位置的 '{' 开始，找到配对的 '}'，返回它的位置。"""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "{":
            depth += 1
        elif text[i] == "}":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    return len(text) - 1


def parse_contracts(text):
    """提取文件里所有合约/库/接口的声明位置。

    返回列表，每个元素是 {"name": "Xxx", "kind": "contract", "line": 12}。
    列表推导的写法等价于"循环 + append"。
    """
    return [
        {"name": m.group(2), "kind": m.group(1), "line": line_number(text, m.start())}
        for m in CONTRACT_RE.finditer(text)
    ]


def parse_functions(text):
    """提取文件里所有函数：名字、行号、可见性、修饰器、风险标记。"""
    functions = []
    # finditer 会逐个返回所有匹配，相当于 C 里循环 regexec
    for m in FUNCTION_RE.finditer(text):
        name = m.group(1)                    # 函数名
        start = m.start()                    # "function" 这个词的字符位置
        tail_start = match_paren(text, m.end() - 1)   # m.end()-1 是 '(' 的位置

        # 从参数列表结束往后找，直到遇到 '{'（有函数体）或 ';'（声明）
        j = tail_start
        while j < len(text) and text[j] not in "{;":
            j += 1
        if j >= len(text):
            continue                          # 文件被截断，跳过

        signature = " ".join(text[start:j].split())   # 把多行签名压成一行
        # 只保留修饰器部分：切掉 returns 及之后的内容
        tail = re.split(r"\breturns\b", text[tail_start:j])[0]

        # 修饰器 = 剩下的单词里，排除可见性和 override/virtual 之类的
        modifiers = [
            word
            for word in re.findall(r"\b([A-Za-z_]\w*)\b", tail)
            if word not in SKIP_MODIFIERS
        ]
        # 找可见性，找不到就当 internal（Solidity 默认也是 internal）
        visibility = next((v for v in VISIBILITY if re.search(rf"\b{v}\b", tail)), "internal")

        if text[j] == "{":
            # 有函数体：找到配对的 }，截出 body 用来检查风险标记
            end = match_brace(text, j)
            body = text[j : end + 1]
            end_line = line_number(text, end)
        else:
            body = ""                          # 接口/抽象函数没有函数体
            end_line = line_number(text, j)

        # 检查函数体里有没有低层调用，去重后排序
        low_level = sorted({kind for token, kind in LOW_LEVEL_PATTERNS.items() if token in body})

        functions.append(
            {
                "name": name,
                "line": line_number(text, start),
                "end_line": end_line,
                "visibility": visibility,
                "modifiers": modifiers,
                "signature": signature,
                "has_body": bool(body),
                "low_level_calls": low_level,
                "uses_safe_erc20": any(token in body for token in SAFE_ERC20),
                "reads_balance": "balanceOf(" in body,
            }
        )
    return functions


def attach_contracts(functions, contracts):
    """给每个函数标上它属于哪个合约（按行号，取它前面最近的那个合约）。"""
    for fn in functions:
        owner = None
        for item in contracts:
            if item["line"] <= fn["line"]:
                owner = item["name"]        # 不断覆盖，最后留下最近的一个
        fn["contract"] = owner


def scan_file(path, root):
    """处理单个 .sol 文件，返回它的结构化信息。"""
    raw = path.read_text(encoding="utf-8", errors="replace")  # 读全文，编码坏了也不崩
    text = strip_comments(raw)                                # 去掉注释，保留行号

    pragma = PRAGMA_RE.search(text)                            # 找 pragma 版本
    contracts = parse_contracts(text)
    functions = parse_functions(text)
    attach_contracts(functions, contracts)

    rel = path.relative_to(root).as_posix()                    # 相对路径，统一用 / 分隔
    return {
        "path": rel,
        "lines": raw.count("\n") + 1,                          # 原始文件行数
        "pragma": pragma.group(1).strip() if pragma else "",
        "contracts": contracts,
        "functions": functions,
    }


def scan(root):
    """扫描整个目录，汇总所有文件。"""
    # rglob 递归找所有 .sol，sorted 保证每次输出顺序一致
    files = [scan_file(p, root) for p in sorted(root.rglob("*.sol"))]

    # 把所有文件的函数摊平到一个大列表里，方便统计
    all_functions = [fn for f in files for fn in f["functions"]]
    external = [fn for fn in all_functions if fn["visibility"] in ("external", "public")]

    return {
        "root": str(root),
        "summary": {
            "files": len(files),
            "contracts": sum(len(f["contracts"]) for f in files),
            "functions": len(all_functions),
            "external_functions": len(external),
            "low_level_call_functions": sum(1 for fn in all_functions if fn["low_level_calls"]),
        },
        "files": files,
    }


def main():
    """命令行入口：python src/scan.py --target 目录 --out 输出文件。"""
    parser = argparse.ArgumentParser(description="Scan Solidity sources")
    parser.add_argument("--target", required=True, help="directory containing .sol files")
    parser.add_argument("--out", default="build/scan.json", help="output json path")
    args = parser.parse_args()                 # 解析出来的参数存在 args 里，用 args.target 取

    root = Path(args.target).resolve()         # 转成绝对路径
    if not root.is_dir():
        raise SystemExit(f"target not a directory: {root}")   # 打印并退出

    result = scan(root)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)   # 建父目录，已存在不报错
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),   # 转 JSON，中文原样输出，缩进美化
        encoding="utf-8",
    )

    # 终端打一行摘要，方便确认跑没跑对
    summary = result["summary"]
    print(
        f"files={summary['files']} contracts={summary['contracts']} "
        f"functions={summary['functions']} external={summary['external_functions']} "
        f"low_level={summary['low_level_call_functions']}"
    )
    print(f"written: {out}")


# 只有直接运行本文件才执行 main；被别的脚本 import 时不执行
if __name__ == "__main__":
    main()
