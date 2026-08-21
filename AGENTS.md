Hello,
We’re a team of builders. Many of us are new to traditional software development, but we’ve gone deep on agentic coding and do all our work with agents.
We’re designing processes that allow agents to take work from idea to implementation, verification, review, and completion.
We care deeply about building systems and workflows that can scale in every possible dimension. At the same time, we want to preserve strong engineering practices, high-quality code, and reliable verification.
Above all, we prefer short, simple solutions. We want agents to reduce complexity, avoid unnecessary machinery, and solve the actual problem as directly as possible.

# Repository Agent Orientation

Start here. This file identifies the repository, states the rules that always
apply, and routes each task to only the context it needs. Replace every
bracketed value during setup.

## Repository identity

- **Project:** Team Launch Planner
- **Purpose:** A synthetic service for testing the repository workflow from planning through landing.
- **Primary users or outcomes:** Small teams coordinating launches, approvals, assets, and schedules.

Use the repository's vocabulary precisely. Do not silently invent a second name
for an established concept or owner.

## Vocabulary and ownership

List only terms that change how work is understood, owned, or routed. Link to a
larger domain model instead of copying a full glossary here.

| Term | Meaning | Owner or authority |
| --- | --- | --- |
| Launch | A coordinated release with an owner, schedule, assets, and approval state. | [`docs/agents/domain.md`](docs/agents/domain.md) and the approved implementation specification |

### Workflow terms

These terms have fixed meanings in every workflow document:

| Term | Meaning |
| --- | --- |
| Work stream | Related tickets that one owner can advance independently of other streams. |
| Landing batch | The tickets that land together in one pull request; the exclusive claim and ownership unit. |
| Slice | The smallest end-to-end change that can be implemented, proved, reviewed, and committed on its own. |
| Local prerequisite | A `local_after` relationship between slices in one batch, satisfied by a reviewed slice checkpoint rather than ticket closure. |
| Landing prerequisite | A `lands_after` relationship between batches that requires the earlier batch to merge before the later batch can land. |
| Slice checkpoint | A GitHub-visible record binding a completed slice to its reviewed commit and proof. |
| Local frontier | The incomplete slices in a claimed batch whose local prerequisites have current slice checkpoints. |
| Conflict surface | A shared resource — file, schema, migration, generated artifact, deployment slot — that two batches cannot safely change in parallel. |
| Claim receipt | The coordinator's GitHub-visible record that a claim succeeded; assignment alone is never a claim. |
| Queue sequence | The immutable, monotonically increasing number assigned when a locally complete draft enters the landing queue. |
| Review finding | A reviewer-observed concern with a priority, evidence, relationship to the candidate, and durable review-time disposition. |
| Deferred-findings register | The single GitHub issue created only when a parent plan first has a deferred finding that needs human triage; reused for the plan's lifetime. |
| Review clean | Every applicable approved slice or landing-batch outcome was reviewed against the exact base-to-candidate diff, no unresolved P0/P1 blocker remains, every P2/P3 has a durable review-time disposition, required tests pass, and the exact candidate commit was reviewed. |

## Authority and current evidence

- Intended product or architecture authority: Human-approved implementation specifications and architecture decisions recorded in GitHub planning issues
- Current implementation and adoption evidence: [`README.md`](README.md), the repository tree, and tests when implementation exists
- Unresolved decisions or blockers: GitHub issues labeled `planning:decision`
- Drift and disagreement routing: [`docs/agents/domain.md`](docs/agents/domain.md)
- Operational procedures and recovery: [`COORDINATION.md`](COORDINATION.md) and [`GITHUB-WORKFLOW.md`](GITHUB-WORKFLOW.md)
- Claim coordinator: GitHub user `ashoka-bm`
- Claim request channel: Landing-batch issue comments using the records in [`COORDINATION.md`](COORDINATION.md)
- Claim heartbeat channel: Landing pull-request comments using the heartbeat record in [`COORDINATION.md`](COORDINATION.md)
- Stale-claim duration: 24 hours
- Recovery-grace duration: 4 hours
- Base branch: `main`
- Workflow Project: `https://github.com/users/ashoka-bm/projects/2`
- Required status checks: `landing-gate`
- Durable approval channel: GitHub issue comments approved with a `+1` reaction

Governing specifications describe intended behavior; code, tests,
configuration, and runtime observations describe what exists now. Record any
disagreement; neither an audit nor existing code silently rewrites the
governing decision. Generated maps, reports, manifests, and baselines are
evidence, not independent architecture authority.

## Start and stop protocol

Before working: classify the task, locate the affected paths, resolve the owner
and governing authority, inspect the smallest relevant current evidence, and
choose the verification that proves the outcome.

Stop and request direction for unresolved ownership, conflicting authority, an
unapproved production-posture change, or an external effect that requires human
authorization.

## Core rule

GitHub Issues are authoritative for shared plans, landing batches, tickets,
dependencies, and ownership. Implementation, testing, and review happen in a
local worktree. Repository-local files preserve commit-bound evidence; they do
not duplicate mutable ticket state.

## Router

Follow the router and expand context only when the task crosses another owner
or boundary; do not preload every glossary, architecture record, map, ticket,
or runbook.

| When you need to... | Load or use |
| --- | --- |
| Understand the complete planning-to-merge process | [`WORKFLOW.md`](WORKFLOW.md) |
| Plan, implement, test, review, or combine local work | [`LOCAL-WORK.md`](LOCAL-WORK.md) |
| Classify, resolve, defer, or revisit review findings | [`docs/agents/review-findings.md`](docs/agents/review-findings.md) |
| Claim, release, hand off, or recover shared work | [`COORDINATION.md`](COORDINATION.md) |
| Push, open a pull request, handle CI, or merge | [`GITHUB-WORKFLOW.md`](GITHUB-WORKFLOW.md) |
| Triage an incoming issue | [`docs/agents/triage-labels.md`](docs/agents/triage-labels.md), using `triage` when available |
| Configure this workflow for the repository | `configure-repository-workflow`, then verify the installation |
| Initialize or verify GitHub labels, Projects, protections, and CI | [`docs/agents/github-setup.md`](docs/agents/github-setup.md), then `configure-github-workflow` |
| Plan or resume a large, uncertain, or multi-session effort | The relevant GitHub planning issue, `plan-new-work`, then [`WORKFLOW.md`](WORKFLOW.md) |
| Change implementation | `src/` and `tests/`, the implicated contract, focused code and tests |
| Define a domain term or record an architecture decision | [`docs/agents/domain.md`](docs/agents/domain.md), then `maintain-domain-model` |
| Resolve architecture or ownership | [`docs/agents/domain.md`](docs/agents/domain.md) and its configured authority |
| Inspect adoption, enforcement, or runtime posture | [`README.md`](README.md), `src/`, and `tests/` |
| Decide documentation impact | [`README.md`](README.md) and `docs/` |
| Turn resolved decisions into an implementation specification | `write-implementation-spec` |
| Break an approved implementation specification into tickets | `plan-implementation-tickets` |

The routed repository skills — `configure-repository-workflow`,
`configure-github-workflow`, `maintain-domain-model`, `plan-new-work`,
`write-implementation-spec`, and `plan-implementation-tickets` — live in this repository at
`.agents/skills/`, one directory per skill. When the router names one your
runner has not loaded, read its `SKILL.md` directly and follow it.

The optional `triage` helper may categorize, verify, and write an intake brief
only. Unresolved product or architecture questions route to `plan-new-work`;
the helper does not resolve planning decisions, update ADRs, or treat external
pull requests as intake unless repository policy explicitly expands its scope.

### Optional helper skills

The installed workflow is complete without global skills. When available,
`repo-architecture-map`, `triage`, `grill-me`, `implement`, `tdd`,
`code-review`, `github:yeet`, and
`github:gh-fix-ci` may help perform a routed step; they never override its
repository contract — including ticket, testing, review, and publishing
conventions — or make verification depend on a contributor's global skill
installation.

## Required working rules

- Surface meaningful ambiguity before implementation.
- For multi-step work, state a concrete, verifiable success condition first.
- Agree on behavior in plain language before coding it, then make the smallest
  change that satisfies it.
- Keep tests and documentation required by an implementation in the same
  implementation ticket and slice; never defer them to completion tickets.
- Treat a landing batch as a landing boundary, not an execution wave. Start any
  slice on the local frontier; never wait for a prerequisite ticket to close
  when its required slice checkpoint is current.
- Use the domain and architecture routes in `docs/agents/domain.md`; never
  create a conventional root file when a configured repository authority owns
  that information elsewhere.
- Complete and verify local setup, then GitHub setup, before publishing planning
  or implementation artifacts.
- Use `plan-new-work` only to resolve uncertainty before specification
  approval. Use `plan-implementation-tickets` only after the exact
  implementation specification is approved and has no open decisions.
- Do not cross a human-approval stage gate when its exact approved artifact
  cannot be verified.
- Treat review as fail-closed: interruption, unavailability, uncertainty,
  timeout, or token exhaustion never counts as approval.
- For a requested GitHub ticket, posting a claim request is allowed. An accepted
  claim authorizes only these routine workflow records and guarded cleanup
  steps; all other live or destructive external actions require explicit human
  approval.

### Ticket lifecycle checkpoints

- For fresh work, do not start implementation until GitHub shows an accepted
  claim receipt, exactly one owner, and `Lifecycle: Building`. For a handoff or
  recovery, verify the new receipt and owner while preserving the existing
  delivery lifecycle.
- Within a claimed batch, post a commit-bound slice checkpoint after local proof
  and another-agent review, then immediately recompute the local frontier.
- Keep the landing pull request draft while implementing. When the batch is
  proved and review clean, post `local-complete` for the exact PR head, then
  wait for `Lifecycle: Locally complete` before posting `queue-request`.
- Do not manually make the pull request ready or merge it. The landing
  controller selects the FIFO candidate, sets `Lifecycle: In PR`, and enables
  auto-merge only after current promotion evidence exists.
- After GitHub merges, verify GitHub shows `Lifecycle: Landed` and that the
  landing batch and delivered tickets closed. Then run the authenticated
  post-merge cleanup in `LOCAL-WORK.md` to remove the exact remote branch,
  local worktree, and local branch; preserve and report anything the cleanup
  refuses.

## Completion language

- **Locally complete:** the ticket meets its acceptance criteria, its focused
  tests pass, its documentation and local records are current, it is review
  clean under [`docs/agents/review-findings.md`](docs/agents/review-findings.md),
  and a local commit preserves the result.
- **Landing candidate:** a draft pull request for one coherent landing batch.
- **Active landing candidate:** the one non-draft pull request currently selected to land next.
- **Landed:** the landing candidate passed required GitHub checks and merged
  into the base branch.

Do not describe locally complete work as landed.

## Repository-specific commands

List only commands that genuinely apply:

- Environment setup: None; the planned service uses the Python 3 standard library
- Focused tests: `python3 -m unittest discover -s tests -p 'test_launches.py'`
- Full local test gate: `python3 -m unittest discover -s tests`
- Build or type-check: `python3 -m compileall src tests`
- Lint or static checks: None configured

## Repository roots

Describe only the important top-level paths an agent must distinguish.

| Path | Owns |
| --- | --- |
| `src/` | Application behavior; it does not own workflow policy or planning state |
| `tests/` | Automated proof for application behavior |
| `docs/` | Durable domain, architecture, and operational documentation |
| `.scratch/` | Commit-bound implementation, test, and review evidence |
| `.tmp/` | Disposable investigations and generated intermediates |

# Coding preferences
- Keep things simple. Channel "yagni" energy unless told otherwise.
- Typesafety is useful, take advantage of it.
- Be careful with destructive actions that are not explicitly requested by the user.
- Tests are good! Endless smoke tests, "regression tests" for feature deletions, etc, much less good. Tests should be focused, not slop.
- Comments are a great way to clarify functionality and how code is used. Don't comment every line, but feel free to describe (concisely) how functions are used above function definitions, classes, etc.
- Keep comments up to date! When making changes, it's important to keep things in sync.

# Questions are read-only
- A question is a request for an answer, not for changes. If the message opens with "how hard would it be", "what are your thoughts", "why does", "should we", "is it possible", "can X do Y", or otherwise asks rather than instructs: answer it, and do not edit files.
- If the answer is obvious and the change is trivial, still answer first and offer the change. Ask before making it.

# Match ceremony to the task
- Do not spawn subagents or a multi-agent panel for work a single agent finishes in one pass. Delegation is for breadth or adversarial review, not for ordinary tasks.
- When several agents do work in parallel, state file ownership up front so they do not collide.
