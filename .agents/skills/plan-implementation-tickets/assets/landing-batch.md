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

## Local execution

- Starting slices: <child tickets with no `local_after` prerequisite>
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
- Must not overlap: <batch links and why, or none>

## Documentation and operations

- Documentation: <combined impact or none>
- Operational impact: <rollout, migration, recovery, or none>
