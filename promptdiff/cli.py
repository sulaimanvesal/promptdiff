"""promptdiff CLI: ``python -m promptdiff old.txt new.txt``."""

from __future__ import annotations

import argparse
import json
import sys
from dataclasses import asdict

from .core import analyze, load_prompt


def build_parser() -> argparse.ArgumentParser:
    p = argparse.ArgumentParser(
        prog="promptdiff",
        description="Diff two LLM system prompts: stats, token/cost deltas, "
        "sentence-level changes, overlap score, and a unified diff.",
    )
    p.add_argument("old", help="Path to the old prompt file")
    p.add_argument("new", help="Path to the new prompt file")
    p.add_argument("--json", action="store_true", help="Emit the full report as JSON")
    p.add_argument(
        "--rate",
        type=float,
        default=3.00,
        metavar="USD_PER_MTOK",
        help="Input price in $/M tokens (default: 3.00)",
    )
    p.add_argument(
        "--no-diff",
        action="store_true",
        help="Skip the unified diff section (useful for huge prompts)",
    )
    return p


def format_report(report: dict) -> str:
    old, new = report["old"], report["new"]
    lines = [
        f"promptdiff: {old.name} -> {new.name}",
        "",
        "Stats (tokens are heuristic estimates):",
        f"  {'':28} chars   lines   words  tokens   est $/1k req*",
    ]
    for s in (old, new):
        lines.append(
            f"  {s.name[:26]:26} {s.chars:6d} {s.lines:7d} {s.words:7d} {s.tokens:7d}   ${s.est_input_cost_usd * 1000:9.4f}"
        )
    d = lambda k: report[k]  # noqa: E731
    sign = lambda v: f"{v:+d}"  # noqa: E731
    lines += [
        "",
        f"Deltas: tokens {sign(d('delta_tokens'))}, chars {sign(d('delta_chars'))}, "
        f"lines {sign(d('delta_lines'))}, est $/1k req {d('delta_est_cost_usd') * 1000:+.4f}",
        f"Jaccard word overlap: {report['jaccard_similarity']:.2%}",
        "",
        f"Changes: {report['num_added']} added, {report['num_removed']} removed, "
        f"{report['num_rewritten']} rewritten sentences",
    ]
    for label, key in (("Added", "added"), ("Removed", "removed")):
        for s in report["changes"][key]:
            lines.append(f"  [+{label[:1]}] {s}" if label == "Added" else f"  [-] {s}")
    for s in report["changes"]["rewritten"]:
        lines.append(f"  [~] {s}")
    lines.append("")
    lines.append("* cost assumes 1k input tokens per request at the given $/M-token rate")
    if not report.get("_skip_diff"):
        lines += ["", "Unified diff:", report["unified_diff"] or "(no line changes)"]
    return "\n".join(lines)


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    try:
        old = load_prompt(args.old)
        new = load_prompt(args.new)
    except OSError as exc:
        print(f"promptdiff: error: {exc}", file=sys.stderr)
        return 2

    report = analyze(old, new, args.old, args.new, args.rate)
    if args.no_diff:
        report["_skip_diff"] = True

    if args.json:
        payload = {k: (asdict(v) if hasattr(v, "__dataclass_fields__") else v) for k, v in report.items() if not k.startswith("_")}
        print(json.dumps(payload, indent=2))
    else:
        print(format_report(report))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
