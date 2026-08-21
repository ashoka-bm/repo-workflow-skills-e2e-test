# GitHub Workflow Setup

This is the repository-owned meaning of the GitHub labels, Project fields, and
settings required by the workflow. The machine-readable authority is
`.workflow/github-setup-contract.json`.

## Planning labels

| Label | Use |
| --- | --- |
| `planning:map` | One parent map for an uncertain effort. |
| `planning:research` | Gather evidence for a question with a verifiable answer. |
| `planning:prototype` | Run a disposable experiment to reduce a named uncertainty. |
| `planning:decision` | Resolve a product, architecture, ownership, or operational choice through its authority. |
| `planning:task` | Update or synthesize planning artifacts without implementing product behavior. |

These categories are complete for new-work planning. They do not depend on
Wayfinder or another globally installed planning skill.

## Delivery labels

- `workflow:plan`, `workflow:batch`, and `workflow:ticket` identify artifact
  type only.
- `surface:*` labels identify the controlled conflict surfaces listed in the
  machine-readable contract.
- `workflow:needs-human-review` is the controlled escalation label for a
  landing batch that remains blocked after five review passes. Remove it only
  when human re-scope or redesign begins a new review cycle.
- Intake labels are governed by [`triage-labels.md`](triage-labels.md).

Apart from that controlled escalation label, do not encode ownership,
readiness, queue position, dependencies, review class, or plan-specific
metadata as labels.

## Project fields

- `Work stream` is text identifying independently advanceable work.
- `Queue sequence` is the immutable number assigned from one monotonically
  increasing repository sequence when a locally complete draft joins the
  landing queue. It belongs on the landing-batch issue's Project item, is empty
  before queue entry and after substantial rework, and only the coordinator
  writes or clears it.
- `Lifecycle` is a single-select field with exactly the workflow lifecycle
  options in the machine-readable contract.

Parent-child hierarchy and dependency relationships use GitHub's native issue
relationships. Batch assignees own claims; child implementation tickets remain
unassigned.

Record the selected Project URL or ID and exact required status-check names in
`AGENTS.md`. Later agents must use that Project rather than selecting another.

Landing coordination records always use the landing pull request's comments;
this is not a setup-time channel choice. The Project fields remain authoritative
for current lifecycle and Queue sequence, while comments preserve the durable
event history.

## Repository settings

The branch, review, CI, and merge requirements are defined in
[`GITHUB-WORKFLOW.md`](../../GITHUB-WORKFLOW.md). The installed controller
defaults to audit mode, where it reports proposed FIFO transitions but cannot
write to GitHub. A named human coordinator can operate the same transitions
using [`COORDINATION.md`](../../COORDINATION.md) and remains the fallback when
the controller is disabled. Use
[`controller-runbook.md`](controller-runbook.md) to connect, inspect, disable,
or recover the audit pilot.

Use `configure-github-workflow` to inspect, initialize, and verify this state.
It may use any authenticated GitHub interface, but no global skill is required.
