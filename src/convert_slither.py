"""把 Slither 的 JSON 输出整理成统一格式。

Slither 原始输出结构复杂（每个告警带一堆 elements），这个脚本只留下
后面要用的字段：id、检测器名、严重度、文件、行号、描述。

对应简历里"整理静态分析结果"这一步。
"""

import argparse
import json
from pathlib import Path

# 严重度排序权重，让 High 排在最前面
IMPACT_ORDER = {"High": 3, "Medium": 2, "Low": 1, "Informational": 0, "Optimization": 0}


def detectors_of(payload):
    """兼容 Slither 不同版本的输出结构，统一取出告警列表。

    - 老版本：顶层就是列表
    - 新版本：{"results": {"detectors": [...]}}
    """
    if isinstance(payload, list):
        return payload
    results = payload.get("results", payload)   # 有 results 就用它，没有就用顶层
    if isinstance(results, dict):
        return results.get("detectors", [])
    return []


def elements_of(detector):
    """从告警的 elements 里抽出文件、行号、函数名。

    elements 是 Slither 给的"这条告警涉及哪些代码位置"。
    """
    out = []
    for element in detector.get("elements", []):
        mapping = element.get("source_mapping", {})   # 位置信息在 source_mapping 里
        out.append(
            {
                "type": element.get("type", ""),
                "name": element.get("name", ""),
                "file": mapping.get("filename_relative", ""),
                "lines": mapping.get("lines", []),
            }
        )
    return out


def normalize(payload):
    """把原始告警全部整理成统一字典，并按严重度排序。"""
    alerts = []
    for index, detector in enumerate(detectors_of(payload), start=1):
        elements = elements_of(detector)
        # 取第一个有文件路径的 element 当主位置
        primary = next((e for e in elements if e["file"]), {})
        alerts.append(
            {
                "id": f"SL-{index:03d}",                      # SL 前缀 = Slither 来源
                "detector": detector.get("check", ""),        # 检测器名，如 reentrancy-eth
                "impact": detector.get("impact", ""),         # High / Medium / Low
                "confidence": detector.get("confidence", ""), # High / Medium / Low
                "description": " ".join(detector.get("description", "").split()),  # 压成一行
                "file": primary.get("file", ""),
                "lines": primary.get("lines", []),
                "elements": elements,
                "status": "tool_alert",                       # 工具告警，还没人工裁决
            }
        )

    # 按严重度从高到低排序
    alerts.sort(key=lambda a: IMPACT_ORDER.get(a["impact"], 0), reverse=True)
    # 排序后重新编号，保证 SL-001 就是最严重的
    for index, alert in enumerate(alerts, start=1):
        alert["id"] = f"SL-{index:03d}"
    return alerts


def main():
    """命令行入口：python src/convert_slither.py --input slither_raw.json。"""
    parser = argparse.ArgumentParser(description="Convert Slither JSON")
    parser.add_argument("--input", required=True, help="slither --json output file")
    parser.add_argument("--out", default="build/slither.json")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    alerts = normalize(payload)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"alerts": alerts}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )

    # 按严重度统计，方便一眼看出有多少 High
    counts = {}
    for alert in alerts:
        counts[alert["impact"]] = counts.get(alert["impact"], 0) + 1
    print(f"alerts={len(alerts)} by_impact={counts}")
    print(f"written: {out}")


if __name__ == "__main__":
    main()
