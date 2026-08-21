---
name: write-implementation-spec
description: Write and durably approve an implementation-ready specification after planning decisions are resolved. Use after a direct, understood request or a completed plan-new-work map and before plan-implementation-tickets; requires testable outcomes, proof, scope, documentation and operational impact, and no open decisions.
---

# Write Implementation Spec

Synthesize resolved decisions into the exact specification that constrains
implementation-ticket planning.

## Check readiness

Read `docs/agents/domain.md`, then read the request or completed planning map,
accepted vocabulary, ADRs, and the smallest relevant repository evidence from
the configured authorities. If the routing file is missing or contains a placeholder,
or lacks an authority needed by the specification, stop and use
`configure-repository-workflow`. Stop and return to `plan-new-work` when the
outcome, ownership, architecture, operational posture, or test boundary is still
undecided.

## Draft the specification

Use [assets/implementation-spec.md](assets/implementation-spec.md). Require:

- a problem and desired outcome in repository vocabulary;
- accepted implementation decisions and links to relevant vocabulary and ADRs;
- strict true-or-false acceptance criteria with one proving method each;
- explicit out-of-scope work;
- documentation impact and operational impact, including an explicit `None`
  when appropriate;
- no open decisions.

Keep implementation freedom where a choice does not affect the accepted
outcome. Do not invent a product or architecture decision to make the document
look complete.

## Approve the exact specification

Present the complete specification before publication. Approval applies only to
the exact specification bytes presented. Post the artifact and its computed
UTF-8 artifact in one comment using the canonical byte-length, artifact-text,
and SHA-256 shape in `WORKFLOW.md`. The human approves by adding GitHub's `+1`
reaction to that exact comment. Re-read the comment and reaction through GitHub's
authenticated API and record the reaction actor, UTC time, proposal URL, and
immutable reaction ID. Validate the record and observation with:

```bash
python3 .workflow/scripts/validate_approval.py <specification> <approval.json> <approval-observation.json>
```

The human only needs to approve or reject the exact artifact presented. They
are never required to calculate, copy, or type the digest, approver identity,
or timestamp. The agent or integration handling approval computes the digest
and records the event evidence returned by GitHub. If durable identity, time,
source, or event ID is unavailable, fail closed; do not ask the human to supply
approval metadata. Ask for ordinary approval only.

Any content change invalidates approval and requires another review. Do not
infer approval from silence or from approval of a prior version. The validator
binds the record to the GitHub observation; the authenticated API query supplies
the event evidence.

## Publish and stop

Before publishing, confirm the `PLAN` label and required GitHub setup
exist under `docs/agents/github-setup.md`; otherwise use
`configure-github-workflow`.

After validation, publish or update the specification as a GitHub Issue with
the `PLAN` label and preserve the approval record and observation in a
GitHub comment.
Do not apply `ready-for-agent`: implementation readiness belongs to landing
batches and is derived later.

Stop after reporting the approved specification issue. Route next to
`plan-implementation-tickets`; do not create implementation tickets or edit
implementation code while using this skill.
