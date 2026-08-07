# Security policy

This repository publishes the signed official Numan registry index. It is not
the Numan CLI and does not build upstream packages.
Operational procedures (yank, rollback, compromise, user remediation) live in
[docs/incident-response.md](docs/incident-response.md).

## Report a vulnerability

Do not publish exploit details, suspected private keys, or unverified artifact
content in a public issue.

Preferred: open a private GitHub security advisory at
<https://github.com/tonythethompson/numan-registry/security/advisories/new>.

Fallback: open a public issue titled **Security contact request** with no
technical details. The maintainer will establish a private channel before
collecting the report.

Helpful report contents:

- Package ID and version (if applicable)
- Target triple and artifact URL / recorded digest
- Registry revision, index hash, or `key_id` when known
- Reproduction steps sufficient for independent verification

## Scope

**In scope for this repo**

- Compromised, mismatched, or malicious artifacts listed in the signed index
- Incorrect or unsafe package metadata that would cause clients to fetch the
  wrong bytes
- Signing-key exposure, signature bypass in CI publish paths, or a bad signed
  index revision reaching production Pages
- Secret leakage in this repository (private keys, tokens, workflow credentials)

**Out of scope here (report elsewhere)**

- Bugs in the Numan CLI client (verification logic, path handling, install,
  activate, self-update):
  [tonythethompson/numan](https://github.com/tonythethompson/numan)
- Plugin / module build and release pipeline issues that never reached a signed
  index:
  [tonythethompson/numan-plugins](https://github.com/tonythethompson/numan-plugins)
- Vulnerabilities in upstream third-party packages themselves (report to the
  upstream project; tell us if a catalog entry needs yank or replacement)
- Social engineering, denial of service against GitHub Pages, or issues that
  require disabling signature checks (`NUMAN_ALLOW_UNSIGNED`)

When unsure, report here. We will route it.

## Trust model (summary)

1. Production clients verify Ed25519 signatures over the canonical bytes of
   `index.json` using the `official` trust root baked into Numan.
2. Plugin artifacts must carry SHA-256 digests; Numan refuses to install a
   plugin binary without a matching digest.
3. Install is inert: fetching a package does not run Nu plugin registration.
   Activation is a separate, user-driven step.
4. Published artifact URLs and digests are immutable. Remediation is a reviewed,
   newly signed index revision (yank or new version), never an in-place rewrite
   of the same version's bytes.
5. The committed `registry/index.json.sig` in this source tree may be a
   placeholder. Clients must use the signature published with the live Pages
   index, not the source-tree placeholder.

## Supported versions

Security fixes apply to the currently published production index and to the
signing / publish tooling on `main`. Older catalog revisions are evidence in
lockfiles; they are not patched in place. Users remediate by syncing a fixed
index and following advisory instructions (see
[incident-response.md](docs/incident-response.md#user-remediation)).

## Related docs

- [Incident response and user remediation](docs/incident-response.md)
- [Key rotation checklist](docs/key-rotation-checklist.md)
- [Key provisioning](docs/key-provisioning.md)
- [Production cutover checklist](docs/production-cutover-checklist.md)
