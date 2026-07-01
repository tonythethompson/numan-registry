# Production Cutover Checklist

This is the step-by-step maintainer runbook for going from "registry
tooling exists but has no real production key" to "official registry is
live and Numan PR #23 can be marked ready for review." It assumes you have
already read `docs/key-provisioning.md`; this document sequences those
steps against the rest of the cutover and adds rollback procedures.

Do not skip ahead. Each section lists the exact WSL commands, the exact
GitHub Settings path, and the expected outcome before you move on.

## Prerequisites

- [ ] WSL with Python 3.9+, `pip`, and `git` available.
- [ ] `cryptography` installed: `python3 -m pip install --user cryptography`.
- [ ] Owner access to `tonythethompson/numan-registry` and
      `tonythethompson/numan`.
- [ ] A password manager or encrypted vault ready to receive one secret
      note.
- [ ] `docs/key-provisioning.md` read in full, including the "Never do
      these things" section.
- [ ] Numan PR #23 (`tonythethompson/numan`) is open, in draft, and its
      merge-gate checklist is otherwise satisfied except for the real key
      and URL.

## Step A — Create the `production` environment

**WSL commands:** none (GitHub web UI only).

**GitHub Settings path:**
`tonythethompson/numan-registry` → **Settings** → **Environments** → **New
environment** → name it `production` → add required reviewers → restrict
**Deployment branches** to `main`.

**Expected outcome:** the `production` environment appears in the
Environments list with at least one required reviewer and a branch
restriction to `main`.

## Step B — Generate the production keypair

**WSL commands:**

```bash
cd numan-registry
git checkout main && git pull
./scripts/provision-production-key.sh
```

**GitHub Settings path:** none yet.

**Expected outcome:** terminal prints a `key_id`, a `public_key_b64`, and a
fingerprint — and nothing that looks like a private key. A new
`provisioning/<timestamp>/` directory exists locally with `.pub`, `.key`,
and `.summary.json` files.

## Step C — Commit the public key

**WSL commands:**

```bash
git checkout -b add-production-public-key
# edit keys/official.pub with the key_id and public_key_b64 from Step B
git add keys/official.pub
git commit -m "Add production public key official-YYYY-MM-01"
git push -u origin add-production-public-key
gh pr create --fill
```

**GitHub Settings path:** review and merge the PR through the normal GitHub
web UI.

**Expected outcome:** `scripts/preflight.py` passes in CI on the PR (it
confirms the key is well-formed and no longer a placeholder); after merge,
`main`'s `keys/official.pub` has the real key.

## Step D — Add the private key secret

**WSL commands:** none (GitHub web UI only). Have the
`provisioning/<timestamp>/official-YYYY-MM-01.key` file open in a terminal
so you can copy its contents without retyping.

**GitHub Settings path:**
`tonythethompson/numan-registry` → **Settings** → **Environments** →
**production** → **Environment secrets** → **Add secret** → name
`NUMAN_REGISTRY_PRIVATE_KEY`, value = contents of the `.key` file.

**Expected outcome:** exactly one secret, `NUMAN_REGISTRY_PRIVATE_KEY`, listed
under the `production` environment (not under repository-level secrets).

## Step E — Back up and delete the local private key

**WSL commands:**

```bash
# after copying the .key file's contents into your password manager:
rm provisioning/<timestamp>/official-YYYY-MM-01.key
```

**GitHub Settings path:** none.

**Expected outcome:** the `.key` file no longer exists locally; the
`.pub` and `.summary.json` files may remain (they contain no secret
material) or be deleted too — your choice.

## Step F — Update the Numan client's built-in trust root

**WSL commands:** in a checkout of `tonythethompson/numan`:

```bash
git checkout -b update-official-trust-root
# edit src/core/official_registry.rs: set the real key_id, public_key_b64,
# and hosted registry URL to match keys/official.pub from Step C
cargo test official_registry
git add src/core/official_registry.rs
git commit -m "Set production official-registry trust root"
git push -u origin update-official-trust-root
gh pr create --fill --base master
```

**GitHub Settings path:** none for this step.

**Expected outcome:** a new PR against `numan` (separate from PR #23) with
`cargo test official_registry` passing.

## Step G — Dispatch the production workflow

**WSL commands:** none (GitHub web UI, or `gh workflow run` if you prefer
the CLI):

```bash
gh workflow run "Production registry" --repo tonythethompson/numan-registry \
  -f reason="Initial production cutover"
```

**GitHub Settings path:** `tonythethompson/numan-registry` → **Actions** →
**Production registry** → **Run workflow**, then approve the pending
deployment when prompted for the `production` environment reviewer.

**Expected outcome:** the run's steps pass in order — debug-tracing guard,
secret-present check, pre-sign schema validation, signing, post-sign
signature validation, publish. The job succeeds and `registry/index.json`
and `registry/index.json.sig` are live on the GitHub Pages root.

## Step H — Verify the published index

**WSL commands:**

```bash
curl -sO https://<published-pages-url>/index.json
curl -sO https://<published-pages-url>/index.json.sig
python3 scripts/validate.py \
  --index index.json --sig index.json.sig \
  --pub keys/official.pub --schema schemas/index-v1.json
```

**Expected outcome:** `Validation passed`, exit code 0.

## Rollback procedures

### Committed the wrong public key

1. Revert the `keys/official.pub` commit on `main` (or push a new commit
   with the correct value) before dispatching the production workflow.
2. If the production workflow already ran with the wrong public key: the
   published signature will fail client-side verification (which is safe —
   clients reject it) but is still live. Re-run Step C with the correct key,
   then re-dispatch Step G to publish a correctly-signed index.
3. Do **not** try to "fix" this by relaxing verification anywhere — publish
   a corrected, correctly-signed index instead.

### Wrong value in the `NUMAN_REGISTRY_PRIVATE_KEY` secret

1. `production.yml`'s "Validate signed index with committed public key"
   step will fail the run — nothing gets published, because publish only
   happens after that step passes.
2. Go to **Settings** → **Environments** → **production** → **Environment
   secrets**, delete the bad secret, and re-add it correctly from your
   password manager backup (or re-run Step B/D if you no longer have the
   correct value — see "Suspected key exposure" below if you're unsure why
   it was wrong).
3. Re-dispatch the workflow.

### Validation failure (schema, signature, or artifact digest)

1. The workflow fails before the publish step — nothing changes on GitHub
   Pages.
2. Read the failing step's output (schema errors, signature mismatch, or
   artifact digest mismatch are each printed explicitly by
   `scripts/validate.py`).
3. Fix `registry/index.json` (or the underlying artifact) on `main` via a
   normal PR, gated by the `staging.yml` ephemeral-key run passing first,
   then re-dispatch the production workflow.

### Key generated but never published (abandoned provisioning run)

1. If you ran `provision-production-key.sh` but decided not to use that
   key (e.g. you want a different `key_id`, or you're starting over):
   delete the local `provisioning/<timestamp>/` directory — it was never
   committed (git-ignored) and no secret was ever added to GitHub, so there
   is nothing to roll back on the GitHub side.
2. If you already added the secret in Step D but stopped before Step G:
   delete the `NUMAN_REGISTRY_PRIVATE_KEY` environment secret via
   **Settings** → **Environments** → **production**, and delete the
   corresponding vault entry if you don't intend to use that key.

### Suspected key exposure

Treat any of these as exposure: the private key was pasted into a chat, an
issue/PR/commit, a CI log, a screen-shared session, or a non-vault file that
may have synced to the cloud.

1. Immediately rotate: generate a brand-new keypair (Step B) with a new
   `key_id`.
2. Follow the **Key rotation** procedure in `docs/key-provisioning.md` —
   the new key must be introduced via a signed successor declaration from
   the still-trusted (but now considered compromised) current key, *before*
   you can retire the old key. Do this even under time pressure; skipping
   the successor-declaration step would let an attacker's index pass
   verification, which is worse than the exposure itself.
3. Update the `production` environment secret to the new key (Step D),
   publish a new signed index (Step G) that both signs with the old key and
   declares the new key as successor, then publish again with the new key
   once clients have had a chance to pick up the successor declaration.
4. Delete the exposed key's vault entry and revoke/rotate the environment
   secret immediately after the successor is trusted.
5. If the exposure was in a public location (a public commit, a public gist,
   a public log), also treat this as needing a public security notice per
   the incident path referenced in Numan issue #18's acceptance criteria.

## Final go/no-go checklist before marking Numan PR #23 ready for review

- [ ] `keys/official.pub` on `numan-registry` `main` has the real,
      non-placeholder key id and public key.
- [ ] `registry/index.json` on `numan-registry` `main` contains real,
      signed, hash-verified seed packages — not fixture records.
- [ ] The **Production registry** workflow has run successfully at least
      once and `scripts/validate.py` passes against the published index.
- [ ] `src/core/official_registry.rs` in the separate `numan` PR (Step F)
      has the matching key id, public key, and real hosted registry URL,
      and `cargo test official_registry` passes.
- [ ] A fresh-install end-to-end check against the real registry succeeds
      (init → search → inspect → install → offline hash reproduction, per
      issue #18's acceptance criteria).
- [ ] No step in this checklist required pasting the private key anywhere
      other than the GitHub secret field and your password manager.
- [ ] Every rollback scenario above has a designated owner (you) who knows
      how to execute it, even if none were triggered this cutover.

Only once every box above is checked should PR #23 move from draft to
ready for review.
