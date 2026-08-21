---
name: configure-github-workflow
description: Initialize or repair the GitHub labels, Project fields, branch protections, CI and lifecycle automation, and coordination prerequisites required by this repository-owned workflow. Also create optional Project Board or Roadmap views when a human explicitly requests them. Use after configure-repository-workflow in a new repository, before planning or publishing issues, whenever GitHub workflow setup may have drifted, or when these Project views are requested. Does not require a globally installed GitHub or Matt Pocock skill.
---

# Configure GitHub Workflow

Make the repository's GitHub state satisfy its installed workflow contract.

## Load the local contract

Run the target-local setup verifier first:

```bash
python3 .workflow/scripts/verify_setup.py --pre-github
```

Read `AGENTS.md`, `GITHUB-WORKFLOW.md`, `COORDINATION.md`,
`docs/agents/github-setup.md`, and `.workflow/github-setup-contract.json`.
Read `references/snapshot-shape.md` before creating a validation snapshot.
Only when a human explicitly requests Project Board or Roadmap views, read
`references/project-views-api.md` before proposing or creating them.
Stop if repository identity, commands, base branch, required CI gates, or
coordination or lifecycle automation is unconfigured.

## Inspect without changing GitHub

Use any available authenticated GitHub API, application, or CLI. Do not require
a particular global skill. Read the target repository's:

- labels;
- linked workflow Project and its fields;
- exact Project ID and URL;
- native issue hierarchy and dependency support;
- base-branch rulesets;
- CI and Lifecycle workflow events, permissions, and job conditions;
- GitHub native merge-queue setting and Mergify App/configuration state; and
- the `WORKFLOW_PROJECT_TOKEN` Actions secret's configured presence (never its
  value) and its documented Project/repository permissions; and
- configured workflow-maintainer identities used only for lifecycle-evidence
  repair.

Normalize the observed values into `.tmp/github-setup-snapshot.json` using the
shape of `.workflow/github-setup-contract.json`, with label objects represented
by their names. Validate it:

```bash
python3 .workflow/scripts/validate_github_setup.py \
  .tmp/github-setup-snapshot.json --contract-only
```

This first pass checks the shared contract only and is not proof that the
repository is ready. Final validation must bind the observed state to
`AGENTS.md`.

## Propose and approve setup

Present every missing or conflicting item and the exact proposed mutations.
GitHub writes, ruleset changes, and CI changes require explicit human approval.
If credentials or permissions are missing, stop with the unresolved setup list.

After approval:

1. migrate the controlled legacy artifact labels before ordinary label setup:
   rename `workflow:plan` to `PLAN`, `workflow:batch` to `BATCH`, and
   `workflow:ticket` to `TICKET` so GitHub preserves every open and closed
   issue assignment. If both names already exist, relabel every legacy issue
   to the replacement, verify none remain, then delete only the three known
   legacy labels. Never delete unknown labels;
2. select or create one repository workflow Project and configure its required
   Work stream and Lifecycle fields with exact lifecycle
   options; record its durable URL or ID in
   `AGENTS.md`, then write the observed repository, base branch, Project node
   ID, Lifecycle field name, and authorized workflow-maintainer logins under
   `authorized_maintainers` in the customizable
   `.workflow/github-state-config.json` runtime file;
3. add or adapt the repository's full-gate CI workflow using the commands in
   `AGENTS.md`, preserving unrelated workflows and the trusted
   `landing-evidence` exact-head check;
4. configure the base-branch ruleset, bind its required status-check names,
   confirm the full-gate job uses the configured commands, disable GitHub's
   native merge queue, install Mergify, configure its `workflow:queued` and
   `workflow:dequeued` labels, and validate `.mergify.yml`;
5. confirm `workflow:unlocks-work` is reserved for `queue_landing.py` and the
   Mergify priority rule uses it without interrupting checks already running;
6. confirm `workflow:landing-validated` is reserved for successful
   `queue_landing.py` checks and is required by the Mergify queue rule;
7. confirm `workflow:needs-human-review` is applied to both the landing-batch
   issue and its PR during escalation, so Mergify observes the hold;
8. create `WORKFLOW_PROJECT_TOKEN` as an Actions secret using an approved
   credential with organization Project write and repository issue/PR read,
   enable `.github/workflows/lifecycle.yml`, and confirm the action uses trusted
   default-branch code, verifies each trigger, and re-reads every update;
9. confirm self-assignment is the only claim signal for planning issues,
   landing batches, and child tickets; assignment events update landing-batch
   Lifecycle; unauthorized third-party assignment or removal is repaired for
   every work-issue type, including when assignment predates the workflow label
   or is present when the issue opens; and authorized workflow maintainers can
   repair lifecycle evidence without approving ordinary claims; and
10. confirm plans and child tickets leave `Lifecycle` empty and that dependency
   or batch-contract changes after `Locally complete` follow the documented
   dequeue-and-return-to-`Building` freeze recovery.

Never weaken an existing protection to make validation pass. Stop and request
direction when an existing setting is stricter but incompatible, or when more
than one Project could be the workflow authority.

## Create optional Project views only on request

Project views are presentation, not required workflow state. Do not create,
update, copy, or delete a view during ordinary setup, repair, validation,
planning, or ticket publication. The setup contract and validators must remain
independent of optional views.

When a human explicitly asks for a delivery Board or Roadmap:

1. resolve the one configured workflow Project from `AGENTS.md` and inspect its
   existing views and fields before proposing writes;
2. explain the exact view names, filters, grouping, date fields, and any item
   date values that would change, then obtain the GitHub-write approval required
   above;
3. use authenticated GitHub REST or GraphQL calls described in
   `references/project-views-api.md`; do not use browser automation, computer
   use, or coordinate-based UI actions;
4. make creation idempotent by reusing an exact matching view and stopping on
   a same-name conflict rather than creating duplicates;
5. re-read the Project through the API and report the observed view layout,
   filter, grouping, and affected item values; and
6. never delete a view unless the human separately approves that permanent
   deletion after the exact view ID and name are shown.

The standard Delivery Board is a Board filtered to `label:BATCH` and vertically
grouped by `Lifecycle`. The standard Delivery Roadmap is filtered to
`label:BATCH` and uses approved `Start date` and `Target date` values for BATCH
items. Public APIs currently create a Roadmap but do not expose its start/target
date-field binding. For a fully configured Roadmap, use an approved
preconfigured Project template/copy flow. Otherwise create only the API-exposed
portion the human approved and report the missing date binding as a manual human
step. Never silently assume GitHub selected the date fields.

## Re-read and verify

Read the resulting GitHub state again; do not validate intended mutations.
Rewrite the disposable snapshot from observed state and rerun the validator.
Update `AGENTS.md` with the observed Project identity and required checks, rerun
the local validator, and pass `--agents AGENTS.md` to the GitHub validator.
Planning may begin only when both validators pass.

Report the repository, Project, ruleset, CI workflow, Mergify configuration,
workflow maintainers, and validation evidence. No claim coordinator is required;
GitHub assignment is authoritative ownership.
