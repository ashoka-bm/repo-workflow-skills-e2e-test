# GitHub Setup Snapshot

Create the snapshot from observed GitHub state, not the desired contract.

```json
{
  "project_identity": {
    "id": "PVT_example",
    "url": "https://github.com/orgs/example/projects/1"
  },
  "labels": ["planning:map", "workflow:plan", "workflow:needs-human-review"],
  "project_fields": {
    "Work stream": {"type": "text"},
    "Queue sequence": {"type": "number"},
    "Lifecycle": {
      "type": "single_select",
      "options": ["Planned", "Building"]
    }
  },
  "repository": {
    "native_issue_hierarchy_enabled": true,
    "native_issue_dependencies_enabled": true,
    "base_branch_ruleset_targets_configured_base": true,
    "pull_requests_required": true,
    "required_status_checks": ["full-gate"],
    "full_gate_commands": ["python3 -m unittest discover -s tests"]
  }
}
```

Include every observed contract setting. The validator reports omissions and
differences. Extra labels, fields, and unrelated repository settings are
allowed and must not be deleted automatically. The controlled `Lifecycle`
options are exact; do not add readiness or blocked states.
