---
name: plan-implementation-tickets
description: Turn a human-approved implementation specification into GitHub work streams, landing batches, and implementation tickets with clear dependencies. Use after planning decisions, vocabulary, ADRs, and specification approval are complete and before implementation begins.
---

# Plan Implementation Tickets

Turn an approved outcome into implementation work with clear dependencies,
safe opportunities for parallel work, and merge order.

## Check the input gate

Require an approved implementation specification with:

- no open decisions;
- true-or-false acceptance criteria and a proving method for each;
- explicit out-of-scope items;
- documentation impact and operational impact;
- links to relevant vocabulary and ADRs when they exist.

If any requirement is missing, stop and request the missing decision or
approval. Do not use this skill to decide the product outcome or settle open
architecture questions.

Before inspecting or splitting the work, confirm that the human explicitly
approved the exact specification in the active conversation. A GitHub label,
issue state, prior conversation, or silence is not approval. If the work
resumes without that approval in the active conversation, present the exact
specification and ask for approval again.

## Inspect the implementation context

Read the approved specification, linked vocabulary and ADRs, and only the code,
tests, and documentation needed to plan the work. Before proposing tickets,
identify existing conventions, sensible places to split the work, migrations,
generated files, and shared resources.

## Draft vertical slices

Split the specification into the smallest complete vertical slices that can be
implemented, verified, reviewed, and committed independently. Prefer a small
slice that works across real system boundaries instead of separate tickets for
types, storage, API, and UI.

Apply the [proof and documentation
policy](../../../LOCAL-WORK.md#proof-and-documentation-policy). Required proof
and documentation stay in the same implementation ticket. Create a separate
documentation or test-infrastructure ticket only when the approved specification
already defines it as an independent outcome with its own user or engineering
value. Approval of the ticket breakdown alone is not enough.

Create a prerequisite or preparatory ticket only when it has value on its own or
removes a proven blocker. For replacement and migration work, use
expand-contract ordering: add compatibility, migrate callers or data, verify
adoption, then remove the old path.

## Draw the dependency graph

Plan work as a dependency graph, not as waves that all move together. Use
`local_after` when one slice needs another slice's reviewed `slice-checkpoint`
tied to a specific commit. The prerequisite ticket does not need to close, and
its batch does not need to merge. A cross-batch local prerequisite is valid only
when the downstream batch also `lands_after` the prerequisite's batch and both
batches mark each other `safe_parallel_with`. Build it on a stacked branch tied
to the exact upstream checkpoint. Do not publish `local_after` as a native
GitHub blocker because child tickets stay open until their batch merges.

Use `lands_after` only when one landing batch must merge before another can
merge. Record these landing prerequisites with GitHub's native dependency
relationship. Use `starts_after` only when the downstream batch cannot be
claimed or built until that direct landing prerequisite merges. Every
`starts_after` edge must also be a direct `lands_after` edge. A `lands_after`
edge without `starts_after` does not block claiming or building when a current
upstream checkpoint provides a safe stacked base.

Keep both relationship types direct and necessary, explain why each edge exists, and
reject cycles. Every batch must have at least one locally executable starting slice.
It may be a root or a cross-batch checkpoint edge, and must have a path that
allows the remaining slices to become ready as checkpoints are added.

## Create work streams and landing batches

Group slices into work streams based on their dependencies and shared resources.
Name any files, contracts, schemas, migrations, generated files, test fixtures,
or operational resources that could make parallel work unsafe.

Create landing batches small enough for one owner to complete and recover
reliably. Put compatible slices in the same batch and branch, including
dependent slices that one owner can complete one at a time.
Preserve a healthy ready frontier so enough useful work remains ready when another item is blocked.
A local dependency between slices is not by itself a reason to split a batch.

Create exclusive landing batches:

- one batch contains work small enough for one owner on one branch;
- each batch states the problem that makes its integrated outcome necessary;
- each batch records the approved work it includes and the
  documented safety, flow, recovery, or review reason for work left in another batch;
- each batch records structured `flow_evidence` explaining why one owner can
  complete and recover it while leaving other useful work ready;
- when a plan has multiple batches, each batch records that reason in the
  required structured `split_reason` field;
- each batch has true-or-false acceptance criteria with one proving method per
  criterion and an explicit out-of-scope boundary;
- a claimed batch has exactly one owner;
- each active child ticket is assigned to its slice worker, and that assignment
  is its complete claim;
- separate batches may build in parallel, including as stacked branches, when
  local checkpoints and conflict surfaces show that it is safe;
- each batch states what must land before it, its locally executable starting
  slices, which landing prerequisites also block its start, and what it may
  safely overlap.

Balance larger batches against keeping work moving. Avoid a separate pull
request and hosted CI run for every slice. Split an otherwise safe group when
one owner could not complete or recover it reliably, or when the split makes
useful independent work available. Staged landing, independent progress,
independent recovery, reliable proof, reviewability, and conflict safety are
valid reasons to split. Always name the evidence that supports a split or a
claim that work is safe to run in parallel.

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

Do not write changing status, ownership, or queue position into ticket prose.
Keep `local_after` and `starts_after` in the exact approved bodies, and use
GitHub's native relationships for `lands_after`. An informal status note cannot
replace these rules.

## Get approval, then publish

Read `docs/agents/github-setup.md`. Before proposing live publication, confirm
the workflow labels, Project fields, hierarchy, and native dependency support
exist; otherwise stop and use `configure-github-workflow`. Offline historical
publication previews do not require live GitHub setup.

Show the complete numbered plan, work streams, landing batches, dependency
graph, shared resources, tickets, and proposed parallel work in the active
conversation. Publish only after the human explicitly approves that exact full
breakdown. Do not make meaningful changes to the GitHub Issues before approval.

Build the proposed publication payload in `.tmp/`, then validate it before
presentation:

```bash
python3 .agents/skills/plan-implementation-tickets/scripts/validate_plan.py <plan.json>
```

Approval applies only to the exact plan presented. Any change requires another
review. If work resumes in a new conversation without the approval in its
active context, show the plan and ask again. GitHub keeps the approved plan and
published issue hierarchy as a record; it is not another place to approve them.

After approval, publish or update the plan, batch, and child issues. Add native
`lands_after` relationships between batches and parent-child links. Keep
`local_after` and `starts_after` in the approved issue bodies rather than
inventing more meanings for GitHub relationships. Determine whether a batch can
be claimed from resolved `starts_after` gates, current local checkpoints,
conflict surfaces, explicit `must_not_overlap` rules, and assignment. Other
landing prerequisites do not block building.

Inside and across claimed batches, calculate the section-wide execution
frontier from `local_after` and exact current slice checkpoints. Do not add a
child-ticket readiness label or wait for child-ticket closure.

Use `PLAN`, `BATCH`, and `TICKET` only to identify the issue type. Keep work
stream and lifecycle in GitHub Project fields, batch membership in the native
hierarchy, landing prerequisites in native dependencies, and ownership on the
batch assignee. Apply only the controlled `surface:*` labels that affect safe
parallel work. Do not use labels for review level, readiness, or plan-specific
details.

The controlled conflict labels are `surface:schema`,
`surface:authentication`, `surface:routing`, `surface:dependencies`,
`surface:generated-files`, `surface:shared-contract`, and
`surface:deployment`. Extend that vocabulary only through an explicit
repository policy change. The closed batch lifecycle is `Planned`, `Building`,
`Locally complete`, `In PR`, and `Landed`; readiness and blocked state remain
derived rather than stored.

## Stop before implementation

Report what was created, what can safely run in parallel, what must run one item
at a time, and any unresolved publishing limitation. Do not claim a batch,
create a worktree, edit implementation code, or open a pull request while using
this skill.
