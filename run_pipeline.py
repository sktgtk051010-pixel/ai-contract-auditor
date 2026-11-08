"""Run the full pipeline: scan -> normalize -> build input -> analyze."""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent


def run(script, args):
    command = [sys.executable, str(ROOT / script), *args]
    print(">", " ".join(command))
    result = subprocess.run(command, cwd=ROOT)
    if result.returncode != 0:
        raise SystemExit(f"step failed: {script}")


def main():
    parser = argparse.ArgumentParser(description="Run audit pipeline")
    parser.add_argument("--target", required=True, help="directory with .sol files")
    parser.add_argument("--slither", default="", help="raw slither --json output, optional")
    parser.add_argument("--analyze", action="store_true", help="call the LLM API instead of dry-run")
    parser.add_argument("--limit", type=int, default=0)
    args = parser.parse_args()

    run("src/scan.py", ["--target", args.target, "--out", "build/scan.json"])

    if args.slither:
        run("src/convert_slither.py", ["--input", args.slither, "--out", "build/slither.json"])
    else:
        Path(ROOT / "build").mkdir(exist_ok=True)
        (ROOT / "build" / "slither.json").write_text('{"alerts": []}', encoding="utf-8")
        print("no --slither given: alerts left empty")

    run("src/build_input.py", ["--scan", "build/scan.json", "--slither", "build/slither.json"])

    analyze_args = ["--input", "build/analysis_input.json"]
    if not args.analyze:
        analyze_args.append("--dry-run")
    if args.limit:
        analyze_args += ["--limit", str(args.limit)]
    run("src/analyze.py", analyze_args)


if __name__ == "__main__":
    main()
