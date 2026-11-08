"""从评估案例表算检出指标：基线、LLM 新增、误报、漏报。

案例表 eval/cases.csv 每行一个已知漏洞案例，列里填 yes/no/TODO。
TODO 表示还没跑，不参与统计。
"""

import argparse
import csv
from pathlib import Path

# 这些写法都当成"是"
YES = {"yes", "y", "1", "true"}


def is_yes(value):
    """把表格里的字符串转成布尔值。空值、no、TODO 都算否。"""
    return value.strip().lower() in YES


def is_pending(row, field):
    """这一列是不是还没填（TODO）。"""
    return row[field].strip().upper() == "TODO"


def load_cases(path):
    """读 CSV，每行变成一个字典，键是表头。"""
    # newline="" 让 csv 模块自己处理换行，避免多出空行
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def summarize(rows, label):
    """对一组案例算各项指标。"""
    total = len(rows)

    # 基线：只有 Slither 时检出的数量
    baseline = sum(1 for r in rows if is_yes(r["slither_detected"]))

    # LLM 提出的数量
    flagged = sum(1 for r in rows if is_yes(r["llm_flagged"]))

    # LLM 提出且复核成立
    confirmed = sum(1 for r in rows if r["llm_flagged"] and is_yes(r["human_confirmed"]))

    # LLM 补上了基线没发现的问题
    llm_extra = sum(1 for r in rows if r["llm_flagged"] and not is_yes(r["slither_detected"]))

    # 两边都没发现 = 漏报
    missed = sum(
        1
        for r in rows
        if not is_yes(r["slither_detected"]) and not is_yes(r["llm_flagged"])
    )

    # 提了但不成立 = 误报
    false_positives = flagged - confirmed

    return {
        "label": label,
        "cases": total,
        "baseline_detected": baseline,
        "llm_flagged": flagged,
        "llm_extra": llm_extra,
        "confirmed": confirmed,
        "false_positives": false_positives,
        "missed": missed,
        "baseline_rate": baseline / total if total else 0.0,
        "llm_precision": confirmed / flagged if flagged else 0.0,
    }


def render(results):
    """把结果列表渲染成 markdown 表格。"""
    lines = [
        "| 集合 | 案例数 | 基线检出 | LLM 提出 | LLM 新增 | 人工确认 | 误报 | 漏报 | 基线检出率 | LLM 精确率 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        # :.0% 表示按百分比显示、保留 0 位小数
        lines.append(
            f"| {r['label']} | {r['cases']} | {r['baseline_detected']} | {r['llm_flagged']} | "
            f"{r['llm_extra']} | {r['confirmed']} | {r['false_positives']} | {r['missed']} | "
            f"{r['baseline_rate']:.0%} | {r['llm_precision']:.0%} |"
        )
    return "\n".join(lines)


def main():
    """命令行入口：python eval/run_eval.py"""
    parser = argparse.ArgumentParser(description="Evaluate detection results")
    parser.add_argument("--cases", default="eval/cases.csv")
    parser.add_argument("--out", default="eval/eval_result.md")
    args = parser.parse_args()

    rows = load_cases(args.cases)
    # 还没填的行先挑出来，统计时排除
    pending = [r["case_id"] for r in rows if is_pending(r, "slither_detected")]

    results = []
    # 调试集和评估集分开算，避免调参污染最终结论
    for split in ("debug", "eval"):
        subset = [
            r
            for r in rows
            if r.get("split", "").strip() == split and r["case_id"] not in pending
        ]
        if subset:
            results.append(summarize(subset, split))

    # 两边合起来再算一次总账
    complete = [r for r in rows if r["case_id"] not in pending]
    if complete:
        results.append(summarize(complete, "all"))

    table = render(results)
    note = f"\n\n未填写（TODO）：{', '.join(pending)}" if pending else ""
    text = "# 评估结果\n\n" + table + note + "\n"

    Path(args.out).write_text(text, encoding="utf-8")
    print(table)
    if pending:
        print(f"pending cases: {', '.join(pending)}")


if __name__ == "__main__":
    main()
