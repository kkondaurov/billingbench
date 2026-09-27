# Runtime prerequisites

The reference runtime is the existing isolated service container used by these
runs. It provides Elixir 1.20.2, Erlang/OTP 29, PostgreSQL 17, Python, browser
dependencies and the agent CLI. The host-side adapter mounts only candidate
source and supplies ephemeral database state, an application clock and actor
authentication. It runs as a non-root user with 2 CPUs and 4 GiB RAM.

Reference local image identities:

- Candidate: `sha256:d916afedec259eb95d980bdf210d77e0d5ea622fac46a9e189081d9ddd068cdc`
- Evaluator: `sha256:2f0a74b32534554767be2c69ad3d9a08f54ba6009d4e33635ffc57cc542fcd9e`
- Docker context: `colima-sweatbench-qemu`
- Container control API: `/opt/v7-evolution/container.py`

These are local immutable image IDs, not public registry pull references. The
images are not distributed in this release. The adapter and commands work with
the reference installation; on another machine the matching runtime must first
be provisioned. Authentication material is never published or included in source
archives. `run_candidate.py` copies the operator's CLI authentication only into
the isolated runtime and archives session evidence separately from it.

For an independently provisioned HTTP application, `evaluate_v05.py` also accepts
`--base-url` and `--secret`. This is useful for individual API checks, but is not
equivalent to full runtime-backed evaluation: restart and upgrade checks need
the runtime control API.
