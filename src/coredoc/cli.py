from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from coredoc.changes import ChangeDetector, report_to_text
from coredoc.doctors import DOCTORS
from coredoc.guidance import suggested_next_command
from coredoc.support_bundle import create_support_bundle
from coredoc.triage import TriageEngine, diagnosis_to_text
from coredoc.tui.app import CoreDocApp


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="coredoc",
        description="Find likely Linux root causes from the terminal.",
        epilog=(
            "Common flows: coredoc fix audio | coredoc fix screenshare | "
            "coredoc fix sleep-drain | coredoc since last-boot"
        ),
    )
    sub = parser.add_subparsers(dest="command")
    fix = sub.add_parser("fix", help="show likely causes for a symptom and the next best checks")
    fix.add_argument(
        "problem",
        help="what hurts: audio, screenshare, sleep-drain, network, system, cleanup, hardware, or permissions",
    )
    fix.add_argument("--json", action="store_true", help="print JSON instead of text")
    since = sub.add_parser("since", help="summarize logs and package activity for a timeframe")
    since.add_argument(
        "timeframe", help="last-boot, today, yesterday, 24h, 1h, or a journalctl-style time"
    )
    since.add_argument("--json", action="store_true", help="print JSON instead of text")
    parser.add_argument(
        "--json",
        action="store_true",
        help="print doctor output as JSON instead of opening the TUI",
    )
    parser.add_argument("--doctor", choices=sorted(DOCTORS), help="run one doctor by name")
    parser.add_argument("--app", default="", help="app name for the clean doctor, such as firefox")
    parser.add_argument(
        "--support-bundle",
        action="store_true",
        help="write a sanitized support bundle you can review and share",
    )
    parser.add_argument("--output-dir", default=".", help="where to write the support bundle")
    return parser


def main(argv: list[str] | None = None) -> int:
    args = build_parser().parse_args(argv)
    if args.command == "fix":
        engine = TriageEngine()
        diagnosis = engine.diagnose(engine.run_doctors(args.problem))
        payload = diagnosis.as_dict()
        payload["suggested_next_command"] = f"coredoc fix {args.problem}"
        print(json.dumps(payload, indent=2) if args.json else diagnosis_to_text(diagnosis))
        return 0
    if args.command == "since":
        report = ChangeDetector(args.timeframe).run_report()
        payload = report.as_dict()
        payload["suggested_next_command"] = "coredoc fix <problem>"
        print(json.dumps(payload, indent=2) if args.json else report_to_text(report))
        return 0
    if args.support_bundle:
        print(create_support_bundle(Path(args.output_dir)))
        return 0
    if args.json:
        doctors = [args.doctor] if args.doctor else list(DOCTORS)
        results = []
        for name in doctors:
            cls = DOCTORS[name]
            result = cls(args.app).run() if name == "clean" else cls().run()
            results.append(_with_guidance(result.as_dict(), name))
        print(json.dumps(results[0] if args.doctor else results, indent=2))
        return 0
    try:
        CoreDocApp().run()
    except Exception as exc:
        print(f"coredoc could not open the TUI: {exc}", file=sys.stderr)
        print("Try a CLI path instead, for example: coredoc fix audio", file=sys.stderr)
        return 1
    return 0


def _with_guidance(payload: dict[str, Any], module: str) -> dict[str, Any]:
    payload["suggested_next_command"] = suggested_next_command(module)
    return payload


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
