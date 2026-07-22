# Lifecycle-prove (Stage 1 intake gate)

After adding a package to `registry/index.json` (usually via
`scripts/add-package.py --spec … --write`), the package **must be staged or
published** in the configured registry before running `scripts/lifecycle-prove.py`,
unless a registry-target override is added. Prove it on a **clean** Numan root
against a **real** Nu that matches the package's `nu_version` constraint.

## Script

```bash
python3 scripts/lifecycle-prove.py \
  --package owner/name \
  --numan /path/to/numan \
  --nu /path/to/nu
```

Omit `--numan` / `--nu` to use whatever is on `PATH`.

The script creates a temporary `--root`, runs:

`init → registry sync → search → info → install → activate → doctor → list → deactivate → remove → gc`

and exits nonzero on the first failing step (printing the step name). Use
`--keep-root` to retain the temp root for debugging, or `--root PATH` to reuse
a directory (never auto-deleted).

## Requirements

- Network access to the official registry (and package artifact URLs)
- A `numan` build new enough for the package under test
- A `nu` binary compatible with the package's `nu_version`

## PR note

Paste the command and OS/Nu version into the intake PR when the prove passes
(or explicitly defer with rationale).
