"""一键跑完四步：扫描 -> 归一化告警 -> 合并 -> 分析。

用法：
    python run_pipeline.py --target D:\\项目\\src
    python run_pipeline.py --target D:\\项目\\src --slither slither_raw.json
    python run_pipeline.py --target D:\\项目\\src --slither slither_raw.json --analyze --limit 10
"""

import argparse
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent   # 本文件所在目录 = 项目根


def run(script, args):
    """调用一个子脚本；它返回非 0 就停，不带着错误继续往下跑。"""
    command = [sys.executable, str(ROOT / script), *args]   # sys.executable = 当前 python 解释器
    print(">", " ".join(command))                           # 打印出来，方便知道在跑什么
    result = subprocess.run(command, cwd=ROOT)              # 相当于 C 的 system()，但能拿返回值
    if result.returncode != 0:
        raise SystemExit(f"step failed: {script}")          # 某一步失败，整体退出


def main():
    parser = argparse.ArgumentParser(description="Run audit pipeline")
    parser.add_argument("--target", required=True, help="directory with .sol files")
    parser.add_argument("--slither", default="", help="raw slither --json output, optional")
    parser.add_argument("--analyze", action="store_true", help="call the LLM API instead of dry-run")
    parser.add_argument("--limit", type=int, default=0, help="analyze first N units only")
    args = parser.parse_args()

    # 第 1 步：扫源码，得到 build/scan.json
    run("src/scan.py", ["--target", args.target, "--out", "build/scan.json"])

    # 第 2 步：有 Slither 输出就归一化；没有就写一个空告警文件
    if args.slither:
        run("src/convert_slither.py", ["--input", args.slither, "--out", "build/slither.json"])
    else:
        Path(ROOT / "build").mkdir(exist_ok=True)
        (ROOT / "build" / "slither.json").write_text('{"alerts": []}', encoding="utf-8")
        print("no --slither given: alerts left empty")

    # 第 3 步：合并成分分析单元
    run("src/build_input.py", ["--scan", "build/scan.json", "--slither", "build/slither.json"])

    # 第 4 步：调 LLM；不加 --analyze 就只生成提示词
    analyze_args = ["--input", "build/analysis_input.json"]
    if not args.analyze:
        analyze_args.append("--dry-run")
    if args.limit:
        analyze_args += ["--limit", str(args.limit)]
    run("src/analyze.py", analyze_args)


if __name__ == "__main__":
    main()
