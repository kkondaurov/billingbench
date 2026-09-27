#!/usr/bin/env python3
"""Host-side runtime API. Mount candidate source only; keep evaluator code outside."""

import argparse
from dataclasses import asdict, dataclass
import json
import os
from pathlib import Path
import re
import subprocess
import tarfile
import tempfile
import time
import uuid


CONTEXTS = ("colima-sweatbench-qemu", "colima-sweatbench-v6-muse")
LABEL = "org.sweatbench.v7-evolution.runtime"
CONTROLLER = "/opt/v7-evolution/container.py"
DEFAULT_IMAGE = "sha256:2f0a74b32534554767be2c69ad3d9a08f54ba6009d4e33635ffc57cc542fcd9e"


class CommandError(RuntimeError):
    """A command failed; inspect output and runtime liveness before scoring it."""

    def __init__(self, operation, result):
        self.returncode = result.returncode
        self.stdout = result.stdout
        self.stderr = result.stderr
        super().__init__(f"Docker {operation} failed ({result.returncode}): {result.stderr or result.stdout}")


def docker(context, *args, timeout=360, check=True):
    if context not in CONTEXTS:
        raise ValueError(f"choose an explicit supported Docker context: {CONTEXTS}")
    result = subprocess.run(["docker", "--context", context, *map(str, args)],
                            text=True, capture_output=True, timeout=timeout)
    if check and result.returncode:
        raise CommandError(args[0], result)
    return result


def resource_id(value):
    if not isinstance(value, str) or not re.fullmatch(r"[0-9a-f]{64}", value):
        raise RuntimeError("Docker resource has no immutable full-length identity")
    return value


def _inspect_resource(context, kind, name, identifier=None):
    query = resource_id(identifier) if identifier is not None else name
    args = ("network", "inspect", query) if kind == "network" else ("inspect", query)
    result = docker(context, *args, timeout=30, check=False)
    if result.returncode:
        prefix = r"(?:Error response from daemon:\s*|Error:\s*)?"
        missing = (prefix + rf"No such (?:container|object):\s*{re.escape(query)}"
                   if kind == "container" else
                   prefix + rf"(?:network {re.escape(query)} not found|No such (?:network|object):\s*{re.escape(query)})")
        if (result.returncode == 1 and result.stdout.strip() in ("", "[]")
                and re.fullmatch(missing, result.stderr.strip(), re.IGNORECASE)):
            return None
        raise CommandError("ownership-inspect", result)
    records = json.loads(result.stdout)
    if not isinstance(records, list) or len(records) != 1 or not isinstance(records[0], dict):
        raise RuntimeError("Docker ownership inspection returned an invalid record")
    record = records[0]
    actual_id = resource_id(record.get("Id"))
    expected_name = "/" + name if kind == "container" else name
    if record.get("Name") != expected_name or (identifier is not None and actual_id != identifier):
        raise RuntimeError("Docker resource ownership/identity mismatch")
    return record


def owned_container(context, name, token, image_id, network, identifier=None):
    record = _inspect_resource(context, "container", name, identifier)
    if record is not None and (
            (record.get("Config", {}).get("Labels") or {}).get(LABEL) != token
            or record.get("Image") != image_id
            or set(record.get("NetworkSettings", {}).get("Networks", {})) != {network}):
        raise RuntimeError("container ownership/image/network mismatch; refusing lifecycle operation")
    return record


def remove_owned_container(context, name, token, image_id, network, identifier):
    # An absent original ID is clean. Never retry by name: it may now identify a replacement.
    resource_id(identifier)
    record = owned_container(context, name, token, image_id, network, identifier)
    if record is not None:
        docker(context, "rm", "-f", record["Id"], timeout=30)


def remove_owned_network(context, name, token, identifier):
    resource_id(identifier)
    record = _inspect_resource(context, "network", name, identifier)
    if record is not None:
        if (record.get("Labels") or {}).get(LABEL) != token or record.get("Containers") != {}:
            raise RuntimeError("network ownership mismatch or connected resources; refusing deletion")
        docker(context, "network", "rm", record["Id"], timeout=30)


@dataclass
class Runtime:
    context: str
    container: str
    network: str
    image_id: str
    workspace: str
    base_url: str
    token: str
    service_workspace: str = "/workspace"
    container_id: str = None
    network_id: str = None

    @classmethod
    def create(cls, workspace, image=DEFAULT_IMAGE,
               context="colima-sweatbench-qemu", provider_url=None, uid=1000, gid=1000,
               allocation=None, environment=None):
        workspace = Path(workspace).resolve()
        if not (workspace / "mix.exs").is_file():
            raise ValueError("workspace must be a candidate Mix project, not the benchmark checkout")
        if any((workspace / name).exists() for name in ("bench.py", "evaluation", ".codex")):
            raise ValueError("refusing to mount evaluator or host configuration with candidate source")
        if uid <= 0 or gid < 0:
            raise ValueError("candidate must use a non-root numeric UID")
        image_id = docker(context, "image", "inspect", image, "--format", "{{.Id}}").stdout.strip()
        token = uuid.uuid4().hex
        network = f"v7e-{token}"
        container = f"v7e-{token}-candidate"

        def record(kind, name, identifier=None):
            if allocation is not None:
                allocation({"kind": kind, "name": name, "context": context, "token": token,
                            "image_id": image_id, "network": network, "id": identifier})

        network_id = container_id = None
        try:
            record("network", network)
            created = docker(context, "network", "create", "--label", f"{LABEL}={token}", network)
            network_id = resource_id(created.stdout.strip())
            record("network", network, network_id)
            command = ["run", "-d", "--name", container, "--label", f"{LABEL}={token}",
                       "--init", "--read-only", "--cap-drop=ALL", "--security-opt=no-new-privileges",
                       "--user", f"{uid}:{gid}", "--pids-limit", "512", "--cpus", "2",
                       "--memory", "4g", "--network", network,
                       "--tmpfs", f"/tmp:rw,nosuid,nodev,size=512m,mode=1777",
                       "--tmpfs", f"/state:rw,nosuid,nodev,size=1536m,mode=700,uid={uid},gid={gid}",
                       "--shm-size", "256m", "-e", "HOME=/state/home", "-e", "V7_STATE_DIR=/state",
                       "-p", "127.0.0.1::4000",
                       "--mount", f"type=bind,src={workspace},dst=/workspace"]
            if provider_url is not None:
                command.extend(["-e", f"PROVIDER_URL={provider_url}"])
            for key, value in (environment or {}).items():
                command.extend(["-e", f"{key}={value}"])
            record("container", container)
            created = docker(context, *command, image_id)
            container_id = resource_id(created.stdout.strip())
            record("container", container, container_id)
            owned_container(context, container, token, image_id, network, container_id)
            ready = False
            for _ in range(120):
                probe = docker(context, "exec", container_id, "test", "-f", "/state/ready", check=False)
                if probe.returncode == 0:
                    ready = True
                    break
                running = docker(context, "inspect", container_id, "--format", "{{.State.Running}}")
                if running.stdout.strip() != "true":
                    raise RuntimeError(docker(context, "logs", container_id).stdout)
                time.sleep(0.25)
            if not ready:
                raise RuntimeError("runtime startup timed out")
            mapping = docker(context, "port", container_id, "4000/tcp").stdout.strip()
            runtime = cls(context, container, network, image_id, str(workspace), f"http://{mapping}", token,
                          container_id=container_id, network_id=network_id)
            runtime.run("python3", CONTROLLER, "prepare")
            return runtime
        except BaseException as exc:
            for identifier, cleanup, args in (
                    (container_id, remove_owned_container, (context, container, token, image_id, network)),
                    (network_id, remove_owned_network, (context, network, token))):
                if identifier is not None:
                    try:
                        cleanup(*args, identifier)
                    except Exception as cleanup_error:
                        exc.add_note(f"Runtime cleanup incomplete: {cleanup_error}")
            raise

    def _check_owned(self):
        record = owned_container(self.context, self.container, self.token, self.image_id,
                                 self.network, self.container_id)
        if record is None:
            raise RuntimeError("owned container is absent; refusing lifecycle operation")
        self.container_id = record["Id"]
        return record

    def run(self, *command, env=None, timeout=360, check=True):
        identifier = self._check_owned()["Id"]
        args = ["exec"]
        for key, value in (env or {}).items():
            args.extend(["-e", f"{key}={value}"])
        return docker(self.context, *args, identifier, "python3", CONTROLLER,
                      "run", "--workspace", self.service_workspace, "--", *command, timeout=timeout, check=check)

    def start(self, name="app", port=4000, provider_url=None, migrate=True, jobs_enabled=True):
        args = ["python3", CONTROLLER, "start", "--workspace", self.service_workspace,
                "--name", name, "--port", str(port)]
        if provider_url is not None:
            args.extend(["--provider-url", provider_url])
        if not migrate:
            args.append("--no-migrate")
        result = self.run(*args, env={"JOBS_ENABLED": "1" if jobs_enabled else "0"})
        return json.loads(result.stdout)

    def stop(self, name="app"):
        self.run("python3", CONTROLLER, "stop", "--name", name)

    def crash(self, name="app"):
        """SIGKILL the managed application process group; do not touch PostgreSQL."""
        self.run("python3", CONTROLLER, "crash", "--name", name)

    def upgrade(self, snapshot, jobs_enabled=True, provider_url=None):
        """Copy the next candidate-only source into container state; never erase host source."""
        snapshot = Path(snapshot).resolve()
        if not (snapshot / "mix.exs").is_file():
            raise ValueError("snapshot must be a candidate Mix project")
        if any((snapshot / name).exists() for name in ("bench.py", "evaluation", ".codex")):
            raise ValueError("snapshot must not include evaluator/host configuration")
        self.run("python3", CONTROLLER, "stop-all")
        destination = "/state/source-" + uuid.uuid4().hex
        self.run("mkdir", destination)
        # Docker cp refuses read-only roots even for a writable tmpfs destination.
        # Stream candidate-only source through exec, which retains the container UID.
        def include(member):
            if any(part in {".git", ".env", ".codex", "deps", "_build", "__pycache__"}
                   for part in Path(member.name).parts):
                return None
            if member.issym() or member.islnk():
                target = (snapshot / member.name).resolve()
                if not target.is_relative_to(snapshot):
                    raise ValueError("snapshot link escapes candidate source")
            member.uid, member.gid = 0, 0
            return member

        with tempfile.TemporaryFile() as stream:
            with tarfile.open(fileobj=stream, mode="w") as archive:
                archive.add(snapshot, arcname=".", filter=include)
            stream.seek(0)
            identifier = self._check_owned()["Id"]
            result = subprocess.run(["docker", "--context", self.context, "exec", "-i", identifier,
                                     "tar", "--no-same-owner", "-xf", "-", "-C", destination],
                                    stdin=stream, capture_output=True, text=True, timeout=120)
            if result.returncode:
                raise CommandError("source-copy", result)
        self.service_workspace = destination
        return self.start(jobs_enabled=jobs_enabled, provider_url=provider_url)

    def restart(self, name="app", port=4000, provider_url=None, migrate=True, jobs_enabled=True):
        self.stop(name)
        return self.start(name, port, provider_url, migrate, jobs_enabled)

    def reset(self):
        """Stops managed application processes; recreates only field_desk and its test DB."""
        self.run("python3", CONTROLLER, "reset")

    def destroy(self):
        # Legacy state files have names only. Verify once and pin IDs before any mutation.
        if self.container_id is None:
            record = owned_container(self.context, self.container, self.token, self.image_id, self.network)
            self.container_id = record["Id"] if record else None
        if self.network_id is None:
            record = _inspect_resource(self.context, "network", self.network)
            if record is not None and (record.get("Labels") or {}).get(LABEL) != self.token:
                raise RuntimeError("network ownership mismatch; refusing deletion")
            self.network_id = record["Id"] if record else None
        if self.container_id is not None:
            remove_owned_container(self.context, self.container, self.token, self.image_id,
                                   self.network, self.container_id)
        if self.network_id is not None:
            remove_owned_network(self.context, self.network, self.token, self.network_id)

    def save(self, path):
        path = Path(path)
        path.write_text(json.dumps(asdict(self), indent=2) + "\n")
        path.chmod(0o600)

    @classmethod
    def load(cls, path):
        return cls(**json.loads(Path(path).read_text()))


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("action", choices=["create", "start", "stop", "restart", "reset", "destroy", "run"])
    parser.add_argument("--state", required=True, type=Path)
    parser.add_argument("--workspace", type=Path)
    parser.add_argument("--image", default=DEFAULT_IMAGE)
    parser.add_argument("--context", choices=CONTEXTS, default=CONTEXTS[0])
    parser.add_argument("--provider-url")
    parser.add_argument("--uid", type=int, default=1000)
    parser.add_argument("--gid", type=int, default=1000)
    args, command = parser.parse_known_args()
    if args.action == "create":
        if not args.workspace or args.state.exists():
            parser.error("create requires --workspace and a new --state file")
        runtime = Runtime.create(args.workspace, args.image, args.context, args.provider_url, args.uid, args.gid)
        try:
            runtime.save(args.state)
        except BaseException:
            runtime.destroy()
            raise
        print(json.dumps(asdict(runtime), indent=2))
    else:
        runtime = Runtime.load(args.state)
        if args.action == "run":
            if command[:1] == ["--"]:
                command = command[1:]
            if not command:
                parser.error("run requires a command after --")
            result = runtime.run(*command, check=False)
            print(result.stdout, end="")
            print(result.stderr, end="", file=__import__("sys").stderr)
            raise SystemExit(result.returncode)
        elif args.action in ("start", "restart"):
            print(json.dumps(getattr(runtime, args.action)(provider_url=args.provider_url)))
        else:
            getattr(runtime, args.action)()
            if args.action == "destroy":
                args.state.unlink()


if __name__ == "__main__":
    main()
