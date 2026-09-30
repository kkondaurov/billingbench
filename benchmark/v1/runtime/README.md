# Runtime prerequisites

The reference runtime is the existing isolated service container used by these
runs. It provides Elixir 1.20.2, Erlang/OTP 29, PostgreSQL 17, Python, browser
dependencies and the agent CLI. The host-side adapter mounts only candidate
source and supplies ephemeral database state, an application clock and actor
authentication. It runs as a non-root user with 2 CPUs and 4 GiB RAM.

Reference local image identities:

- Original Codex CLI 0.155.1 candidate: `sha256:d916afedec259eb95d980bdf210d77e0d5ea622fac46a9e189081d9ddd068cdc`
- Sol 6.1 Codex CLI 0.159.0 candidate: `sha256:11b4572f54f50e9baf6e1e52e76fe39fda15bca923852e1949e7fd653153f3dc`
- Evaluator: `sha256:2f0a74b32534554767be2c69ad3d9a08f54ba6009d4e33635ffc57cc542fcd9e`
- Docker context: `colima-sweatbench-qemu`
- Container control API: `/opt/v7-evolution/container.py`

These are local immutable image IDs, not public registry pull references. The
images are not distributed in this release. The adapter and commands work with
the reference installation; on another machine the matching runtime must first
be provisioned. Authentication material is never published or included in source
archives. `run_candidate.py` copies the operator's CLI authentication only into
the isolated runtime and archives session evidence separately from it.

The Sol 6.1 image changes only the Codex CLI installation. Its initial 0.155.1
setup attempts rejected that model before implementation; the three measured
trajectories start from the scaffold with 0.159.0. Pass the corresponding local
image explicitly using `run.py candidate --image <image-id>`. The CLI version
difference is part of the reported methodology, not an isolated model-only
comparison. The evaluator image and public requirement/scaffold bytes did not
change when updating the candidate CLI.

For an independently provisioned HTTP application, `evaluate_v05.py` also accepts
`--base-url` and `--secret`. This is useful for individual API checks, but is not
equivalent to full runtime-backed evaluation: restart and upgrade checks need
the runtime control API.
