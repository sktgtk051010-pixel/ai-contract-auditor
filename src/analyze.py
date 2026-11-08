"""Run LLM-assisted risk hypothesis generation over analysis units."""

import argparse
import json
import os
import time
import urllib.error
import urllib.request
from pathlib import Path
from string import Template

DEFAULT_MODEL = "gpt-4o-mini"
DEFAULT_BASE = "https://api.openai.com/v1"


def load_units(path):
    return json.loads(Path(path).read_text(encoding="utf-8"))


def render(template, unit):
    alerts = "\n".join(
        f"- {a['id']} [{a['impact']}/{a['confidence']}] {a['detector']}: {a['description']}"
        for a in unit["alerts"]
    ) or "(no static analysis alert attached)"
    return template.safe_substitute(
        file=unit["file"],
        contract=unit["contract"],
        function=unit["function"],
        visibility=unit["visibility"],
        modifiers=", ".join(unit["modifiers"]) or "none",
        alerts=alerts,
        source=unit["source"],
    )


def extract_json(text):
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no json object found")
    return json.loads(text[start : end + 1])


def call_api(prompt, api_key, base_url, model, timeout=90):
    payload = {
        "model": model,
        "temperature": 0.2,
        "messages": [
            {
                "role": "system",
                "content": (
                    "You are a smart contract security assistant. "
                    "Only propose risk hypotheses grounded in the given source lines. "
                    "Never invent code, line numbers, or findings."
                ),
            },
            {"role": "user", "content": prompt},
        ],
    }
    request = urllib.request.Request(
        f"{base_url.rstrip('/')}/chat/completions",
        data=json.dumps(payload).encode("utf-8"),
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {api_key}",
        },
        method="POST",
    )
    with urllib.request.urlopen(request, timeout=timeout) as response:
        body = json.loads(response.read().decode("utf-8"))
    return body["choices"][0]["message"]["content"]


def analyze_unit(unit, template, api_key, base_url, model):
    prompt = render(template, unit)
    last_error = None
    for _ in range(3):
        try:
            content = call_api(prompt, api_key, base_url, model)
            data = extract_json(content)
            return {
                "unit_id": unit["id"],
                "file": unit["file"],
                "function": unit["function"],
                "risk_hypothesis": data.get("risk_hypothesis", ""),
                "code_evidence": data.get("code_evidence", []),
                "preconditions": data.get("preconditions", []),
                "verification_suggestion": data.get("verification_suggestion", ""),
                "severity_guess": data.get("severity_guess", "Low"),
                "confidence": data.get("confidence", 0.0),
                "status": "unconfirmed",
                "raw_ok": True,
            }
        except (urllib.error.URLError, TimeoutError, ValueError, KeyError) as exc:
            last_error = str(exc)
            time.sleep(1.5)
    return {
        "unit_id": unit["id"],
        "file": unit["file"],
        "function": unit["function"],
        "risk_hypothesis": "",
        "code_evidence": [],
        "preconditions": [],
        "verification_suggestion": "",
        "severity_guess": "",
        "confidence": 0.0,
        "status": "unverifiable",
        "raw_ok": False,
        "error": last_error,
    }


def main():
    parser = argparse.ArgumentParser(description="LLM-assisted risk analysis")
    parser.add_argument("--input", default="build/analysis_input.json")
    parser.add_argument("--out", default="build/llm_findings.json")
    parser.add_argument("--template", default="prompts/risk_analysis.md")
    parser.add_argument("--dry-run", action="store_true", help="write prompts only, no API call")
    parser.add_argument("--limit", type=int, default=0, help="analyze first N units only")
    args = parser.parse_args()

    payload = load_units(args.input)
    units = payload["units"]
    if args.limit:
        units = units[: args.limit]

    template = Template(Path(args.template).read_text(encoding="utf-8"))

    if args.dry_run:
        out_dir = Path("build/prompts")
        out_dir.mkdir(parents=True, exist_ok=True)
        for unit in units:
            (out_dir / f"{unit['id']}.txt").write_text(render(template, unit), encoding="utf-8")
        print(f"dry-run: wrote {len(units)} prompts to {out_dir}")
        return

    api_key = os.environ.get("LLM_API_KEY", "")
    if not api_key:
        raise SystemExit("LLM_API_KEY is not set; use --dry-run or export the key")

    base_url = os.environ.get("LLM_BASE_URL", DEFAULT_BASE)
    model = os.environ.get("LLM_MODEL", DEFAULT_MODEL)

    findings = []
    for index, unit in enumerate(units, start=1):
        findings.append(analyze_unit(unit, template, api_key, base_url, model))
        print(f"[{index}/{len(units)}] {unit['id']} {unit['function']}")

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"model": model, "findings": findings}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    ok = sum(1 for f in findings if f["raw_ok"])
    print(f"findings={len(findings)} parsed={ok} written: {out}")


if __name__ == "__main__":
    main()
