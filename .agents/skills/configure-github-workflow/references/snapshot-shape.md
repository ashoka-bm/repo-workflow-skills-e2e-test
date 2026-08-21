# GitHub Setup Snapshot

Create the snapshot from observed GitHub state, not the desired contract.

```json
{
  "repository_identity": {"name_with_owner": "example/repository"},
  "project_identity": {
    "id": "PVT_example",
    "url": "https://github.com/orgs/example/projects/1"
  },
  "labels": ["planning:map", "PLAN", "workflow:needs-human-review", "workflow:unlocks-work", "workflow:landing-validated", "workflow:queued", "workflow:dequeued"],
  "project_fields": {
    "Work stream": {"type": "text"},
    "Lifecycle": {
      "type": "single_select",
      "options": ["Planned", "Building", "Locally complete", "In PR", "Landed"]
    }
  },
  "repository": {
    "native_issue_hierarchy_enabled": true,
    "native_issue_dependencies_enabled": true,
    "base_branch_ruleset_targets_configured_base": true,
    "pull_requests_required": true,
    "github_merge_queue_disabled": true,
    "mergify_app_installed": true,
    "mergify_serial_mode": true,
    "mergify_batch_size_one": true,
    "mergify_queue_labels_configured": true,
    "lifecycle_sync_enabled": true,
    "lifecycle_project_token_configured": true,
    "required_status_checks": ["landing-evidence", "full-gate"],
    "full_gate_commands": ["python3 -m unittest discover -s tests"]
  }
}
```

Include every observed contract setting. The validator reports omissions and
differences. Extra labels, fields, and unrelated repository settings are
allowed and must not be deleted automatically. The three deprecated controlled
labels `workflow:plan`, `workflow:batch`, and `workflow:ticket` are the sole
exception: migrate them to `PLAN`, `BATCH`, and `TICKET` before final
validation. The controlled `Lifecycle`
options are exact; do not add readiness or blocked states. Lifecycle values
belong only to landing-batch Project items; plans and child tickets leave the
field empty.
