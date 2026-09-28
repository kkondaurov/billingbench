"""Release-boundary isolation for new runs; never alter archived submissions."""

import hashlib
import fcntl
import json
from pathlib import Path
import shutil
import stat
import subprocess
from contextlib import contextmanager

PROTOCOLS = ("handoff", "continuous")
AGENT_STATE = {".codex", ".claude", ".opencode"}


@contextmanager
def run_lock(directory):
    directory = Path(directory).resolve()
    directory.parent.mkdir(parents=True, exist_ok=True)
    with (directory.parent / f".{directory.name}.runner.lock").open("a") as lock:
        try:
            fcntl.flock(lock, fcntl.LOCK_EX | fcntl.LOCK_NB)
        except BlockingIOError:
            raise RuntimeError("Another controller already owns this run") from None
        yield


def require_protocol(protocol, state=None):
    if protocol not in PROTOCOLS:
        raise ValueError("Choose --protocol handoff or continuous explicitly")
    if state is not None and state.get("protocol", "continuous") != protocol:
        raise ValueError("Cannot change a trajectory's protocol; create a new run from its M1 snapshot")
    return protocol


def assert_not_stopped(directory):
    directory = Path(directory)
    if (directory / "STOPPED.md").exists():
        raise RuntimeError("Run stopped by user; explicit new authorization is required")
    status_path = directory / "status.json"
    if status_path.exists() and json.loads(status_path.read_text()).get("status") == "stopped_by_user":
        raise RuntimeError("Run stopped by user")


def file_hashes(root):
    root = Path(root)
    hashes = {}
    if root.is_symlink() or not root.is_dir():
        raise ValueError("Source must be a real directory")
    for path in sorted(root.rglob("*")):
        if path.is_symlink():
            raise ValueError(f"Handoff source contains an unverified link: {path}")
        if path.is_file():
            hashes[path.relative_to(root).as_posix()] = hashlib.sha256(path.read_bytes()).hexdigest()
        elif not path.is_dir():
            raise ValueError(f"Handoff source contains a special file: {path}")
    return hashes


def copy_submission(source, destination, expected):
    source, destination = Path(source), Path(destination)
    if not expected or file_hashes(source) != expected:
        raise ValueError("Submitted snapshot hashes do not match; refusing handoff")
    if any(AGENT_STATE.intersection(Path(name).parts) for name in expected):
        raise ValueError("Submitted source contains agent state; refusing handoff")
    shutil.copytree(source, destination)
    for path in [destination, *destination.rglob("*")]:
        path.chmod(path.stat().st_mode | stat.S_IWUSR)
    if file_hashes(destination) != expected:
        raise ValueError("Handoff copy did not preserve submitted source")


def register_session(state, milestone, session):
    if not isinstance(session, str) or not session:
        raise RuntimeError("CLI did not supply a session identity")
    expected = state.get("session_id")
    if state.get("protocol") == "handoff":
        if state.get("session_milestone") != milestone:
            raise RuntimeError("Release boundary was not prepared")
        prior = {item.get("session_id") for item in state["completed"]}
        if session in prior:
            raise RuntimeError("CLI reused a previous release's conversation")
    if expected and session != expected:
        raise RuntimeError("Same-release retry changed conversation identity")
    state["session_id"] = session


def prepare_release(directory, state, milestone, runtime, runtime_class, save):
    """Fresh container and source copy on handoff, but retain same-release retries."""
    directory = Path(directory)
    if state["protocol"] == "continuous":
        return runtime, Path(state["workspace"])
    if state.get("session_milestone") == milestone:
        return runtime, Path(state["workspace"])
    if milestone != len(state["completed"]) + 1:
        raise ValueError("Release must follow the completed prefix")
    if milestone == 1:
        state.update(session_id=None, session_milestone=1)
        save(directory / "status.json", state)
        return runtime, Path(state["workspace"])
    previous = state["completed"][-1]
    if previous["milestone"] != milestone - 1 or not previous.get("session_id"):
        raise ValueError("Prior release lacks verified session provenance")
    workspace = directory / "workspaces" / f"milestone-{milestone}"
    copy_submission(previous["snapshot"], workspace, previous["sha256"])
    state["status"] = "preparing_handoff"
    save(directory / "status.json", state)
    databases = None
    # Carry application databases, not the old agent's home, processes, or temp files.
    if runtime is not None:
        archive = directory / "runtimes" / f"milestone-{milestone - 1}.json"
        archive.parent.mkdir(exist_ok=True)
        if archive.exists():
            raise RuntimeError("Prior runtime receipt already exists; inspect incomplete handoff")
        runtime.save(archive)
        runtime.run("python3", "/opt/v7-evolution/container.py", "stop-all")
        databases = archive_databases(runtime, directory / "databases" / f"milestone-{milestone - 1}")
        stop_runtime(runtime)
    runtime = runtime_class.create(
        workspace, context=state["docker_context"], image=state["runtime_image"],
        environment={"BILLING_AUTH_SECRET": "billingbench-candidate-development",
                     "BILLING_GL_URL": "http://billing-gl:4100"})
    runtime.save(directory / "runtime.json")
    if databases:
        restore_databases(runtime, databases)
    state.update(workspace=str(workspace), session_id=None, session_milestone=milestone,
                 runtime_container_id=runtime.container_id, status="prepared",
                 handoff_receipt={"from_milestone": milestone - 1,
                                  "source_sha256": previous["sha256"],
                                  "development_databases": "restored" if databases else "not available in imported M1 source snapshot",
                                  "fresh_runtime": runtime.container_id})
    save(directory / "status.json", state)
    return runtime, workspace


def stop_runtime(runtime):
    from docker_runtime import docker
    runtime._check_owned()
    docker(runtime.context, "stop", "--timeout", "20", runtime.container_id)


def archive_databases(runtime, destination):
    runtime._check_owned()
    destination.mkdir(parents=True, exist_ok=False)
    receipts = []
    for name in ("field_desk", "field_desk_test"):
        path = destination / f"{name}.dump"
        with path.open("xb") as stream:
            subprocess.run(["docker", "--context", runtime.context, "exec", runtime.container_id,
                            "/usr/lib/postgresql/17/bin/pg_dump", "-h", "127.0.0.1", "-U", "candidate",
                            "--format=custom", "--no-owner", "--no-privileges", name],
                           stdout=stream, stderr=subprocess.PIPE, check=True, timeout=120)
        receipts.append({"database": name, "path": str(path),
                         "sha256": hashlib.sha256(path.read_bytes()).hexdigest()})
    (destination / "manifest.json").write_text(json.dumps(receipts, indent=2) + "\n")
    return receipts


def restore_databases(runtime, receipts):
    runtime._check_owned()
    for receipt in receipts:
        path = Path(receipt["path"])
        if hashlib.sha256(path.read_bytes()).hexdigest() != receipt["sha256"]:
            raise ValueError("Database checkpoint hash mismatch")
        with path.open("rb") as stream:
            subprocess.run(["docker", "--context", runtime.context, "exec", "-i", runtime.container_id,
                            "/usr/lib/postgresql/17/bin/pg_restore", "-h", "127.0.0.1", "-U", "candidate",
                            "--clean", "--if-exists", "--exit-on-error", "--no-owner", "--no-privileges",
                            "-d", receipt["database"]], stdin=stream, stdout=subprocess.PIPE,
                           stderr=subprocess.PIPE, check=True, timeout=120)


def packet_signature(directory, through):
    directory = Path(directory)
    manifest = json.loads((directory / "manifest.json").read_text())
    signature = {"prompt": manifest["prompt"], "milestones": []}
    for milestone in range(1, through + 1):
        packet = next(p for p in manifest["milestones"] if p["milestone"] == milestone)
        names = packet["files"]
        if any(Path(name).name != name for name in names):
            raise ValueError("Unsafe public packet path")
        signature["milestones"].append({name: hashlib.sha256((directory / name).read_bytes()).hexdigest()
                                        for name in sorted(names)})
    return signature


def import_m1(source_run, directory, state):
    """Import only the accepted M1 artifact, never its live workspace or CLI state."""
    source_run, directory = Path(source_run), Path(directory)
    original = json.loads((source_run / "status.json").read_text())
    for key in ("model", "effort"):
        if original[key] != state[key]:
            raise ValueError(f"M1 {key} differs from requested run")
    if original.get("harness", "codex") != state["harness"]:
        raise ValueError("M1 harness differs from requested run")
    if state["protocol"] != "handoff":
        raise ValueError("M1 imports require the handoff protocol")
    through = len(json.loads((directory / "inputs/manifest.json").read_text())["milestones"])
    if packet_signature(source_run / "inputs", through) != packet_signature(directory / "inputs", through):
        raise ValueError("M1 public packets differ from the selected benchmark")
    first = original["completed"][0]
    if first["milestone"] != 1:
        raise ValueError("Missing accepted M1 submission")
    session = first.get("session_id")
    if not session:
        sessions = set()
        for log in sorted((source_run / "logs").glob("milestone-1*.jsonl")):
            for line in log.read_text().splitlines():
                try:
                    event = json.loads(line)
                except ValueError:
                    continue
                if event.get("type") == "thread.started":
                    sessions.add(event["thread_id"])
        if len(sessions) != 1:
            raise ValueError("Cannot establish a unique M1 session")
        session = sessions.pop()
    destination = directory / "snapshots/milestone-1"
    destination.parent.mkdir(exist_ok=True)
    copy_submission(source_run / "snapshots/milestone-1", destination, first["sha256"])
    state["completed"] = [{**first, "snapshot": str(destination), "session_id": session,
                           "inherited_from": str(source_run), "protocol": "fresh-initial-release"}]
    state["prefix_provenance"] = {"source_run": str(source_run), "milestones": [1],
                                  "independent_new_sample": False}
