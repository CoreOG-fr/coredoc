from __future__ import annotations

import shutil
import subprocess
from collections.abc import Sequence
from dataclasses import dataclass


@dataclass(frozen=True)
class CommandResult:
    argv: tuple[str, ...]
    returncode: int
    stdout: str
    stderr: str
    missing: bool = False


class CommandRunner:
    """Run system commands in the one boring, safe way coredoc expects."""

    def run(self, argv: Sequence[str], timeout: float = 5.0) -> CommandResult:
        if not argv:
            raise ValueError("argv must not be empty")
        exe = argv[0]
        if shutil.which(exe) is None:
            return CommandResult(tuple(argv), 127, "", f"missing command: {exe}", True)
        try:
            proc = subprocess.run(
                list(argv),
                check=False,
                capture_output=True,
                text=True,
                timeout=timeout,
            )
        except subprocess.TimeoutExpired as exc:
            stdout = exc.stdout.decode() if isinstance(exc.stdout, bytes) else (exc.stdout or "")
            stderr = (
                exc.stderr.decode() if isinstance(exc.stderr, bytes) else (exc.stderr or "timeout")
            )
            return CommandResult(tuple(argv), 124, stdout, stderr)
        return CommandResult(tuple(argv), proc.returncode, proc.stdout, proc.stderr)
