# Mergify Landing Runbook

Mergify is responsible only for the final serialized merge. GitHub Issues are
the source of truth for the plan, landing batches, `lands_after`, and
`starts_after`. The repository workflow verifies the evidence that says a
candidate is ready.

## Automatic lifecycle updates

The Project `Lifecycle` field is for landing-batch issues only. Plans and child
tickets leave it empty. The trusted Lifecycle workflow verifies each event,
updates the field, and re-reads the Project item. Agents wait for the resulting
value; an authorized workflow maintainer repairs a failed action instead of moving a
card based on appearance. Delayed queue events are checked against the PR's
current Mergify labels, and an early merge event records `In PR` before
`Landed`. The workflow rechecks queue state after writing and corrects an
overlapping transition or fails visibly if state does not stabilize:

| Verified trigger | Batch lifecycle |
| --- | --- |
| Landing batch receives its sole assignee | `Building` |
| Landing batch becomes unassigned | `Planned` |
| Current-commit `local-complete` is valid | `Locally complete` |
| Mergify confirms the current commit is queued for merge | `In PR` |
| Mergify dequeues it but current-commit evidence remains valid | `Locally complete` |
| Evidence is invalidated or rework is accepted | `Building` |
| A new commit is pushed after local completion | `Building` |
| GitHub reports the PR merged into the configured base | `Landed` |

Do not use `Waiting to land`; Mergify is responsible for live queue state. Do not move cards
based on apparent readiness.

## Queue a candidate

1. Confirm the landing batch is `Locally complete`, the pull request is ready
   for review, and the required evidence is valid for its current commit.
2. Confirm every `lands_after` prerequisite has landed. A `starts_after`
   prerequisite also prevents claiming or building the downstream batch until
   the upstream batch merges.
3. Run:

   ```bash
   GH_TOKEN=<token> python3 .workflow/scripts/queue_landing.py \
     --github-repository <owner/repository> \
     --pull-request <number>
   ```

The command verifies the current sole assignee and current-commit evidence. It
rejects any native `lands_after` prerequisite without a merged landing PR or a
verified physical `Depends-On:` stack edge, reads every open landing batch's explicit
`Starts after` field, and checks each unresolved start gate against the matching
native dependency. It then reconciles `workflow:unlocks-work`
across all open landing PRs: direct unlockers and their open `Depends-On:`
predecessors receive it, and every stale copy is removed. Only after all reads,
validation, and label reconciliation succeed does it add
`workflow:landing-validated` to the top PR and every open stack predecessor,
then post `@mergifyio queue` on the top PR.

Do not add the priority label by hand. Missing, repeated, cross-repository,
ambiguous, or drifted metadata fails closed; repair the plan and native
dependency instead of guessing.
Do not add `workflow:landing-validated` or post the queue command by hand.
Changing landing dependencies or batch metadata requires dequeueing, removing
that eligibility label, and rerunning the command.

Once the batch is `Locally complete`, its entire approved contract is frozen:
outcome, acceptance criteria, scope boundaries, verification, documentation and
operational commitments, dependencies, child membership, conflict surfaces,
and PR batch/stack markers. To change one, dequeue, remove
`workflow:landing-validated`, return the PR to draft, invalidate the completion
evidence, wait for `Lifecycle: Building`, and only then edit the plan. Repeat
review and queue entry afterward.

## Queue behavior

`.mergify.yml` uses one serial queue with `batch_size: 1`. The priority label
moves work-unlocking PRs ahead of ordinary waiting PRs, but
`allow_checks_interruption: false` lets an already-running validation finish.
Mergify still requires the candidate to be non-draft, free of the human-review
hold label, and passing `landing-evidence` and `landing-gate`. A push makes the
current-commit evidence check fail until review and `local-complete` are
refreshed. Branch protection remains the source of truth for any additional
required checks or approvals.

For a physical branch stack, queue its top PR. The command validates every
member and Mergify uses matching `Depends-On:` markers to queue open
predecessors in order.

## Failure and recovery

- If classification fails, no queue command is posted. Correct the issue or PR
  metadata and run the command again.
- Every dequeue retires `workflow:landing-validated`. If CI or review fails,
  remove that label, fix the PR locally, refresh its evidence when affected, and
  rerun the same queue command. Do not use the deprecated `requeue` command.
- To stop a candidate, comment `@mergifyio dequeue` and return it to draft when
  more implementation is required.
- For a human-review escalation, apply `workflow:needs-human-review` to both
  the landing-batch issue and its PR. The issue blocks evidence validation; the
  PR label makes Mergify dequeue the candidate immediately.
- If Mergify is unavailable, leave candidates open and unmerged. A maintainer
  may use GitHub's protected merge only as an explicitly approved fallback,
  after reproducing the same ordering and gates.
