Hello,
We’re a team of builders. Many of us are new to traditional software development, but we’ve gone deep on agentic coding and do all our work with agents.
We’re designing processes that allow agents to take work from idea to implementation, verification, review, and completion.
We care deeply about building systems and workflows that can scale in every possible dimension. At the same time, we want to preserve strong engineering practices, high-quality code, and reliable verification.
Above all, we prefer short, simple solutions. We want agents to reduce complexity, avoid unnecessary machinery, and solve the actual problem as directly as possible.

# Repository Agent Orientation

Start here. This file identifies the repository, states the rules that always
apply, and routes each task to only the context it needs. Replace every
bracketed value during setup.

## How work moves through this repository

Shared plans and ownership live in GitHub. Implementation, testing, and review
happen in a local worktree. A person or agent claims a landing batch by
assigning it to themselves. Each active child ticket is likewise assigned to
its slice worker. An independent reviewer checks the result. The pull request
can merge only after its evidence, review, and required GitHub checks pass.

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

These terms have fixed meanings in every workflow document. In short: a landing
batch is one pull request, a slice is one independently testable change, the
local frontier is the ready work inside one claimed batch, and the execution
frontier is the ready work across all batches.

| Term | Meaning |
| --- | --- |
| Work stream | A group of related tickets that one owner can move forward independently of other groups. |
| Landing batch | The tickets merged together in one pull request. One owner claims the batch and is responsible for it. |
| Slice | The smallest complete change that can be implemented, verified, reviewed, and committed on its own. |
| Local prerequisite | A slice that must be completed and reviewed before another slice can begin. It is recorded as `local_after` and satisfied by a slice checkpoint, not by closing the ticket. A cross-batch prerequisite uses a stacked branch tied to the exact checkpoint. |
| Landing prerequisite | A `lands_after` relationship: the earlier batch must merge before the later batch can merge. |
| Start prerequisite | A `starts_after` relationship: the earlier batch must merge before anyone can claim or build the later batch. It must also be a direct landing prerequisite. |
| Slice checkpoint | A record in GitHub that ties a completed slice to the exact commit, test evidence, and review. |
| Local frontier | The unfinished slices that are ready to start because their local prerequisites have valid checkpoints. |
| Execution frontier | The combined view of ready batches and ready slices across the plan. |
| Conflict surface | A shared file, schema, migration, generated artifact, or deployment resource that two batches cannot safely change at the same time. |
| Work unlocker | A landing batch whose merge allows at least one waiting `starts_after` batch to be claimed and built. |
| Review finding | A concern found during review, including its priority, evidence, connection to the change, and durable review-time disposition. |
| Deferred-findings register | One GitHub issue that holds findings awaiting human triage. It is created only when a parent plan first has a deferred finding that needs human triage, and it is reused for the life of that plan. |
| Review clean | The required outcomes and exact base-to-candidate diff were reviewed, required tests pass, no P0/P1 blocker remains, every P2/P3 has a durable review-time disposition, and the exact candidate commit was reviewed. |

The workflow also uses these role names consistently:

- **Batch owner:** the person or agent assigned to and accountable for one landing batch.
- **Worker:** the person or agent implementing a slice or batch.
- **Reviewer:** an independent agent who reviews a specific commit.
- **Workflow maintainer:** a person allowed to repair lifecycle evidence and failed workflow runs.
- **GitHub actor:** the GitHub account that authenticates a workflow record.

## Authority and current evidence

- Intended product or architecture authority: Human-approved implementation specifications and architecture decisions recorded in GitHub planning issues
- Current implementation and adoption evidence: [`README.md`](README.md), the repository tree, and tests when implementation exists
- Unresolved decisions or blockers: GitHub issues labeled `planning:decision`
- Drift and disagreement routing: [`docs/agents/domain.md`](docs/agents/domain.md)
- Operational procedures and recovery: [`COORDINATION.md`](COORDINATION.md) and [`GITHUB-WORKFLOW.md`](GITHUB-WORKFLOW.md)
- Workflow maintainers: `ashoka-bm`
- Base branch: `main`
- Workflow Project: `https://github.com/users/ashoka-bm/projects/2`
- Required status checks: `landing-evidence`, `landing-gate`

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
- Landing prerequisites block merging, not claiming or building. Start
  prerequisites block both claiming and building until merge. Use the
  execution frontier to take other ready batches and slices, including
  checkpoint-bound stacked work across landing-only prerequisites.
- Use the domain and architecture routes in `docs/agents/domain.md`; never
  create a conventional root file when a configured repository authority owns
  that information elsewhere.
- Complete and verify local setup, then GitHub setup, before publishing planning
  or implementation artifacts.
- Use `plan-new-work` only to resolve uncertainty before specification
  approval. Use `plan-implementation-tickets` only after the exact
  implementation specification is approved and has no open decisions.
- Do not cross a human-approval stage gate without explicit approval of the
  exact artifact in the active conversation. Ask again after any material
  change or when work resumes in a new conversation without that approval.
- Treat review as fail-closed: interruption, unavailability, uncertainty,
  timeout, or token exhaustion never counts as approval.
- For a requested GitHub ticket, self-assignment is allowed after the checks in
  `COORDINATION.md`. Assignment is the complete claim. Do not change an issue
  already assigned to someone else. All other live or destructive external
  actions require explicit human approval unless this workflow names them as a
  routine implementation step.

### Batch lifecycle and ticket checkpoints

- The Project `Lifecycle` field belongs only to landing-batch issues. Leave it
  empty on plans and child tickets; use slice checkpoints to determine child
  progress.
- After each lifecycle trigger, wait for the trusted Lifecycle workflow to
  verify the GitHub evidence, update the batch Project value, and re-read it.
  Do not report the transition complete until GitHub shows the expected value.
- For fresh work, assign the issue to yourself and re-read it. Start when GitHub
  shows you as the only assignee. Assignment takes effect immediately;
  `Lifecycle: Building` is a derived display value and is not an additional
  claim gate.
- Within a claimed batch, post a commit-bound slice checkpoint after local
  verification and independent review, then immediately recompute the local
  frontier.
- The batch owner may delegate independent frontier slices to parallel workers
  in isolated worktrees or branches. Each worker assigns the active child
  ticket to themself; the batch owner remains accountable for integration and
  is the only checkpoint publisher.
- Preserve independent slice ancestry. Start a newly unlocked dependent from
  its prerequisite checkpoint, not from a later batch head containing unrelated
  completed slices.
- After publishing a checkpoint, dispatch newly unlocked work before reviewing,
  integrating, or checkpointing unrelated completed deliveries.
- Keep the landing pull request draft while implementing. When the batch is
  verified and review clean, post `local-complete` for the exact PR head using
  an authenticated GitHub actor. Wait for `Lifecycle: Locally complete`, then
  complete the ready-for-review gate and run
  `.workflow/scripts/queue_landing.py`; do not apply queue labels by hand.
- Freeze the approved batch contract at `Lifecycle: Locally complete`. Any
  material scope, dependency, membership, evidence, or PR-marker change
  requires dequeue, invalidation, and a return to `Building` before editing.
- After queue entry, wait for `Lifecycle: In PR`. Mergify owns current queue
  state and merges only after the required landing gates pass. Do not manually
  merge or enable GitHub auto-merge.
- After GitHub merges, verify GitHub shows `Lifecycle: Landed` and that the
  landing batch and delivered tickets closed. Then run the authenticated
  post-merge cleanup in `LOCAL-WORK.md` to remove the exact remote branch,
  local worktree, and local branch; preserve and report anything the cleanup
  refuses.

## Completion language

- **Complete slice:** the child ticket's slice meets its acceptance criteria,
  its focused tests pass, its documentation and local records are current, it
  is review clean, and a slice checkpoint preserves the result.
- **Locally complete batch:** every required slice checkpoint is current, the
  full batch passes its local gates, and the exact candidate commit is review
  clean.
- **Landing candidate:** the pull request for one coherent landing batch. It is
  a draft landing candidate while the batch is being built.
- **Queued landing candidate:** a non-draft landing candidate accepted into the
  Mergify queue. GitHub shows this as `Lifecycle: In PR`.
- **Landed:** the landing candidate passed required GitHub checks and merged
  into the base branch.

Do not describe locally complete work as landed.

## Repository-specific commands

List only commands that genuinely apply:

- Environment setup: None; the planned service uses the Python 3 standard library
- Focused tests: `python3 -m unittest discover -p 'test_launches.py'`
- Full local test gate: `python3 -m unittest discover`
- Build or type-check: `python3 -m compileall .`
- Lint or static checks: None

## Repository roots

Describe only the important top-level paths an agent must distinguish.

| Path | Owns |
| --- | --- |
| `src/` | Application behavior; it does not own workflow policy or planning state |
| `tests/` | Automated proof for application behavior |
| `docs/` | Durable domain, architecture, and operational documentation |
| `.local-work/` | Commit-bound implementation, test, and review evidence |
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
