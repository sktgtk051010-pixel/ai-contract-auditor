"""Merge scan.json and slither.json into per-function analysis units."""

import argparse
import json
from pathlib import Path

MAX_SOURCE_LINES = 120


def load(path, default):
    p = Path(path)
    if not p.exists():
        return default
    return json.loads(p.read_text(encoding="utf-8"))


def read_snippet(root, rel_path, start, end):
    """Read a line range from the original source, capped for prompt size."""
    path = Path(root) / rel_path
    if not path.exists():
        return ""
    lines = path.read_text(encoding="utf-8", errors="replace").splitlines()
    first = max(0, start - 1)
    last = min(len(lines), end)
    if last - first > MAX_SOURCE_LINES:
        last = first + MAX_SOURCE_LINES
    return "\n".join(f"{i + 1:5d}| {lines[i]}" for i in range(first, last))


def assign_alerts(alerts, files_index):
    """Attach each alert to the function whose body covers its first line."""
    assigned = {}
    unassigned = []
    for alert in alerts:
        rel = alert["file"]
        lines = alert.get("lines") or []
        entry = files_index.get(rel)
        if not entry or not lines:
            unassigned.append(alert)
            continue
        target = lines[0]
        match = None
        for fn in entry["functions"]:
            if fn["line"] <= target <= fn.get("end_line", fn["line"]):
                if match is None or fn["line"] > match["line"]:
                    match = fn
        if match:
            assigned.setdefault((rel, match["name"], match["line"]), []).append(alert)
        else:
            unassigned.append(alert)
    return assigned, unassigned


def build(scan_data, slither_data):
    root = scan_data["root"]
    files_index = {f["path"]: f for f in scan_data["files"]}
    alerts = slither_data.get("alerts", []) if slither_data else []
    assigned, unassigned = assign_alerts(alerts, files_index)

    units = []
    for path, entry in files_index.items():
        for fn in entry["functions"]:
            if fn["visibility"] not in ("external", "public"):
                continue
            key = (path, fn["name"], fn["line"])
            units.append(
                {
                    "id": f"CH-{len(units) + 1:03d}",
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
    parser = argparse.ArgumentParser(description="Build LLM analysis input")
    parser.add_argument("--scan", default="build/scan.json")
    parser.add_argument("--slither", default="build/slither.json")
    parser.add_argument("--out", default="build/analysis_input.json")
    args = parser.parse_args()

    scan_data = load(args.scan, None)
    if scan_data is None:
        raise SystemExit(f"missing scan file: {args.scan} (run scan.py first)")
    slither_data = load(args.slither, {"alerts": []})

    result = build(scan_data, slither_data)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")
    print(f"units={result['summary']['units']} alerts_assigned={result['summary']['alerts_assigned']}")
    print(f"written: {out}")


if __name__ == "__main__":
    main()
