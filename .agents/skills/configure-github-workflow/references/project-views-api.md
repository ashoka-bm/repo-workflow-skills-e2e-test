# Optional GitHub Project Views Through the API

Use this reference only after a human explicitly asks to create or repair a
workflow Project Board or Roadmap. These views are optional presentation. They
are not part of `.workflow/github-setup-contract.json`, normal setup, repair,
validation, planning, or ticket publication.

## Required boundary

- Resolve the configured Project from `AGENTS.md`; never guess an account or
  choose a second Project.
- Inspect existing view names, layouts, filters, and fields before writing.
- Present the exact proposed writes and obtain approval.
- Use authenticated REST or GraphQL calls only. Do not invoke browser
  automation, computer use, or coordinate-based UI actions.
- Reuse an exact match. Stop on a same-name conflict so retries cannot create
  duplicate views.
- Never delete a view without separate approval for the exact view ID and name.
- Re-read and report observed API state after every write.

## Supported API surface

GitHub's live GraphQL schema exposes `createProjectV2View`,
`updateProjectV2View`, and `deleteProjectV2View`. Supported layouts are
`TABLE_LAYOUT`, `BOARD_LAYOUT`, and `ROADMAP_LAYOUT`. At the time this behavior
was recorded, `ProjectV2ViewConfigurationInput` exposed only
`visibleFieldIds`.

The REST Project views API, using version `2026-03-10`, accepts `name`,
`layout`, `filter`, `visible_fields`, `sort_by`, `group_by`, and
`vertical_group_by`. `vertical_group_by` selects a Board's column field, such
as `Lifecycle`.

Official references:

- <https://docs.github.com/en/rest/projects/views>
- <https://docs.github.com/en/graphql/reference/projects>
- <https://docs.github.com/en/graphql/overview/changelog?apiVersion=2022-11-28>
- <https://docs.github.com/en/issues/planning-and-tracking-with-projects/managing-your-project/managing-project-templates-in-your-organization>

Because this API is evolving, inspect the live schema or current official
documentation before changing these calls. Do not fall back to UI automation
when the API differs; stop and report the unsupported operation.

## Owner-specific endpoints

For a user-owned Project:

```text
/users/<user-id>/projectsV2/<project-number>/views
```

For an organization-owned Project:

```text
/orgs/<org>/projectsV2/<project-number>/views
```

`user-id` is GitHub's unique user identifier, not the login. Resolve it through
the API instead of substituting the account name. The organization endpoint
documents GitHub App and fine-grained-token support with Project write
permission. The user endpoint does not support those token types, although an
existing authenticated `gh` credential succeeded in the recorded test. Never
inspect or record credential values.

## Standard Delivery Board

Create this only when requested:

- name: `Delivery Board`;
- layout: `board`;
- filter: `label:BATCH`; and
- vertical grouping: the configured `Lifecycle` field.

Before creating it, resolve the Project number and the Lifecycle field's REST
database ID through the API. REST accepts `vertical_group_by` as an array of
integer field IDs and supports one field. A generic request has this shape:

```bash
gh api --method POST \
  -H 'Accept: application/vnd.github+json' \
  -H 'X-GitHub-Api-Version: 2026-03-10' \
  /users/<user-id>/projectsV2/<project-number>/views \
  -f name='Delivery Board' \
  -f layout='board' \
  -f filter='label:BATCH' \
  -F 'vertical_group_by[]=<Lifecycle database ID>'
```

Use the organization endpoint for organization-owned Projects. Confirm through
a fresh API read that the layout is Board, the filter is `label:BATCH`, and the
vertical grouping field is `Lifecycle`.

## Standard Delivery Roadmap

Create this only when requested:

- name: `Delivery Roadmap`;
- layout: `roadmap`;
- filter: `label:BATCH`;
- Project date fields: `Start date` and `Target date`; and
- dates on BATCH items only, using a human-approved forecast.

Creating the view is API-supported:

```bash
gh api --method POST \
  -H 'Accept: application/vnd.github+json' \
  -H 'X-GitHub-Api-Version: 2026-03-10' \
  /users/<user-id>/projectsV2/<project-number>/views \
  -f name='Delivery Roadmap' \
  -f layout='roadmap' \
  -f filter='label:BATCH'
```

The API can also create the two date fields and set their values on Project
items with `updateProjectV2ItemFieldValue`. Dates are planning commitments, so
show the proposed issue-to-date mapping and obtain approval before writing.
Never invent production dates from dependency order unless the human explicitly
asks for an illustrative forecast.

## Roadmap date-binding limitation

The public REST and GraphQL inputs currently do not expose a way to bind a
Roadmap to its start and target date fields. `visible_fields` is not valid for
Roadmap views. A tested GraphQL attempt to include date fields returned:

```text
Roadmap views do not support visible fields.
```

An API-created Roadmap can therefore exist with the correct name and filter
while still omitting timeline bars. Do not call that fully configured and do
not rely on GitHub to choose the fields automatically.

For a fully API-driven repeat installation, the recommended route is an
approved preconfigured Project template or copy flow, because copied view
configuration preserves the Roadmap binding. For an ad hoc Project, create
only the API-supported portion the human approved and report selecting `Start
date` and `Target date` as a manual human step. This workflow never performs
that step through computer use.

## Verification checklist

- The original table and unrelated views remain unchanged.
- Exactly one requested view exists; retries did not create duplicates.
- Delivery Board: Board layout, `label:BATCH` filter, Lifecycle vertical group.
- Delivery Roadmap: Roadmap layout and `label:BATCH` filter.
- `Start date` and `Target date` values, if approved, exist only on intended
  BATCH items and match the approved mapping.
- A copied/template Roadmap exposes the two bound date fields. An ad hoc
  API-created Roadmap is reported as incomplete until a human binds them.
- No Lifecycle values changed as a side effect of view setup.
