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
