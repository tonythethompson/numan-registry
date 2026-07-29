# Lifecycle-prove (Stage 1 intake gate)

An activatable package cannot earn lifecycle evidence until it is available to
Numan. Add it without `verified_with` using `scripts/add-package.py --spec …
--provisional --write`, then stage that candidate. Staging explicitly permits
missing evidence; production validation does not. Run lifecycle-prove against
the staged package on a **clean** Numan root and a **real** Nu matching the
package's `nu_version` constraint. After success, record the exact version(s) in
`verified_with`, rerun intake without `--provisional`, and only then promote it.

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
