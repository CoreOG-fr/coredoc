from __future__ import annotations

import pytest

from coredoc.cli import main
from coredoc.tui.app import CoreDocApp


def test_cli_json_single_doctor(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["--json", "--doctor", "clean"])
    assert code == 0
    assert '"module": "clean"' in capsys.readouterr().out


@pytest.mark.asyncio
async def test_tui_instantiates_and_quits() -> None:
    app = CoreDocApp()
    async with app.run_test() as pilot:
        await pilot.pause(0.1)
        app.exit()
