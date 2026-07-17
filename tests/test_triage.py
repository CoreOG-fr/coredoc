from __future__ import annotations

from coredoc.models import DoctorResult, Finding, Severity
from coredoc.triage import TriageEngine


def result(module: str, findings: list[Finding]) -> DoctorResult:
    return DoctorResult(module, module.title(), "summary", Severity.WARN, {}, findings)


def test_pipewire_rule_correlates_audio_and_wayland() -> None:
    diagnosis = TriageEngine().diagnose(
        {
            "audio": result(
                "audio",
                [
                    Finding(
                        "audio.server_unreachable",
                        "Audio server is unreachable",
                        Severity.ERROR,
                        "pactl failed",
                    )
                ],
            ),
            "wayland": result(
                "wayland",
                [
                    Finding(
                        "wayland.pipewire_inactive",
                        "PipeWire inactive",
                        Severity.WARN,
                        "screen capture unavailable",
                    )
                ],
            ),
        }
    )
    assert diagnosis.root_causes[0].id == "pipewire_stack"
    assert {"audio", "wayland"}.issubset(set(diagnosis.root_causes[0].affected_modules))
    assert any(action.id == "restart_pipewire" for action in diagnosis.action_plan)


def test_disk_rule_ranks_above_pipewire() -> None:
    diagnosis = TriageEngine().diagnose(
        {
            "core": result(
                "core",
                [
                    Finding(
                        "core.disk_usage_critical",
                        "Disk Usage Critical",
                        Severity.ERROR,
                        "root is full",
                    )
                ],
            ),
            "audio": result(
                "audio",
                [
                    Finding(
                        "audio.server_unreachable",
                        "Audio server is unreachable",
                        Severity.ERROR,
                        "pactl failed",
                    )
                ],
            ),
        }
    )
    assert diagnosis.root_causes[0].id == "disk_exhaustion"
    assert diagnosis.severity == Severity.ERROR


def test_no_major_root_cause_for_ok_results() -> None:
    diagnosis = TriageEngine().diagnose(
        {
            "core": DoctorResult(
                "core",
                "Core",
                "ok",
                Severity.OK,
                {},
                [Finding("core.system_running", "System running", Severity.OK, "ok")],
            )
        }
    )
    assert diagnosis.root_causes[0].id == "no_major_root_cause"
