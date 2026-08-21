# Controller Runbook

The installed controller is an audit pilot. It reads GitHub, computes the FIFO
transition the workflow would make, and writes that proposal only to the GitHub
Actions job summary. This build has no mutation executor, so changing the
configuration text cannot make it edit a Project, change a pull request, or
merge code.

## Connect audit mode

1. Keep `mode` set to `audit` and `enforcement_enabled` set to `false` in
   [`.workflow/controller-config.json`](../../.workflow/controller-config.json).
2. Set the repository name, base branch, Project node ID, Project field names,
   permitted merge method, exact required status-check names, and the GitHub
   logins authorized to post coordinator receipts. Keep historical human or App
   coordinator logins listed while their receipts still establish Queue history.
3. Create a private GitHub App with the least privileges needed to read the
   configured Project, repository metadata, issues, pull requests, checks, and
   Actions. Install it only on the pilot repository.
4. Store its client ID as the `WORKFLOW_APP_CLIENT_ID` repository variable and
   its complete private key as the `WORKFLOW_APP_PRIVATE_KEY` Actions secret.
5. Run **Repository workflow controller (audit)** manually. Confirm its summary
   says either that configuration is pending or lists proposed mutations.

The privileged workflow checks out the default branch, never the pull-request
branch. It uses a short-lived App installation token only while reading state.
Landing records are read from landing pull-request comments. Current Lifecycle
and Queue sequence values are read from the landing-batch issue's Project item.
The snapshot also reads each child ticket's `Local after` contract and validates
claim-bound slice reviews, checkpoints, and invalidations against pull-request
commits. Its `local_frontier`, `locally_blocked`, and `slice_checkpoints` fields
are the derived local-work view; issue closure is not a readiness signal.

## Review an audit proposal

Compare each proposed mutation with
[`GITHUB-WORKFLOW.md`](../../GITHUB-WORKFLOW.md). A proposal is evidence, not an
applied transition. Investigate any duplicate Queue sequence, multiple active
candidate, missing Project item, stale commit receipt, or unavailable GitHub
state. Do not repair ambiguous state by guessing.

The workflow also reconciles every 15 minutes. Repeated proposals are expected
until a human performs the transition because audit mode does not mutate the
authoritative state.

## Disable or recover

Disable the Actions workflow or remove the App credentials to stop the pilot.
Branch rules and auto-merge settings are unchanged. The named human coordinator
can continue the same serialized protocol using
[`COORDINATION.md`](../../COORDINATION.md).

Enforcement requires a separately reviewed mutation executor, idempotency proof,
least-privilege write permissions, branch protection, required CI, and explicit
human approval. This audit build intentionally rejects enforcement
configuration.
