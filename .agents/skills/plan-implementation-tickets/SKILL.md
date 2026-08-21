---
name: plan-implementation-tickets
description: Turn a human-approved implementation specification into dependency-aware GitHub work streams, exclusive landing batches, and implementation tickets. Use after planning decisions, vocabulary, ADRs, and specification approval are complete and before implementation begins.
---

# Plan Implementation Tickets

Convert an approved outcome into implementation work that makes dependencies,
safe parallelism, and landing order explicit.

## Check the input gate

Require an approved implementation specification with:

- no open decisions;
- true-or-false acceptance criteria and a proving method for each;
- explicit out-of-scope items;
- documentation impact and operational impact;
- links to relevant vocabulary and ADRs when they exist.

Stop and request the missing decision or approval when this gate is not met. Do
not use this skill to discover the product outcome or make unresolved
architecture decisions.

Approval must be bound to the exact specification. Before inspecting or
splitting the work, validate the specification and its approval record:

```bash
python3 .workflow/scripts/validate_approval.py <specification.md> <specification-approval.json> <specification-approval-observation.json>
```

Stop if validation fails. The command binds the approval record to an event
re-read through GitHub's authenticated API, including its actor and time.

## Inspect the implementation context

Read the approved specification, linked vocabulary and ADRs, and the smallest
relevant code, test, and documentation paths. Identify existing conventions,
natural seams, migrations, generated artifacts, and shared resources before
proposing tickets.

## Draft vertical slices

Split the specification into the smallest end-to-end vertical slices that can
be implemented, proved, reviewed, and committed independently. Prefer a thin
tracer slice through real boundaries over separate horizontal tickets for
types, storage, API, and UI.

Tests and documentation required by an implementation stay in the same
implementation ticket. Never create separate or follow-up tickets merely to add
its proof or documentation. A documentation-only or test-infrastructure ticket
is valid only when that work is an independently approved outcome rather than
unfinished completion work for another ticket.

Create a prerequisite or prefactor ticket only when it is independently
valuable or removes a proven blocker. For replacement and migration work, use
expand-contract ordering: introduce compatibility, migrate callers or data,
prove adoption, then remove the old path.

## Draw the dependency graph

Model execution as a graph, not a set of waves. Use `local_after` for a slice
that needs another slice in the same landing batch. A local prerequisite is
satisfied by that earlier slice's reviewed, commit-bound `slice-checkpoint`;
ticket closure and batch landing are not required. Do not publish `local_after`
as a native GitHub blocker because child tickets remain open until the batch
lands.

Use `lands_after` only between landing batches when one batch truly must merge
before another can land. Publish those landing prerequisites with GitHub's
native dependency relationship. Keep both relationship types direct and
minimal, explain why each edge exists, and reject cycles. Every batch must have
at least one locally executable starting slice and a path that lets all of its
remaining slices become locally executable as checkpoints accumulate.

## Create work streams and landing batches

Group slices into work streams based on dependency order and conflict surfaces.
Name shared files, contracts, schemas, migrations, generated artifacts, test
fixtures, and operational resources that could make parallel work unsafe.

Create bounded landing batches that one owner can complete and recover
reliably. Put compatible slices in the same batch and branch, including
dependent slices that one owner can complete serially, while preserving a
healthy ready frontier across the approved effort. A local dependency between
slices is not by itself a reason to split a batch.

Create exclusive landing batches:

- one batch contains bounded work on one branch;
- each batch states the problem that makes its integrated outcome necessary;
- each batch records its boundary: the bounded approved work it includes and
  the documented safety, flow, recovery, or review reason for work left in
  another batch;
- each batch records structured `flow_evidence` explaining why one owner can
  complete and recover it without starving the approved effort's ready frontier;
- when a plan has multiple batches, each batch records that reason in the
  required structured `split_reason` field;
- each batch has true-or-false acceptance criteria with one proving method per
  criterion and an explicit out-of-scope boundary;
- a claimed batch has exactly one owner;
- child tickets remain unassigned;
- separate batches may proceed in parallel only when native dependencies and
  conflict surfaces show that it is safe;
- each batch states what must land before it, its locally executable starting
  slices, and what it may safely overlap.

Balance consolidation against continuous flow. Avoid per-slice pull requests
and hosted CI, but split an otherwise safe group when one owner could not
complete or recover it reliably or when the split exposes useful independent
work. Staged landing, useful independent flow, independent recovery, reliable
proof, reviewability, and conflict safety remain valid split reasons. Never
claim a split or parallel safety without naming the evidence.

## Write implementation tickets

Read [references/ticket-writing.md](references/ticket-writing.md) before writing
or reviewing titles and bodies. Use
[assets/landing-batch.md](assets/landing-batch.md) for batch issues and
[assets/implementation-ticket.md](assets/implementation-ticket.md) for child
ticket bodies.

Each ticket must include:

- the problem and desired outcome;
- its parent plan, work stream, and landing batch;
- direct `local_after` prerequisites and conflict surfaces;
- bounded in-scope and out-of-scope work;
- true-or-false acceptance criteria with one proving method per criterion;
- documentation impact and operational impact;
- enough repository context to start without rediscovering the plan.

Do not encode mutable status, ownership, or queue position in prose. Preserve
`local_after` in the exact approved ticket body and use native GitHub
relationships for `lands_after`; never substitute an informal status note for
either contract.

## Get approval, then publish

Read `docs/agents/github-setup.md`. Before proposing live publication, confirm
the workflow labels, Project fields, hierarchy, and native dependency support
exist; otherwise stop and use `configure-github-workflow`. Offline historical
publication previews do not require live GitHub setup.

Present the complete numbered plan, work streams, landing batches, dependency
graph, conflict surfaces, tickets, and proposed safe parallel work. Publishing
begins only after the human approves the full breakdown. Do not materially
change GitHub Issues before that approval.

Build the proposed publication payload in `.tmp/`, then validate it before
presentation:

```bash
python3 .agents/skills/plan-implementation-tickets/scripts/validate_plan.py <plan.json>
```

Approval applies only to the exact plan presented. Post the UTF-8 plan in one
comment using the canonical byte-length, artifact-text, and SHA-256 shape in
`WORKFLOW.md`. The human approves by adding GitHub's `+1` reaction to that exact
comment. Re-read the comment and reaction through GitHub's authenticated
API and record the reaction actor, UTC time, proposal URL, and immutable
reaction ID. Validate the record and observation before publishing:

```bash
python3 .workflow/scripts/validate_approval.py <plan.json> <approval.json> <approval-observation.json>
```

The human only needs to approve or reject the exact artifact presented. They
are never required to calculate, copy, or type the digest, approver identity,
or timestamp. The agent or integration handling approval computes the digest
and records the event evidence returned by GitHub. If durable identity, time,
source, or event ID is unavailable, fail closed; do not ask the human to supply
approval metadata. Ask for ordinary approval only.

Any plan change invalidates approval and requires another review.

After approval, publish or update the plan, batch, and child issues. Add native
`lands_after` relationships between batches and parent-child links. Keep
`local_after` in the approved ticket contract rather than native blockers.
Batch claim readiness is derived only for batches whose landing prerequisites
are resolved, whose conflict surfaces do not overlap active work, and which
remain unassigned. Inside a claimed batch, derive the local frontier from
`local_after` and current slice checkpoints; do not add a child-ticket readiness
label or wait for child-ticket closure.

Use `workflow:plan`, `workflow:batch`, and `workflow:ticket` only for artifact
type. Keep stream and lifecycle in GitHub Project fields, batch membership in
the native hierarchy, landing prerequisites in native dependencies, and
ownership on the batch assignee. Apply only the controlled `surface:*` labels
that affect safe parallel work; do not encode review level, readiness, or
plan-specific metadata as labels.

The controlled conflict labels are `surface:schema`,
`surface:authentication`, `surface:routing`, `surface:dependencies`,
`surface:generated-files`, `surface:shared-contract`, and
`surface:deployment`. Extend that vocabulary only through an explicit
repository policy change. The closed batch lifecycle is `Planned`, `Building`,
`Locally complete`, `Waiting to land`, `In PR`, and `Landed`; readiness and
blocked state remain derived rather than stored. Preserve the validated plan
approval record and observation in a comment on the GitHub plan issue.

## Stop before implementation

Report what was created, what can safely run in parallel, what must remain
serial, and any unresolved publishing limitation. Do not claim a batch, create
a worktree, edit implementation code, or open a pull request while using this
skill.
