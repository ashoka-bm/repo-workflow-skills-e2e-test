---
name: configure-repository-workflow
description: Configure this repository-owned workflow after installation or when repository identity, commands, coordination, tracker, or domain-authority routes change. Use before planning new work in a fresh repository so every bundled skill can find the repository's vocabulary, context documents, ADRs, current-state evidence, and drift record without depending on global skills.
---

# Configure Repository Workflow

Make the installed workflow usable without inventing a second authority or
assuming conventional root paths.

## Inspect before proposing changes

Read `AGENTS.md` and `docs/agents/domain.md`. Inspect only the repository files
needed to identify its existing architecture, domain, commands, tracker, and
coordination practices. Existing authoritative documents win over template
defaults.

Stop and ask for direction when two existing sources claim the same authority
or the repository owner cannot be determined. Do not overwrite or relocate an
existing authority merely to match a conventional layout.

## Configure the repository

Present the proposed values in plain language before editing. Resolve:

1. the repository identity, purpose, users, governing authority, evidence,
   commands, base branch, intended workflow Project, required status checks,
   durable GitHub approval channel, and coordination fields in `AGENTS.md`;
2. whether the domain layout is `single-context` or `multi-context`;
3. the vocabulary entry point and context-document path, explicit paths, or
   pattern;
4. the architecture authority or approval process and the architecture-decision
   path or process;
5. the current-state evidence and drift-record routes. The drift route may be
   `None` only when current-state evidence is the durable fallback. Do not
   configure both routes as `None`.
6. every remaining placeholder in `AGENTS.md`, including the sample vocabulary
   row and repository-root table; replace useful examples and remove unused
   optional rows rather than leaving angle-bracket text.

When the GitHub Project or required check names do not exist yet, replace their
placeholders with the literal `Pending GitHub setup`; do not invent identities.
`configure-github-workflow` will write the values it observes from GitHub.

For a single context, the vocabulary entry point and context document may be
the same file. For multiple contexts, use one context map as the entry point
and one context document per bounded context. If a pattern could also match the
entry-point map, state an explicit exclusion or use explicit context paths.

After the human agrees, edit only the customizable setup files:
`AGENTS.md` and `docs/agents/domain.md`. Preserve their headings and consumer
rules so installer verification remains deterministic. Do not create domain
documents, ADRs, maps, or implementation files during configuration.

## Verify and stop

Confirm that neither customizable file contains unresolved angle-bracket
placeholders, every configured path or process is unambiguous, and the layout
is exactly `single-context` or `multi-context`. Run the installed verifier:

```bash
python3 .workflow/scripts/verify_setup.py --pre-github
```

Report the configured routes and any deliberately absent routes. Route next to
`configure-github-workflow`; stop before planning or implementation.
