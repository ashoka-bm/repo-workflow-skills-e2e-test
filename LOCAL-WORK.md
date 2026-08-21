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
GitHub refuses a pull request when its branch has no commits beyond the base, so
bootstrap the candidate with one empty commit and push before opening the draft:

```bash
git commit --allow-empty -m "chore: open landing candidate for #<batch-issue>"
git push -u origin <feature|fix|chore>/<batch-issue>-<name>
```

The bootstrap commit is not a slice — an empty diff is never a slice — and no
record binds to it; it exists only so the draft can be created before
implementation starts.

## Keep evidence with the work

Store commit-bound evidence at `.local-work/<batch>/evidence.md`. Record the plan,
batch, and ticket IDs; each slice's starting commit; relevant commits; focused
and full test results; reviewer and reviewed commit; documentation impact; and
each review finding's stable ID, priority, evidence, relationship to the
candidate, and review-time disposition. Use
[`docs/agents/review-findings.md`](docs/agents/review-findings.md) as the
finding and review-time disposition authority.

Do not copy shared issue status, assignees, dependencies, readiness, or queue
priority into local files. GitHub Issues are the source of truth for issue state
and dependency relationships. Mergify is responsible for current queue state.
Priority is derived at queue entry.

## Plan safe parallel work

- Each claimed landing batch has exactly one owner.
- Before a slice starts, its worker assigns the child ticket to themself. The
  ticket assignment is its complete claim. The batch owner remains accountable
  and integrates delegated work one slice at a time.
- Prefer one branch that can accumulate compatible slices; create another batch
  only for a documented safety, flow, staged-landing, recovery, or review reason.
- Treat the batch as a merge boundary, not an execution wave. `local_after`
  orders slices on this branch; `lands_after` orders batch merges.
- Different owners may claim different batches—including downstream stacked
  batches—when current checkpoints and conflict surfaces make building safe.
- Do not claim or build a batch with an unresolved `starts_after` gate. That
  edge is intentionally stronger than an ordinary landing prerequisite.
- Shared resources must be named as conflict surfaces.
- If implementation reveals a new dependency or conflict, stop the affected
  work, update the GitHub plan and native dependency relationships, and
  re-evaluate which batches remain safe to run in parallel.

GitHub ticket assignment remains the shared claim for delegated work. Use
sequential execution when slices overlap.

## Treat authority, evidence, and documentation separately

For audits and behavior claims, check these independently:

- **Implementation:** the behavior or mechanism exists in code.
- **Adoption:** the intended callers, data, or configurations use it.
- **Enforcement:** tests, validation, permissions, or gates prevent bypass.
- **Runtime posture:** deployed systems actually have the claimed state.

“Implemented” does not mean adopted, enforced, deployed, or running. Give every
material behavior change its smallest durable documentation home and update it
in the same slice.

## Proof and documentation policy

A verification method is the test or check used to verify an acceptance
criterion. Evidence is the saved result showing that verification happened.
This policy uses “proof” as a short umbrella term for the required verification
and its evidence.

Tests and documentation required to make an implementation complete belong to
the same child ticket, slice, and change. Never create a separate or follow-up
ticket merely to add them. A documentation-only or test-infrastructure ticket
is valid only when the exact approved implementation specification already
defines it as a standalone outcome with independent user or engineering value.
Ticket-breakdown approval alone does not qualify, and the ticket must not finish
verification or documentation deferred from another implementation.

Verify observable behavior at the most stable useful boundary. Reuse or extend
existing coverage when it is sufficient; one verification method may satisfy multiple
acceptance criteria. Do not add tests solely to preserve intentionally removed
behavior, exact prose that is not itself a contract, or internal implementation
structure. Remove obsolete tests with the behavior they protected.

## Landing-batch completion loop

A batch is ready to claim when at least one starting slice is executable, that
ticket's conflict surfaces do not overlap active work, and no explicit
`must_not_overlap` contract forbids the claim. An unresolved
`lands_after` relationship blocks merging, but does not block claiming or
building from a current prerequisite checkpoint on a stacked branch. An
unresolved `starts_after` relationship does block claiming and building and
cannot be satisfied by a checkpoint. Claim an otherwise ready batch through
[`COORDINATION.md`](COORDINATION.md) before starting. Assigning yourself and
re-reading GitHub to confirm you are the only assignee is the complete claim.

### 1. Confirm the contract

Read the batch, child tickets, approved implementation specification, and only
the repository context needed for the affected code.

### 2. Implement a slice

Use test-driven development for behavioral changes. Keep each slice bounded to
one child ticket and follow the [proof and documentation
policy](#proof-and-documentation-policy).

Choose any incomplete slice on the local frontier: every ticket named by its
`local_after` relationship must have a current `slice-checkpoint`. A root slice
has no local prerequisite and is immediately executable. Ticket closure is not
a prerequisite for local work; child tickets remain open until their batch
merges. Before starting, assign the child ticket to yourself and re-read GitHub;
do not start if another person is assigned. Record a starting commit that
contains every current local prerequisite commit; the completed slice commit
must strictly descend from it.

When a checkpoint unlocks a dependent slice, start it from the prerequisite
checkpoint, not from a batch head that already contains unrelated slices. Add
another slice to that starting commit only when it is an explicit prerequisite
or is required by a named conflict surface. Do not rebase independent worker
branches onto one another merely to make the history linear.

For a cross-batch local prerequisite, create or refresh the downstream stacked
branch from the exact upstream checkpoint commit. Keep its draft pull request
stacked on the upstream branch until that batch merges, then retarget or rebase
it without changing the reviewed behavior. Bind the downstream checkpoint to
the exact upstream checkpoint using `prerequisite_checkpoints`.

When several frontier slices are conflict-safe, the owner may delegate them to
parallel slice workers. After accepting a delegation, each worker assigns the
ticket to themself before starting. Workers use isolated local branches; they
never push competing histories to the shared batch branch. Each worker posts a
`slice-delivery` for its exact result. The owner integrates each result, reruns
affected verification, obtains review of the integrated commit, and publishes
the checkpoint bound to that worker-authored delivery. When subagents are
unavailable, use the same frontier rules with sequential execution.

### 3. Verify the logic

Walk the result against every acceptance criterion and its verification method. Run
the smallest relevant tests and inspect their real output.

### 4. Commit and review locally

Record the focused verification result in `.local-work/<batch>/evidence.md` and
commit the slice candidate before an independent reviewer checks it. Have that
reviewer check the exact
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
Apply the same hold to its PR so Mergify removes it from the queue.

Review is fail-closed as defined in [`AGENTS.md`](AGENTS.md). Any
implementation change invalidates review of the affected behavior, not
unrelated surfaces. Commit a repair and repeat the affected review before
publishing a checkpoint.

### 5. Publish the checkpoint

When the slice is review clean, add its review result to
`.local-work/<batch>/evidence.md`; a later evidence-only commit does not change the
reviewed slice commit. Have the reviewer post `slice-review` for the exact
reviewed slice diff, then have the batch owner post `slice-checkpoint` bound to
that commit, review, current assignee, and any delegated worker's
`slice-delivery` using
[`.workflow/coordination-records.md`](.workflow/coordination-records.md).
Keep child tickets open until the landing batch merges.

A current slice checkpoint satisfies `local_after`. Recompute the local
frontier immediately and continue with newly executable, conflict-safe work.
When the checkpoint unlocks another slice, dispatch that newly unlocked work
before processing unrelated completed deliveries; their review and integration
can continue afterward. If the frontier is empty while incomplete slices
remain, record the exact blocker, preserve the branch, and release or hand off
the batch.

## Changing an earlier dependency

When an earlier slice's behavior or verification changes, post
`slice-checkpoint-invalidated`, identify every dependent, and repeat affected
tests and review. The derived frontier keeps those dependents blocked until the
prerequisite chain has current checkpoints again. Update the GitHub dependency
relationships if the safe order or parallel plan also changed.

## Maintain the landing candidate

Maintain the landing candidate—the batch's one pull request—as a draft while
building.
When every batch acceptance criterion is verified and all slices are review
clean, have the exact-commit reviewer post `local-review`, then post the
owner-authored `local-complete` record with the implementation worker and
session, bound to that review, from
[`.workflow/coordination-records.md`](.workflow/coordination-records.md) for the
pull request's current commit. Do not queue until the Lifecycle workflow has set the
landing batch's Project `Lifecycle` to `Locally complete`. Any later
commit invalidates that completion record and requires the affected checks,
review, and record to be repeated.
The ready-for-review gate, priority classification, and Mergify queue entry are
governed by [`GITHUB-WORKFLOW.md`](GITHUB-WORKFLOW.md).

## Clean up after a confirmed merge

The batch owner cleans its local checkout only through authenticated GitHub
evidence that the pull request has merged. A closed, unmerged pull request is
not permission to remove local work.

From a different retained worktree for the same repository, run the bundled
cleanup command with the GitHub repository and pull request that identify the
exact batch branch and worktree. The command reads `GH_TOKEN` or `GITHUB_TOKEN`:

```bash
python3 .workflow/scripts/cleanup_landed_batch.py \
  --repository <retained-repository-worktree> \
  --worktree <batch-worktree> \
  --branch <batch-branch> \
  --github-repository <owner/repository> \
  --pull-request <number>
```

The token needs pull request read access. The configured `origin` Git remote
must authenticate to the same GitHub repository with permission to delete the
batch branch.

For fail-closed target binding, cleanup refuses Git remotes that use
`url.*.insteadOf` or `url.*.pushInsteadOf` rewriting; use one direct push URL.

The command verifies the confirmed merged pull request, binds `origin` to that
repository, and uses an expected-SHA lease to delete the remote branch only if
it still points to the merged commit. It then removes only the registered batch
worktree and deletes the local branch with the same expected-SHA guard. It
refuses cleanup when the worktree contains modified, untracked, or ignored
files, belongs to
another repository, is checked out on another branch, or its local or remote
commit differs from the merged pull request's commit. Preserve the worktree and report the
recovery details when cleanup is refused; never force-remove ambiguous,
unpushed, or unmerged work. A partial result is reported separately if a
failure occurs after remote deletion, with the remaining local ref preserved
for recovery.
