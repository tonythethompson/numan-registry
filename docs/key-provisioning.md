# Key Provisioning

This document is the maintainer's manual procedure for provisioning the
**production** Ed25519 signing key for the Numan official registry
(`tonythethompson/numan-registry`). It is written for a maintainer working in
**WSL** (Windows Subsystem for Linux) with `bash` and Python 3, who is
comfortable with the command line and GitHub's web UI but is not a
cryptography specialist.

Read the whole document, including the checklist at the end, before running
any command in this file.

## Never do these things

- **Never** paste a private key into a chat window, an AI assistant, an issue,
  a PR description, a commit message, or a code review comment.
- **Never** commit a private key file to any Git repository, including this
  one, a fork, a gist, or a "temporary" branch.
- **Never** print a private key to a CI log. CI only ever receives the key as
  a GitHub Actions secret, only the production workflow reads it, and that
  workflow never echoes the secret value.
- **Never** send a private key over Slack, email, a shared drive, or any
  cloud-synced folder (Dropbox, OneDrive, Google Drive, iCloud Drive) in
  plain text.
- **Never** reuse a staging/ephemeral/test key as the production key. Test
  keys are generated fresh by CI and thrown away; they must never become the
  real signing key.
- **Never** ask a coding agent (including Claude Code or any other AI
  assistant) to generate, view, transmit, or store the production private
  key. Agents may edit this document and the tooling around it, but the key
  material itself is a human-only, local, out-of-band action.
- **Never** assume a deleted file is unrecoverable. See "About secure
  deletion" below.

If you are unsure whether an action is safe, stop and re-read this document
rather than guessing.

## Public key vs. private key, in plain language

An Ed25519 keypair is two related pieces of data:

- The **private key** is a secret. Whoever holds it can produce a signature
  that anyone can verify as "signed by the official registry." Treat it like
  a master password: if it leaks, an attacker can publish a malicious index
  that every Numan client will accept as trustworthy.
- The **public key** is not a secret. It is safe to commit to this
  repository, paste anywhere, and hand out publicly. It lets anyone verify a
  signature *without* being able to create one.

Provisioning is the one-time act of generating this pair, keeping the private
half secret and out of the repository, and publishing the public half so
Numan clients can verify signatures produced by the private half.

## What you need

- A WSL shell (Ubuntu or similar) with Python 3.9+ and `pip`.
- Owner access to `tonythethompson/numan-registry` on GitHub.
- Permission to configure GitHub Environments and Actions secrets on that
  repository.
- A password manager or encrypted vault you already use and trust (1Password,
  Bitwarden, a LUKS/VeraCrypt container, etc.) to hold the one backup copy of
  the private key.

Install the Python dependency once:

```bash
python3 -m pip install --user cryptography
```

## Step 1: Create the production GitHub Environment

1. Open `https://github.com/tonythethompson/numan-registry` in a browser.
2. Go to **Settings > Environments**.
3. Click **New environment**, name it exactly `production`.
4. Configure protection rules:
   - **Required reviewers**: add yourself (and any other trusted
     maintainers). This forces a manual approval click before the production
     workflow can run.
   - **Wait timer**: optional; a short delay (e.g. 10–60 minutes) gives you a
     window to cancel a mistaken trigger.
   - **Deployment branches**: restrict to `main` only.
5. Do not add the secret yet — that happens in Step 4, after the key exists.

**Expected outcome:** the `production` environment exists with at least one
required reviewer and is restricted to `main`.

## Step 2: Generate the keypair locally, in WSL

From the repository root, in WSL:

```bash
./scripts/provision-production-key.sh
```

This script (see `scripts/provision-production-key.sh` for full behavior):

- Generates a fresh Ed25519 keypair locally using Python's `cryptography`
  library. The key never leaves your machine at this step.
- Refuses to overwrite a previous run's output unless you pass `--force`.
- Writes a **timestamped** output directory under `provisioning/` (already
  git-ignored — see `.gitignore`) containing:
  - `official-YYYY-MM-01.pub` — the public key, base64.
  - `official-YYYY-MM-01.key` — the private key, base64, file permissions
    restricted to your user only.
  - `official-YYYY-MM-01.summary.json` — a safe-to-share summary (key id,
    public key, fingerprint, creation time, next steps). This file contains
    **no** private key material and can be pasted anywhere if you need to
    hand it to a co-maintainer for review.
- Prints the public key, its fingerprint, the output filenames, and the next
  GitHub UI steps. It **never** prints the private key to your terminal.

**Expected outcome:** a new directory under `provisioning/<timestamp>/` with
the three files above, and terminal output showing only public material.

## Step 3: Commit the public key

1. Open the printed `official-YYYY-MM-01.pub` file and copy its JSON content
   (or copy the `public_key_b64` field out of the `.summary.json`).
2. Update `keys/official.pub` in this repository to:

   ```json
   {
     "key_id": "official-YYYY-MM-01",
     "public_key_b64": "<the public key from the summary file>",
     "note": "Production public key for the Numan official registry."
   }
   ```

3. Open a pull request against `tonythethompson/numan-registry` with just
   this change. `scripts/preflight.py` runs in CI on this PR and confirms
   the file is well-formed and no longer a placeholder.
4. After this PR merges, open a **separate** pull request against
   `tonythethompson/numan` to update the built-in trust root in
   `src/core/official_registry.rs` with the same `key_id` and
   `public_key_b64`. Do this only after the public key is merged here — the
   client PR should reference this repository's commit.

**Expected outcome:** `keys/official.pub` on `main` contains the real key id
and public key; CI is green.

## Step 4: Add the private key to GitHub Actions secrets

1. In `tonythethompson/numan-registry`, go to **Settings > Environments >
   production**.
2. Under **Environment secrets**, click **Add secret**.
3. **Name**: `NUMAN_REGISTRY_PRIVATE_KEY`
4. **Value**: paste the entire contents of the `official-YYYY-MM-01.key`
   file (the base64 string, nothing else).
5. Save. Adding it as an **environment** secret (not a repository secret)
   means only workflow runs that target the `production` environment can
   read it — this is why `.github/workflows/production.yml` declares
   `environment: production`.

**Expected outcome:** the `production` environment has exactly one secret,
`NUMAN_REGISTRY_PRIVATE_KEY`, and no other workflow in this repository can
read it.

## Step 5: Handle the local private key file

After the secret is saved in GitHub:

1. Copy the private key **once** into your password manager or encrypted
   vault as a single secure note. This is the only backup you keep.
2. Delete the local `provisioning/<timestamp>/official-YYYY-MM-01.key` file.

### About secure deletion

Do not assume deleting the file makes it unrecoverable. On SSDs (which is
most modern disks, including most WSL/Windows setups), wear-leveling and
copy-on-write mean a "secure delete" tool like `shred` provides **no
reliable guarantee** the data is actually overwritten on the physical media —
this is a well-known limitation, not a WSL quirk.

What actually reduces risk is minimizing the number of copies that ever
existed in the first place:

- Generate the key directly in the working directory you'll delete from —
  don't copy it elsewhere "just in case."
- Don't email it to yourself, don't put it in a cloud-synced folder even
  temporarily, don't paste it into a scratch file in an editor that
  autosaves to a sync location.
- The **one** durable backup is the password manager / encrypted vault entry
  from step 1 above. If you need the key again, restore it from there rather
  than keeping loose copies "for convenience."
- After copying to the vault, delete the local file (`rm` is fine) and move
  on — treat the deletion as hygiene, not as a cryptographic guarantee.

**Expected outcome:** exactly one durable copy of the private key exists (in
your password manager / vault); no plaintext copy remains on disk outside
that vault's storage.

## Step 6: Verify the production workflow

1. Open the **Actions** tab, select **Production registry**, click **Run
   workflow**, fill in a reason, and dispatch it against `main`.
2. Approve the deployment when GitHub prompts for the required reviewer on
   the `production` environment.
3. Watch the run. It validates the index schema, signs it with the secret,
   re-validates the signed output against the committed `keys/official.pub`,
   and only then publishes to GitHub Pages. It never echoes the secret value
   and does not enable shell debug tracing.
4. Locally, verify the published signature against the committed public key:

```bash
curl -sO https://<published-pages-url>/index.json
curl -sO https://<published-pages-url>/index.json.sig
python3 scripts/validate.py \
  --index index.json \
  --sig index.json.sig \
  --pub keys/official.pub \
  --schema schemas/index-v1.json
```

**Expected outcome:** `validate.py` prints `Validation passed` and exits 0.

## Key rotation

To rotate to a new key later:

1. Run `scripts/provision-production-key.sh` again (new timestamp, new
   `official-YYYY-MM-01` id for the new month) to generate a new keypair.
2. Add the new public key as a successor in the registry index's `trust`
   section, and sign that declaration with the **current** (old) key.
3. Publish an index signed by the current key that includes the successor
   declaration.
4. Update `keys/official.pub` and the Numan client's built-in trust root to
   the new public key, and update the `production` environment secret to the
   new private key.
5. Once the new key is trusted, remove the old key from the index's `trust`
   section and retire it (delete its vault entry once you're certain it's no
   longer needed for any signed-but-unpublished index).

A new key never becomes trusted merely by signing an index — it must be
introduced by a signed successor declaration from an already-trusted key.
This rule is enforced by client and CI verification and must not be
weakened.

## Final stop-and-review checklist

Before you do anything in Step 6 (the actual production trigger), stop and
confirm every line below is true:

- [ ] I generated the key with `scripts/provision-production-key.sh` in WSL,
      on a machine I trust, not in a container or VM I'm about to discard.
- [ ] I have never pasted the private key into a chat window, AI assistant,
      issue, PR, commit, or log.
- [ ] `keys/official.pub` on `main` has the real `key_id` and
      `public_key_b64`, and CI (`scripts/preflight.py`) is green on that
      change.
- [ ] `NUMAN_REGISTRY_PRIVATE_KEY` is set as an **environment** secret on the
      `production` environment only, and I verified no other secret name or
      workflow can read it.
- [ ] The `production` environment has at least one required reviewer and is
      restricted to the `main` branch.
- [ ] Exactly one durable copy of the private key exists, in my password
      manager / encrypted vault. No loose plaintext copies remain.
- [ ] `git status` in my local `provisioning/` output directory shows nothing
      staged or committed (it's git-ignored, but double-check).
- [ ] I have read and understand the "Never do these things" section above,
      and none of those things happened during this process.

Only after every box is checked should you dispatch the **Production
registry** workflow.
