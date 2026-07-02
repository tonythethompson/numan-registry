# Key Rotation Checklist

This is the maintainer runbook for rotating the production signing key
**after** it has already been provisioned once (see
`docs/key-provisioning.md` and `docs/production-cutover-checklist.md` for
first-time provisioning). It reuses the same scripts; nothing here needs new
tooling.

There is no automated rotation script. Rotation is infrequent and has a
judgment call baked in (how long to wait for propagation), so it stays a
checklist, not a script, until real-world rotations show a stable enough
shape to automate.

## Why the ordering matters

A new key must never start signing the index on its own. If it did, a
client that has never seen it would correctly reject it (that's the whole
point of the trust root), and a client with a cached trust store would be
silently stuck unable to sync. Instead, the **currently-trusted** key signs
an index that *declares* the new key as a successor. Clients that sync while
that declaration is present cache the new key locally
(`registry/<name>/derived_keys.json` on the client) before it ever needs to
be trusted on its own. Only after that has had time to propagate does the
new key start signing, and only after that switch is confirmed does the old
key retire.

Skipping the successor-declaration step is the one mistake that can lock out
clients or make a compromised-key incident worse instead of better.

## Trigger: routine vs. suspected compromise

- **Routine** (e.g. annual hygiene rotation): follow every step below with
  full propagation windows. No rush.
- **Suspected compromise**: follow `docs/production-cutover-checklist.md`'s
  "Suspected key exposure" rollback section instead — it points back here
  for the mechanics but tells you which waits you can safely compress and
  why.

## Step A — Generate the new keypair

**WSL commands:**

```bash
./scripts/provision-production-key.sh
```

**Expected outcome:** same as first-time provisioning — a new
`provisioning/<timestamp>/official-YYYY-MM-01.{pub,key,summary.json}` with a
**new** key id for the new month/rotation. Do not reuse the old key id.

## Step B — Publish a successor declaration signed by the CURRENT key

1. Edit `registry/index.json` and add (or extend) a `trust` block naming the
   new key, without touching `packages`:

   ```json
   {
     "schema_version": 1,
     "trust": {
       "keys": [
         { "key_id": "official-YYYY-MM-01", "public_key_b64": "<new public key>" }
       ]
     },
     "packages": [ ... ]
   }
   ```

2. Open a normal PR with just this change, merge it to `main`.
3. Dispatch the **Production registry** workflow as usual. It signs this
   index with the **current** (old, still-active) key — that signature is
   what makes clients trust the declaration.

**Expected outcome:** the published `registry/index.json.sig` still has the
**old** `key_id`. `keys/official.pub` is unchanged. Verifying with the old
public key succeeds; the index content now carries the new key's successor
declaration.

## Step C — Wait for propagation

**WSL commands:** none — this step is elapsed time, not an action.

For routine rotation, wait long enough that the large majority of active
installs have run a sync (`numan registry sync` or equivalent) at least once
since Step B published. There's no built-in telemetry to measure this
precisely — as a rule of thumb, wait at least a week for a low-traffic
registry like this one; extend it if you have reason to think sync
frequency is lower.

**Expected outcome:** no action, just elapsed time. Nothing to verify here
beyond "has it been long enough."

## Step D — Switch signing to the new key

1. Commit the new public key: update `keys/official.pub` to the new
   `key_id`/`public_key_b64`, same as first-time provisioning (Step C in
   `docs/production-cutover-checklist.md`). Merge.
2. Update the `production` environment secret `NUMAN_REGISTRY_PRIVATE_KEY`
   to the new private key (Step D there). Delete the old secret value when
   replacing it.
3. In `tonythethompson/numan`, run:

   ```bash
   ./scripts/update-official-trust-root.sh \
     --from-pub-json /path/to/numan-registry/keys/official.pub \
     --force
   ```

   `--force` is required here because the trust root is already
   non-placeholder from the first cutover. Omit `--url` unless the hosted
   registry URL is actually changing as part of this rotation (it normally
   isn't) — pass it only when you need to update `production_url` too,
   same as during first-time provisioning. Review the diff and the
   `cargo test official_registry` output the script prints, then push the
   commit per the branching guidance in
   `docs/production-cutover-checklist.md` Step F, and open a PR as usual.
4. Dispatch the **Production registry** workflow again.

**Expected outcome:** the published `registry/index.json.sig` now has the
**new** `key_id`. `scripts/validate.py --pub keys/official.pub` (with the
new public key) passes against it.

## Step E — Verify before retiring anything

```bash
curl -sO https://<published-pages-url>/index.json
curl -sO https://<published-pages-url>/index.json.sig
python3 scripts/validate.py \
  --index index.json --sig index.json.sig \
  --pub keys/official.pub --schema schemas/index-v1.json
```

**Expected outcome:** `Validation passed`. Also spot-check that a client
which only ever trusted the old key (i.e. never synced during Step B–C)
still fails closed rather than silently accepting the new key — that's
correct behavior, not a bug; it just means that install needs a fresh
`numan registry sync` or re-init to pick up the transition.

## Step F — Retire the old key

1. Delete the old private key's entry from your password manager / vault.
2. Delete any remaining local copies (there shouldn't be any outside the
   vault at this point — see "About secure deletion" in
   `docs/key-provisioning.md`).
3. If the old key was itself introduced as a successor key in some earlier
   rotation (i.e. this is a third-or-later key in the chain, not the
   original built-in one), remove its entry from `registry/index.json`'s
   `trust.keys` list in a follow-up index publish, so the trust list
   doesn't grow unbounded. The original built-in key needs no such cleanup
   — it was never listed in `trust.keys` to begin with.

**Expected outcome:** exactly one production private key exists (the new
one), in exactly one vault entry.

## Rollback

- **Realized you rotated the wrong direction, or the successor declaration
  had a typo, before Step D:** just publish a corrected index in Step B
  again, still signed by the old key. Nothing has switched yet, so there's
  nothing to undo beyond publishing the fix.
- **Already switched (Step D) and something's wrong:** do not revert
  `keys/official.pub` back to the old key unless you're certain no client
  has picked up the new-key-signed index yet — reverting after clients have
  moved forward just creates a second inconsistent transition. Instead,
  treat it as a forward-only fix: publish a corrected index signed by the
  (still-active) new key.
- **Suspected exposure of the OLD key during rotation:** the old key is
  being retired anyway; finish Steps D–F on the expedited timeline described
  in `docs/production-cutover-checklist.md`'s "Suspected key exposure"
  section, and treat the exposure as resolved once Step F completes.
- **Suspected exposure of the NEW key before Step D (still generating/
  waiting):** discard it, delete its vault entry if one was created, and
  restart from Step A with a fresh key id. The old key is still the active
  signer and was never exposed, so there's no user-facing impact.
