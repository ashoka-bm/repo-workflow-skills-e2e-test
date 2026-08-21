---
name: plan-new-work
description: Resolve uncertainty for large, materially unclear, or multi-session work as a GitHub planning map. Use before an implementation specification exists to answer product and architecture questions, establish vocabulary and ADRs, and make the work ready for specification without creating implementation tickets or code.
---

# Plan New Work

Turn an uncertain destination into resolved decisions that
`write-implementation-spec` can synthesize.

Read `docs/agents/domain.md` before resolving domain or architecture questions.
If it is unconfigured, stop and use `configure-repository-workflow` first.
Read `docs/agents/github-setup.md` before publishing planning issues. If its
planning labels, Project fields, or native relationships are unavailable, use
`configure-github-workflow`. An explicitly offline publication preview does not
require live GitHub setup and must not publish.

## Set the destination

Confirm the intended outcome, scope, decision authority, and what must be true
before an implementation specification can be written. If the work is already
small and understood, stop and route directly to `write-implementation-spec`.

## Create the GitHub planning map

Use one GitHub Issue labelled `planning:map` as the canonical map. Create child
issues only for decisions or investigations that can be stated precisely now.
Use `planning:research` for evidence gathering, `planning:prototype` for a
disposable uncertainty-reducing experiment, `planning:decision` for a choice
that requires an authority, and `planning:task` for planning-stage synthesis or
documentation. Use native issue dependencies for blockers. Follow the
planning-issue assignment protocol in `COORDINATION.md`; assigning an open,
unassigned issue to yourself is the complete claim.

Keep the map as an index: destination, decisions with links, not-yet-specified
fog, and out-of-scope work. Keep each detailed answer in its decision issue so
one decision has one authority.

## Resolve the frontier

Work open, unassigned, unblocked decision issues. Assign the issue to yourself
and re-read GitHub to confirm you are its only assignee before starting. Record the answer, close the
issue, update the map index, and add or invalidate later questions revealed by
the answer. More than one decision may be resolved in a session when each has
its own claim and remains independently attributable and reviewed.

Use `maintain-domain-model` when a resolved answer changes a domain term,
context boundary, architecture decision, current-state record, or known drift.
It routes the result through `docs/agents/domain.md`; do not assume root
`CONTEXT.md`, `CONTEXT-MAP.md`, or `docs/adr/` locations. Link the accepted
vocabulary and ADRs from the map.

## Exit at specification readiness

The planning stage is complete only when:

- the destination and out-of-scope boundary are explicit;
- no product, architecture, ownership, or operational decision needed by
  implementation remains open;
- relevant vocabulary and ADRs are accepted and linked;
- the evidence needed to write testable outcomes is available.

Route the resolved map to `write-implementation-spec`.

Never implement, create implementation tickets, define landing batches, open an
implementation pull request, or use planning notes to carry execution past this
boundary.
