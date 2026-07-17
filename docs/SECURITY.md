# Security review for coredoc

Date: 2026-07-16

## Scope

This review covers the Python runtime code, support bundle generation, TUI actions, and packaging helper scripts.

## What looks good

- Runtime command execution goes through helper code that uses `subprocess.run` with `shell=False`.
- Doctors are read-only. They gather facts and return findings.
- The TUI only offers buttons for actions marked `safe`, and it asks before running them.
- No runtime code uses `eval`, `exec`, or dynamic imports from user input.
- Support bundles are built from generated JSON and a generated README. They do not archive arbitrary paths from the host.
- The support bundle sanitizer redacts common `password=`, `token=`, `secret=`, `apikey=`, and `Authorization:` patterns.

## Things to keep in mind

- Sanitizing logs is hard. Users should still review support bundles before sharing them.
- Some packaging scripts are shell scripts. They are developer tools, not part of the normal runtime path.
- Future fix actions must stay behind explicit confirmation and should default to `manual` unless they are clearly safe.

## Recommendation before 1.0

- Add stronger redaction tests for URLs, bearer tokens, private hostnames, email addresses, and unusual secret formats.
- Add CI jobs that build packages in container images.
- Keep expanding the triage rule tests whenever a new safe action is added.

## Verdict

No runtime shell injection or unsafe automatic repair behavior was found. coredoc is safe to run as a read-first diagnostic tool under the current design.
