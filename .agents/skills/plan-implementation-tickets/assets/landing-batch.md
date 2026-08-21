# <Outcome-first landing-batch title>

## Problem

<What current user or repository outcome is unsafe or incomplete, who or what is affected, and why it matters.>

## Desired outcome

<The coherent result this batch can land.>

## Batch boundary

- Included bounded work: <Confirm that one owner can complete and recover this coherent work reliably.>
- Flow evidence: <Why this size preserves a useful ready frontier without creating per-slice landing overhead.>
- Split reason: <Required when the plan has more than one batch; name the documented safety, flow, recovery, or review reason for the boundary.>

## Planning relationships

- Parent plan: <issue link>
- Work stream: <stream name or identifier>
- Child tickets: <sub-issue links>
- Lands after: <native batch dependency plus why that batch must merge first, or none>
- Starts after: <direct `lands_after` batches that must merge before this batch can be claimed or built, plus why, or none>

## Local execution

- Starting slices: <after all `starts_after` gates resolve, child tickets with no prerequisite or with a cross-batch prerequisite checkpoint that provides the stacked base>
- Unlock rule: <Each reviewed `slice-checkpoint` makes its direct local dependants executable.>

## Acceptance and proof

| Acceptance criterion | Proving method |
| --- | --- |
| <True-or-false integrated result> | <Combined test, build, documentation, or review evidence> |

## Out of scope

- <Nearby result this batch deliberately excludes>

## Parallel-work contract

- Conflict surfaces: <shared files, contracts, schemas, migrations, or resources>
- Safe to run in parallel with: <batch links and why, or none>
- Must not overlap: <links to other landing batches in this Project and why, or none>

## Documentation and operations

- Documentation: <combined impact or none>
- Operational impact: <rollout, migration, recovery, or none>
