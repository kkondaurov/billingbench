import io
import json
from pathlib import Path
import shutil
import subprocess
import tempfile
from types import SimpleNamespace
import unittest
import sys
from unittest.mock import patch

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'benchmark/v1'))
import run_candidate
import session_protocol as protocol


class FakeRuntime:
    serial = 0
    instances = {}

    def __init__(self, workspace, context="test", image="test-image", **_):
        type(self).serial += 1
        self.context = context
        self.image_id = image
        self.container_id = f"container-{self.serial}"
        self.workspace = str(workspace)
        self.service_workspace = "/workspace"
        self.instances[self.container_id] = self

    create = classmethod(lambda cls, workspace, **kw: cls(workspace, **kw))

    def save(self, path):
        Path(path).write_text(json.dumps({"container_id": self.container_id}))

    @classmethod
    def load(cls, path):
        return cls.instances[json.loads(Path(path).read_text())["container_id"]]

    def _check_owned(self):
        return {"Id": self.container_id}

    def run(self, *_args, **_kwargs):
        return SimpleNamespace(stdout="", returncode=0)


class FakeProcess:
    pid = 12345

    def __init__(self, session, success=True):
        self.stdin = io.StringIO()
        self.stdout = io.StringIO("\n".join(json.dumps(e) for e in (
            {"type": "thread.started", "thread_id": session},
            {"type": "turn.completed" if success else "turn.failed", "usage": {}})) + "\n")
        self.returncode = None

    def wait(self, **_):
        self.returncode = 0
        return 0

    def poll(self):
        return self.returncode


class SessionProtocolTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.addCleanup(self.temp.cleanup)
        self.root = Path(self.temp.name)

    def fixture(self):
        bundle = self.root / "bundle"
        scaffold = bundle / "scaffold"
        scaffold.mkdir(parents=True)
        (scaffold / "mix.exs").write_text("# test source\n")
        packets = bundle / "candidate/0.5"
        packets.mkdir(parents=True)
        (packets / "manifest.json").write_text(json.dumps({
            "version": "0.5", "prompt": "Implement TASK.md", "milestones": [
                {"milestone": i, "files": [f"{i}.md"]} for i in (1, 2)]}))
        for i in (1, 2):
            (packets / f"{i}.md").write_text(f"Release {i}\n")
        return SimpleNamespace(directory=self.root / "run", benchmark_root=bundle,
                               version="0.5", harness="codex", protocol="handoff", model="test-model",
                               effort="low", through=2, context="test", image="test-image", resume=False)

    def execute(self, args, events):
        with patch.object(run_candidate, "Runtime", FakeRuntime), \
             patch.object(run_candidate, "provision_auth"), \
             patch.object(run_candidate, "confirm_packet", return_value={}), \
             patch.object(run_candidate, "archive_sessions"), \
             patch.object(run_candidate, "docker"), \
             patch.object(protocol, "stop_runtime"), \
             patch.object(protocol, "archive_databases", return_value=[{"test": "database"}]), \
             patch.object(protocol, "restore_databases"), \
             patch.object(run_candidate.subprocess, "Popen", side_effect=events) as launch:
            result = run_candidate.run(args)
        return result, [call.args[0] for call in launch.call_args_list]

    def test_protocol_is_mandatory_before_any_launch(self):
        args = self.fixture()
        del args.protocol
        with patch.object(run_candidate.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(ValueError, "explicitly"):
                run_candidate.run(args)
            launch.assert_not_called()
        self.assertFalse(args.directory.exists())

    def test_fresh_session_and_runtime_at_every_release(self):
        args = self.fixture()
        result, commands = self.execute(args, [FakeProcess("first"), FakeProcess("second")])
        self.assertEqual(result, 0)
        self.assertTrue(all("resume" not in cmd for cmd in commands))
        state = json.loads((args.directory / "status.json").read_text())
        first, second = state["completed"]
        self.assertNotEqual(first["runtime_container_id"], second["runtime_container_id"])
        self.assertEqual([x["session_id"] for x in state["completed"]], ["first", "second"])
        self.assertEqual((Path(state["workspace"]) / "mix.exs").read_text(), "# test source\n")
        self.assertFalse((Path(first["snapshot"]) / "requests/2.md").exists())
        self.assertEqual(state["handoff_receipt"]["development_databases"], "restored")

    def test_explicit_continuous_mode_still_resumes(self):
        args = self.fixture()
        args.protocol = "continuous"
        result, commands = self.execute(args, [FakeProcess("first"), FakeProcess("first")])
        self.assertEqual(result, 0)
        self.assertNotIn("resume", commands[0])
        self.assertEqual(commands[1][commands[1].index("resume") + 1], "first")

    def test_pause_at_release_boundary_starts_new_session(self):
        args = self.fixture()
        args.through = 1
        self.execute(args, [FakeProcess("first")])
        args.resume, args.through = True, 2
        result, commands = self.execute(args, [FakeProcess("second")])
        self.assertEqual(result, 0)
        self.assertNotIn("resume", commands[0])

    def test_interrupted_same_release_keeps_its_session(self):
        args = self.fixture()
        result, _ = self.execute(args, [FakeProcess("first"), FakeProcess("second", False)])
        self.assertEqual(result, 1)
        args.resume = True
        result, commands = self.execute(args, [FakeProcess("second")])
        self.assertEqual(result, 0)
        self.assertEqual(commands[0][commands[0].index("resume") + 1], "second")

    def test_reused_prior_session_rejected_and_not_submitted(self):
        args = self.fixture()
        with self.assertRaisesRegex(RuntimeError, "previous release"):
            self.execute(args, [FakeProcess("first"), FakeProcess("first")])
        state = json.loads((args.directory / "status.json").read_text())
        self.assertEqual(len(state["completed"]), 1)
        self.assertFalse((args.directory / "snapshots/milestone-2").exists())

    def test_missing_session_identity_is_not_delivery(self):
        args = self.fixture()
        process = FakeProcess("first")
        process.stdout = io.StringIO('{"type":"turn.completed"}\n')
        result, _ = self.execute(args, [process])
        self.assertEqual(result, 1)
        self.assertFalse((args.directory / "snapshots/milestone-1").exists())

    def test_retry_must_report_its_session_identity_again(self):
        args = self.fixture()
        self.execute(args, [FakeProcess("first"), FakeProcess("second", False)])
        args.resume = True
        process = FakeProcess("second")
        process.stdout = io.StringIO('{"type":"turn.completed"}\n')
        result, _ = self.execute(args, [process])
        self.assertEqual(result, 1)
        self.assertFalse((args.directory / "snapshots/milestone-2").exists())

    def test_cannot_switch_legacy_run_to_handoff(self):
        with self.assertRaisesRegex(ValueError, "Cannot change"):
            protocol.require_protocol("handoff", {"completed": []})
        self.assertEqual(protocol.require_protocol("continuous", {}), "continuous")

    def test_submitted_source_tamper_and_unexpected_files_rejected(self):
        source = self.root / "source"
        source.mkdir()
        (source / "mix.exs").write_text("original")
        expected = protocol.file_hashes(source)
        (source / "extra.jsonl").write_text("unrecorded transcript")
        with self.assertRaisesRegex(ValueError, "hashes"):
            protocol.copy_submission(source, self.root / "copy", expected)
        self.assertFalse((self.root / "copy").exists())

    def test_symlinks_and_agent_state_are_rejected(self):
        source = self.root / "source"
        source.mkdir()
        (source / "log").symlink_to(self.root / "private-session")
        with self.assertRaisesRegex(ValueError, "link"):
            protocol.file_hashes(source)
        (source / "log").unlink()
        (source / ".codex").mkdir()
        (source / ".codex/session.jsonl").write_text("prior conversation")
        with self.assertRaisesRegex(ValueError, "agent state"):
            protocol.copy_submission(source, self.root / "copy", protocol.file_hashes(source))

    def test_stopped_and_duplicate_runs_cannot_launch(self):
        args = self.fixture()
        args.directory.mkdir()
        (args.directory / "STOPPED.md").write_text("User stopped this")
        with self.assertRaisesRegex(RuntimeError, "stopped"):
            run_candidate.run(args)
        with protocol.run_lock(self.root / "another"):
            with self.assertRaisesRegex(RuntimeError, "already owns"):
                with protocol.run_lock(self.root / "another"):
                    self.fail("duplicate controller acquired lock")

    def test_m1_import_uses_snapshot_not_live_workspace(self):
        args = self.fixture()
        self.execute(args, [FakeProcess("first"), FakeProcess("second")])
        original = args.directory
        before = protocol.file_hashes(original / "snapshots/milestone-1")
        (original / "workspace/mix.exs").write_text("MUST NOT BE IMPORTED")
        args.directory = self.root / "replacement"
        args.from_run = original
        result, commands = self.execute(args, [FakeProcess("new-second")])
        self.assertEqual(result, 0)
        self.assertNotIn("resume", commands[0])
        self.assertEqual(protocol.file_hashes(original / "snapshots/milestone-1"), before)
        state = json.loads((args.directory / "status.json").read_text())
        self.assertFalse(state["prefix_provenance"]["independent_new_sample"])
        self.assertEqual((Path(state["workspace"]) / "mix.exs").read_text(), "# test source\n")

    def test_import_rejects_different_model_effort_harness_or_packet(self):
        args = self.fixture()
        self.execute(args, [FakeProcess("first"), FakeProcess("second")])
        source = args.directory
        for field, value in (("model", "other"), ("effort", "xhigh"), ("harness", "other")):
            with self.subTest(field=field):
                target = self.root / field
                target.mkdir()
                state = dict(protocol="handoff", model="test-model", effort="low", harness="codex")
                state[field] = value
                with self.assertRaises(ValueError):
                    protocol.import_m1(source, target, state)
        target = self.root / "packet"
        target.mkdir()
        shutil.copytree(source / "inputs", target / "inputs")
        (target / "inputs/2.md").write_text("Changed requirements")
        state = dict(protocol="handoff", model="test-model", effort="low", harness="codex")
        with self.assertRaisesRegex(ValueError, "public packets differ"):
            protocol.import_m1(source, target, state)
        self.assertFalse((target / "snapshots").exists())

    def test_database_restore_failure_never_launches_next_candidate(self):
        args = self.fixture()
        args.through = 1
        self.execute(args, [FakeProcess("first")])
        args.resume, args.through = True, 2
        with patch.object(run_candidate, "Runtime", FakeRuntime), \
             patch.object(protocol, "stop_runtime"), \
             patch.object(protocol, "archive_databases", return_value=[{"test": "database"}]), \
             patch.object(protocol, "restore_databases", side_effect=RuntimeError("restore failed")), \
             patch.object(run_candidate.subprocess, "Popen") as launch:
            with self.assertRaisesRegex(RuntimeError, "restore failed"):
                run_candidate.run(args)
            launch.assert_not_called()
        state = json.loads((args.directory / "status.json").read_text())
        self.assertEqual(len(state["completed"]), 1)
        self.assertEqual(state["status"], "failed")


if __name__ == "__main__":
    unittest.main()
