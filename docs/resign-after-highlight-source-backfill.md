# Checklist: resign after Workstream A provenance backfill

`registry/index.json` was surgically updated so
`cptpiepmatz/nu_plugin_highlight@1.4.15` includes a `source` block.
Artifact URLs and sha256 values were not changed.

**Required before users see this via `numan registry sync`:**

1. Review the index diff (highlight `source` only, plus any unrelated dirty state).
2. Run staging/production signing for the updated index (same workflow as any other index change).
3. Publish / deploy gh-pages (or current publish path).
4. Spot-check: `numan registry sync` then `numan info cptpiepmatz/nu_plugin_highlight` shows source lines.

This file is intentionally a checklist, not an automation step.
