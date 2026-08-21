---
name: write-implementation-spec
description: Write and obtain active-conversation approval for an implementation-ready specification after planning decisions are resolved. Use after a direct, understood request or a completed plan-new-work map and before plan-implementation-tickets; requires testable outcomes, proof, scope, documentation and operational impact, and no open decisions.
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

Present the complete specification in the active conversation before
publication and explicitly ask the human to approve or reject it. Approval
applies only to the exact content presented in that request. Do not infer
approval from silence, a prior artifact, a GitHub label, or an earlier
conversation. Continue only when the human explicitly approves it.

Any content change invalidates the approval and requires another review. If the
work resumes in a new conversation and the exact approval is not present in the
active conversation, present the specification and ask for approval again.
GitHub stores the approved specification for traceability; it is not an
additional approval interface.

## Publish and stop

Before publishing, confirm the `PLAN` label and required GitHub setup
exist under `docs/agents/github-setup.md`; otherwise use
`configure-github-workflow`.

After approval, publish or update the specification as a GitHub Issue with the
`PLAN` label.
Do not apply `ready-for-agent`: implementation readiness belongs to landing
batches and is derived later.

Stop after reporting the approved specification issue. Route next to
`plan-implementation-tickets`; do not create implementation tickets or edit
implementation code while using this skill.
