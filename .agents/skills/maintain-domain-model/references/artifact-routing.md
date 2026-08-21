# Domain Artifact Routing

Use the configured route in `docs/agents/domain.md`; the example filenames in
this skill are structures, not required locations. The architecture-authority
route governs who or what may accept an ADR; the architecture-decisions route
governs where the decision record lives.

| Resolved information | Authoritative artifact | Does not establish |
| --- | --- | --- |
| Term, invariant, capability meaning, or ownership inside one context | Owning context document | Architecture approval or current implementation |
| Context boundary, owner, or relationship between contexts | Context map | That every relationship is implemented |
| Durable, surprising, cross-boundary, or costly-to-reverse choice | ADR | Current adoption without evidence |
| Observed implementation, adoption, enforcement, or runtime posture | Current-state evidence | Intended architecture |
| Conflict between intended authority and observed state | Drift or disagreement record, or current-state evidence when the drift route is `None` | A replacement decision or repair status |
| Unresolved product, architecture, ownership, or operational question | GitHub planning issue | A resolved term or decision |

When the drift route is `None`, record the factual mismatch in configured
current-state evidence. If both routes are `None`, stop and use
`configure-repository-workflow` to establish one durable evidence owner.

An implementation specification describes an approved outcome after planning.
Implementation tickets describe delivery after the specification is approved.
Neither belongs in a context document, context map, ADR, or current-state map.

For a single-context repository, one context document may also be the
vocabulary entry point. For a multi-context repository, the entry point should
route readers to the owning context documents without copying their full
definitions.
