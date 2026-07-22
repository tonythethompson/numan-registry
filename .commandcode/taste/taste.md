# Taste (Continuously Learned by [CommandCode][cmd])

[cmd]: https://commandcode.ai/

# registry-schema
See [registry-schema/taste.md](registry-schema/taste.md)
# python-scripts
- Validate base64 input with `base64.b64decode(..., validate=True)` in a `try`/`except` block rather than relying on the caller to sanitize — fail explicitly on malformed keys. Confidence: 0.70
- When checking for placeholder/incomplete signatures, verify **both** the key_id and the signature value are placeholder strings — a half-placeholder envelope is not unsigned. Confidence: 0.70
- Print actionable `git diff` commands after generating files, quoting the path with `\\\"` shell escaping so the user can copy-paste directly. Confidence: 0.65
- Name boolean variables with explicit prefixes (`sig_id_is_placeholder`, `sig_value_is_placeholder`) so the condition reads as a plain-English sentence. Confidence: 0.65
- Make error messages name the specific files involved and describe the directional inconsistency — prefer `\"{SIG_PATH} is signed with key_id {sig_key_id!r} but {PUB_PATH} is still a placeholder\"` over generic "consistency" messages. Confidence: 0.70

# documentation
- In key-provisioning docs, explicitly link to the PR where the trust root lives and give the exact command to run, including the repo-specific paths — never assume the reader knows where files live. Confidence: 0.65
- Use a changelog table in intake-candidate docs that links each change to its PR for traceability. Confidence: 0.65
- When listing scripts in README, show them as an indented tree (├── / └──) with a one-line description comment so the hierarchy is visually scannable. Confidence: 0.65
- In cutover runbooks, give the full command with placeholder values that the operator replaces, not a template with abstract variables — reduces mental translation. Confidence: 0.65
