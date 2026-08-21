# repo-workflow-skills-e2e-test
End-to-end sandbox for testing the repository workflow

## Service quick start

The service uses only the Python 3 standard library:

```bash
PYTHONPATH=src python3 -m team_launch_planner
```

It listens on `127.0.0.1:8000`. Check it with
`curl http://127.0.0.1:8000/health`; a healthy response reports service version
`1` and `database: available`. Stop it with Ctrl-C. The default SQLite file is
`team-launch.db`.

Startup settings are read before the listener or database is opened:

| Setting | Default | Rule |
| --- | --- | --- |
| `TLP_HOST` | `127.0.0.1` | Must not be empty |
| `TLP_PORT` | `8000` | Integer from 1 through 65535 |
| `TLP_DATABASE_PATH` | `team-launch.db` | Must not be empty; `:memory:` is supported |

For example: `TLP_PORT=9000 PYTHONPATH=src python3 -m team_launch_planner`.
Invalid values stop startup without binding a port or creating the database.
