# Coordination Records

Post delivery records in the landing pull request. Keep field names and event
values exact. Use ISO-8601 UTC timestamps and GitHub issue or pull request
URLs. GitHub assignment—not a comment record—is the only ownership record.

Landing records — `slice-delivery`, `slice-review`, `slice-checkpoint`,
`slice-checkpoint-invalidated`, `local-review`, `local-complete`,
`local-completion-invalidated`, `local-completion-missing`, `queue-classified`,
`rework-request`, and `candidate-landed` events belong in the landing pull
request's comments. Optional handoff or recovery comments may preserve useful
context, but they never create, transfer, or release ownership.

## Slice checkpoint

When a delegated worker finishes a slice, that worker first records the exact
delivery in the landing pull request. The GitHub comment author authenticates
the record's account; `worker` and `session` identify the delivering agent.

```yaml
event: slice-delivery
ticket: {child ticket URL}
starting_commit: {commit SHA}
slice_commit: {commit SHA}
worker: {delegated slice worker identity}
session: {delegated slice worker session}
```

After focused verification, another agent records review of the exact slice diff:

```yaml
event: slice-review
ticket: {child ticket URL}
starting_commit: {commit SHA}
slice_commit: {commit SHA}
reviewer_worker: {review agent identity}
reviewer_session: {review run identifier}
verdict: passed
```

The batch owner then records the completed slice. The comment author and
timestamp provide the owner and completion time.

```yaml
event: slice-checkpoint
batch: {landing-batch issue URL}
ticket: {child ticket URL}
starting_commit: {commit SHA}
slice_commit: {commit SHA}
focused_gates_passed: true
worker: {delegated slice worker identity}
session: {delegated slice worker session}
delivery: {slice-delivery comment URL; required for delegated work}
review: {slice-review comment URL}
prerequisite_checkpoints: {for cross-batch edges: #ticket=checkpoint comment URL, comma separated; otherwise omit}
```

A current checkpoint satisfies `local_after` when its GitHub author is the
current batch assignee, its review identifies a worker/session distinct from
the slice worker, and its slice commit strictly descends from its recorded
starting commit in the batch branch history;
an empty diff is never a slice. For a dependent slice, that starting commit must
also contain every current local prerequisite commit. The batch owner authors
the checkpoint and remains accountable; `worker` and `session` identify the
delegated slice worker. Delegated work also
binds the worker-authored `slice-delivery`; the review must use a different
worker/session, even when both records share one GitHub account. A cross-batch
checkpoint must bind every upstream prerequisite through
`prerequisite_checkpoints`. When a later commit changes the slice's behavior or
verification, the owner or an authorized workflow maintainer posts:

```yaml
event: slice-checkpoint-invalidated
checkpoint: {retired slice-checkpoint comment URL}
reason: {behavior or verification that changed}
```

Invalidation also makes checkpoints for local dependents ineligible until the
prerequisite chain is proven again. Child tickets remain open until the batch
merges. The GitHub snapshot exposes `local_frontier`, `locally_blocked`, and the
current `slice_checkpoints`; agents use that derived view instead of inferring
readiness from ticket closure.

## Local completion

Before queueing, another agent posts its review result for
the exact candidate:

```yaml
event: local-review
base_commit: {reviewed base commit SHA}
candidate_commit: {commit SHA}
verdict: passed
reviewed_by: {GitHub actor who authored this comment}
reviewer_worker: {review agent identity}
reviewer_session: {review run identifier}
```

The batch owner then binds completion to that authenticated review. The review
worker must differ from the completion worker; the session identifies each run.
`base_commit` must still be the pull request's base.
The GitHub comment author and timestamp are the owner and completion time; do
not duplicate them as editable fields. Every child slice must also have a
current checkpoint before this record is eligible.

```yaml
event: local-complete
candidate_commit: {commit SHA}
local_gates_passed: true
worker: {implementation worker identity}
session: {implementation session}
review: {local-review comment URL}
```

A later commit makes this record stale. An authorized workflow maintainer retires it before
returning the batch to `Building`; a later rollback to the old SHA does not
restore retired evidence.

```yaml
event: local-completion-invalidated
completion: {retired local-complete comment URL}
reason: {why the evidence no longer matches the candidate}
maintainer: {GitHub actor}
recorded_at: {UTC timestamp}
```

If Project state claims `Locally complete` but no current record exists, the
workflow maintainer posts the equivalent missing-evidence barrier.

```yaml
event: local-completion-missing
reason: {why current completion evidence is absent}
maintainer: {GitHub actor}
recorded_at: {UTC timestamp}
```

## Queue classification

```yaml
event: queue-classified
batch: {GitHub issue URL}
pull_request: {pull request URL}
candidate_commit: {commit SHA}
priority: {high|normal}
reason: {open starts_after dependent URL or no open start dependent}
classified_by: {GitHub actor}
classified_at: {UTC timestamp}
```

This record is optional human-readable evidence. The queue-entry command's
label change and `@mergifyio queue` comment show what was submitted to Mergify.

## Candidate returned to rework

```yaml
event: rework-request
pull_request: {pull request URL}
candidate_commit: {commit SHA}
reason: {why approved scope, acceptance criteria, or local completion changed}
requested_by: {GitHub actor}
requested_at: {UTC timestamp}
```

## Candidate merged

```yaml
event: candidate-landed
pull_request: {pull request URL}
merge_commit: {commit SHA}
recorded_by: {GitHub actor}
landed_at: {UTC timestamp}
```
