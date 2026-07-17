from __future__ import annotations

import io
import json
import re
import tarfile
from datetime import datetime, timezone
from pathlib import Path
from tempfile import TemporaryDirectory

from coredoc.doctors import DOCTORS
from coredoc.models import DoctorResult

_SECRET_PATTERNS = [
    re.compile(r"(?i)(password|passwd|token|secret|apikey|api_key)=\S+"),
    re.compile(r"(?i)authorization:\s*\S+"),
]


def sanitize(text: str) -> str:
    out = text
    for pat in _SECRET_PATTERNS:
        out = pat.sub(
            lambda m: (
                m.group(0).split("=", 1)[0] + "=<redacted>"
                if "=" in m.group(0)
                else "authorization: <redacted>"
            ),
            out,
        )
    return out


def gather_all() -> list[DoctorResult]:
    results: list[DoctorResult] = []
    for name, cls in DOCTORS.items():
        if name == "clean":
            results.append(cls("").run())
        else:
            results.append(cls().run())
    return results


def create_support_bundle(output_dir: Path | None = None) -> Path:
    output_dir = output_dir or Path.cwd()
    output_dir.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    bundle = output_dir / f"coredoc-support-{stamp}.tar.gz"
    results = [r.as_dict() for r in gather_all()]
    data = sanitize(json.dumps({"generated_at": stamp, "results": results}, indent=2))
    with tarfile.open(bundle, "w:gz") as tf:
        payload = data.encode("utf-8")
        info = tarfile.TarInfo("coredoc-report.json")
        info.size = len(payload)
        tf.addfile(info, io.BytesIO(payload))
        with TemporaryDirectory() as td:
            p = Path(td) / "README.txt"
            p.write_text(
                "Sanitised coredoc diagnostic bundle. Review before sharing.\n", encoding="utf-8"
            )
            tf.add(p, arcname="README.txt")
    return bundle
