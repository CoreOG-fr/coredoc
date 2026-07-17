from __future__ import annotations

import subprocess
from typing import Any

from textual import work
from textual.app import App, ComposeResult
from textual.containers import Horizontal, VerticalScroll
from textual.screen import ModalScreen
from textual.widgets import Button, Footer, Header, Label, LoadingIndicator, Static

from coredoc.doctors import DOCTORS
from coredoc.guidance import scenario_for_root_cause, what_next_for_module
from coredoc.models import DoctorResult, Severity
from coredoc.support_bundle import create_support_bundle
from coredoc.triage import TriageEngine
from coredoc.triage.models import GlobalDiagnosis, TriageAction

SEV_STYLE = {
    Severity.OK: "green",
    Severity.INFO: "cyan",
    Severity.WARN: "yellow",
    Severity.ERROR: "red",
    Severity.UNKNOWN: "magenta",
}


class ConfirmAction(ModalScreen[bool]):
    def __init__(self, action: TriageAction) -> None:
        super().__init__()
        self.action = action

    def compose(self) -> ComposeResult:
        yield Static(f"Ready to run: {self.action.title}")
        yield Static(self.action.description)
        yield Static(f"Safety: {self.action.safety}")
        yield Static("Command to run: " + " ".join(self.action.command))
        yield Button("Run this action", id="confirm-run", variant="warning")
        yield Button("Cancel", id="confirm-cancel")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss(event.button.id == "confirm-run")


class HelpScreen(ModalScreen[None]):
    def compose(self) -> ComposeResult:
        yield Static("coredoc help")
        yield Static(
            "Doctors inspect one part of the system. Global diagnosis connects their findings "
            "and ranks what to check first.\n\n"
            "Keys:\n"
            "  g  Global diagnosis\n"
            "  d  Per-module dashboard\n"
            "  f  Fix the top issue\n"
            "  r  Refresh checks\n"
            "  b  Write support bundle\n"
            "  h or ?  This help\n"
            "  q  Quit\n\n"
            "Fix actions marked safe still ask before they run."
        )
        yield Button("Close", id="help-close")

    def on_button_pressed(self, event: Button.Pressed) -> None:
        self.dismiss()


class ResultView(VerticalScroll):
    def __init__(self, result: DoctorResult, **kwargs: Any) -> None:
        super().__init__(**kwargs)
        self.result = result

    def compose(self) -> ComposeResult:
        color = SEV_STYLE.get(self.result.severity, "white")
        yield Static(f"[{color}]{self.result.title}: {self.result.severity.value.upper()}[/]")
        yield Static(self.result.summary)
        for finding in self.result.findings:
            fcolor = SEV_STYLE.get(finding.severity, "white")
            yield Static(f"\n[{fcolor}]■ {finding.title}[/]\n{finding.summary}")
            if finding.evidence:
                yield Static("Evidence:\n" + "\n".join(f"  - {e}" for e in finding.evidence[:6]))
            if finding.advice:
                yield Static("Advice:\n" + "\n".join(f"  - {a}" for a in finding.advice[:6]))
        yield Static("\n" + what_next_for_module(self.result.module))


class CoreDocApp(App[None]):
    CSS = """
    Screen { background: $surface; }
    #sidebar { width: 25; border: solid $primary; }
    #content { width: 1fr; border: solid $secondary; padding: 1 2; }
    #title { text-style: bold; }
    Button { margin: 1 1; }
    .banner { color: yellow; }
    .safe { color: green; }
    .manual { color: yellow; }
    .risky { color: red; }
    """
    BINDINGS = [
        ("q", "quit", "Quit"),
        ("g", "diagnosis", "Global diagnosis"),
        ("d", "dashboard", "Modules"),
        ("r", "refresh", "Refresh"),
        ("b", "bundle", "Support bundle"),
        ("f", "fix_top", "Fix top issue"),
        ("h", "help", "Help"),
        ("?", "help", "Help"),
    ]

    def __init__(self) -> None:
        super().__init__()
        self.current_view = "diagnosis"
        self.actions: dict[str, TriageAction] = {}
        self.latest_diagnosis: GlobalDiagnosis | None = None
        self.tip_shown = False

    def compose(self) -> ComposeResult:
        yield Header(show_clock=True)
        with Horizontal():
            with VerticalScroll(id="sidebar"):
                yield Label("coredoc v0.2")
                yield Button("Global Diagnosis", id="nav-diagnosis")
                yield Button("Module Dashboard", id="nav-dashboard")
                yield Button("Support Bundle", id="support-bundle")
                yield Button("Help", id="nav-help")
                for name in DOCTORS:
                    yield Button(name.title(), id=f"nav-{name}")
            with VerticalScroll(id="content"):
                yield Static(
                    "coredoc\nChecking your system and looking for the first useful thing to try..."
                )
        yield Footer()

    def on_mount(self) -> None:
        self.show_diagnosis_loading()

    def action_diagnosis(self) -> None:
        self.current_view = "diagnosis"
        self.show_diagnosis_loading()

    def action_dashboard(self) -> None:
        self.current_view = "dashboard"
        self.show_dashboard()

    def action_refresh(self) -> None:
        if self.current_view == "diagnosis":
            self.show_diagnosis_loading()
        elif self.current_view == "dashboard":
            self.show_dashboard()
        elif self.current_view in DOCTORS:
            self.show_doctor(self.current_view)
        elif self.current_view.startswith("fix:"):
            self.show_fix_loading(self.current_view.split(":", 1)[1])

    def action_bundle(self) -> None:
        bundle = create_support_bundle()
        self.notify(f"Support bundle written to {bundle}")

    def action_help(self) -> None:
        self.push_screen(HelpScreen())

    def action_fix_top(self) -> None:
        if not self.latest_diagnosis or not self.latest_diagnosis.root_causes:
            self.notify("No diagnosis is ready yet. Press r to refresh.", severity="warning")
            return
        scenario = scenario_for_root_cause(self.latest_diagnosis.root_causes[0])
        self.show_fix_loading(scenario)

    def show_diagnosis_loading(self) -> None:
        content = self._content()
        content.remove_children()
        content.mount(
            Static("coredoc\n\nChecking your system...\nFinding the first useful thing to try.")
        )
        content.mount(LoadingIndicator())
        self._run_diagnosis()

    @work(thread=True, exclusive=True)
    def _run_diagnosis(self) -> None:
        diagnosis = TriageEngine().diagnose()
        self.call_from_thread(self.show_diagnosis, diagnosis)

    def show_diagnosis(self, diagnosis: GlobalDiagnosis) -> None:
        self.current_view = "diagnosis"
        self.latest_diagnosis = diagnosis
        self.actions = {action.id: action for action in diagnosis.action_plan}
        content = self._content()
        content.remove_children()
        color = SEV_STYLE.get(diagnosis.severity, "white")
        content.mount(Static(f"[{color}]Global diagnosis: {diagnosis.severity.value.upper()}[/]"))
        content.mount(Static(diagnosis.summary))
        for banner in diagnosis.warning_banners:
            content.mount(Static(f"[yellow]⚠ {banner}[/]", classes="banner"))
        content.mount(Static("\nRoot-cause tree"))
        for idx, cause in enumerate(diagnosis.root_causes, 1):
            c = SEV_STYLE.get(cause.severity, "white")
            content.mount(Static(f"[{c}]{idx}. {cause.title} ({cause.severity.value})[/]"))
            content.mount(Static(f"   {cause.summary}"))
            content.mount(Static(f"   Affects: {', '.join(cause.affected_modules) or 'unknown'}"))
            for ev in cause.evidence[:4]:
                content.mount(Static(f"   └─ {ev}"))
        content.mount(Static("\nSuggested next steps"))
        if not diagnosis.action_plan:
            content.mount(Static("No direct safe action is available; review the evidence above."))
        for idx, action in enumerate(diagnosis.action_plan, 1):
            badge = f"[{action.safety}]".upper()
            cmd = " ".join(action.command) if action.command else "manual"
            content.mount(Static(f"{idx}. {badge} {action.title}: {action.description}\n   {cmd}"))
            if action.safety == "safe" and action.command:
                content.mount(
                    Button(f"Run: {action.title}", id=f"action-{action.id}", variant="success")
                )

        scenario = scenario_for_root_cause(
            diagnosis.root_causes[0] if diagnosis.root_causes else None
        )
        content.mount(
            Static(
                "\nWhat next? Press F to start a guided fix for the top issue "
                f"(`coredoc fix {scenario}`), or use the safe action buttons above. "
                "Every action asks before it runs."
            )
        )
        if not self.tip_shown:
            self.tip_shown = True
            self.notify("Tip: g = global, d = details, f = fix top issue, h = help")

    def show_fix_loading(self, scenario: str) -> None:
        self.current_view = f"fix:{scenario}"
        content = self._content()
        content.remove_children()
        content.mount(Static(f"Preparing a guided fix for: {scenario}"))
        content.mount(LoadingIndicator())
        self._run_fix_scenario(scenario)

    @work(thread=True, exclusive=True)
    def _run_fix_scenario(self, scenario: str) -> None:
        engine = TriageEngine()
        diagnosis = engine.diagnose(engine.run_doctors(scenario))
        self.call_from_thread(self.show_fix_diagnosis, scenario, diagnosis)

    def show_fix_diagnosis(self, scenario: str, diagnosis: GlobalDiagnosis) -> None:
        self.latest_diagnosis = diagnosis
        self.actions = {action.id: action for action in diagnosis.action_plan}
        content = self._content()
        content.remove_children()
        content.mount(Static(f"Fix: {scenario}"))
        content.mount(Static(diagnosis.summary))
        content.mount(Static("\nAction plan"))
        if not diagnosis.action_plan:
            content.mount(Static("No direct safe action is available. Review the evidence below."))
        for idx, action in enumerate(diagnosis.action_plan, 1):
            cmd = " ".join(action.command) if action.command else "manual"
            content.mount(
                Static(f"{idx}. [{action.safety}] {action.title}: {action.description}\n   {cmd}")
            )
            if action.safety == "safe" and action.command:
                content.mount(
                    Button(f"Run: {action.title}", id=f"action-{action.id}", variant="success")
                )
        content.mount(Static("\nEvidence"))
        for cause in diagnosis.root_causes[:5]:
            content.mount(Static(f"- {cause.title}: {cause.summary}"))
        content.mount(
            Static(
                "\nWhat next? Run safe buttons one at a time, or press G to return to global diagnosis."
            )
        )

    def show_dashboard(self) -> None:
        content = self._content()
        content.remove_children()
        content.mount(Static("coredoc per-module dashboard"))
        for name, cls in DOCTORS.items():
            try:
                result = cls("").run() if name == "clean" else cls().run()
                color = SEV_STYLE.get(result.severity, "white")
                content.mount(
                    Static(
                        f"[{color}]{name:12} {result.severity.value.upper():7}[/] {result.summary}"
                    )
                )
            except Exception as exc:
                content.mount(Static(f"[red]{name:12} ERROR[/] {exc}"))

    def show_doctor(self, name: str) -> None:
        self.current_view = name
        content = self._content()
        content.remove_children()
        cls = DOCTORS[name]
        result = cls("").run() if name == "clean" else cls().run()
        content.mount(ResultView(result))

    def on_button_pressed(self, event: Button.Pressed) -> None:
        bid = event.button.id or ""
        if bid == "nav-diagnosis":
            self.action_diagnosis()
        elif bid == "nav-dashboard":
            self.action_dashboard()
        elif bid == "support-bundle":
            self.action_bundle()
        elif bid == "nav-help":
            self.action_help()
        elif bid.startswith("nav-"):
            name = bid.removeprefix("nav-")
            if name in DOCTORS:
                self.show_doctor(name)
        elif bid.startswith("action-"):
            action_id = bid.removeprefix("action-")
            action = self.actions.get(action_id)
            if action:
                self.push_screen(ConfirmAction(action), self._execute_if_confirmed(action))

    def _execute_if_confirmed(self, action: TriageAction):  # type: ignore[no-untyped-def]
        def callback(confirmed: bool) -> None:
            if not confirmed:
                return
            if action.safety != "safe" or not action.command:
                self.notify("This action is not marked safe for the TUI.", severity="warning")
                return
            proc = subprocess.run(
                action.command, check=False, capture_output=True, text=True, timeout=15
            )
            if proc.returncode == 0:
                self.notify(f"Action succeeded: {action.title}")
            else:
                self.notify(
                    f"Action failed ({proc.returncode}): {proc.stderr[:120]}", severity="error"
                )
            self.show_diagnosis_loading()

        return callback

    def _content(self) -> VerticalScroll:
        return self.query_one("#content", VerticalScroll)
