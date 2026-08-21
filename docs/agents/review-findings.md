# Review Findings

This policy keeps review fail-closed without allowing repair and re-review to
continue indefinitely. It applies to slice reviews and integrated
landing-candidate reviews.

## Review basis and boundary

Every review has two authoritative inputs:

- **Approved outcome:** for a slice, use the child ticket's approved problem,
  desired outcome, scope boundaries, acceptance criteria, and proving methods.
  For an integrated candidate, use the approved landing-batch outcome and all
  included approved child-ticket outcomes. If any applicable contract changed,
  stop and resolve its approval before reviewing.
- **Exact code diff:** for a slice, the diff from its recorded starting commit
  through the reviewed commit; for an integrated candidate, the diff from its
  recorded base commit through the reviewed commit.

Review whether that exact diff delivers every applicable approved outcome,
stays within its boundaries, and preserves the directly affected behavior and
architecture. Inspect unchanged or adjacent code only as needed to understand
the diff's effects. Handoffs, previews, implementation summaries, and reviewer
assumptions are navigation aids only: they do not redefine the ticket contract
and are not themselves review subjects.

Every candidate finding must cite a violated part of an applicable approved
contract or a concrete risk introduced, worsened, or exposed by the exact diff.
Do not base a candidate verdict on the wording or completeness of a handoff,
preview, or summary, or on unrelated repository state. Route a useful
pre-existing or unrelated observation outside the candidate review; only a P0
emergency may interrupt that boundary.

## Priorities and landing effect

| Priority | Meaning | Landing effect |
| --- | --- | --- |
| P0 | Active catastrophic risk, such as security compromise, data loss, major outage, or an irreversible unsafe operation. | Blocks landing and requires immediate human escalation. |
| P1 | The candidate violates an acceptance criterion, introduces or worsens a meaningful regression, breaks an architecture or security boundary, or makes required verification unreliable. | Blocks the candidate. |
| P2 | A valid issue whose deferral leaves the approved outcome correct and safe. | Record and defer. |
| P3 | Polish, readability, optional hardening, or a speculative improvement without demonstrated correctness impact. | Record when useful; bundle or take no action. |

Only P0 and P1 block landing. A reviewer must cite the violated acceptance
criterion or concrete risk for each P0 or P1. If the priority cannot be
resolved, request human judgment; uncertainty is not approval.

The test-quality rules in [`LOCAL-WORK.md`](../../LOCAL-WORK.md) define reliable
proof. Required tests and documentation must remain in the same implementation
ticket. Deferring either to a separate completion ticket leaves the candidate
incomplete and is a P1 finding.

A finding does not silently expand the candidate's scope.

## Bounded review cycle

One cycle has at most five review passes by another agent:

1. Review every applicable approved outcome against the exact
   base-to-reviewed-commit diff and the surfaces affected by that change.
2. Fix P0 and P1 findings. Give every P2 and P3 a durable review-time
   disposition without adding it to the current batch.
3. Perform a focused re-review of the fixes and behavior they can affect. This
   is not a fresh repository-wide audit.
4. If needed, repeat the blocker repair and focused re-review up to three more
   times.

If a P0 or P1 remains or appears on the fifth pass, mark the candidate blocked,
return it to draft when necessary, request human re-scope or redesign, and
apply `workflow:needs-human-review` to the landing-batch issue. The workflow does not
merge the blocker and does not begin a sixth autonomous pass. A material,
human-approved re-scope or redesign starts a new cycle; record the reason in
the batch evidence.

## Durable finding record

Record every finding in `.scratch/<batch>/evidence.md` against the reviewed
commit. Use stable finding IDs within the batch and include:

| Field | Required content |
| --- | --- |
| Finding ID | Stable batch-local identifier. |
| Priority | P0, P1, P2, or P3. |
| Reviewed commit | Exact commit inspected by the reviewer. |
| Evidence | Reproduction, affected path, failed criterion, or concrete risk. |
| Relationship to the candidate | Introduced, worsened, or exposed by the reviewed diff. |
| Review-time disposition | Fixed, deferred for later triage, duplicate, rejected with rationale, or recorded with no action recommended. |

The review-time disposition is immutable for the reviewed commit. Later triage
outcomes never update batch evidence.

## Separated responsibilities

| Record | Owns | Does not own |
| --- | --- | --- |
| Batch evidence for Every review finding | The reviewed commit, evidence, relationship, and review-time disposition. | Later triage or work status. |
| Deferred-findings register | Mutable human triage for deferred P2 and P3 findings. | Scheduled repair after promotion. |
| Configured drift record, or current-state evidence fallback | The factual mismatch between intended authority and observed state. | Triage or repair status. |
| Standalone GitHub issue or linked existing issue | Mutable status for human-approved work with its own scope, owner, dependencies, or schedule. | Original review evidence. |

Batch evidence is immutable history and never owns mutable status. A drift
record may describe the same finding as factual evidence, but it never owns
triage or repair status. The current-state fallback has the same limit. The
register is the sole mutable status owner while triage is pending. A linked
standalone or existing issue becomes the sole owner after a `promoted` or
`duplicate` outcome. A `closed-no-action` outcome leaves no mutable work status
to track. If the mismatch needs scheduled repair, link its issue.

Record each terminal triage outcome and issue link in the register. A drift
record retains only the factual mismatch and repair-issue link. Both remain
durable history; do not mirror the linked issue's changing status. GitHub issue
state and closure are authoritative.

## One register per parent plan

A parent plan creates and links a deferred-findings register only when its first
finding needs later triage. It reuses that one register for the plan's lifetime.
If later findings need triage after it closes, reopen that register instead of
creating another.
Only findings whose review-time disposition is `deferred` and that need later human
triage enter the register. The register uses one structured comment per landing
batch that has at least one such finding rather than one issue per finding. Each
comment names the batch and pull request, reviewed commit, finding IDs,
priorities, summaries, and review-time dispositions. Fixed, duplicate, rejected, and
no-action findings remain only in the batch evidence.

Each registered finding has one triage outcome:

| Outcome | Meaning |
| --- | --- |
| `pending` | Human triage has not reached a decision. |
| `promoted` | A linked standalone issue now owns the work. |
| `duplicate` | A linked existing issue already owns the work. |
| `closed-no-action` | Triage rejected or declined the work with a recorded rationale. |

Only `pending` is non-terminal. Record outcomes in the register and never copy
them into batch evidence. Close the register only when no finding remains
`pending`. Closing the parent plan does not close a register with pending
findings. Reopen the same register if a later finding needs triage.

A P2 or P3 does not require its own GitHub issue. The standalone issue is
created only when later human triage promotes the finding into work with its
own scope, owner, dependencies, or schedule. Recording a finding does not
authorize its implementation.

## Review-clean gate

Review clean means all of the following are true:

- there are no unresolved P0 or P1 blockers;
- every P2 or P3 finding has a durable review-time disposition;
- required tests pass; and
- every applicable approved outcome and the exact base-to-reviewed-commit diff
  were the review basis; and
- the exact candidate commit was reviewed.

Review clean does not mean that the reviewer reported no findings.
