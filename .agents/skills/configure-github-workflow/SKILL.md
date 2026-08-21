---
name: configure-github-workflow
description: Initialize or repair the GitHub labels, Project fields, branch protections, CI triggers, and manual coordination prerequisites required by this repository-owned workflow. Use after configure-repository-workflow in a new repository, before planning or publishing issues, and whenever GitHub workflow setup may have drifted. Does not require a globally installed GitHub or Matt Pocock skill.
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
Stop if repository identity, commands, base branch, required CI gates, or
manual coordination is unconfigured.

## Inspect without changing GitHub

Use any available authenticated GitHub API, application, or CLI. Do not require
a particular global skill. Read the target repository's:

- labels;
- linked workflow Project and its fields;
- exact Project ID and URL;
- native issue hierarchy and dependency support;
- base-branch rulesets;
- CI workflow events and job conditions;
- merge-queue setting; and
- configured human coordination channels.

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

1. create or update the contract-owned labels without deleting unknown labels;
2. select or create one repository workflow Project and configure its required
   Work stream, Queue sequence, and Lifecycle fields with exact lifecycle
   options; record its durable URL or ID in
   `AGENTS.md`;
3. add or adapt the repository's full-gate CI workflow using the commands in
   `AGENTS.md`, preserving unrelated workflows;
4. configure the base-branch ruleset, bind its required status-check names,
   confirm the full-gate job uses the configured commands, and disable GitHub's
   merge queue; and
5. confirm the named human coordinator can use the configured GitHub-visible
   claim, heartbeat, and recovery channels.

Never weaken an existing protection to make validation pass. Stop and request
direction when an existing setting is stricter but incompatible, or when more
than one Project could be the workflow authority.

## Re-read and verify

Read the resulting GitHub state again; do not validate intended mutations.
Rewrite the disposable snapshot from observed state and rerun the validator.
Update `AGENTS.md` with the observed Project identity and required checks, rerun
the local validator, and pass `--agents AGENTS.md` to the GitHub validator.
Planning may begin only when both validators pass.

Report the repository, Project, ruleset, CI workflow, coordinator, and validation
evidence. The named human coordinator is a supported operating mode; do not
block work on an automated FIFO controller.
