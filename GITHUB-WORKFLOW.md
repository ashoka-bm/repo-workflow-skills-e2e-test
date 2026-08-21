# GitHub Workflow

Pull requests assemble and merge batches. GitHub Issues are the source of truth
for plans, landing batches, tickets, native dependencies, ownership, and
progress. Mergify is responsible for the final serialized merge queue.

## Repository setup contract

Use `configure-github-workflow` and
[`docs/agents/github-setup.md`](docs/agents/github-setup.md) before planning.
Install the Mergify GitHub App and keep [`.mergify.yml`](.mergify.yml) on the
default branch.

Protect the base branch with a ruleset that:

- requires the repository's selected status checks;
- requires the pull request branch to be up to date with the base branch;
- requires resolved review conversations;
- blocks force pushes and deletion; and
- applies to administrators and automation with no routine bypass.

Do not also enable GitHub's native merge queue. Mergify is the one merge queue.
Configure expensive hosted CI for `ready_for_review`, and for `synchronize` or
`reopened` only when `github.event.pull_request.draft == false`. Draft events
and ordinary batch-branch pushes do not run the landing gate.

## Each batch has one landing candidate

The landing candidate is the one pull request for a claimed landing batch. Open
it as a draft before implementation. Several draft landing candidates may
coexist. A draft is a place to accumulate slice evidence; it is not queued and
does not run expensive landing CI. After Mergify accepts it, it becomes a
queued landing candidate.

When a cross-batch `local_after` prerequisite is current but its batch has not
merged, the downstream draft may stack on the upstream batch branch and record
the exact checkpoint binding. A `lands_after` edge prevents merging but not
claiming or building. A `starts_after` edge is different: the downstream batch
cannot be claimed or built until that prerequisite has merged, and every
`starts_after` edge must also be a direct `lands_after` edge.

Each PR uses [`.github/pull_request_template.md`](.github/pull_request_template.md)
and links its parent plan, landing batch, and child tickets. Use closing
keywords only for issues fully delivered by that batch.

## Local completion and readiness

The batch owner must report local completion by posting the structured
`local-complete` record only after the pull request's current commit
passes the local completion loop and independent review. Automation treats
that record as the trigger; it never infers completion from tests, labels, or an
apparently finished diff. A later commit invalidates that evidence; repeat the
affected checks and review before queueing.
Post workflow records with the reporting actor's GitHub credential. GitHub
suppresses follow-on workflow runs for events created by a repository Action's
`GITHUB_TOKEN`, so that token cannot publish the completion report.
The owner confirms GitHub shows `Lifecycle: Locally complete` before queue
entry.

`Lifecycle` applies only to landing-batch issues. Plans and child tickets
intentionally have no `Lifecycle` value: plan state comes from approval and
closure, while child-ticket progress comes from current slice checkpoints and
the parent batch. This avoids two competing sources of progress state.

GitHub assignment is the ownership authority. A sole assignee means the issue
is claimed immediately; an unassigned issue is available. `Lifecycle` mirrors
landing-batch delivery state and is not an extra claim approval gate.

The trusted Lifecycle workflow verifies each durable trigger, writes the
Project value, and re-reads it. Agents must wait for the observed value before
reporting the transition complete. If the action fails, leave `Lifecycle`
unchanged and route recovery to an authorized workflow maintainer; never advance a
card because work merely looks ready.
Lifecycle event jobs run independently because repository-wide Actions
concurrency can replace a pending event. Every job re-validates live state and
the allowed prior Lifecycle value, so duplicate or out-of-order events fail
closed instead of skipping a transition. Queue events must still match the
PR's current mutually exclusive Mergify state labels. If merge evidence arrives
before its queue event, the workflow records the missing `In PR` transition
before `Landed` so the Project converges without erasing the lifecycle step.
After a queue-state write, it rechecks those live labels and corrects a raced
transition; if state does not stabilize within the bounded reconciliation, the
action fails for workflow-maintainer repair.

Lifecycle transitions remain GitHub-visible:

| Transition | Durable trigger | Writer |
| --- | --- | --- |
| `Planned` to `Building` | Landing batch receives its sole assignee | Lifecycle workflow |
| `Building` to `Planned` | Landing batch becomes unassigned | Lifecycle workflow |
| `Building` to `Locally complete` | Current-commit `local-complete` | Lifecycle workflow |
| `Locally complete` to `In PR` | Mergify applies `workflow:queued` for that commit | Lifecycle workflow |
| `In PR` to `Landed` | GitHub reports the PR merged into the configured base | Lifecycle workflow |
| `In PR` to `Locally complete` | Mergify applies `workflow:dequeued` while current-commit evidence remains valid | Lifecycle workflow |
| `Locally complete` or `In PR` to `Building` | New pull request commit, maintainer evidence invalidation, or accepted rework request | Lifecycle workflow |

The action uses the repository `GITHUB_TOKEN` for read-only evidence checks and
the `WORKFLOW_PROJECT_TOKEN` secret for organization Project updates. It runs
trusted default-branch code for `pull_request_target`; it never checks out or
executes candidate PR code.

When a batch reaches `Locally complete`, freeze its dependency and batch
contract. That means the approved outcome, acceptance criteria, scope and
out-of-scope boundary, verification requirements, documentation and operational
commitments, `lands_after`, `starts_after`, child membership, conflict
surfaces, and the PR's `Landing batch` and `Depends-On` markers. GitHub Actions
cannot subscribe directly to native issue-dependency changes without another
GitHub App, so this freeze is a workflow-maintainer-enforced rule. If any
frozen value must change, dequeue the PR, remove
`workflow:landing-validated`, return the PR to draft, invalidate
`local-complete`, wait for `Lifecycle: Building`, make the approved
planning change, and repeat review and queue entry. Do not edit frozen values
while the candidate remains eligible to merge.

Before making the draft ready for review, the queue-entry command will verify
the dependency and evidence rules below. The batch owner also confirms them:

1. confirm every `lands_after` prerequisite has merged;
2. reconcile with the latest remote base and resolve conflicts locally;
3. run all applicable full local tests, builds, and static checks from
   [`AGENTS.md`](AGENTS.md);
4. update the evidence file and PR description, and commit that update — this
   evidence commit precedes the final review so the reviewed commit is the one
   that queues;
5. have an independent reviewer check the exact base-to-candidate diff against
   the approved landing-batch outcome and every included approved child-ticket
   outcome; and
6. confirm the candidate is review clean under
   [`docs/agents/review-findings.md`](docs/agents/review-findings.md), freezing
   each finding's review-time disposition with the reviewed commit.

The review itself changes no commits: its verdict is recorded as a pull request
comment (`local-review`), so a clean pass needs no further evidence commit and
the reviewed commit queues as-is. If the review records new P2 or P3 findings,
add their dispositions to the evidence file, commit, and have the same reviewer
confirm that evidence-only commit in one focused re-review; because it contains
no behavior change, that confirmation ends the cycle rather than restarting it.
Any behavior-changing commit after the reviewed commit invalidates that review
and returns to step 3.

Then mark the PR ready for review and use the queue-entry command in
[`docs/agents/mergify-runbook.md`](docs/agents/mergify-runbook.md). Do not use
GitHub auto-merge or click GitHub's merge button in normal operation.

## Queue and priority

`.mergify.yml` defines one serial queue with `batch_size: 1`. Repository
landing batches therefore remain one PR each and are never combined by
Mergify. Mergify requires `landing-evidence`, `landing-gate`, a non-draft PR,
the queue-entry label `workflow:landing-validated`, and no
`workflow:needs-human-review` hold before merging. The evidence check
runs trusted default-branch code for every non-draft commit and fails unless the
current sole assignee, `local-complete`, and independent `local-review`
records bind that exact commit in chronological order. Branch protection may
impose additional checks or approvals.

Run `.workflow/scripts/queue_landing.py` for every queue attempt. It derives
priority from the plan rather than trusting a manually applied label:

- reject the candidate unless every native `lands_after` prerequisite has a
  merged landing PR, except an open direct predecessor in the same physically
  chained `Depends-On:` stack being queued bottom-up;
- if an open downstream landing batch explicitly `Starts after` this PR's
  batch, apply `workflow:unlocks-work` and give the PR high priority;
- propagate that priority to open `Depends-On:` predecessors so a stacked
  unlocker cannot wait behind its own prerequisite;
- validate the sole assignee, current-commit evidence, native `lands_after`
  relationship, ready state, and `BATCH` issue for every open stack member, then apply
  `workflow:landing-validated` to each one;
- otherwise remove a stale priority label from the PR; and
- only after classification succeeds, post `@mergifyio queue`.

The command adds `workflow:landing-validated` only after those live checks
pass for the candidate and every propagated predecessor. Do not post the
Mergify command or apply that label by hand. Any change
to landing dependencies or batch metadata invalidates it: dequeue the PR,
remove the label, and rerun the command after the plan is correct.

High priority means “this merge makes another batch available to start.” It
does not mean merely “another PR must merge after this one.” Priority does not
interrupt checks already running; the unlocker goes immediately after them.
Arrival order resolves ties within the same priority.

This prioritization improves flow but is not a throughput guarantee. The
expected rate of at most roughly one PR per work stream per hour comes from
coherent ticket batching, not from a timer or custom scheduler.

## CI failure, review defects, and rework

Diagnose hosted failures locally. Fix P0/P1 blockers, repeat affected gates,
and perform the focused re-review required by the bounded review cycle. Give
P2/P3 findings durable dispositions without expanding the candidate.

If work needs material rework, comment `@mergifyio dequeue`, remove
`workflow:landing-validated`, return the PR to draft, invalidate the old
completion, set the batch back to `Building`, and refresh local-completion
evidence.
If a blocker remains after five review passes, apply
`workflow:needs-human-review` to both the landing-batch issue and its PR so the
current-commit evidence check and Mergify both stop the candidate, then request
human re-scope or redesign. When the
candidate is ready again, run the same queue-entry command; do not use the
deprecated `requeue` command.

## Merge and cleanup

GitHub's merged state is the source of truth for a merge. The Lifecycle workflow
records `Lifecycle: Landed`; an authorized workflow maintainer
closes the landing batch and only the declared, delivered child tickets. A
closed, unmerged PR has not reached `Lifecycle: Landed`.

The batch owner then follows the authenticated post-merge procedure in
[`LOCAL-WORK.md`](LOCAL-WORK.md). It verifies the confirmed merge and current
commit before deleting the remaining remote batch branch, exact local worktree,
and local branch. Cleanup refusal preserves local work for recovery.
