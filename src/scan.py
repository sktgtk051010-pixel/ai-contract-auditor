"""Extract structure and risk markers from Solidity sources into JSON."""

import argparse
import json
import re
from pathlib import Path

CONTRACT_RE = re.compile(r"\b(contract|library|interface)\s+(\w+)")
FUNCTION_RE = re.compile(r"\bfunction\s+(\w+)\s*\(")
PRAGMA_RE = re.compile(r"pragma\s+solidity\s+([^;]+);")
VISIBILITY = ("external", "public", "internal", "private")
SKIP_MODIFIERS = set(VISIBILITY) | {"returns", "override", "virtual", "payable"}
LOW_LEVEL_PATTERNS = {
    ".call{": "call",
    ".call(": "call",
    ".delegatecall": "delegatecall",
    ".staticcall": "staticcall",
    ".send(": "send",
}
SAFE_ERC20 = ("safeTransfer(", "safeTransferFrom(", "safeApprove(", "safeIncreaseAllowance(")


def strip_comments(text):
    """Blank out comments while preserving line numbers."""
    def blank(match):
        return re.sub(r"[^\n]", " ", match.group(0))

    text = re.sub(r"/\*.*?\*/", blank, text, flags=re.S)
    text = re.sub(r"//[^\n]*", blank, text)
    return text


def line_number(text, offset):
    return text.count("\n", 0, offset) + 1


def match_paren(text, start):
    """Return index just past the matching ')' for the '(' at start."""
    depth = 0
    i = start
    while i < len(text):
        if text[i] == "(":
            depth += 1
        elif text[i] == ")":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    return len(text)


def match_brace(text, start):
    """Return index of the matching '}' for the '{' at start."""
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
    return [
        {"name": m.group(2), "kind": m.group(1), "line": line_number(text, m.start())}
        for m in CONTRACT_RE.finditer(text)
    ]


def parse_functions(text):
    functions = []
    for m in FUNCTION_RE.finditer(text):
        name = m.group(1)
        start = m.start()
        tail_start = match_paren(text, m.end() - 1)
        j = tail_start
        while j < len(text) and text[j] not in "{;":
            j += 1
        if j >= len(text):
            continue
        signature = " ".join(text[start:j].split())
        tail = re.split(r"\breturns\b", text[tail_start:j])[0]
        modifiers = [
            word
            for word in re.findall(r"\b([A-Za-z_]\w*)\b", tail)
            if word not in SKIP_MODIFIERS
        ]
        visibility = next((v for v in VISIBILITY if re.search(rf"\b{v}\b", tail)), "internal")

        if text[j] == "{":
            end = match_brace(text, j)
            body = text[j : end + 1]
            end_line = line_number(text, end)
        else:
            body = ""
            end_line = line_number(text, j)

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
    for fn in functions:
        owner = None
        for item in contracts:
            if item["line"] <= fn["line"]:
                owner = item["name"]
        fn["contract"] = owner


def scan_file(path, root):
    raw = path.read_text(encoding="utf-8", errors="replace")
    text = strip_comments(raw)
    pragma = PRAGMA_RE.search(text)
    contracts = parse_contracts(text)
    functions = parse_functions(text)
    attach_contracts(functions, contracts)
    rel = path.relative_to(root).as_posix()
    return {
        "path": rel,
        "lines": raw.count("\n") + 1,
        "pragma": pragma.group(1).strip() if pragma else "",
        "contracts": contracts,
        "functions": functions,
    }


def scan(root):
    files = [scan_file(p, root) for p in sorted(root.rglob("*.sol"))]
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
    parser = argparse.ArgumentParser(description="Scan Solidity sources")
    parser.add_argument("--target", required=True, help="directory containing .sol files")
    parser.add_argument("--out", default="build/scan.json", help="output json path")
    args = parser.parse_args()

    root = Path(args.target).resolve()
    if not root.is_dir():
        raise SystemExit(f"target not a directory: {root}")

    result = scan(root)
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(json.dumps(result, ensure_ascii=False, indent=2), encoding="utf-8")

    summary = result["summary"]
    print(
        f"files={summary['files']} contracts={summary['contracts']} "
        f"functions={summary['functions']} external={summary['external_functions']} "
        f"low_level={summary['low_level_call_functions']}"
    )
    print(f"written: {out}")


if __name__ == "__main__":
    main()
