# Review Findings

This policy stops work from moving forward when review is incomplete, while
preventing repair and re-review from continuing forever. It applies to reviews
of individual slices and complete landing candidates.

## Review basis and boundary

Every review has two required inputs:

- **Approved outcome:** for a slice, use the child ticket's approved problem,
  desired outcome, scope boundaries, acceptance criteria, and verification methods.
  For an integrated candidate, use the approved landing-batch outcome and all
  included approved child-ticket outcomes. If any approved requirement changed,
  stop and get the updated requirement approved before reviewing.
- **Exact code diff:** for a slice, the diff from its recorded starting commit
  through the reviewed commit; for an integrated candidate, the diff from its
  recorded base commit through the reviewed commit.

The review record names the reviewer and session. The reviewer must differ from
the implementation worker and, for an integrated candidate, from the batch
owner. The session identifies the specific review run. GitHub shows
who posted the record, but it does not replace the agent identity in the record.

Check whether the exact diff delivers every applicable approved outcome, stays
within scope, and preserves the behavior and architecture it affects. Inspect
unchanged or nearby code only when needed to understand the diff. Handoffs,
previews, implementation summaries, and reviewer assumptions may help locate
information, but they do not change the approved requirements and are not
themselves review subjects.

Every finding must point to an approved requirement that the candidate violates
or a concrete risk introduced, worsened, or exposed by the exact diff. Do not
judge the candidate based on the wording or completeness of a handoff, preview,
or summary, or on unrelated repository state. Record useful pre-existing or
unrelated observations outside the candidate review. Only a P0 emergency may
interrupt that boundary.

## Priorities and merge effect

| Priority | Meaning | Merge effect |
| --- | --- | --- |
| P0 | An active catastrophic risk, such as a security compromise, data loss, major outage, or irreversible unsafe operation. | Blocks the merge and requires immediate human help. |
| P1 | The candidate fails an acceptance criterion, causes or worsens an important regression, breaks an architecture or security boundary, or makes required verification unreliable. | Blocks the candidate. |
| P2 | A valid issue that can wait without making the approved outcome incorrect or unsafe. | Record and defer. |
| P3 | Polish, readability, optional hardening, or a possible improvement with no demonstrated effect on correctness. | Record when useful; group with later work or take no action. |

Only P0 and P1 block the merge. For each one, the reviewer must name the failed
acceptance criterion or concrete risk. If the priority remains unclear, ask a
human to decide. Uncertainty is not approval.

The [proof and documentation
policy](../../LOCAL-WORK.md#proof-and-documentation-policy) defines reliable
verification, evidence, and the same-ticket boundary. Deferring required tests or documentation
to a separate completion ticket leaves the candidate incomplete and is a P1
finding.

A finding does not silently expand the candidate's scope.

## Bounded review cycle

One cycle has at most five review passes by an independent reviewer:

1. Review every applicable approved outcome against the exact
   base-to-reviewed-commit diff and the surfaces affected by that change.
2. Fix P0 and P1 findings. Give every P2 and P3 a durable review-time
   disposition without adding it to the current batch.
3. Perform a focused re-review of the fixes and behavior they can affect. This
   is not a fresh repository-wide audit.
4. If needed, repeat the blocker repair and focused re-review up to three more
   times.

If a P0 or P1 remains or appears on the fifth pass, mark the candidate blocked.
Return it to draft when necessary, request human re-scope or redesign, and apply
`workflow:needs-human-review` to the landing-batch issue and its pull request.
The workflow does not merge the blocker and does not begin a sixth autonomous
pass. A material, human-approved re-scope or redesign starts a new cycle. Record
the reason in the batch evidence.

## Durable finding record

Record every finding in `.local-work/<batch>/evidence.md` for the reviewed
commit. Give each finding an ID that does not change within the batch and
include:

| Field | Required content |
| --- | --- |
| Finding ID | An identifier that does not change within the batch. |
| Priority | P0, P1, P2, or P3. |
| Reviewed commit | Exact commit inspected by the reviewer. |
| Evidence | Steps to reproduce, affected path, failed criterion, or concrete risk. |
| Relationship to the candidate | Introduced, worsened, or exposed by the reviewed diff. |
| Review-time disposition | Exactly one canonical token: `fixed`, `deferred` (needs later human triage), `duplicate`, `rejected` (with recorded rationale), or `no-action` (recorded, no action recommended). Every document and record uses these tokens, not prose variants. |

The review-time disposition is immutable for the reviewed commit. Later triage
outcomes never update batch evidence.

## Separated responsibilities

Every review finding has one record that stores each kind of information:

| Record | Stores | Does not store |
| --- | --- | --- |
| Batch evidence for every review finding | The reviewed commit, evidence, relationship, and review-time disposition. | Later triage decisions or work status. |
| Deferred-findings register | Human triage status for deferred P2 and P3 findings. | Repair work after a finding is promoted. |
| Configured drift record, or current-state evidence fallback | The factual difference between the intended design and observed system. | Triage decisions or repair status. |
| Standalone GitHub issue or linked existing issue | Current status for human-approved work with its own scope, owner, dependencies, or schedule. | Original review evidence. |

Batch evidence is immutable history and never stores mutable status. A drift
record may describe the same finding as factual evidence, but it never stores
triage or repair status. The current-state fallback has the same limit. The
register stores the current status while triage is pending. After a `promoted`
or `duplicate` outcome, the linked standalone or existing issue tracks the
work. A `closed-no-action` outcome leaves no mutable work status to track. If
the mismatch needs scheduled repair, link its issue.

Record each terminal triage outcome and issue link in the register. A drift
record retains only the factual mismatch and repair-issue link. Both remain
durable history; do not mirror the linked issue's changing status. GitHub issue
state and closure are the source of truth.

## One register per parent plan

A parent plan creates and links a deferred-findings register only when its first
finding needs later triage. It reuses that one register for the plan's lifetime.
If later findings need triage after it closes, reopen that register instead of
creating another.
Only findings whose review-time disposition is `deferred` and that need later human
triage enter the register. The register uses one structured comment per landing
batch that has at least one such finding rather than one issue per finding. Each
comment names the batch and pull request, reviewed commit, finding IDs,
priorities, summaries, and review-time dispositions. `fixed`, `duplicate`,
`rejected`, and `no-action` findings remain only in the batch evidence.

Each registered finding has one triage outcome:

| Outcome | Meaning |
| --- | --- |
| `pending` | Human triage has not reached a decision. |
| `promoted` | A linked standalone issue now tracks the work. |
| `duplicate` | A linked existing issue already tracks the work. |
| `closed-no-action` | Triage rejected or declined the work with a recorded rationale. |

Only `pending` is non-terminal. Record outcomes in the register and do not copy
them into batch evidence. Close the register only when no finding remains
`pending`. Closing the parent plan does not close a register with pending
findings. Reopen the same register if another finding later needs triage.

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
