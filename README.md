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

## Response metadata

Every JSON response includes `X-API-Version: 1` and an
`X-Correlation-ID`. If a client sends `X-Correlation-ID`, the service returns
that same value; otherwise it generates a UUID for the request. Correlation
identifiers are diagnostic metadata and must not contain credentials.

## Error contract

Failures use one JSON shape:

```json
{"error":{"correlation_id":"request-id","message":"Route not found","type":"missing"}}
```

The stable categories are `validation` (400), `missing` (404), `conflict`
(409), `authorization` (403), and `internal` (500). Unexpected failures return
the generic message `Internal server error`; stack traces and private diagnostic
details are never returned to clients. The server logs the private diagnostic
with the same correlation identifier for operators.

## Administrative shell

Discover the administrative boundary with:

```bash
PYTHONPATH=src python3 -m team_launch_planner.admin --help
```

The shell reserves `migrate`, `tokens`, `export`, and `backup` for later
batches. Each supports `--help`; invoking an unimplemented or unknown command
exits with code 2 and performs no mutation. Successful commands will use exit
code 0, invalid input will use 2, and runtime failures will use 1.
