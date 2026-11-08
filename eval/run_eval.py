"""Compute detection metrics from the evaluation case table."""

import argparse
import csv
from pathlib import Path


YES = {"yes", "y", "1", "true"}


def is_yes(value):
    return value.strip().lower() in YES


def is_pending(row, field):
    return row[field].strip().upper() == "TODO"


def load_cases(path):
    with Path(path).open(encoding="utf-8", newline="") as handle:
        return list(csv.DictReader(handle))


def summarize(rows, label):
    total = len(rows)
    baseline = sum(1 for r in rows if is_yes(r["slither_detected"]))
    flagged = sum(1 for r in rows if is_yes(r["llm_flagged"]))
    confirmed = sum(1 for r in rows if r["llm_flagged"] and is_yes(r["human_confirmed"]))
    llm_extra = sum(1 for r in rows if r["llm_flagged"] and not is_yes(r["slither_detected"]))
    missed = sum(
        1
        for r in rows
        if not is_yes(r["slither_detected"]) and not is_yes(r["llm_flagged"])
    )
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
    lines = [
        "| 集合 | 案例数 | 基线检出 | LLM 提出 | LLM 新增 | 人工确认 | 误报 | 漏报 | 基线检出率 | LLM 精确率 |",
        "|---|---|---|---|---|---|---|---|---|---|",
    ]
    for r in results:
        lines.append(
            f"| {r['label']} | {r['cases']} | {r['baseline_detected']} | {r['llm_flagged']} | "
            f"{r['llm_extra']} | {r['confirmed']} | {r['false_positives']} | {r['missed']} | "
            f"{r['baseline_rate']:.0%} | {r['llm_precision']:.0%} |"
        )
    return "\n".join(lines)


def main():
    parser = argparse.ArgumentParser(description="Evaluate detection results")
    parser.add_argument("--cases", default="eval/cases.csv")
    parser.add_argument("--out", default="eval/eval_result.md")
    args = parser.parse_args()

    rows = load_cases(args.cases)
    pending = [r["case_id"] for r in rows if is_pending(r, "slither_detected")]

    results = []
    for split in ("debug", "eval"):
        subset = [r for r in rows if r.get("split", "").strip() == split and r["case_id"] not in pending]
        if subset:
            results.append(summarize(subset, split))
    complete = [r for r in rows if r["case_id"] not in pending]
    if complete:
        results.append(summarize(complete, "all"))

    table = render(results)
    note = (
        f"\n\n未填写（TODO）：{', '.join(pending)}" if pending else ""
    )
    text = "# 评估结果\n\n" + table + note + "\n"
    Path(args.out).write_text(text, encoding="utf-8")
    print(table)
    if pending:
        print(f"pending cases: {', '.join(pending)}")


if __name__ == "__main__":
    main()
