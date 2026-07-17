from __future__ import annotations

import json

from coredoc.changes import ChangeReport, report_to_text
from coredoc.cli import main
from coredoc.guidance import fix_footer, since_footer, suggested_next_command


def test_suggested_next_command_for_audio() -> None:
    assert suggested_next_command("audio") == "coredoc fix audio"


def test_doctor_json_includes_suggested_command(capsys) -> None:  # type: ignore[no-untyped-def]
    assert main(["--json", "--doctor", "clean"]) == 0
    payload = json.loads(capsys.readouterr().out)
    assert payload["suggested_next_command"] == "coredoc fix cleanup"


def test_fix_footer_mentions_tui_confirmation() -> None:
    footer = fix_footer()
    assert "TUI" in footer
    assert "ask" in footer


def test_since_report_has_next_step() -> None:
    text = report_to_text(ChangeReport("last-boot", "done", changes=["changed kernel"]))
    assert since_footer() in text
    assert "coredoc fix <problem>" in text
