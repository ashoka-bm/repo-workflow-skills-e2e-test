# Domain and Architecture Routing

Configure this file once with `configure-repository-workflow`. It tells every
bundled skill where resolved language, architecture decisions, and current-state
evidence belong. Do not create a conventional root file when a configured
repository authority owns the same information elsewhere.

## Configured routes

- Layout: `single-context`
- Vocabulary entry point: `docs/agents/domain.md`
- Context documents: `docs/agents/domain.md`
- Architecture authority: Human approval of the exact implementation specification in its GitHub planning issue
- Architecture decisions: GitHub issues labeled `planning:decision`, with the resolution linked from the approved specification
- Current-state evidence: `README.md`, the repository tree, and automated tests when implementation exists
- Drift or disagreement record: GitHub issues labeled `planning:decision`

## Consumer rules

- Read the vocabulary entry point, then only the context documents relevant to
  the task.
- Use one owning context for every resolved term. Record cross-context ownership
  and relationships in the configured vocabulary entry point.
- Record durable architecture trade-offs only through the configured decision
  authority, with the decision itself in the configured ADR route. A glossary
  edit does not approve architecture.
- Treat current-state maps as evidence of implementation, adoption,
  enforcement, or runtime posture; they do not ratify intended architecture.
- Keep unresolved terminology and decisions in the planning issue until they
  are resolved. Do not write guesses into durable domain documents.
- If current evidence conflicts with intended architecture, record the
  disagreement through the configured drift route instead of silently changing
  either authority.
- When the drift route is `None`, record the factual mismatch in configured
  current-state evidence. If both routes are `None`, stop and use
  `configure-repository-workflow` to establish one durable evidence owner.
