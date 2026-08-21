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
| `question` | `question` | Request for information or clarification; no repository change is requested. |
| `documentation` | `documentation` | Documentation is missing, wrong, or unclear. |

## State mapping

| Canonical role | Repository label | Meaning |
| --- | --- | --- |
| `needs-triage` | `triage:needs-triage` | A maintainer must evaluate the intake request. |
| `needs-info` | `triage:needs-info` | The intake request is waiting for information from the reporter. |
| `ready-for-agent` | `triage:ready-for-agent` | The intake request is clear enough for its next agent-owned step. |
| `ready-for-human` | `triage:ready-for-human` | The intake request requires human judgment or action. |
| `wontfix` | `triage:wontfix` | The intake request will not be acted on. |

## Rules

- Replace the prior triage state when the state changes; never accumulate two
  state labels.
- Treat an unlabeled intake issue as needing triage.
- `triage:ready-for-agent` does not bypass vocabulary, ADR, specification, or
  implementation-ticket planning gates. It identifies intake routing only.
- An intake brief may summarize the request and link to later artifacts. The
  brief does not replace an approved implementation specification.
- Labels do not claim work. A GitHub issue's sole assignee is its current owner,
  as defined in [`COORDINATION.md`](../../COORDINATION.md).
- Keep stream, lifecycle, dependency, batch membership, ownership, readiness,
  landing order, and review requirements in their authorities defined by the
  repository workflow, not in triage labels.
