"""把 scan.json（源码结构）和 slither.json（告警）合成分析单元。

每个"对外函数"变成一个分析单元，里面带：
- 这个函数属于哪个文件、哪个合约
- 它的源码片段（带行号）
- 跟它相关的静态分析告警

这样 LLM 每次只看一个函数 + 它的告警，不用把整个仓库塞进去。
"""

import argparse
import json
from pathlib import Path

# 一个函数最多截多少行源码，防止 prompt 太长烧钱
MAX_SOURCE_LINES = 120


def load(path, default):
    """读 JSON 文件；文件不存在时返回默认值，不报错。"""
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def read_snippet(root, rel_path, start, end):
    """从原始源码里截取 start..end 行，并在每行前面加行号。

    加了行号，LLM 引用代码位置时才有依据，人工复核也好对。
    """
    path = Path(root) / rel_path          # 用 / 拼路径，跨平台安全
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    first = max(0, start - 1)             # 行号从 1 开始，列表下标从 0 开始
    last = min(len(lines), end)
    if last - first > MAX_SOURCE_LINES:   # 太长就截断
        last = first + MAX_SOURCE_LINES
    # f"{i+1:5d}|" 表示右对齐占 5 格，后面跟竖线和代码
    return "\n".join(f"{i + 1:5d}| {lines[i]}" for i in range(first, last))


def assign_alerts(alerts, files_index):
    """把每条告警挂到"函数体覆盖它行号"的那个函数上。

    返回两个东西：
    - assigned：{(文件, 函数名, 行号): [告警列表]}
    - unassigned：挂不上的告警（比如在 modifier 或构造函数里）
    """
    assigned = {}
    unassigned = []
    for alert in alerts:
        rel = alert["file"]
        lines = alert.get("lines") or []
        entry = files_index.get(rel)       # 这个文件扫描过没有
        if not entry or not lines:
            unassigned.append(alert)
            continue
        target = lines[0]                  # 用告警的第一行来定位
        match = None
        for fn in entry["functions"]:
            # 告警行号落在函数起止行之间，就算属于这个函数
            if fn["line"] <= target <= fn.get("end_line", fn["line"]):
                if match is None or fn["line"] > match["line"]:
                    match = fn              # 取最内层（起始行最靠后的）那个
        if match:
            assigned.setdefault((rel, match["name"], match["line"]), []).append(alert)
        else:
            unassigned.append(alert)
    return assigned, unassigned


def build(scan_data, slither_data):
    """合成所有分析单元。"""
    root = scan_data["root"]
    files_index = {f["path"]: f for f in scan_data["files"]}   # 路径 -> 文件信息
    alerts = slither_data.get("alerts", []) if slither_data else []
    assigned, unassigned = assign_alerts(alerts, files_index)

    units = []
    for path, entry in files_index.items():        # 遍历每个文件
        for fn in entry["functions"]:              # 遍历文件里的每个函数
            # 只分析对外函数：internal/private 攻击者调不到
            if fn["visibility"] not in ("external", "public"):
                continue
            key = (path, fn["name"], fn["line"])
            units.append(
                {
                    "id": f"CH-{len(units) + 1:03d}",   # CH = check unit
                    "file": path,
                    "contract": fn.get("contract") or "",
                    "function": fn["name"],
                    "visibility": fn["visibility"],
                    "modifiers": fn["modifiers"],
                    "line_start": fn["line"],
                    "line_end": fn.get("end_line", fn["line"]),
                    "low_level_calls": fn["low_level_calls"],
                    "uses_safe_erc20": fn["uses_safe_erc20"],
                    "alerts": assigned.get(key, []),
                    "source": read_snippet(root, path, fn["line"], fn.get("end_line", fn["line"])),
                }
            )

    return {
        "units": units,
        "unassigned_alerts": unassigned,
        "summary": {
            "units": len(units),
            "alerts_total": len(alerts),
            "alerts_assigned": len(alerts) - len(unassigned),
        },
    }


def main():
    """命令行入口：先跑 scan.py 和 convert_slither.py，再跑这个。"""
    parser = argparse.ArgumentParser(description="Build LLM analysis input")
    parser.add_argument("--scan", default="build/scan.json")
    parser.add_argument("--slither", default="build/slither.json")
    parser.add_argument("--out", default="build/analysis_input.json")
    args = parser.parse_args()

    scan_data = load(args.scan, None)
    if scan_data is None:
        raise SystemExit(f"missing scan file: {args.scan} (run scan.py first)")
    slither_data = load(args.slither, {"alerts": []})   # 没跑 Slither 就当成零告警

    result = build(scan_data, slither_data)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps(result, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    print(f"units={result['summary']['units']} alerts_assigned={result['summary']['alerts_assigned']}")
    print(f"written: {out}")


if __name__ == "__main__":
    main()
