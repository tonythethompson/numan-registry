# `/oc` GitHub PR commands

These instructions apply when a user message is posted on a GitHub PR via the opencode
GitHub Action and begins with `/oc` (or `/opencode`). The message usually carries a
`<pull_request>` context block (title, body, changed files, comments, reviews) — read it
carefully before answering.

## Model routing

The workflow probes and selects the agent model per command (see `.github/workflows/opencode.yml`):

| Command      | Primary model                          | Fallback chain                                                                                |
| ------------ | -------------------------------------- | --------------------------------------------------------------------------------------------- |
| `/oc review` | `opencode/gpt-5.6-luna`                | `opencode/big-pickle` → `opencode/nemotron-3-ultra-free` → `opencode/nemotron-3.5-lightning-free` → `opencode/deepseek-v4-flash` → `alibaba-token-plan/qwen3.8-max` → `alibaba/qwen3.8-max` → `opencode/nemotron-3-ultra` |
| `/oc fix`    | `opencode/big-pickle`                  | `opencode/nemotron-3-ultra-free` → `opencode/nemotron-3.5-lightning-free` → `opencode/deepseek-v4-flash` → `alibaba-token-plan/qwen3.8-max` → `alibaba/qwen3.8-max` → `opencode/nemotron-3-ultra` |

Each model is probed with a minimal request before the run; a disabled or unavailable model
falls through to the next in the chain. The `opencode/*` models are probed through the
opencode.ai `/zen` gateway; the two `alibaba/*` models are probed through their direct
compatible-mode endpoints (`token-plan.ap-southeast-1.maas.aliyuncs.com` and
`dashscope.aliyuncs.com`) behind the `ALIBABA_TOKEN_PLAN_API_KEY` / `DASHSCOPE_API_KEY`
secrets. `/oc review` uses `gpt-5.6-luna` for fast and accurate finding quality; `/oc fix` runs
use `big-pickle` for multi-turn editing loops. Review runs send code snippets to an
OpenAI-hosted model — acceptable for public repos; keep in mind OpenAI may retain requests
for evaluation purposes.

## Using context7

The `context7` MCP server (remote, wired via `.opencode/opencode.json`) is available to
look up **current, version-accurate library/framework documentation** — handy because the
agent's training data can go stale. Use its `resolve-library-id` and `query-docs` tools.

**When to use it** (both commands):

- **Authoring or changing API calls** — before writing code that calls a library, framework,
  or SDK, look up the exact current API so you don't invent a wrong signature or import
  (e.g. React 19 hooks, Express routes, Vite config).
- **Resolving an API-relevant review finding** — when `/oc fix` addresses a comment about a
  library usage, confirm the expected current behavior/API from docs rather than guessing.
- **Copy-pasted code that may be outdated** — verify before trusting it.

**When NOT to use it:**

- For pure project-internal logic, the diff, or code you're already certain about — don't
  spend tool calls (and context) re-confirming things you know.
- For general web/non-library lookups — context7 is a documentation index, not a search
  engine; prefer the model's own knowledge for non-API questions.

**How to use it:**

1. `resolve-library-id` (pass the library name from the message, e.g. "Express", "React").
2. `query-docs` with the returned library ID and a focused, single-concept question.
3. Use `use context7` in tool choice; keep queries narrow so results stay small and relevant.

## `/oc review`

A review also runs **automatically when a pull request is first opened** (the workflow's
`pull_request: [opened]` trigger), in addition to on-demand. It does NOT re-run on later
commits to the same PR.

When a user message is exactly `/oc review` or begins with `/oc review`, treat it as a
request to review the current pull request. Extra text after the shortcut, e.g.
`/oc review focus on security`, scopes the review to those concerns. The same posting
behavior below applies whether the review is triggered by `/oc review` or by PR creation.

### Posting behavior

**CRITICAL REQUIREMENT: YOU MUST POST EACH FINDING VIA THE `bash` TOOL BEFORE RETURNING.**
Do NOT dump findings into your final response text. Instead:

1. **Identify the actionable findings in the PR diff.**
2. **For EVERY finding located in the PR diff, you MUST execute a `bash` tool call** to post it as an **individual inline resolvable review thread** via `gh api`:

   a. **Inline line comment with committable suggestion** (REQUIRED for diff lines):
      Pins the finding to a line in the PR diff and creates a resolvable thread with a one-click commit button. Query the current PR head SHA and use that as `commit_id`:

      ```bash
      HEAD_SHA=$(gh pr view "$PR_NUMBER" -R "$REPO" --json headRefOid --jq .headRefOid)
      cat <<'EOF' > finding.md
      **[P1] Bug title** — explanation of the issue.

      ```suggestion
      <exact replacement lines matching the current file content>
      ```
      EOF

      gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments" \
        -F body=@finding.md \
        -f path="registry/index.json" \
        -F line=2469 \
        -f commit_id="$HEAD_SHA"
      ```

      For line ranges, add `-F start_line=<first line>` (and `-f start_side=LEFT` for deletions).

   b. **File-level comment** (fallback if line is not in the diff):
      ```bash
      gh api "repos/${REPO}/pulls/${PR_NUMBER}/comments" \
        -F body=@finding.md \
        -f path="registry/index.json" \
        -f subject_type=file
      ```

   c. **Issue comment** (last resort only for findings with NO file in the diff):
      ```bash
      gh api "repos/${REPO}/issues/${PR_NUMBER}/comments" -F body=@finding.md
      ```

3. **Your final response text MUST ONLY be a concise overall summary:**
   - A high-level assessment of the changes and review outcome.
   - An **"Out of diff"** section detailing any findings that have no diff location (e.g. missing test suites, cross-file architectural concerns, or files untouched by the PR). For each out-of-diff finding, you must include: **file name**, **line number or range** (when applicable), **severity**, and **the issue description**.
   - Do NOT duplicate the inline finding bodies or list links to created comments in your final text—all inline findings and committable code suggestions live directly in the threads created in step 2.

### Committing behavior — suggestions only

You are reviewing, not editing:

- **Do NOT modify any files and do NOT leave the working tree dirty.** The action auto-commits
  and pushes any uncommitted changes to the PR branch — that is not wanted here.
- Include a **committable suggestion** in each finding comment when it is feasible to write
  one for that specific finding. Wrap the exact replacement in a GitHub `suggestion`
  fenced block so GitHub renders a one-click **Commit suggestion** button right in the
  comment:

  ````markdown
  ```suggestion
  <exact replacement lines — must match the current file content>
  ```
  ````

  Use one contiguous block per finding, matching the existing lines it replaces; GitHub
  applies it to the file on commit. If a finding does not have a cut-and-dried fix — no
  contiguous single-file replacement — say so and describe the change needed instead of
  inventing code.

### Finding comment format

Each finding comment should contain:

1. **Severity** — `high` / `medium` / `low` (or `critical`).
2. **Location** — `file:line` (or a line range).
3. **Problem** — why it is wrong, grounded in the actual code.
4. **Suggested fix** — a GitHub `suggestion` fenced block (see "Committing behavior")
   when the fix is a contiguous replacement, otherwise a description of the change needed.

### Review scope

Look for: correctness bugs, security issues (injection, secret handling, authorization),
performance, maintainability, and test coverage gaps. Ground every finding in the actual diff
and files. Do not invent issues; verify against the code. If there are no actionable findings,
just say so in the summary comment and do not post finding comments.

## `/oc fix`

When a user message is exactly `/oc fix` or begins with `/oc fix`, fix the review feedback on
the current pull request.

### Behavior

1. **Collect ALL review feedback** — do not rely on the `<pull_request>` context alone; it may
   be partial, out of order, or missing threads you'd otherwise need to resolve. You MUST
   actively enumerate and read every source of feedback on the PR before fixing anything:
   - **List every thread** via the GraphQL query in step 3 below (with its `isResolved` state) so
     you know the complete, canonical set of threads before deciding what to act on.
   - **Skip threads already resolved.** A thread whose `isResolved` is true has already been
     dealt with — do not re-read or re-judge its contents; doing so just blows up context. Record
     it in the summary as already handled and move on. (Only revisit a resolved thread if its
     resolution appears wrong, e.g. resolved without an actual fix.)
   - **Read every inline review comment** on the open (unresolved) threads (`<pull_request_reviews>`
     → comments), not just the first one in each thread.
   - **Read every timeline / issue comment** (`<pull_request_comments>`); a real fix request can
     live there even though it is not a resolvable thread.
   - **Read every review body / overall PR review summary** (`<pull_request_reviews>`), including
     comments on the diff that were never grouped into a thread.
   - **Read the pull request body itself** for context.
   Every comment that contains feedback — open inline threads, timeline, review-body — must be
   judged. Do not skip an open comment only because it is not inline-resolvable; it still counts
   as addressed. Resolved threads are the one exception and may be skipped to save context.
2. **For each comment, judge whether it is valid and actionable** against the current code:
   - **Valid and fixable** → implement the fix by editing files in the working tree. The
     GitHub Action auto-commits and pushes any uncommitted changes to the PR branch; you do
     not need to `git commit`/`git push` yourself (though committing yourself is also fine —
     the action detects it and pushes).
   - **Not valid, not fixable, or already handled** → do not change code for it, but it still
     counts as addressed (addressed *as not valid*): reply on the thread with the reason and
     resolve it (step 3).
   - **Not an inline-resolvable thread but still contains real feedback to address** (e.g. a
      timeline comment or a general review-body request) → address it with a commit too when
      the feedback is valid, and record it in the summary.
3. **Resolve addressed review threads.** A review thread (inline review comment chain) is
   resolvable; timeline comments are not. "Addressed" includes threads you **explicitly
   skip**: a comment judged not valid, already handled, or intentionally not applicable is
   still addressed (as not valid) and gets resolved too. For every thread you resolve, reply
   on the thread with the reason first (a fix summary, or the justification for skipping)
   when possible — the thread then keeps its rationale and the author sees it in place. Use
   `gh`:

   ```bash
   # 1. List threads, their resolved state, and the first comment's databaseId
   # (For PRs with many comments, paginate reviewThreads and comments)
   gh api graphql -f query='query($owner:String!,$repo:String!,$number:Int!){repository(owner:$owner,name:$repo){pullRequest(number:$number){reviewThreads(first:100){nodes{id isResolved comments(first:10){nodes{databaseId}}}}}}}' -F owner=... -F repo=... -F number=...

   # 2. Reply to the thread with the reason before resolving
   gh api graphql -f query='mutation($id:ID!,$body:String!){addPullRequestReviewThreadReply(input:{pullRequestReviewThreadId:$id,body:$body}){comment{id}}}' -F id=THREAD_ID -f body=REASON
   #    REST equivalent (reply to the first comment in the thread):
   #    gh api repos/{owner}/{repo}/pulls/{pr_number}/comments/{comment_id}/replies -F body=@thread.md

   # 3. Resolve the thread
   gh api graphql -f query='mutation($id:ID!){resolveReviewThread(input:{threadId:$id}){thread{isResolved}}}' -F id=THREAD_ID
   ```

   Write the reason to a temp file (`thread.md`) and pass `-F body=@thread.md` when it is
   long, so multiline Markdown survives intact. Only leave open a thread you genuinely could
   not address — no fix and no justification — and say why in the summary.
4. **Your final reply text IS the single summary comment** (the action posts it). Do NOT post
   extra per-finding comments. The summary must cover **everything**:
   - **Fixed** — for each addressed item: the change made (file:line) and whether its thread
     was resolved.
   - **Not fixed (resolved as not valid)** — for each comment you skipped: a brief reason
     (invalid, already handled, duplicate, out of scope, not fixable) and a note that its
     thread was replied to and resolved.
   - **Addressed non-thread feedback** — any feedback that wasn't an inline thread but still
     warranted a code change: list the change made.
   - A short overall assessment of remaining risk.

### Fixing behavior notes

- Ground every judgment in the actual diff and files. Verify a comment is still valid against
  the current code before acting on it.
- Keep fixes minimal and targeted to the feedback. Do not refactor unrelated code.
- Resolve every thread you addressed — fixed or explicitly skipped (skipping with a reason
  is addressing *as not valid*) — and reply on each thread with the reason when possible.
  Do not resolve a thread you genuinely could not address. Do not modify files for invalid
  or duplicate feedback.
