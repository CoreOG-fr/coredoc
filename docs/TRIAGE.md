# coredoc triage design

The triage layer is what turns coredoc from “a dashboard of checks” into “start here.”

Individual doctors are good at their own area. The audio doctor can say PipeWire is unreachable. The Wayland doctor can say screen capture has no PipeWire path. The triage engine notices that these are probably the same problem.

## Data model

`Finding` stays backward-compatible. New optional fields give the triage engine more room to order issues by urgency later:

- `confidence`: how sure we are
- `impact`: how wide the blast radius is
- `safety`: whether a related action is safe, reversible, manual, or risky
- `tags`: machine-readable labels for future rules

The triage package adds:

- `TriageAction`: a proposed command or manual step
- `RootCause`: a likely cause with evidence and affected modules
- `GlobalDiagnosis`: the summary shown by the CLI and TUI

## Rules

Rules live in:

```text
src/coredoc/triage/rules.toml
```

A rule matches one or more finding IDs and produces a root cause. Rules are deliberately boring. They should encode troubleshooting knowledge that Linux users repeat all the time:

- Disk full? Fix that before chasing app crashes.
- PipeWire down? Audio and screen sharing may both fail.
- Portal backend missing? Wayland screen sharing and Flatpak integration may both fail.
- DNS broken? Package managers and browsers are not the first problem.

## Ranking

Root causes are ordered by severity, confidence, impact, and how many modules they affect. The goal is not perfect certainty. The goal is a better first move than “grep the whole journal and hope.”

## Actions

Actions have safety badges:

- `safe`: low-risk and allowed in the TUI after confirmation
- `reversible`: possible later, but should keep backups or quarantine
- `manual`: show the command or advice, but do not run it
- `risky`: never execute from the TUI

Restarting a user-level service can be safe. Installing packages, deleting files, editing boot parameters, and repairing filesystems are not.

## TUI behavior

The TUI opens on Global Diagnosis. It shows the summary, root-cause tree, warning banners, and action plan. Press `r` to rerun the doctors. Press `d` to switch to the per-module dashboard.
