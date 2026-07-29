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

## Promotion requirement

Lifecycle evidence is mandatory before an activatable package is promoted to
production. Paste the successful command, OS, Nu version, and package version
into the intake PR, and record every successfully proved Nu version in the
version entry's non-empty `verified_with` list. Production validation rejects
plugins and explicitly activated modules unless every entry is an exact
`MAJOR.MINOR.PATCH` Nu version satisfying the package's `nu_version` constraint.
Build validation proves archive structure and hashes;
staging proves the unsigned catalog and ephemeral signature path; neither is a
substitute for exercising install, activation, deactivation, removal, and
cleanup against a real Nu. If the lifecycle prove cannot run, keep the package
out of the production catalog until the evidence is available.
