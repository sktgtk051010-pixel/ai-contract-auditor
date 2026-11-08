"""把分析单元发给 LLM，拿回风险假设。

两个模式：
- --dry-run：只把提示词写到 build/prompts/，不联网、不花钱
- 默认（真跑）：读 LLM_API_KEY，调 OpenAI 兼容接口

LLM 只负责"提假设"，不负责下结论。status 一律写成 unconfirmed。
"""

import argparse
import json
import os
import re
import string
import time
import urllib.error
import urllib.request
from pathlib import Path

# 项目根目录：本文件在 src/ 下，往上退一级
ROOT = Path(__file__).resolve().parent.parent

# 提示词模板里的占位符长这样：$file $function $source
TEMPLATE = string.Template(
    (ROOT / "prompts" / "risk_analysis.md").read_text(encoding="utf-8")
)

# 调接口用的配置，从环境变量读；没配就用默认值
API_URL = os.environ.get("LLM_BASE_URL", "https://api.openai.com/v1").rstrip("/")
MODEL = os.environ.get("LLM_MODEL", "gpt-4o-mini")
API_KEY = os.environ.get("LLM_API_KEY", "")


def format_alerts(alerts):
    """把告警列表压成几行文字，塞进提示词。没有告警就写一句说明。"""
    if not alerts:
        return "(no static analysis alert attached)"
    lines = []
    for alert in alerts:
        lines.append(
            f"- [{alert.get('id', '')}] {alert.get('detector', '')} "
            f"impact={alert.get('impact', '')} lines={alert.get('lines', [])}: "
            f"{alert.get('description', '')}"
        )
    return "\n".join(lines)


def build_prompt(unit):
    """把分析单元填进模板，生成完整提示词。"""
    return TEMPLATE.substitute(
        file=unit["file"],
        contract=unit["contract"],
        function=unit["function"],
        visibility=unit["visibility"],
        modifiers=", ".join(unit["modifiers"]) or "(none)",
        alerts=format_alerts(unit["alerts"]),
        source=unit["source"],
    )


def extract_json(text):
    """从模型回复里抠出 JSON 对象。

    模型有时会说"好的，这是结果"再跟代码块，所以不能直接 json.loads。
    做法：找第一个 { 和最后一个 }，把中间部分截出来再解析。
    """
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object in response")
    return json.loads(text[start : end + 1])


def call_api(prompt, retries=3):
    """调 /chat/completions，失败重试。返回 (解析后的 JSON, 原始文本)。"""
    body = json.dumps(
        {
            "model": MODEL,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0.2,        # 低温度让输出更稳定，不要天马行空
        }
    ).encode("utf-8")

    request = urllib.request.Request(
        f"{API_URL}/chat/completions",
        data=body,
        headers={
            "Content-Type": "application/json",
            "Authorization": f"Bearer {API_KEY}",   # 鉴权头
        },
    )

    last_error = None
    for attempt in range(retries):
        try:
            # timeout=60 表示 60 秒没响应就放弃
            with urllib.request.urlopen(request, timeout=60) as response:
                payload = json.loads(response.read().decode("utf-8"))
            raw = payload["choices"][0]["message"]["content"]
            return extract_json(raw), raw
        except (urllib.error.URLError, TimeoutError, KeyError, ValueError) as exc:
            last_error = exc
            time.sleep(1.5)            # 歇一下再试，避免连续打
    raise RuntimeError(f"api failed after {retries} attempts: {last_error}")


def analyze_unit(unit, dry_run):
    """处理一个分析单元，返回一条 finding。"""
    prompt = build_prompt(unit)

    if dry_run:
        # 只写提示词，不联网
        path = ROOT / "build" / "prompts" / f"{unit['id']}.txt"
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(prompt, encoding="utf-8")
        return {"unit_id": unit["id"], "status": "unconfirmed", "dry_run": True}

    try:
        data, raw = call_api(prompt)
        finding = {
            "unit_id": unit["id"],
            "file": unit["file"],
            "contract": unit["contract"],
            "function": unit["function"],
            "line_start": unit["line_start"],
            "line_end": unit["line_end"],
            "risk_hypothesis": data.get("risk_hypothesis", ""),
            "code_evidence": data.get("code_evidence", []),
            "preconditions": data.get("preconditions", []),
            "verification_suggestion": data.get("verification_suggestion", ""),
            "severity_guess": data.get("severity_guess", ""),
            "confidence": data.get("confidence", 0),
            "status": "unconfirmed",       # 等人工复核，不在这里下结论
            "raw": raw,
        }
        return finding
    except (RuntimeError, ValueError, KeyError) as exc:
        # 调用失败或解析失败，标记为不可验证，保留错误信息方便排查
        return {
            "unit_id": unit["id"],
            "file": unit["file"],
            "function": unit["function"],
            "status": "unverifiable",
            "error": str(exc),
        }


def main():
    """命令行入口：python src/analyze.py --input build/analysis_input.json [--dry-run]"""
    parser = argparse.ArgumentParser(description="Analyze units with an LLM")
    parser.add_argument("--input", default="build/analysis_input.json")
    parser.add_argument("--out", default="build/llm_findings.json")
    parser.add_argument("--dry-run", action="store_true", help="only write prompts")
    parser.add_argument("--limit", type=int, default=0, help="analyze first N units only")
    args = parser.parse_args()

    units = json.loads(Path(args.input).read_text(encoding="utf-8"))["units"]
    if args.limit > 0:
        units = units[: args.limit]        # 只取前 N 个，省钱

    if not args.dry_run and not API_KEY:
        raise SystemExit("LLM_API_KEY not set; use --dry-run or export the key")

    findings = [analyze_unit(unit, args.dry_run) for unit in units]

    if args.dry_run:
        print(f"dry-run: wrote {len(findings)} prompts to build/prompts")
        return

    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(
        json.dumps({"findings": findings}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )
    confirmed = sum(1 for f in findings if f["status"] == "unverifiable")
    print(f"findings={len(findings)} failed={confirmed}")
    print(f"written: {out}")


if __name__ == "__main__":
    main()
