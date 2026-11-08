"""Normalize Slither JSON output into a flat alert list."""

import argparse
import json
from pathlib import Path


IMPACT_ORDER = {"High": 3, "Medium": 2, "Low": 1, "Informational": 0, "Optimization": 0}


def detectors_of(payload):
    if isinstance(payload, list):
        return payload
    results = payload.get("results", payload)
    if isinstance(results, dict):
        return results.get("detectors", [])
    return []


def elements_of(detector):
    out = []
    for element in detector.get("elements", []):
        mapping = element.get("source_mapping", {})
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
    alerts = []
    for index, detector in enumerate(detectors_of(payload), start=1):
        elements = elements_of(detector)
        primary = next((e for e in elements if e["file"]), {})
        alerts.append(
            {
                "id": f"SL-{index:03d}",
                "detector": detector.get("check", ""),
                "impact": detector.get("impact", ""),
                "confidence": detector.get("confidence", ""),
                "description": " ".join(detector.get("description", "").split()),
                "file": primary.get("file", ""),
                "lines": primary.get("lines", []),
                "elements": elements,
                "status": "tool_alert",
            }
        )
    alerts.sort(key=lambda a: IMPACT_ORDER.get(a["impact"], 0), reverse=True)
    for index, alert in enumerate(alerts, start=1):
        alert["id"] = f"SL-{index:03d}"
    return alerts


def main():
    parser = argparse.ArgumentParser(description="Convert Slither JSON")
    parser.add_argument("--input", required=True, help="slither --json output file")
    parser.add_argument("--out", default="build/slither.json")
    args = parser.parse_args()

    payload = json.loads(Path(args.input).read_text(encoding="utf-8"))
    alerts = normalize(payload)

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps({"alerts": alerts}, ensure_ascii=False, indent=2), encoding="utf-8")

    counts = {}
    for alert in alerts:
        counts[alert["impact"]] = counts.get(alert["impact"], 0) + 1
    print(f"alerts={len(alerts)} by_impact={counts}")
    print(f"written: {out}")


if __name__ == "__main__":
    main()
