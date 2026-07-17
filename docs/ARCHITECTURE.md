# coredoc architecture

coredoc has three layers: doctors gather facts, triage connects the facts, and the UI shows the answer without making you read raw logs first.

## 1. Doctors

Doctors live in `src/coredoc/doctors/`. Each doctor owns one area of the system: audio, Wayland, sleep, hardware, permissions, logs, clean-up, or core system health.

A doctor returns a `DoctorResult`:

- `module`: the doctor name
- `severity`: the highest severity it found
- `facts`: raw structured data for later correlation
- `findings`: human-readable observations with evidence and advice
- `actions`: optional action IDs

Doctors are read-only. They use `BaseDoctor.cmd()` so command execution stays consistent: no shell, captured output, timeout, and graceful handling when a tool is missing.

## 2. Triage

Triage lives in `src/coredoc/triage/`.

The `TriageEngine` takes doctor results and matches them against rules in `rules.toml`. Rules turn scattered findings into root causes. For example:

- PipeWire trouble can explain audio failures and Wayland screen-sharing failures.
- Disk exhaustion can explain package errors, service failures, and strange application behavior.
- Missing firmware can explain hardware, Bluetooth, audio, and sleep problems.

The engine returns a `GlobalDiagnosis` with:

- a short summary
- likely root causes in the order coredoc would check them
- an action plan
- warning banners for missing or limited data
- the original doctor results

## 3. Interfaces

The CLI is in `src/coredoc/cli.py`.

Useful entry points:

```bash
coredoc
coredoc --json --doctor audio
coredoc fix screenshare
coredoc since last-boot
```

The TUI is in `src/coredoc/tui/app.py`. It starts with the global diagnosis, then lets you switch to the per-module dashboard or an individual doctor.

## 4. Change detection

`src/coredoc/changes.py` powers `coredoc since <timeframe>`. It compares available journal data, package history, and kernel information. It is intentionally simple for now: it gives useful clues without pretending to be a full system history database.

## 5. Safety

coredoc is designed around a simple rule: read first, explain clearly, and ask before doing anything.

The TUI only executes actions marked `safe`, and every action goes through a confirmation dialog. Anything that could remove data, edit configuration, change packages, or alter boot behavior stays as manual advice.
