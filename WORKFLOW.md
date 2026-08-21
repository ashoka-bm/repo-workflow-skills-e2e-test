# Planning-to-Merge Workflow

This is the main process for repository work. GitHub stores shared plans and
tickets. [`LOCAL-WORK.md`](LOCAL-WORK.md) explains how to complete work locally,
and [`GITHUB-WORKFLOW.md`](GITHUB-WORKFLOW.md) explains how pull requests move
through review and merge.

**understand → resolve uncertainty when needed → vocabulary and ADRs when
needed → approved implementation specification → implementation tickets and
landing batches → implement → test → review → draft landing candidate → final
gates → CI → merge**

## 0. Initialize the repository workflow

After installation, use `configure-repository-workflow` and run
`python3 .workflow/scripts/verify_setup.py --pre-github`. The `--pre-github`
flag skips the values that GitHub setup has not created yet: the Workflow
Project, required status checks, and GitHub state config. These values should
still say `Pending GitHub setup`. Running the command without `--pre-github`
will fail at this stage by design; that does not mean the installation is
broken.

Next, use `configure-github-workflow` to create and verify the required labels,
Project fields, issue relationships, branch protection, CI triggers, lifecycle
automation, and coordination. Finish by running
`python3 .workflow/scripts/verify_setup.py` without a flag. It must now pass.
Planning begins only after both setup checks pass. Install the Mergify GitHub
App and validate the repository's `.mergify.yml`; no private queue-controller
App or long-running repository scheduler is required.

## 1. Understand and decide

Clarify the desired outcome, constraints, ownership, and important unknowns by
following the start and stop protocol in [`AGENTS.md`](AGENTS.md).

Use `plan-new-work` only for large work, work with important unknowns, or work
that will span several sessions. It organizes the questions and decisions
needed to write a specification; it does not create implementation tickets.
For smaller, well-understood work, continue directly.

When the work introduces or changes important domain terms, context boundaries,
or architecture decisions, read `docs/agents/domain.md` and use
`maintain-domain-model`. It records agreed vocabulary, context relationships,
ADRs, current-state evidence, and known disagreements in the configured
governing sources. Record an ADR when a decision will last, is surprising, crosses a
system boundary, or would be costly to reverse. Keep unresolved questions in
the planning map.

## 2. Approve the outcome

Use `write-implementation-spec` to create an approved implementation
specification containing:

- strict true-or-false acceptance criteria;
- a verification method for each criterion;
- explicit out-of-scope items;
- documentation impact and required updates, or a specific reason none are
  needed;
- operational impact, or an explicit statement that there is none;
- no unresolved implementation decisions.

Before tickets are created, the human explicitly approves the complete
specification in the active conversation. Approval applies only to the exact
content shown in that request. Any change requires another review. If work
resumes in a new conversation without that approval in its active context, show
the specification and ask for approval again. Do not treat silence, an earlier document, a
GitHub label, or issue state as approval. If a decision remains open, return to
planning instead of guessing. GitHub keeps the approved specification as a
record; it is not another place to approve it.

## 3. Plan implementation tickets and landing batches

Use `plan-implementation-tickets` to turn the approved specification into
GitHub Issues. Make each slice independently verifiable. Group slices into
landing batches that one owner can complete and recover reliably.
Keep enough work ready that another item can move forward when one is blocked. Preserve
expand-contract ordering and record these relationships:

- work streams and safe opportunities for parallel work;
- exclusive landing batches;
- `local_after` prerequisites between slices, including checkpoint-bound edges
  across stacked landing batches;
- native `lands_after` prerequisites between landing batches;
- `starts_after` gates for the smaller set of batches that cannot be claimed or
  built until a named landing prerequisite merges;
- conflict surfaces and shared resources;
- acceptance criteria with verification methods;
- documentation and operational impact.

Apply the [proof and documentation
policy](LOCAL-WORK.md#proof-and-documentation-policy) while splitting the work.
Required verification and documentation stay in the same implementation ticket.

Show the complete proposed breakdown in the active conversation before
publishing or updating GitHub Issues. The human must explicitly approve that
exact plan. If the plan changes, or work resumes in a new conversation without
the approval in context, show the plan and ask for approval again. GitHub keeps the approved
plan and issue hierarchy as a record; it is not another place to approve them.

Start titles with the outcome and descriptions with the problem. The detailed
writing rules belong to `plan-implementation-tickets`.

A local prerequisite is satisfied by a reviewed slice checkpoint tied to a
specific commit; closing the child ticket does not. A landing prerequisite
controls when a batch may merge, but it does not prevent someone from claiming
or building the batch from an exact upstream checkpoint. A start prerequisite
prevents both claiming and building. It must also be a direct landing
prerequisite and cannot be bypassed with a checkpoint. Every batch without an
unresolved start prerequisite must have a slice that can start locally.

## 4. Complete a landing batch locally

Claim one ready landing batch using the rules in
[`COORDINATION.md`](COORDINATION.md). Then follow the completion loop in
[`LOCAL-WORK.md`](LOCAL-WORK.md) to implement, verify, review, and save evidence
for each slice. Assign each active child ticket to its slice worker before work
starts; that assignment is the ticket's complete claim. After every slice
checkpoint, recalculate the local frontier and continue with any slice that is
now ready. Start a newly unlocked dependent from its prerequisite checkpoint,
even when the batch branch has since integrated unrelated work. Do not rebase
independent slices onto each other merely to create a linear history. Give that
dispatch priority over processing unrelated completed deliveries. Do not wait
for child tickets to close.

The GitHub snapshot calculates each batch's local frontier from child-ticket
`local_after` rules and current checkpoints authored by the current assignee. Its execution
frontier combines the ready batches and slices across the plan and shows the
exact checkpoints blocking work. This prevents the next worker from waiting
for an artificial wave.

Follow the review policy in
[`docs/agents/review-findings.md`](docs/agents/review-findings.md). P0 and P1
findings block the batch. Record a durable review-time disposition for each P2
and P3 without expanding the current batch. Only deferred findings that need
later human triage enter a shared register.
When the full batch is verified for the draft pull request's current commit, an
independent reviewer posts the authenticated `local-review`; the batch owner
then posts the assignee-authored `local-complete` record and waits for the
trusted Lifecycle workflow to set `Lifecycle` to `Locally complete`.

## 5. Publish and merge

Open or update the landing candidate: the one pull request for the landing
batch. Keep it as a draft landing candidate while building. After GitHub shows
`Lifecycle: Locally complete`, complete the
ready-for-review gate and run `.workflow/scripts/queue_landing.py`. Link the
parent plan's deferred-findings register only when at least one finding is
marked `deferred` and needs later human triage. The command determines whether
the merge unlocks later work, applies the Mergify priority, and queues the pull
request.
After Mergify confirms the pull request's current commit is queued, the
Lifecycle workflow verifies the `workflow:queued` event. It sets the batch—not
its child tickets—to `Lifecycle: In PR`, meaning queued for merge, and re-reads
the Project item. The batch contract cannot
change between local completion and merge. To change it, follow the dequeue and
return-to-`Building` recovery in `GITHUB-WORKFLOW.md`.
Mergify validates pull requests one at a time and merges only after every
required check and approval passes. [`GITHUB-WORKFLOW.md`](GITHUB-WORKFLOW.md)
defines candidate rules, priority, the ready-for-review gate, and merge
requirements.
After GitHub confirms the merge and the Lifecycle workflow records the landed
state, the batch owner follows [`LOCAL-WORK.md`](LOCAL-WORK.md) to remove the
exact clean local worktree and branch. If cleanup is refused, report the reason
and preserve the local work for recovery instead of forcing deletion.

## Exceptions

An earlier push is allowed for collaboration, handoff, or remote backup. It does
not make the work locally complete, review-ready, or eligible to merge.
