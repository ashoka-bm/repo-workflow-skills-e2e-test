# Planning-to-Merge Workflow

The canonical lifecycle for repository work. GitHub owns shared plans and
tickets; [`LOCAL-WORK.md`](LOCAL-WORK.md) owns implementation mechanics; and
[`GITHUB-WORKFLOW.md`](GITHUB-WORKFLOW.md) owns landing-candidate movement.

**understand → resolve uncertainty when needed → vocabulary and ADRs when
needed → approved implementation specification → implementation tickets and
landing batches → implement → test → review → draft landing candidate → final
gates → CI → merge**

## 0. Initialize the repository workflow

After installation, use `configure-repository-workflow` and run
`.workflow/scripts/verify_setup.py`. Then use `configure-github-workflow` to
initialize and verify the labels, Project fields, native relationships, branch
protection, CI triggers, and manual coordination required by the lifecycle.
Planning begins only after both setup checks pass. The installed FIFO controller
starts in audit mode and cannot change GitHub until enforcement is explicitly
configured. The named human coordinator can operate the same protocol as a
fallback.

## 1. Understand and decide

Clarify the desired outcome, constraints, ownership, and important unknowns by
following the start and stop protocol in [`AGENTS.md`](AGENTS.md).

Use `plan-new-work` only for large, materially uncertain, or multi-session work.
It organizes the questions and decisions needed to reach a specification, not
implementation tickets. For smaller, understood work, proceed directly.

When the work introduces or changes important domain terms, context boundaries,
or architecture decisions, read `docs/agents/domain.md` and use
`maintain-domain-model`. It places resolved vocabulary, context relationships,
ADRs, current-state evidence, and drift in their configured authorities. Record
an ADR when a decision is durable, surprising, cross-boundary, or costly to
reverse. Unresolved questions remain in the planning map.

## 2. Approve the outcome

Use `write-implementation-spec` to create an approved implementation
specification containing:

- strict true-or-false acceptance criteria;
- a proving test or verification method for each criterion;
- explicit out-of-scope items;
- documentation impact and required updates, or a specific reason none are
  needed;
- operational impact, or an explicit statement that there is none;
- no unresolved implementation decisions.

The human approves the specification before tickets are created. Post the exact
UTF-8 artifact in one GitHub issue comment through the configured durable
approval channel using this exact shape: `WORKFLOW APPROVAL REQUEST`, `Artifact
byte length: <bytes>`, `Artifact:`, the exact artifact text, then `Artifact
SHA-256: <digest>`. The human approves by adding GitHub's `+1` reaction to that
exact comment. After approval, preserve
the approval record and observation returned by GitHub's authenticated API.
Validate the artifact, record, and observation with
`.workflow/scripts/validate_approval.py`. Any content change invalidates the
approval. If a decision remains open, return to planning instead of guessing.
The validator uses GitHub's REST API with `GH_TOKEN` or `GITHUB_TOKEN`; it does
not require a globally installed skill and exposes no offline mode. The source
repository's sealed historical harness uses a separate wrapper that is never
installed into target repositories.

The human only needs to approve or reject the exact artifact presented. They
are never required to calculate, copy, or type its digest, their identity, or a
timestamp. The agent or integration handling approval computes the digest and
records the reaction actor, UTC time, proposal URL, and immutable reaction ID
returned by GitHub. If the channel
cannot be queried for durable event evidence, the gate must fail closed; do not
ask the human to supply approval metadata. These fields are evidence, not
approval-form inputs.

## 3. Plan implementation tickets and landing batches

Use `plan-implementation-tickets` to turn the approved specification into
GitHub Issues. Keep slices independently provable and create bounded landing
batches that one owner can complete and recover reliably while preserving a
healthy ready frontier across the effort. Preserve expand-contract ordering
while making these relationships explicit:

- work streams and safe opportunities for parallel work;
- exclusive landing batches;
- `local_after` prerequisites between slices in one batch;
- native `lands_after` prerequisites between landing batches;
- conflict surfaces and shared resources;
- acceptance criteria with proving methods;
- documentation and operational impact.

Tests and documentation required by an implementation stay in the same
implementation ticket. Do not create separate or follow-up tickets to finish
proof or documentation for implementation work.

Present the complete proposed breakdown for human approval before publishing
or updating the GitHub issues. Bind that approval to the exact plan using the
same durable SHA-256 approval contract and user-input rule.

Use outcome-first titles and problem-first descriptions; the detailed semantic
writing contract belongs to `plan-implementation-tickets`.

A local prerequisite is satisfied by a reviewed, commit-bound slice checkpoint,
not by closing its child ticket. A landing prerequisite controls when a batch
may land; it does not turn all work in an effort into a wave. Every planned
batch must have a locally executable starting slice.

## 4. Complete a landing batch locally

Claim one ready landing batch through the claim rules in
[`COORDINATION.md`](COORDINATION.md), then follow the completion loop in
[`LOCAL-WORK.md`](LOCAL-WORK.md) to implement, verify, review, and preserve
evidence for each slice. After every slice checkpoint, recompute the local
frontier and continue with any newly executable slice without waiting for child
tickets to close. The GitHub snapshot derives that frontier from child-ticket
`local_after` contracts and current claim-bound checkpoint records. Review
follows the bounded priority and disposition
policy in [`docs/agents/review-findings.md`](docs/agents/review-findings.md): P0
and P1 block, while P2 and P3 receive durable review-time dispositions without
expanding the current batch. Only deferred findings that need later human
triage enter a shared register.
When the full batch is proven for the exact draft pull-request head, post its
authenticated `local-review` and claim-bound `local-complete` records, then wait
for the controller to set `Lifecycle` to `Locally complete`.

## 5. Publish and land

Open or update one draft pull request for the landing batch — its landing
candidate. After GitHub shows `Lifecycle: Locally complete`, post the
`queue-request` record to enter the FIFO landing order. Link the parent plan's single
deferred-findings register only when at least one finding's review-time disposition is
`deferred` and needs later human triage. At its landing turn the candidate
passes the ready-for-review gate, then the controller makes it the one
non-draft candidate, enables auto-merge, and lets GitHub CI verify it. GitHub
merges only after every required check and approval passes. Candidate
semantics, queue behavior, the ready-for-review gate, and
merge requirements are governed by [`GITHUB-WORKFLOW.md`](GITHUB-WORKFLOW.md).
After GitHub confirms the merge and the controller or fallback coordinator
completes remote cleanup,
the batch owner follows [`LOCAL-WORK.md`](LOCAL-WORK.md) to remove the exact
clean local batch worktree and branch. Refused cleanup is reported and
preserved for recovery rather than forced.

## Exceptions

An earlier push is allowed for collaboration, handoff, or remote backup. It does
not make the work locally complete, review-ready, or eligible to land.
