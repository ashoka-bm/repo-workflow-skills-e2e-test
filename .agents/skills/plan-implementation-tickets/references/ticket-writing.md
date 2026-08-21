# Implementation Work Item Writing

Write for the person or agent starting the work later.

## Titles

Use established repository vocabulary and inspect recent accepted work for
title conventions. Lead with the behavior, outcome, or problem being resolved.
Keep an implementation detail only when it distinguishes the outcome.

Do not encode type, stream, batch, owner, queue position, review, or temporary
status metadata in a title. Include a measurable target only when it is an
approved acceptance criterion; never promise an unverified result.

Name each artifact at its own altitude:

- a plan names the overall outcome;
- a batch names the integrated capability it can land;
- a ticket names one independently verifiable behavior; and
- a pull request names the completed batch outcome using the repository's
  merge-title convention.

## Body order

The approved plan body is governed by
`.agents/skills/write-implementation-spec/assets/implementation-spec.md`. The
completed pull-request body is governed by
`.github/pull_request_template.md`. The order below applies to proposed landing
batches and implementation tickets; those two higher-level assets express the
same outcome-first contract at their own stage.

Open with two short plain-language sections. The first paragraph explains the
problem: what happens now, who or what is affected, and why it matters. The
second states the desired outcome without beginning with files, functions, or
an implementation inventory.

Then use this order:

1. **Problem** — why the current state is insufficient.
2. **Desired outcome** — the bounded result this work item owns.
3. **Batch boundary, for landing batches** — confirm the work is bounded for
   one owner and justify each split with a safety, flow, recovery, or review
   reason.
4. **Parent and dependencies** — the plan and batch, local prerequisites between
   slices, and true landing prerequisites between batches.
5. **Starting context, when needed** — the smallest paths, contracts, or
   conventions needed to begin without rediscovery.
6. **Acceptance and proof** — one proving method for every criterion.
7. **Out of scope** — nearby work this item deliberately excludes.
8. **Conflict surfaces** — shared files, contracts, data, or resources.
9. **Documentation and operations** — required updates, rollout, or recovery.

Keep implementation choices open when the specification does not require them,
but never hide an unresolved product or architecture decision inside a ticket.
Prefer links to authoritative specifications and ADRs over copied prose.

Use current-versus-desired language for proposed plans, batches, and tickets.
For pull requests, state the problem addressed and the completed outcome.

Use controlled conflict surfaces: name the smallest shared unit that matters,
not a broad directory when only one contract is shared. A ticket is not safe to
run in parallel merely because it has no formal dependency.

## Quality review

Complete a semantic review before publication. Confirm that:

- a reader can understand the impact without knowing the implementation;
- the title promises no unapproved or unverified result;
- the first paragraph explains the problem instead of listing edits;
- every acceptance criterion has explicit proof that follows the [test-quality
  and same-ticket rules](../../../../LOCAL-WORK.md#proof-and-documentation-policy),
  including stable-boundary proof, coverage reuse, and shared proof where
  sufficient;
- every cross-batch `local_after` is backed by downstream `lands_after` and
  reciprocal `safe_parallel_with`, `lands_after` names only a true landing
  prerequisite, every `starts_after` is a direct `lands_after` edge whose merge
  is required before downstream implementation can begin, and conflict surfaces
  explain unsafe parallelism; and
- every separate batch has a documented safety, flow, recovery, or review
  reason; and
- status, ownership, queue, readiness, and review metadata are absent from the
  title and body; relationship links and blocker reasons may supplement the
  native GitHub relationships without replacing them.

Structural validation checks fields and relationships. It cannot replace this
semantic review or judge an outcome-first title with a simplistic regex.
