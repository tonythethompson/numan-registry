# registry-schema
- Pin every `nu_version` field to an upper bound (`>=X <Y`) rather than an open lower bound — never write `">=0.113.0"` without capping it. Confidence: 0.80
- Use `"activation": {"kind": "nu-module", "import": "all"}` instead of `"import": "module"` — module scoping makes exported commands available directly. Confidence: 0.75
- Tag entries with explicit platform-awareness tags (`"windows-only"`, `"linux-aarch64-only"`, `"partial-platform"`) to surface platform constraints at a glance. Confidence: 0.70
- Never reference GitHub's ephemeral tag archives as artifact URLs — mirror the release asset to a byte-stable release under your own org. Confidence: 0.75
- Format JSON arrays that are semantically independent items as multi-line blocks (one item per line), not single-line arrays — aids diff readability. Confidence: 0.65
- Bump `updated_at` to a real timestamp on every semantic change to the registry index — never leave a placeholder or stale timestamp. Confidence: 0.70
