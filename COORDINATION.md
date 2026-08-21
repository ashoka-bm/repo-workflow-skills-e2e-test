# Coordination Protocol

This document explains how people and agents coordinate work across sessions
and machines. GitHub assignment is the shared source of truth for who currently
owns work. Local worktrees and notes provide evidence, but they do not claim an
issue.

## Claim work by assigning yourself

The same rule applies to every work issue. A landing-batch assignee owns the
integrated batch. A child implementation ticket is assigned to the person
working its slice; assignment is its complete claim, including when the batch
owner delegates that slice. During
new-work planning, each decision or investigation issue is claimed separately.
Issue assignment is the only shared claim; workers do not publish a second
claim system.

Before starting:

1. Refresh the GitHub issue and confirm it is open and unassigned. For a landing
   batch, also confirm a starting slice is ready, no unresolved `starts_after`
   prerequisite exists, and no active conflict prevents work. For a child
   ticket, confirm its prerequisites are complete and its conflict surfaces are
   safe.
2. Assign the issue to yourself in GitHub. Do not remove, replace, or add to an
   existing assignee.
3. Re-read the issue. The claim is valid when GitHub shows exactly one assignee
   and that assignee is you. Assignment itself is the complete claim; no claim
   request, receipt, comment, command, coordinator approval, or Lifecycle
   confirmation is required.

An unassigned issue is available. An issue with one assignee is claimed and
actively being worked on. If simultaneous assignments leave more than one
assignee, nobody may treat either assignment as a valid claim until the
ambiguity is resolved; webhook arrival order is not ownership evidence. For
`PLAN`, `BATCH`, and `TICKET` issues, the trusted Lifecycle workflow removes a
sole assignment made by someone other than the assignee or an authorized
workflow maintainer. It also restores an owner removed by anyone other than
that owner or an authorized workflow maintainer. If a delayed removal event
finds a newer sole assignee, it preserves both people as an invalid, ambiguous
state instead of guessing which claim is newer. When a workflow label is added
after assignment, or a labeled issue opens preassigned, the workflow verifies
the assignment actor from GitHub's issue history before accepting the owner.

The same rule applies in a single-operator or multi-operator repository. A
maintainer may assign work during an agreed handoff or recovery, but that
assignment has exactly the same meaning and does not create a separate
coordinator-managed claim mode.

## Update batch lifecycle after every trigger

`Lifecycle` belongs only to landing-batch issues. Plans and child tickets leave
that Project field empty, but their assignment is still a complete claim.
Assignment takes effect immediately; the trusted Lifecycle workflow mirrors a
newly assigned batch as `Building` and an unassigned batch as `Planned`. A
delayed or failed Project update does not undo or postpone the claim.

The workflow records `Locally complete` after the owner reports completion for
the pull request's current commit. It records `In PR`, meaning queued for merge,
after Mergify confirms that commit is queued, and `Landed` after GitHub reports
the pull request merged. A dequeue with current
evidence returns the batch to `Locally complete`. A new commit, invalid evidence,
or rework returns it to `Building`.

## Keep the local frontier moving

A current slice checkpoint—not issue closure or batch merge—satisfies
`local_after`. The ready slices inside the claimed batch form its local
frontier. The owner can complete any unfinished slice whose local
prerequisites have checkpoints. After posting a checkpoint, refresh
`execution_frontier`, the combined view across all batches, immediately.

Ticket assignment is the only shared slice claim. Before a delegated worker
starts, that worker accepts the delegation by assigning the ready child ticket
to themself and re-reading GitHub to confirm they are its sole assignee. Do not
publish a second claim system. Use ticket conflict surfaces and isolated worker
branches to prevent collisions, and keep the batch owner accountable for
integration.

`ready_batches` and `ready_slices` show unassigned work that can start now;
assigned child tickets are already claimed and are omitted from `ready_slices`.
`blocked_batches` lists missing checkpoints, conflicts with active work,
`must_not_overlap` rules, and unresolved start gates. Each candidate's
`locally_blocked` field lists its missing checkpoints. Readiness compares only
the shared resources used by work that is ready now. A possible future conflict
does not hide a safe slice that can proceed. Each `Must not overlap` entry must
name another landing batch in the configured Project or say `none`.

These fields are produced by `.workflow/github_snapshot.py`. With `GH_TOKEN`
set to a token that can read the configured repository and Project, refresh
them with:

```bash
python3 .workflow/github_snapshot.py collect \
  --config .workflow/github-state-config.json \
  --output .tmp/github-snapshot.json
```

If the snapshot cannot run, determine the same answer manually from the rules
in [`.workflow/coordination-records.md`](.workflow/coordination-records.md).
The snapshot is a convenience, not a separate source of truth.

## Release, hand off, and recover work

To release work, preserve any useful branch or commit evidence and remove
yourself as assignee. Re-read the issue; it becomes available only when GitHub
shows no assignee.

For a handoff, agree on the incoming owner and change the GitHub assignee from
the outgoing owner to that person. Re-read the issue before the incoming owner
continues. An optional comment may explain the branch and next action, but it
does not determine ownership.

For stale work, inspect recent branches, pull request updates, comments, and
commits before changing assignment. Preserve recoverable work and obtain the
repository's normal authority for taking work from another person. Never treat
staleness alone as permission to overwrite an existing assignee.

Parallel slice workers use isolated local branches; only the batch owner
integrates and updates the shared batch branch.

## Protect shared resources and landing candidates

Shared resources that only one worker can safely change at a time—such as
schemas, migrations, identifiers, generated registries, dependency files, and
deployment slots—need an explicit order or one owning batch. If a new conflict
appears, stop the affected work and update GitHub before continuing.

The batch owner is also responsible for its landing candidate: the one pull
request for that batch. It remains a draft landing candidate while building.
After local completion, the owner completes the ready-for-review gate and runs the repository's queue-entry
command. Mergify validates and merges one pull request at a time while the
Lifecycle workflow records verified delivery state. Exact behavior is governed
by [`GITHUB-WORKFLOW.md`](GITHUB-WORKFLOW.md).

From `Locally complete` onward, workflow maintainers enforce the frozen batch
contract. A required dependency, membership, conflict, or PR-marker change must
dequeue and return the batch to `Building` before the plan is edited.

Anyone must be able to discover the current owner, branch, blockers, conflict
surfaces, Mergify queue state, and recovery context from GitHub.
