# GitHub Workflow

Pull requests assemble and land batches; GitHub Issues remain authoritative for
plans, landing batches, tickets, native dependencies, ownership, and progress.

## Repository setup contract

Use `configure-github-workflow` and the authority in
[`docs/agents/github-setup.md`](docs/agents/github-setup.md) to initialize and
verify this contract before planning begins.

Protect the base branch with a branch ruleset that:

- requires the repository's selected required status checks;
- requires the pull request branch to be up to date with the base branch;
- requires resolved review conversations;
- blocks force pushes and deletion; and
- applies to administrators and automation with no routine bypass.

Do not enable GitHub's merge queue; this workflow owns FIFO activation.

Configure expensive hosted CI for pull requests targeting the base branch. It
must run for `ready_for_review`, and for `synchronize` or `reopened` only when
`github.event.pull_request.draft == false`, never for draft events or ordinary
batch-branch pushes. A typical gate:

```yaml
on:
  pull_request:
    branches: [<base>]
    types: [ready_for_review, synchronize, reopened]

jobs:
  full-gate:
    if: github.event.pull_request.draft == false
```

Use the base branch, exact required status-check names, and full-gate commands
configured in [`AGENTS.md`](AGENTS.md).

## Draft pull requests are landing candidates

Draft pull requests are landing candidates, not a second ticket system: one per
claimed landing batch, updated as locally complete slices accumulate.
Several draft candidates may coexist for independently owned batches.

Draft candidates do not enter the active landing position or run expensive CI,
but still require the per-slice local gates in [`LOCAL-WORK.md`](LOCAL-WORK.md).
Keep the draft open as compatible slices accumulate and avoid per-slice GitHub
CI. Run expensive GitHub CI for the complete batch at its landing attempt, and
rerun it when later changes invalidate that attempt.

Each pull request links its parent plan, landing batch, and child tickets and
uses [`.github/pull_request_template.md`](.github/pull_request_template.md),
completing every section.

Use closing keywords only for issues fully delivered by the batch; a draft may
list them because GitHub applies them only on merge.

## Lifecycle transitions

Every lifecycle change has one durable GitHub trigger and one responsible
writer:

| Transition | Trigger | Writer |
| --- | --- | --- |
| `Planned` to `Building` | Accepted claim for a fresh landing batch | Claim coordinator |
| `Building` to `Locally complete` | Current owner-authored `local-complete` record for the exact PR head | Landing controller |
| `Locally complete` to `Waiting to land` | Accepted `queue-request` | Landing controller |
| `Waiting to land` to `In PR` | Current `promote-request` at the candidate's landing turn | Landing controller |
| `In PR` to `Landed` | GitHub reports the pull request merged | Landing controller |
| `Locally complete` to `Building` | The PR head no longer matches its completion record | Landing controller |
| `Waiting to land` or `In PR` to `Building` | Accepted substantial-rework record | Landing controller |

The batch owner posts `local-complete` only after the local completion loop is
proved for the exact draft PR head. The controller verifies that the record was
authored by the current owner, references the current accepted claim receipt,
matches that claim's worker and session, and binds its gates to a passing
exact-commit review authored by another GitHub actor. Claim, review, completion,
and invalidation evidence must remain unedited after posting. It then sets
`Lifecycle` from `Building` to `Locally complete`. A later commit invalidates
and durably retires that evidence and any partial queue state; the controller
returns it to `Building` before accepting any queue request. The owner must
repeat the affected checks and review and post new commit-bound records.

Use a protected GitHub App identity or named human as the authorized
coordinator. Batch workers must not control that identity. Coordinator-authored
retirement records are part of the workflow's trusted GitHub history; editing
or deleting one is an administrative integrity incident, not a supported
workflow action.

## FIFO landing order

Landing order is first in, first out by when a locally complete draft posts the
`queue-request` record defined in
[`.workflow/coordination-records.md`](.workflow/coordination-records.md), which
the batch owner posts in the landing pull request's comments and the coordinator
serializes under [`COORDINATION.md`](COORDINATION.md). When it
accepts the request, the coordinator performs one serialized operation: assign
the sequence, post that value in the `queue-receipt`, write the same value to
the landing-batch issue's Project item, and set `Lifecycle` to `Waiting to
land`. The first accepted request receives Queue sequence `1`; each later
request receives one more than the highest Queue sequence ever accepted. The
monotonically increasing Queue sequence is immutable and never reused or
recalculated from GitHub timestamps, Project ordering, or current queue length.
A queue request is not the ready-for-review event: the candidate remains draft
and CI stays inactive.

However many drafts exist, only one non-draft pull request is the active landing
candidate, and no later candidate activates until it lands or becomes blocked.
Blocking and unblocking never change Queue sequence: record the blocker,
return it to draft, then activate the lowest-sequence eligible draft; when the
condition clears the coordinator posts a `candidate-unblocked` record and
re-evaluates the lowest-sequence eligible draft. A blocked candidate keeps its
place and is skipped only until it is eligible again. Each transition is one
serialized coordinator operation, so two candidates are never non-draft at
once. Eligibility never changes only in local notes or by inference.

A temporary blocker or bounded correction inside the approved batch scope is
not substantial rework. Substantial rework begins when the approved scope or
acceptance criteria change, or when the batch owner reports that the batch no
longer meets the `Locally complete` definition and returns to implementation.
The coordinator then performs one serialized operation: post a
`candidate-rework` record, retire the candidate's Queue sequence, clear the
landing-batch issue's `Queue sequence` Project field, return the batch to
`Building`, and keep the pull request draft. After the batch is locally complete
again, its owner posts a new `queue-request`; an accepted request receives the
next Queue sequence. Retired sequences are never reused.

## Ready-for-review gate

When a draft reaches its landing turn:

1. rebase or otherwise reconcile it with the latest remote base branch;
2. resolve conflicts locally and repeat any affected focused verification;
3. run all applicable full local tests, builds, and static checks, using the
   repository-specific commands in [`AGENTS.md`](AGENTS.md);
4. have another agent review the exact recorded-base-to-integrated-commit diff
   against the approved landing-batch outcome and every included approved
   child-ticket outcome;
5. confirm the candidate is review clean under
   [`docs/agents/review-findings.md`](docs/agents/review-findings.md);
6. update the evidence and pull-request description;
7. post a `promote-request` bound to the exact candidate and base commits.

The serialized controller verifies that the request is current, the candidate
is the lowest-sequence eligible draft, and no other candidate is non-draft. The
controller marks the pull request ready for review, records its activation, sets its
Project lifecycle to `In PR`, and enables GitHub auto-merge. The controller
does not call the merge endpoint directly: GitHub keeps the pull request open
until all required checks and any configured approvals pass, then performs the
configured merge. A named human coordinator may perform the same transition
when the controller is disabled.

## When CI or review finds a defect

Return to the local workflow and classify the defect under
[`docs/agents/review-findings.md`](docs/agents/review-findings.md). Fix P0/P1
blockers, repeat affected gates, and perform only the focused re-review required
by the bounded review cycle. Give P2/P3 findings durable review-time
dispositions without expanding the candidate. If a P0 or P1 blocker remains or
appears after five review passes, post a `candidate-blocked` record, return the
pull request to draft, request human re-scope or redesign, apply
`workflow:needs-human-review` to the landing-batch issue, and advance other
eligible work.
Use hosted failure logs for diagnosis. Do not make untested fixes directly in
GitHub.

## Merge

Merge only when the active candidate is review clean, still represents the
locally reviewed commit, all required GitHub checks and any configured
approvals pass, and no dependency or base-branch change has invalidated its
evidence. GitHub auto-merge enforces these repository gates.

The controller treats a pull request `closed` event with `merged == true` as
the authoritative landing signal. It records the merge, closes the landing
batch and declared child tickets, and advances the lowest-sequence eligible
draft candidate. As part of that transition, it must delete its remote batch
branch and unblock dependants. A
closed, unmerged pull request is instead flagged for attention and retains its
queue position. GitHub is authoritative for the pull request and merge commit;
local evidence does not need a follow-up commit only to copy those identifiers.

The batch owner must use the authenticated post-merge procedure in
[`LOCAL-WORK.md`](LOCAL-WORK.md). It verifies the authoritative merge and exact
head before deleting any remaining remote batch branch, then removes the exact
local worktree and local branch. Cleanup refusal preserves local work for
recovery and does not change the landed GitHub state.
