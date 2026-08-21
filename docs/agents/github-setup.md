# GitHub Workflow Setup

This is the repository-owned meaning of the GitHub labels, Project fields, and
settings required by the workflow. The machine-readable source of truth is
`.workflow/github-setup-contract.json`.

## Planning labels

| Label | Use |
| --- | --- |
| `planning:map` | Parent map for unresolved new-work planning. |
| `planning:research` | Question that gathers evidence with an independently verifiable answer. |
| `planning:prototype` | Disposable experiment that reduces a named uncertainty. |
| `planning:decision` | Product, architecture, ownership, or operational choice that requires an authorized decision. |
| `planning:task` | Planning-stage documentation or synthesis that does not change product behavior. |

These categories are complete for new-work planning. They do not depend on
Wayfinder or another globally installed planning skill.

## Delivery labels

- `PLAN`, `BATCH`, and `TICKET` identify issue type only. A `TICKET` is a child
  implementation ticket for one slice; it is not the slice itself.
- Upgrades must rename the former controlled labels `workflow:plan`,
  `workflow:batch`, and `workflow:ticket` to those exact names so existing open
  and closed issues keep their issue type. Setup is incomplete while a
  legacy label remains.
- `surface:*` labels identify the controlled conflict surfaces listed in the
  machine-readable contract.
- `workflow:needs-human-review` is the controlled escalation label for a
  landing batch that remains blocked after five review passes. Apply it to both
  the batch issue and its PR so evidence validation and Mergify stop landing.
  Remove both copies only when human re-scope or redesign begins a new review
  cycle.
- `workflow:unlocks-work` is derived by `queue_landing.py` when a PR's merge
  releases an open `starts_after` batch. Do not apply it by hand.
- `workflow:landing-validated` is added to a ready PR only by
  `queue_landing.py` after live landing-order, evidence, and metadata checks.
  Mergify rejects a direct queue command without it. Remove it whenever landing
  dependencies or batch metadata change, then rerun the command.
- `workflow:queued` and `workflow:dequeued` are Mergify-owned event labels.
  They let the trusted Lifecycle workflow distinguish queue confirmation
  from a dequeue without copying queue position into the Project.
- Intake labels are governed by [`triage-labels.md`](triage-labels.md).

Apart from these controlled workflow labels, do not encode ownership,
readiness, queue position, dependencies, review class, or plan-specific
metadata as labels.

## Project fields

- `Work stream` is text identifying independently advanceable work.
- `Lifecycle` is a single-select field with exactly the workflow lifecycle
  options in the machine-readable contract. Set it only on landing-batch
  issues; plans and child tickets intentionally leave it empty.

Parent-child hierarchy and dependency relationships use GitHub's native issue
relationships. A batch assignee owns the integrated batch. A child ticket's
assignee owns its active slice; assignment is the complete claim for both.

Record the selected Project URL or ID and exact required status-check names in
`AGENTS.md`. Later agents must use that Project rather than selecting another.
Write the corresponding repository `owner/name`, base branch, Project node ID,
Lifecycle field name, and authorized lifecycle-evidence maintainer logins under
`authorized_maintainers` in the customizable
`.workflow/github-state-config.json`. These maintainers repair
trusted workflow evidence; they do not approve claims. Assignment alone is the
claim in both single-operator and multi-operator repositories. Final local
verification rejects pending runtime values, and installer checks allow this
file to differ by repository.

Landing coordination records use the landing pull request's comments. The
Project is the source of truth for batch lifecycle; Mergify is responsible for
current queue state, and comments preserve durable event history. Configure
the `WORKFLOW_PROJECT_TOKEN` Actions secret with organization Project write
access and repository issue/PR read access. The trusted Lifecycle workflow
verifies, writes, and re-reads transitions; an authorized workflow maintainer
repairs failed runs.

## Repository settings

The branch, review, CI, and merge requirements are defined in
[`GITHUB-WORKFLOW.md`](../../GITHUB-WORKFLOW.md). Install the Mergify GitHub App,
keep GitHub's native merge queue disabled, configure Mergify's queued/dequeued
labels, enable `.github/workflows/lifecycle.yml`, add the
`WORKFLOW_PROJECT_TOKEN` secret, and validate `.mergify.yml`. Use
[`mergify-runbook.md`](mergify-runbook.md) to queue, retry, stop, or recover a
landing candidate. Keep the Lifecycle workflow's `issues: write` permission so
it can remove an unauthorized third-party assignment or restore an existing
owner after an unauthorized assignee change on a `PLAN`, `BATCH`, or `TICKET`.

Use `configure-github-workflow` to inspect, initialize, and verify this state.
It may use any authenticated GitHub interface, but no global skill is required.

## Optional Project views

Delivery Board and Delivery Roadmap views are optional presentation, not
required workflow state. Do not create them during installation, GitHub setup,
repair, validation, planning, or ticket publication. Create or repair them only
when a human explicitly asks, then use the API-only procedure in
`configure-github-workflow`.

The standard Board shows `BATCH` issues grouped by `Lifecycle`. The standard
Roadmap shows `BATCH` issues against approved `Start date` and `Target date`
values. GitHub's public API can create both views but cannot currently bind a
fresh Roadmap to those date fields. Use a preconfigured Project template/copy
for a fully API-driven Roadmap, or report the date binding as a manual human
step. The repository workflow never uses browser automation or computer use for
Project view setup.
