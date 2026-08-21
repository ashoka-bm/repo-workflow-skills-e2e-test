# Coordination Records

Post these records in the configured GitHub channel. Keep the field names and
event values exact. Use ISO-8601 UTC timestamps and GitHub issue or
pull-request URLs.

Landing records — `slice-review`, `slice-checkpoint`,
`slice-checkpoint-invalidated`, `local-review`, `local-complete`,
`local-completion-invalidated`, `local-completion-missing`, `queue-request`,
`queue-receipt`, `promote-request`, `rework-request`, and all `candidate-*`
events — belong in the landing pull request's comments. Claim, heartbeat,
release, handoff, and recovery records belong in the configured coordination
channel for their issue or landing batch.

## Slice checkpoint

After focused proof, another agent records review of the exact slice diff in the
landing pull request:

```yaml
event: slice-review
ticket: {child ticket URL}
starting_commit: {commit SHA}
slice_commit: {commit SHA}
verdict: passed
```

The batch owner then records the locally complete slice. The comment author and
timestamp provide the owner and completion time.

```yaml
event: slice-checkpoint
batch: {landing-batch issue URL}
ticket: {child ticket URL}
starting_commit: {commit SHA}
slice_commit: {commit SHA}
focused_gates_passed: true
claim_receipt: {current accepted claim-receipt comment URL}
worker: {worker from current claim-request}
session: {session from current claim-request}
review: {slice-review comment URL}
```

A current checkpoint satisfies `local_after` when it belongs to the current
batch claim, its review was posted by another GitHub actor, and its slice commit
strictly descends from its recorded starting commit in the batch branch history;
an empty diff is never a slice. For a dependent slice, that starting commit must
also contain every current local prerequisite commit. When a later commit
changes the slice's behavior or proof, the owner or coordinator posts:

```yaml
event: slice-checkpoint-invalidated
checkpoint: {retired slice-checkpoint comment URL}
reason: {behavior or proof that changed}
```

Invalidation also makes checkpoints for local dependants ineligible until the
prerequisite chain is proven again. Child tickets remain open until the batch
lands. The GitHub snapshot exposes `local_frontier`, `locally_blocked`, and the
current `slice_checkpoints`; agents use that derived view instead of inferring
readiness from ticket closure.

## Claim request

```yaml
event: claim-request
item: {GitHub issue URL}
item_kind: {planning-issue|landing-batch}
actor: {GitHub actor}
worker: {human or agent identity}
session: {run identifier}
branch: {batch branch or none}
requested_at: {UTC timestamp}
```

## Claim receipt

```yaml
event: claim-receipt
request: {claim-request comment URL}
accepted: {true|false}
coordinator: {GitHub actor}
reason: {acceptance or rejection reason}
recorded_at: {UTC timestamp}
```

## Heartbeat

```yaml
event: heartbeat
item: {GitHub issue URL}
session: {run identifier}
last_proven_commit: {commit SHA or none}
recorded_at: {UTC timestamp}
```

## Release

```yaml
event: release
item: {GitHub issue URL}
session: {run identifier}
reason: {why work stopped}
recoverable_branch: {branch or none}
last_proven_commit: {commit SHA or none}
recorded_at: {UTC timestamp}
```

## Handoff

```yaml
event: handoff
item: {GitHub issue URL}
from_worker: {identity and session}
to_worker: {identity and session}
branch: {branch or none}
last_proven_commit: {commit SHA or none}
unresolved: {remaining findings or none}
next_action: {first bounded action}
recorded_at: {UTC timestamp}
```

## Recovery notice

```yaml
event: recovery-notice
item: {GitHub issue URL}
stale_session: {run identifier}
reason: {stale evidence}
response_due_at: {UTC timestamp after the configured grace duration}
coordinator: {GitHub actor}
```

## Recovery result

```yaml
event: recovery-result
item: {GitHub issue URL}
stale_session: {run identifier}
outcome: {restored|released}
preserved_branch: {branch or none}
last_proven_commit: {commit SHA or none}
coordinator: {GitHub actor}
completed_at: {UTC timestamp}
```

## Local completion

Before requesting a queue position, another agent posts its review result for
the exact candidate:

```yaml
event: local-review
candidate_commit: {commit SHA}
verdict: passed
reviewed_by: {GitHub actor who authored this comment}
```

The batch owner then binds completion to the current accepted claim and that
authenticated review. The GitHub comment author and timestamp are the owner
and completion time; do not duplicate them as editable fields.

```yaml
event: local-complete
candidate_commit: {commit SHA}
local_gates_passed: true
claim_receipt: {current accepted claim-receipt comment URL}
worker: {worker from current claim-request}
session: {session from current claim-request}
review: {local-review comment URL}
```

A later commit makes this record stale. The coordinator retires it before
returning the batch to `Building`; a later rollback to the old SHA does not
restore retired evidence.

```yaml
event: local-completion-invalidated
completion: {retired local-complete comment URL}
reason: {why the evidence no longer matches the candidate}
retired_queue_sequence: {positive integer or none}
coordinator: {GitHub actor}
recorded_at: {UTC timestamp}
```

If Project state claims `Locally complete` but no current record exists, the
coordinator posts the equivalent missing-evidence barrier. Either barrier
retires older queue requests and receipts. A positive partial Queue sequence is
recorded before it is cleared so the number is never reused.

```yaml
event: local-completion-missing
reason: {why current completion evidence is absent}
retired_queue_sequence: {positive integer or none}
coordinator: {GitHub actor}
recorded_at: {UTC timestamp}
```

## Landing queue request

```yaml
event: queue-request
batch: {GitHub issue URL}
pull_request: {draft pull-request URL}
candidate_commit: {commit SHA}
requested_by: {GitHub actor}
requested_at: {UTC timestamp}
```

## Landing queue receipt

```yaml
event: queue-receipt
request: {queue-request comment URL}
accepted: {true|false}
queue_sequence: {positive integer or none}
reason: {acceptance or rejection reason}
coordinator: {GitHub actor}
recorded_at: {UTC timestamp}
```

`accepted: true` requires a positive `queue_sequence`. `accepted: false`
requires `queue_sequence: none`. The receipt and the landing-batch issue's
Project field must contain the same accepted value.

## Candidate activation

```yaml
event: candidate-activation
pull_request: {pull-request URL}
queue_request: {queue-request comment URL}
candidate_commit: {post-rebase commit SHA}
coordinator: {GitHub actor}
activated_at: {UTC timestamp}
```

## Promotion request

The batch owner posts this only after verifying the exact candidate and base
commits. The controller rejects a stale request rather than inferring that its
evidence still applies.

```yaml
event: promote-request
pull_request: {draft pull-request URL}
candidate_commit: {commit SHA}
base_commit: {commit SHA}
local_gates_passed: true
another_agent_review_passed: true
requested_by: {GitHub actor}
requested_at: {UTC timestamp}
```

## Candidate blocked

```yaml
event: candidate-blocked
pull_request: {pull-request URL}
reason: {blocking condition}
queue_sequence_preserved: true
coordinator: {GitHub actor}
recorded_at: {UTC timestamp}
```

## Candidate unblocked

```yaml
event: candidate-unblocked
pull_request: {pull-request URL}
resolved_blocker: {resolved blocking condition}
queue_sequence_preserved: true
coordinator: {GitHub actor}
recorded_at: {UTC timestamp}
```

## Candidate attention or rejected manual promotion

```yaml
event: candidate-attention
pull_request: {pull-request URL}
queue_sequence: {positive integer}
reason: {invalid transition or condition requiring owner attention}
coordinator: {GitHub actor}
recorded_at: {UTC timestamp}
```

## Candidate returned to draft

```yaml
event: candidate-returned-to-draft
pull_request: {pull-request URL}
queue_sequence: {positive integer}
queue_sequence_preserved: true
coordinator: {GitHub actor}
recorded_at: {UTC timestamp}
```

## Candidate returned to substantial rework

The batch owner requests substantial rework against the current pull-request
head before the coordinator applies it:

```yaml
event: rework-request
pull_request: {pull-request URL}
candidate_commit: {commit SHA}
reason: {why approved scope, acceptance criteria, or local completion changed}
requested_by: {GitHub actor}
requested_at: {UTC timestamp}
```

The coordinator then posts the applied transition:

```yaml
event: candidate-rework
pull_request: {pull-request URL}
retired_queue_sequence: {positive integer}
reason: {why local completion is invalidated}
coordinator: {GitHub actor}
recorded_at: {UTC timestamp}
```

## Candidate landed

```yaml
event: candidate-landed
pull_request: {pull-request URL}
merge_commit: {commit SHA}
coordinator: {GitHub actor}
landed_at: {UTC timestamp}
```
