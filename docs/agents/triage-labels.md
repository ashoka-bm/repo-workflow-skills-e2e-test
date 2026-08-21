# Intake Triage Labels

## Intake issues only

This file maps canonical intake roles to this repository's GitHub labels. It is
the label authority for intake issues only.

Every triaged intake issue carries exactly one category and exactly one triage
state. Do not apply triage-state labels to implementation tickets,
specifications, landing batches, or pull requests.

## Category mapping

| Canonical role | Repository label | Meaning |
| --- | --- | --- |
| `bug` | `bug` | Existing behavior is broken. |
| `enhancement` | `enhancement` | New capability or improvement. |

## State mapping

| Canonical role | Repository label | Meaning |
| --- | --- | --- |
| `needs-triage` | `triage:needs-triage` | A maintainer must evaluate the request. |
| `needs-info` | `triage:needs-info` | The request is waiting on its reporter. |
| `ready-for-agent` | `triage:ready-for-agent` | The intake request is sufficiently defined for its next agent-owned step. |
| `ready-for-human` | `triage:ready-for-human` | The next step requires human judgment or action. |
| `wontfix` | `triage:wontfix` | The request will not be actioned. |

## Rules

- Replace the prior triage state when the state changes; never accumulate two
  state labels.
- Treat an unlabeled intake issue as needing triage.
- `triage:ready-for-agent` does not bypass vocabulary, ADR, specification, or
  implementation-ticket planning gates. It identifies intake routing only.
- An intake brief may summarize the request and link to later artifacts. The
  brief does not replace an approved implementation specification.
- Labels do not claim work. Planning issues and landing batches use the claim
  receipt protocol in [`COORDINATION.md`](../../COORDINATION.md).
- Keep stream, lifecycle, dependency, batch membership, ownership, readiness,
  landing order, and review requirements in their authorities defined by the
  repository workflow, not in triage labels.
