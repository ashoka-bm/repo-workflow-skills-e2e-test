# Local Work

This file governs implementation, testing, review, evidence, and preparation
of a landing batch.

## Start from the remote base

Fetch the remote and create one prefixed branch and worktree per claimed
landing batch from the current base. Both names must include the batch issue
number, making the local work traceable to its GitHub landing-batch issue.

```bash
git fetch origin
git worktree add -b <feature|fix|chore>/<batch-issue>-<name> ../<repo>-<batch-issue>-<name> origin/<base>
```

Open the draft landing candidate before implementing the first slice so its
comments can hold every slice review, checkpoint, and invalidation record.

## Keep evidence with the work

Store commit-bound evidence at `.scratch/<batch>/evidence.md`. Record the plan,
batch, and ticket IDs; each slice's starting commit; relevant commits; focused
and full test results; reviewer and reviewed commit; documentation impact; and
each review finding's stable ID, priority, evidence, relationship to the
candidate, and review-time disposition. Use
[`docs/agents/review-findings.md`](docs/agents/review-findings.md) as the
finding and review-time disposition authority.

Do not copy shared issue status, assignees, dependencies, readiness, or Queue
sequence into local files. GitHub Issues own issue state, and the configured
GitHub Project displays Queue sequence. Only the coordinator writes or clears
that field through the serialized landing protocol in `GITHUB-WORKFLOW.md`.

## Plan safe parallel work

- Each claimed landing batch has exactly one owner.
- Its child tickets remain unassigned; that owner may complete several dependent
  slices under the one claim.
- Prefer one branch that can accumulate compatible slices; create another batch
  only for a documented safety, flow, staged-landing, recovery, or review reason.
- Treat the batch as a landing boundary, not an execution wave. `local_after`
  orders slices on this branch; `lands_after` orders batch landing.
- Different owners may claim different batches only when their dependencies and
  conflict surfaces show that parallel work is safe.
- Shared resources must be named as conflict surfaces.
- If implementation reveals a new dependency or conflict, stop the affected
  work, update the GitHub plan and native dependency relationships, and
  re-evaluate which batches remain safe to run in parallel.

## Treat authority, evidence, and documentation separately

For audits and behavior claims, check these independently:

- **Implementation:** the behavior or mechanism exists in code.
- **Adoption:** the intended callers, data, or configurations use it.
- **Enforcement:** tests, validation, permissions, or gates prevent bypass.
- **Runtime posture:** deployed systems actually have the claimed state.

“Implemented” does not mean adopted, enforced, deployed, or running. Give every
material behavior change its smallest durable documentation home and update it
in the same slice.

## Landing-batch completion loop

A batch is ready to claim when its GitHub landing prerequisites are resolved and
its listed conflict surfaces do not overlap active work. Claim it through
[`COORDINATION.md`](COORDINATION.md) before starting; assignment without a
recorded claim receipt is not enough.

### 1. Confirm the contract

Read the batch, child tickets, approved implementation specification, and only
the repository context needed for the affected code.

### 2. Implement a slice

Use test-driven development for behavioral changes. Keep each slice bounded to
one child ticket. Tests and documentation required to make an implementation
complete belong to the same child ticket and slice. Never create a separate or
follow-up ticket merely to add them. A documentation-only or test-infrastructure
ticket is valid only when that work is the independently approved outcome, not
unfinished proof or documentation for another implementation.

Choose any incomplete slice on the local frontier: every ticket named by its
`local_after` relationship must have a current `slice-checkpoint`. A root slice
has no local prerequisite and is immediately executable. Ticket closure is not
a prerequisite for local work; child tickets remain open until their batch
lands. Record a starting commit that contains every current local prerequisite
commit; the completed slice commit must strictly descend from it.

### 3. Verify the logic

Walk the result against every acceptance criterion and its proving method. Prove
observable behavior at the most stable useful boundary. Reuse or extend existing
coverage when it is sufficient; one proof may satisfy multiple acceptance
criteria. Do not add tests solely to preserve intentionally removed behavior,
exact prose that is not itself a contract, or internal implementation structure.
Remove obsolete tests with the behavior they protected. Run the smallest
relevant tests and inspect their real output.

### 4. Commit and review locally

Record the focused proof in `.scratch/<batch>/evidence.md` and commit the slice
candidate before another agent reviews it. Have that agent review the exact
commit for correctness, boundary and architecture fit, maintainability, test
quality, and documentation accuracy.
Use the approved child-ticket outcome as the intent authority and review the
exact diff from the slice's recorded starting commit through the reviewed
commit. Handoffs, previews, and implementation summaries may help locate the
work, but they do not define the expected behavior and are not review subjects.
Inspect surrounding code only as needed to understand the diff's effects. Every
candidate finding must connect to the approved outcome or a concrete risk
introduced, worsened, or exposed by that diff. Classify findings under
[`docs/agents/review-findings.md`](docs/agents/review-findings.md). Fix P0 and
P1 blockers. Record a durable review-time disposition for every P2 and P3
without expanding the current batch, using the parent plan's single
deferred-findings register when later triage is needed.

One review cycle allows at most five review passes: the initial review and up
to four focused re-reviews of blocker repairs and the behavior they can affect.
If a P0 or P1 remains or appears on the fifth pass, stop the loop, mark the
candidate blocked when one exists, request human re-scope or redesign, and
apply `workflow:needs-human-review` to the landing-batch issue.

Review is fail-closed as defined in [`AGENTS.md`](AGENTS.md). Any
implementation change invalidates review of the affected behavior, not
unrelated surfaces. Commit a repair and repeat the affected review before
publishing a checkpoint.

### 5. Publish the checkpoint

When the slice is review clean, add its review result to
`.scratch/<batch>/evidence.md`; a later evidence-only commit does not change the
reviewed slice commit. Have the reviewer post `slice-review` for the exact
reviewed slice diff, then have the batch owner post `slice-checkpoint` bound to
that commit, review, and current claim using
[`.workflow/coordination-records.md`](.workflow/coordination-records.md).
Keep child tickets open until the landing batch lands.

A current slice checkpoint satisfies `local_after`. Recompute the local
frontier immediately and begin any newly executable slice. If the frontier is empty
while incomplete slices remain, record the exact blocker, preserve the branch,
and release or hand off the batch rather than waiting for an artificial wave.

## Changing an earlier dependency

When an earlier slice's behavior or proof changes, post
`slice-checkpoint-invalidated`, identify every dependant, and repeat affected
tests and review. The derived frontier keeps those dependants blocked until the
prerequisite chain has current checkpoints again. Update the GitHub landing
relationships if the safe order or parallel plan also changed.

## Maintain the landing candidate

Maintain the draft pull request opened before the first slice — the batch's
landing candidate.
When every batch acceptance criterion is proved and all slices are review
clean, have the exact-commit reviewer post `local-review`, then post the
owner-authored `local-complete` record bound to that review and the current
accepted claim receipt, worker, and session from
[`.workflow/coordination-records.md`](.workflow/coordination-records.md) for the
exact pull-request head. Do not request a queue position until the controller
has set the landing batch's Project `Lifecycle` to `Locally complete`. Any later
commit invalidates that completion record and requires the affected checks,
review, and record to be repeated.
Queueing, the ready-for-review gate at its landing turn, and leaving draft
status are governed by [`GITHUB-WORKFLOW.md`](GITHUB-WORKFLOW.md).

## Clean up after a confirmed merge

The batch owner cleans its local checkout only through authenticated GitHub
evidence that the pull request has merged. A closed, unmerged pull request is
not permission to remove local work.

From a different retained worktree for the same repository, run the bundled
cleanup command with the GitHub repository and pull request that own the exact
batch branch and worktree. The command reads `GH_TOKEN` or `GITHUB_TOKEN`:

```bash
python3 .workflow/scripts/cleanup_landed_batch.py \
  --repository <retained-repository-worktree> \
  --worktree <batch-worktree> \
  --branch <batch-branch> \
  --github-repository <owner/repository> \
  --pull-request <number>
```

The token needs pull-request read access. The configured `origin` Git remote
must authenticate to the same GitHub repository with permission to delete the
batch branch.

For fail-closed target binding, cleanup refuses Git remotes that use
`url.*.insteadOf` or `url.*.pushInsteadOf` rewriting; use one direct push URL.

The command verifies the authoritative merged PR, binds `origin` to that
repository, and uses an expected-SHA lease to delete the remote branch only if
it still points to the merged head. It then removes only the registered batch
worktree and deletes the local branch with the same expected-SHA guard. It
refuses cleanup when the worktree contains modified, untracked, or ignored
files, belongs to
another repository, is checked out on another branch, or its local or remote
head differs from the merged PR head. Preserve the worktree and report the
recovery details when cleanup is refused; never force-remove ambiguous,
unpushed, or unmerged work. A partial result is reported separately if a
failure occurs after remote deletion, with the remaining local ref preserved
for recovery.
