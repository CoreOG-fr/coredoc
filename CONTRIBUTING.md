# Contributing to coredoc

Thanks for wanting to help. coredoc is for the moments when Linux gives you five clues in five places and none of them say what to do next. Good contributions make that experience less lonely.

## Set up a dev checkout

```bash
git clone https://github.com/CoreOG-fr/coredoc.git
cd coredoc
python3 -m pip install --user -e . pytest pytest-cov pytest-asyncio ruff black isort mypy textual
make test lint
```

If your distro complains about user installs, use a virtual environment.

## Add or improve a doctor

Doctors live in:

```text
src/coredoc/doctors/
```

A doctor should:

1. Run read-only checks only.
2. Use `BaseDoctor.cmd()` for commands. It handles missing tools, timeouts, and `shell=False`.
3. Return a `DoctorResult` with useful `facts` and at least one `Finding`.
4. Treat missing optional tools as information, not a crash.
5. Explain what the evidence means in plain language.

A good finding answers four questions:

- What did coredoc see?
- Why might it matter?
- What evidence backs it up?
- What should the user check next?

## Add a triage rule

Rules live in:

```text
src/coredoc/triage/rules.toml
```

Use a rule when several doctor findings point to the same root cause. For example, PipeWire can explain both broken audio and broken Wayland screen sharing.

A rule needs:

- a stable `id`
- `finding_ids` to match
- a short title and summary
- confidence and impact scores
- affected modules
- optional actions

Only mark an action as `safe` if it is low-risk, reversible, and okay to run after a confirmation prompt. Restarting a user service is usually safe. Editing configs, installing packages, deleting files, and changing kernel parameters are not.

## Add tests

Use focused tests. Mock doctor results when testing triage. Avoid tests that depend on your personal laptop hardware.

```bash
python3 -m pytest tests/test_triage.py
make test lint
```

## Writing style

The reader may be annoyed, tired, or trying to fix a machine during a call. Be direct and kind.

Prefer:

> PipeWire is not reachable, so apps cannot see an audio server.

Avoid:

> The PipeWire subsystem appears to be unavailable, which may impact audio capabilities.

## Safety rules

- Do not run commands through a shell.
- Do not add automatic destructive actions.
- Do not hide permission limits. If a check needs root for full detail, say so and keep going.
- Do not make coredoc install packages or edit configs by default.

## Add a finishing touch

Small UX improvements matter here. If you add a prompt, hint, help screen, or action label, check the whole loop:

1. Does the user know what coredoc found?
2. Do they know what to do next?
3. Is it clear whether coredoc will run something or only show advice?
4. If an action can change state, does it ask first?

Keep the tone calm. People usually open diagnostics tools when something is already annoying.

## Before opening a PR

Run:

```bash
make test lint
PYTHONPATH=src python3 -m coredoc.cli fix screenshare
PYTHONPATH=src python3 -m coredoc.cli since last-boot
```

If the TUI changed, run a quick smoke test too:

```bash
PYTHONPATH=src python3 -m coredoc.cli
```
