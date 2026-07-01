# Key Provisioning

This document describes how the maintainer manually provisions the production
signing key for the Numan official registry. **No coding agent, CI log, or
repository file should ever contain the private key.**

## What you need

- A machine with Python 3 and the `cryptography` package installed.
- Owner access to the `tonythethompson/numan-registry` GitHub repository.
- Access to configure GitHub Environments and Secrets.

## Step 1: Create the production environment

1. Open the repository on GitHub.
2. Go to **Settings > Environments**.
3. Click **New environment** and name it `production`.
4. Configure protection rules:
   - **Required reviewers**: add yourself (and any other trusted maintainers).
   - **Wait timer**: optional, e.g., 60 minutes for a final review window.
   - **Deployment branches**: restrict to `main` / `master` only.

## Step 2: Generate the keypair locally

On a trusted local machine, run:

```bash
python3 <<'PY'
import base64
from pathlib import Path
from cryptography.hazmat.primitives import serialization
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey

private_key = Ed25519PrivateKey.generate()
public_key = private_key.public_key()

pub_b64 = base64.b64encode(public_key.public_bytes(
    serialization.Encoding.Raw, serialization.PublicFormat.Raw
)).decode()
priv_b64 = base64.b64encode(private_key.private_bytes(
    serialization.Encoding.Raw,
    serialization.PrivateFormat.Raw,
    serialization.NoEncryption()
)).decode()

Path("official-2026-01.pub").write_text(pub_b64)
Path("official-2026-01.key").write_text(priv_b64)
print(f"Public key: {pub_b64}")
print("Private key written to official-2026-01.key")
PY
```

This produces:

- `official-2026-01.key` — the **private** key (base64, 32 bytes raw).
- `official-2026-01.pub` — the **public** key (base64, 32 bytes raw).

## Step 3: Commit the public key

1. Update `keys/official.pub`:

```json
{
  "key_id": "official-2026-01",
  "public_key_b64": "<paste the contents of official-2026-01.pub>",
  "note": "Production public key for the Numan official registry."
}
```

2. Open a pull request in the `tonythethompson/numan` repository to update the
   built-in trust root (`src/core/official_registry.rs`) with the same
   `key_id` and `public_key_b64`. Do this **only after** the public key is
   committed to this registry repo.

## Step 4: Add the private key to GitHub Actions secrets

1. In `tonythethompson/numan-registry`, go to **Settings > Secrets and
   variables > Actions**.
2. Click **New repository secret** (or environment secret) and add:
   - **Name**: `NUMAN_REGISTRY_PRIVATE_KEY`
   - **Value**: the entire contents of `official-2026-01.key` (base64).
3. If you added it as a repository secret, additionally restrict the
   `.github/workflows/production.yml` workflow to the `production` environment,
   which is already configured.

## Step 5: Secure the local private key file

After copying the secret:

```bash
shred -u official-2026-01.key
```

On macOS or Windows, delete the file securely and empty the recycle bin / trash.

Keep a backup only in a trusted password manager or hardware token, never in:

- the repository,
- a gist,
- CI logs,
- chat messages,
- cloud-synced plain text files.

## Step 6: Verify the production workflow

1. Trigger the **Production registry** workflow manually from the Actions tab.
2. Approve the deployment from the `production` environment.
3. Confirm that the workflow signs and publishes `registry/index.json` and
   `registry/index.json.sig` to the GitHub Pages root.
4. Verify the published signature using the committed public key:

```bash
python scripts/validate.py \
  --index registry/index.json \
  --sig registry/index.json.sig \
  --pub keys/official.pub \
  --schema schemas/index-v1.json
```

## Key rotation

To rotate to a new key:

1. Generate a new keypair locally.
2. Add the new public key as a successor in the registry index `trust` section,
   signed by the **current** key.
3. Publish the index with the current key.
4. Update `keys/official.pub` and the Numan built-in root to the new public key.
5. After the new key is trusted, remove the old key from the index `trust`
   section and retire it.

This process ensures a new key never becomes trusted merely by signing an index;
it must be introduced by a signed successor declaration from an already-trusted
key.
