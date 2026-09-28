#!/usr/bin/env python3
"""Run staged packets with an explicitly selected conversation protocol."""

import argparse
import hashlib
import io
import json
import os
from pathlib import Path
import shutil
import signal
import subprocess
import sys
import tarfile
import time

ROOT = Path(__file__).resolve().parent
sys.path.insert(0, str(ROOT / "runtime"))
from docker_runtime import Runtime, CONTROLLER, CONTEXTS, DEFAULT_IMAGE, docker
from session_protocol import (PROTOCOLS, assert_not_stopped, import_m1, prepare_release,
                              register_session, require_protocol, run_lock)

EXCLUDED = {".git", "deps", "_build", "node_modules", ".elixir_ls", "__pycache__", ".DS_Store"}
PROMPT = """Implement the current milestone in TASK.md, including its public API and usable operator views.
Read RUNBOOK.md and every request currently present in requests/. Earlier requirements remain in force.
Choose your own domain architecture and preserve your existing application and its data across this change.
Use your own tests, exercise the application, fix problems you discover, and review the implementation before finishing.
You may iterate freely. Do not delegate to other agents. Do not consult external benchmark solutions or later requests.
When the current milestone is complete, give a concise delivery summary. Do not implement imagined later milestones.
"""


def save(path, data):
    temporary = path.with_suffix(path.suffix + ".tmp")
    temporary.write_text(json.dumps(data, indent=2) + "\n")
    temporary.replace(path)


def command(runtime, effort, session=None, model="gpt-6-astra"):
    cmd = ["docker", "--context", runtime.context, "exec", "-i", "-e", "CODEX_HOME=/state/codex",
           runtime.container_id, "python3", CONTROLLER, "run", "--workspace", "/workspace", "--",
           "/usr/local/bin/codex", "--dangerously-bypass-approvals-and-sandbox", "--cd", "/workspace",
           "--model", model, "--config", f'model_reasoning_effort="{effort}"', "--disable", "multi_agent",
           "--disable", "multi_agent_v2", "exec"]
    if session:
        cmd += ["resume", session]
    return cmd + ["--json", "--ignore-user-config", "--ignore-rules", "--skip-git-repo-check", "-"]


def provision_auth(runtime):
    source = Path(os.environ.get("CODEX_HOME", Path.home() / ".codex")) / "auth.json"
    if not source.is_file():
        raise RuntimeError(f"Existing subscription authentication not found at {source}")
    script = "from pathlib import Path;import sys;p=Path('/state/codex');p.mkdir(mode=0o700,exist_ok=True);f=p/'auth.json';f.write_bytes(sys.stdin.buffer.read());f.chmod(0o600)"
    result = subprocess.run(["docker", "--context", runtime.context, "exec", "-i", runtime.container_id,
                             "python3", "-c", script], input=source.read_bytes(), capture_output=True)
    if result.returncode:
        raise RuntimeError("Could not provision the candidate's private CLI authentication")


def opencode_command(runtime, model, effort="default", session=None, prompt=PROMPT):
    cmd = ["docker", "--context", runtime.context, "exec", "-i", runtime.container_id,
           "python3", CONTROLLER, "run", "--workspace", "/workspace", "--",
           "/usr/local/bin/opencode", "run", "--pure", "--auto", "--thinking", "--format", "json",
           "--dir", "/workspace", "--model", model]
    if effort != "default":
        cmd += ["--variant", effort]
    if session:
        cmd += ["--session", session]
    return cmd + [prompt]


def provision_opencode(runtime, model):
    # Keep provider state outside the submitted project; no host auth is needed
    # for OpenCode's free models. Disable delegation, as in the Codex lane.
    config = {"model": model, "small_model": model,
              "permission": {"task": "deny"}}
    script = "from pathlib import Path;import sys;p=Path('/state/home/.config/opencode');p.mkdir(parents=True,exist_ok=True);(p/'opencode.json').write_text(sys.argv[1])"
    runtime.run("python3", "-c", script, json.dumps(config))


def archive_opencode(runtime, destination, session):
    if not session:
        return
    # OpenCode can exit before a large piped stdout buffer drains. Export to a
    # regular file first, then let Python validate and stream the complete JSON.
    script = """import json,subprocess,sys,tempfile
with tempfile.TemporaryFile() as output:
    subprocess.run(['/usr/local/bin/opencode','export',sys.argv[1]],stdout=output,check=True)
    output.seek(0)
    data=output.read()
json.loads(data)
sys.stdout.buffer.write(data)
"""
    result = runtime.run("python3", "-c", script, session, timeout=120)
    # Export contains the session messages and usage, not provider credentials.
    json.loads(result.stdout)
    destination.mkdir(parents=True, exist_ok=True)
    (destination / f"{session}.json").write_text(result.stdout)


def opencode_event(event):
    part = event.get("part") or {}
    return dict(session_id=event.get("sessionID"),
                completed=event.get("type") == "step_finish" and part.get("reason") == "stop",
                error=event if event.get("type") == "error" else None,
                finish_reason=part.get("reason") if event.get("type") == "step_finish" else None,
                usage=part.get("tokens"),
                last_event={"type": event.get("type"),
                            "text": str(part.get("text", part.get("tool", "")))[-1800:]})


def archive_sessions(runtime, destination):
    # Copy rollout evidence only, never the surrounding authentication directory.
    script = """from pathlib import Path
import tarfile,sys
root=Path('/state/codex')
with tarfile.open(fileobj=sys.stdout.buffer,mode='w|') as archive:
    for name in ('sessions','archived_sessions'):
        for path in sorted((root/name).rglob('rollout-*.jsonl')):
            if path.is_file() and not path.is_symlink():
                archive.add(path,arcname=str(path.relative_to(root)),recursive=False)
"""
    result = subprocess.run(["docker", "--context", runtime.context, "exec", runtime.container_id, "python3", "-c", script], capture_output=True)
    if result.returncode:
        raise RuntimeError("Could not archive candidate session evidence")
    destination.mkdir(parents=True, exist_ok=True)
    with tarfile.open(fileobj=io.BytesIO(result.stdout)) as archive:
        archive.extractall(destination, filter="data")


def snapshot(workspace, destination):
    shutil.copytree(workspace, destination, ignore=lambda _p, names: set(names) & EXCLUDED, symlinks=True)
    files = {}
    for path in sorted(destination.rglob("*")):
        if path.is_file() and not path.is_symlink():
            files[str(path.relative_to(destination))] = hashlib.sha256(path.read_bytes()).hexdigest()
    return files


def deliver(workspace, milestone, source=None):
    source = source or ROOT / "candidate/0.1"
    manifest = json.loads((source / "manifest.json").read_text())
    packet = next(p for p in manifest["milestones"] if p["milestone"] == milestone)
    destination = workspace / "requests"
    destination.mkdir(exist_ok=True)
    for filename in packet["files"]:
        shutil.copyfile(source / filename, destination / filename)
    (workspace / "TASK.md").write_text(f"# Billing Bench {manifest['version']}: Milestone {milestone}\n\n" + manifest.get("prompt", PROMPT) + "\nCurrent request files:\n" +
                                      "".join(f"- requests/{name}\n" for name in packet["files"]))


def confirm_packet(runtime, workspace, wait_seconds=30):
    paths = [workspace / "TASK.md", *sorted(p for p in (workspace / "requests").iterdir() if p.is_file())]
    expected = {str(path.relative_to(workspace)): hashlib.sha256(path.read_bytes()).hexdigest()
                for path in paths}
    # Host writes can lag on the VM's bind mount. Check the candidate's view before
    # starting its turn; a successful CLI exit does not prove it received the task.
    script = """import hashlib,json,pathlib,sys,time
root=pathlib.Path(sys.argv[1]); expected=json.loads(sys.argv[2])
deadline=time.monotonic()+float(sys.argv[3])
while True:
    observed={}
    for name in expected:
        try: observed[name]=hashlib.sha256((root/name).read_bytes()).hexdigest()
        except FileNotFoundError: observed[name]=None
    if observed==expected:
        print(json.dumps(observed)); break
    if time.monotonic()>=deadline:
        raise SystemExit('Candidate cannot read delivered task files: '+json.dumps(
            [name for name in expected if observed[name]!=expected[name]]))
    time.sleep(0.25)
"""
    receipt = runtime.run("python3", "-c", script, runtime.service_workspace, json.dumps(expected),
                          str(wait_seconds), timeout=wait_seconds + 30)
    if json.loads(receipt.stdout) != expected:
        raise RuntimeError("Candidate task delivery receipt does not match the packet")
    return dict(verified_at=time.time(), sha256=expected)


def run(args):
    require_protocol(getattr(args, "protocol", None))
    assert_not_stopped(args.directory)
    with run_lock(args.directory):
        return run_locked(args)


def run_locked(args):
    protocol = require_protocol(getattr(args, "protocol", None))
    harness = getattr(args, "harness", "codex")
    version = getattr(args, "version", "0.1")
    benchmark_root = Path(getattr(args, "benchmark_root", ROOT))
    source = benchmark_root / "candidate" / version
    manifest = json.loads((source / "manifest.json").read_text())
    if not 1 <= args.through <= len(manifest["milestones"]):
        raise ValueError("Requested milestone is outside the selected version")
    if args.effort == "default" and harness != "opencode":
        raise ValueError("default effort requires OpenCode")
    directory = args.directory.resolve()
    assert_not_stopped(directory)
    state_path = directory / "status.json"
    workspace = directory / "workspace"
    runtime_path = directory / "runtime.json"
    if args.resume:
        if getattr(args, "from_run", None):
            raise ValueError("--from-run creates a new trajectory; it cannot be used with --resume")
        state = json.loads(state_path.read_text())
        require_protocol(protocol, state)
        state["protocol"] = protocol
        if (state.get("version", "0.1"), state["model"], state["effort"], state.get("harness", "codex")) != (version, args.model, args.effort, harness):
            raise ValueError("Resume must retain the original version, model, effort and harness")
        if state["status"] not in ("prepared", "paused", "interrupted", "failed"):
            raise ValueError("Resume requires a paused or stopped run")
        workspace = Path(state.get("workspace", workspace))
        runtime = Runtime.load(runtime_path)
        runtime._check_owned()
    else:
        directory.mkdir(parents=True, exist_ok=False)
        shutil.copytree(source, directory / "inputs")
        state = dict(version=version, model=args.model, effort=args.effort, harness=harness, status="setup", completed=[], session_id=None,
                     delegation=False, started_at=time.time(), through=args.through,
                     protocol=protocol, workspace=str(workspace), docker_context=args.context,
                     runtime_image=getattr(args, "image", DEFAULT_IMAGE))
        runtime = None
        if getattr(args, "from_run", None):
            import_m1(args.from_run, directory, state)
        else:
            shutil.copytree(benchmark_root / "scaffold", workspace, ignore=lambda _p, names: set(names) & EXCLUDED)
            for path in [workspace, *workspace.rglob("*")]:
                if not path.is_symlink():
                    path.chmod(path.stat().st_mode | 0o200)
            deliver(workspace, 1, directory / "inputs")
            runtime = Runtime.create(workspace, context=args.context, image=state["runtime_image"],
                                     environment=dict(BILLING_AUTH_SECRET="billingbench-candidate-development", BILLING_GL_URL="http://billing-gl:4100"))
            runtime.save(runtime_path)
            state["runtime_image"] = runtime.image_id
        save(state_path, state)
    if args.through <= len(state["completed"]):
        raise ValueError("No uncompleted release requested")
    state["workspace"] = str(workspace)
    manifest = json.loads((directory / "inputs/manifest.json").read_text())
    prompt = manifest.get("prompt", PROMPT)
    def archive():
        if harness == "opencode":
            archive_opencode(runtime, directory / "sessions", state["session_id"])
        else:
            archive_sessions(runtime, directory / "sessions")
    state["through"] = args.through
    process = None
    previous_handlers = {}

    def interrupted(signum, _frame):
        if process and process.poll() is None:
            # Only this run's isolated container; do not touch other runs or host CLIs.
            docker(runtime.context, "exec", runtime.container_id, "pkill", "-INT", "-f", f"/usr/local/bin/{harness}", check=False)
        raise KeyboardInterrupt

    for signum in (signal.SIGINT, signal.SIGTERM):
        previous_handlers[signum] = signal.signal(signum, interrupted)
    try:
        for milestone in range(len(state["completed"]) + 1, args.through + 1):
            runtime, workspace = prepare_release(directory, state, milestone, runtime, Runtime, save)
            if harness == "opencode":
                provision_opencode(runtime, args.model)
            else:
                provision_auth(runtime)
            deliver(workspace, milestone, directory / "inputs")
            receipt = confirm_packet(runtime, workspace)
            logs = directory / "logs"
            logs.mkdir(exist_ok=True)
            log = logs / f"milestone-{milestone}.jsonl"
            if log.exists():
                log = logs / f"milestone-{milestone}-resume-{time.time_ns()}.jsonl"
            started = time.time()
            state.update(status="running", milestone=milestone, milestone_started_at=started,
                         input_receipt=receipt, last_event=None, failure=None, exit_code=None)
            save(state_path, state)
            print(f"{args.effort}: starting milestone {milestone}", flush=True)
            attempts = []
            for attempt in range(1, 6 if harness == "opencode" else 2):
                if attempt > 1:
                    log = logs / f"milestone-{milestone}-retry-{time.time_ns()}.jsonl"
                success, usage, finish_reason = False, None, None
                session_observed = False
                attempt_started = time.time()
                state.update(attempt=attempt, last_error=None)
                with log.open("w") as output, (log.with_suffix(".stderr")).open("w") as stderr:
                    cli = (opencode_command(runtime, args.model, args.effort, state["session_id"], prompt)
                           if harness == "opencode" else command(runtime, args.effort, state["session_id"], args.model))
                    process = subprocess.Popen(cli, stdin=subprocess.PIPE, stdout=subprocess.PIPE,
                                               stderr=stderr, text=True, bufsize=1)
                    state.update(controller_pid=os.getpid(), exec_pid=process.pid)
                    save(state_path, state)
                    if harness != "opencode":
                        process.stdin.write(prompt)
                    process.stdin.close()
                    for line in process.stdout:
                        output.write(line)
                        output.flush()
                        try:
                            event = json.loads(line)
                        except ValueError:
                            continue
                        if harness == "opencode":
                            parsed = opencode_event(event)
                            if parsed["session_id"]:
                                register_session(state, milestone, parsed["session_id"])
                                session_observed = True
                            if event.get("type") == "step_start":
                                success = False
                            if parsed["finish_reason"] is not None:
                                finish_reason = parsed["finish_reason"]
                                success, usage = parsed["completed"], parsed["usage"]
                            if parsed["error"]:
                                success = False
                                state["last_error"] = parsed["error"]
                            state.update(last_event=parsed["last_event"], last_event_at=time.time())
                            save(state_path, state)
                            continue
                        if event.get("type") == "thread.started":
                            register_session(state, milestone, event["thread_id"])
                            session_observed = True
                        if event.get("type") == "turn.completed":
                            success, usage = True, event.get("usage")
                        if event.get("type") in ("turn.failed", "error"):
                            state["last_error"] = event
                        state["last_event_at"] = time.time()
                        item = event.get("item", {})
                        if isinstance(item, dict):
                            state["last_event"] = {k: str(item[k])[-1800:] for k in ("type", "text", "command", "status") if k in item}
                        save(state_path, state)
                    exit_code = process.wait()
                archive()
                attempts.append(dict(log=str(log), exit_code=exit_code, finish_reason=finish_reason,
                                     completed=success, seconds=time.time() - attempt_started))
                state["attempts"] = attempts
                save(state_path, state)
                if exit_code == 0 and success and session_observed:
                    break
                if harness != "opencode" or finish_reason not in ("unknown", "tool-calls") or attempt == 5:
                    break
                delay = min(30 * attempt, 120)
                state.update(status="retry_wait", retry_at=time.time() + delay)
                save(state_path, state)
                print(f"OpenCode stream incomplete ({finish_reason}); resuming the same milestone/session in {delay}s, attempt {attempt + 1}/5", flush=True)
                time.sleep(delay)
                state.update(status="running")
            if exit_code or not success or not session_observed:
                state.update(status="failed", exit_code=exit_code, controller_pid=None, exec_pid=None,
                             failure="CLI did not complete its milestone turn")
                save(state_path, state)
                print(f"{args.effort}: milestone {milestone} stopped, inspect {log}", flush=True)
                return 1
            destination = directory / "snapshots" / f"milestone-{milestone}"
            hashes = snapshot(workspace, destination)
            stage = dict(milestone=milestone, seconds=time.time() - started, usage=usage, input_receipt=receipt,
                         snapshot=str(destination), sha256=hashes, log=str(log), attempts=attempts,
                         protocol=protocol, session_id=state["session_id"], runtime_container_id=runtime.container_id)
            state["completed"].append(stage)
            save(state_path, state)
            print(f"{args.effort}: milestone {milestone} completed in {stage['seconds'] / 60:.1f} minutes", flush=True)
        state.update(status="paused" if args.through < len(manifest["milestones"]) else "completed", paused_at=time.time(), controller_pid=None, exec_pid=None)
        save(state_path, state)
        return 0
    except KeyboardInterrupt:
        if process and process.poll() is None:
            process.wait()
        archive()
        state.update(status="interrupted", stopped_at=time.time())
        save(state_path, state)
        return 130
    except Exception as exc:
        if process and process.poll() is None:
            docker(runtime.context, "exec", runtime.container_id, "pkill", "-INT", "-f", f"/usr/local/bin/{harness}", check=False)
            process.wait(timeout=30)
        state.update(status="failed", failure=f"{type(exc).__name__}: {exc}", stopped_at=time.time())
        save(state_path, state)
        raise
    finally:
        for signum, handler in previous_handlers.items():
            signal.signal(signum, handler)


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--directory", type=Path, required=True)
    parser.add_argument("--protocol", choices=PROTOCOLS, required=True)
    parser.add_argument("--from-run", type=Path, help="New handoff trajectory from an unchanged accepted M1")
    parser.add_argument("--benchmark-root", type=Path, default=ROOT)
    parser.add_argument("--model", default="gpt-6-astra")
    parser.add_argument("--version", choices=("0.1", "0.2", "0.3", "0.4", "0.5"), default="0.5")
    parser.add_argument("--harness", choices=("codex", "opencode"), default="codex")
    parser.add_argument("--image", default="sha256:d916afedec259eb95d980bdf210d77e0d5ea622fac46a9e189081d9ddd068cdc")
    parser.add_argument("--effort", choices=("default", "low", "medium", "high", "xhigh"), required=True)
    parser.add_argument("--through", type=int, choices=range(1, 7), default=2)
    parser.add_argument("--context", choices=CONTEXTS, default=CONTEXTS[0])
    parser.add_argument("--resume", action="store_true")
    args = parser.parse_args()
    sys.path.insert(0, str(ROOT))
    import network_support
    network_support.enable()
    raise SystemExit(run(args))


if __name__ == "__main__":
    main()
