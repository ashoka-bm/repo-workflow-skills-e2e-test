---
name: maintain-domain-model
description: Place resolved domain terms, bounded-context relationships, architecture decisions, current-state evidence, and known drift into their configured repository authorities. Use during new-work planning when vocabulary or architecture changes, and when later work discovers a durable correction. Do not use for unresolved questions, implementation specifications, tickets, or code.
---

# Maintain Domain Model

Record each resolved fact once, in the authority configured by the repository.

## Load the route and relevant authority

Read `docs/agents/domain.md` completely, then read
`references/artifact-routing.md`. Stop and use
`configure-repository-workflow` if the routing file is missing, contains a
placeholder, or does not identify an owner for the artifact being changed.
Apply the drift fallback and stop conditions defined in the routing reference.

Load only the relevant context document, context-map entry, architecture
authority, ADR index, or evidence record. The configured routes always override
conventional filenames such as root `CONTEXT.md`, `CONTEXT-MAP.md`, or
`docs/adr/`.

## Classify before writing

Classify each item using the routing reference:

- a stable term or invariant belongs to its owning context document;
- a context owner, boundary, or relationship belongs to the context map;
- a durable, surprising, cross-boundary, or costly-to-reverse decision belongs
  in an ADR;
- observed implementation, adoption, enforcement, or runtime posture belongs
  in configured current-state evidence;
- a disagreement between intended authority and observed state belongs in the
  configured drift record, or in configured current-state evidence when the
  drift route is `None`;
- an unresolved question stays in its GitHub planning issue.

Do not let a glossary edit approve an architecture decision. Do not let an ADR
claim that an unverified implementation already exists. Do not turn domain
documents into an implementation specification or ticket backlog.

## Update the owner

Reuse an existing entry when it owns the concept. Create a routed artifact
only when its configured owner does not yet exist. Use the matching file in
`assets/` as a starting structure only for a file-owned route, adapting
headings without changing the repository's established format. For a
process-owned route, use its configured interface and retain its durable
receipt, URL, or record ID instead of creating a substitute local file.

Keep definitions concrete, identify the owner and boundary, and link the
planning issue or evidence that resolved the item. Mark a new ADR `Proposed`
until the configured architecture authority accepts it; record approval
through that configured process rather than inferring it from an edit.

When a decision changes, preserve history through supersession or the
repository's existing mechanism. Never silently rewrite an accepted decision.

## Verify and return

Check that every changed item has one authoritative owner, cross-context links
resolve, ADR status matches its approval state, and evidence is described as
current state rather than desired intent. Report the exact paths changed and
any durable receipt, URL, or record ID. Link the updated authorities from the
planning map when one exists; for a later correction, link them from the
calling issue or work record instead.

Stop before writing an implementation specification, creating implementation
tickets, or changing code.
