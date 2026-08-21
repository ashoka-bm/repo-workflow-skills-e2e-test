# Coordination Protocol

This protocol governs shared work across people, agents, sessions, and
machines. GitHub remains the authority; local worktrees and notes are evidence,
not coordination state.

## Configure before concurrent work

Before any concurrent batch implementation, complete the claim coordinator,
request channel, heartbeat channel, and stale and recovery-grace durations in
[`AGENTS.md`](AGENTS.md), and use the exact GitHub-visible record formats in
[`.workflow/coordination-records.md`](.workflow/coordination-records.md).

The named human coordinator is the supported fallback when the controller is
disabled. In normal operation, the controller performs the serialized decisions
defined here from GitHub events. A 15-minute reconciliation pass repairs a
missed or delayed event by deriving the same transition from current GitHub
state. Audit mode reports that transition without changing GitHub; enforcement
mode applies it.

## Claim shared work before starting

Child implementation tickets remain unassigned; the landing batch is the
exclusive claim unit. During new-work planning, each decision or investigation
issue is its own claim unit under the same receipt protocol.

1. Refresh the work item, its native blockers, relevant active conflict
   surfaces, and current assignee.
2. Submit a claim request through the configured GitHub channel. Its GitHub
   actor, human or agent identity, and session or run identifier distinguish
   separate agents that share a machine or GitHub account.
3. The coordinator processes requests one at a time in GitHub event order.
4. A claim succeeds only when the item is open, unassigned, unblocked, and—when
   it is a batch—conflict-safe. For a fresh `Planned` landing batch, the
   coordinator assigns exactly one owner, sets `Lifecycle` to `Building`, and
   posts a claim receipt in one serialized operation. A recovered or handed-off
   batch keeps its existing delivery lifecycle while ownership changes.
5. Re-read the receipt before resolving a planning issue or creating a batch
   branch or worktree. A direct assignment, local note, or unacknowledged
   request is not a successful claim.

If two requests race, the first valid request wins. Every later request receives
a rejection that links to the active claim.

## Keep the local frontier moving

The batch is the claim unit, but its child tickets form a local execution graph.
Within that graph, `local_after` is satisfied by the prerequisite ticket's
current slice checkpoint, not by issue closure. The owner selects any incomplete
slice whose local prerequisites have checkpoints, completes it, posts its
checkpoint, and refreshes the GitHub snapshot's derived `local_frontier`
immediately. `locally_blocked` names each remaining slice and the checkpoints it
still needs.

Do not wait for the slowest unrelated ticket or for all work at the same depth
to finish. When one slice is blocked, continue another frontier slice that does
not share the blocker or an active conflict surface. If no local slice can
proceed, preserve the branch and release or hand off the claim so another ready
batch can be taken.

## Keep, release, and hand off a claim

The owner sends GitHub-visible heartbeats through the configured mechanism.
Release a batch when work stops: preserve commit-bound evidence, post the
`release` record, and let the coordinator remove the assignee and claim
metadata.

Hand off with a `handoff` record. Ownership changes only after the coordinator
records the incoming claim receipt, and two workers must never edit the same
batch branch at the same time.

## Recover stale work

Missing heartbeats make a claim eligible for recovery; they do not silently
transfer ownership. The coordinator posts a recovery notice, checks for recent
branches, pull-request updates, comments, and commits, waits the configured
recovery-grace duration, then either restores the claim or releases it with a
durable `recovery-result` record. Preserve recoverable work before assigning a
replacement.

## Protect shared resources

Single-writer resources — schemas, migrations, identifiers, generated
registries, dependency files, deployment slots — require an explicit order or
one owning batch. When a new collision appears, stop the affected work and
update GitHub before continuing.

## Coordinate landing candidates

The batch owner owns its draft landing candidate. The coordinator serializes
queue requests and candidate transitions using the exact records in
[`.workflow/coordination-records.md`](.workflow/coordination-records.md). FIFO,
eligibility, activation, blocking, and merge behavior are governed by
[`GITHUB-WORKFLOW.md`](GITHUB-WORKFLOW.md), not local ownership.

Anyone must be able to discover the current batch owner, worker/session,
branch, blockers, conflict surfaces, last heartbeat, Queue sequence, and
handoff or recovery state from GitHub.
