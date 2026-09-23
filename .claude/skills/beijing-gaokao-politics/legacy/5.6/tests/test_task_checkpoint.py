import datetime as dt
import hashlib
import json
import os
import subprocess
import tempfile
import time
import unittest
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
SCRIPT = ROOT / "scripts" / "task_checkpoint.py"
SHA_A = "a" * 64
SHA_B = "b" * 64
SHA_C = "c" * 64


def utc_stamp(value):
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


class CheckpointCliTests(unittest.TestCase):
    def setUp(self):
        self.temp = tempfile.TemporaryDirectory()
        self.path = Path(self.temp.name) / "checkpoint.json"
        self.run_cli(
            "init", str(self.path), "--task-id", "test", "--stage", "stage-1",
            "--verified-action", "initialized", "--next-action", "work",
            "--resume-token", "stage-1:work", "--progress", "items=1",
        )

    def tearDown(self):
        self.temp.cleanup()

    def run_cli(self, *args, check=True):
        return subprocess.run(
            ["python3", str(SCRIPT), *args], text=True,
            capture_output=True, check=check,
        )

    def read(self):
        return json.loads(self.path.read_text(encoding="utf-8"))

    def write(self, data):
        self.path.write_text(json.dumps(data), encoding="utf-8")

    def expire(self):
        data = self.read()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        prior = utc_stamp(now - dt.timedelta(seconds=2))
        data["updated_at"] = prior
        data["lease_expires_at"] = utc_stamp(now - dt.timedelta(seconds=1))
        if data.get("last_session_poll") is not None:
            data["last_session_poll"] = prior
        if data.get("pending_tool") is not None:
            data["pending_tool"]["prepared_at"] = prior
        for session in data.get("active_sessions", []):
            session["last_poll"] = prior
        for history_name in ("tool_call_history", "session_history"):
            for event in data.get(history_name, []):
                event["at"] = prior
        self.write(data)

    def alarm(self):
        self.expire()
        self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "90", "--max-cycles", "1",
        )
        return self.read()["alarm_events"][0]["alarm_id"]

    def add_worker(self, session_id="worker:1"):
        self.run_cli(
            "session", str(self.path), "--action", "add",
            "--session-id", session_id, "--purpose", "worker", "--state", "running",
        )

    def completion_args(self):
        return (
            "terminal", str(self.path), "--status", "COMPLETED",
            "--outcome", "done", "--plan-clear", "--deliverables-verified",
            "--links-ready", "--deliverable", f"candidate.docx={SHA_A}",
            "--gate", "visual_qa=passed", "--link", "sandbox:/candidate.docx",
        )

    # 1. Initialization must not overwrite or manufacture a monitor.
    def test_init_refuses_overwrite_and_forged_monitor(self):
        overwrite = self.run_cli(
            "init", str(self.path), "--task-id", "again", "--stage", "x",
            "--verified-action", "x", "--next-action", "x",
            "--resume-token", "x", check=False,
        )
        self.assertNotEqual(overwrite.returncode, 0)
        other = Path(self.temp.name) / "other.json"
        forged = self.run_cli(
            "init", str(other), "--task-id", "x", "--stage", "x",
            "--verified-action", "x", "--next-action", "x",
            "--resume-token", "x", "--monitor-agent", "pretend:watch",
            check=False,
        )
        self.assertNotEqual(forged.returncode, 0)
        self.assertFalse(other.exists())

    # 2. No-op and expired heartbeats never renew a lease.
    def test_noop_and_expired_heartbeat_are_rejected(self):
        before = self.read()
        no_op = self.run_cli("heartbeat", str(self.path), check=False)
        self.assertNotEqual(no_op.returncode, 0)
        self.assertEqual(self.read(), before)
        self.expire()
        expired = self.run_cli(
            "heartbeat", str(self.path), "--progress", "items=2", check=False,
        )
        self.assertNotEqual(expired.returncode, 0)
        self.assertIn("verifiable artifact", expired.stderr)
        self.assertEqual(self.read()["alarm_events"], [])

    def test_burst_progress_never_extends_wall_clock_lease_past_600_seconds(self):
        for value in range(2, 22):
            self.run_cli(
                "heartbeat", str(self.path), "--progress", f"items={value}",
            )
        expires = dt.datetime.strptime(
            self.read()["lease_expires_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=dt.timezone.utc)
        self.assertLessEqual(
            expires,
            dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=600),
        )

    def test_default_lease_allows_real_five_to_ten_minute_work(self):
        data = self.read()
        updated = dt.datetime.strptime(
            data["updated_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=dt.timezone.utc)
        expires = dt.datetime.strptime(
            data["lease_expires_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=dt.timezone.utc)
        self.assertEqual((expires - updated).total_seconds(), 600)

    def test_turn_gate_final_rejects_live_running_and_returns_resume_fields(self):
        before = self.path.read_bytes()
        result = self.run_cli(
            "turn-gate", str(self.path), "--intent", "final", check=False,
        )
        self.assertEqual(result.returncode, 4)
        event = json.loads(result.stdout)
        self.assertEqual(event["event"], "TURN_CONTINUE_REQUIRED")
        self.assertEqual(event["stage"], "stage-1")
        self.assertEqual(event["next_action"], "work")
        self.assertEqual(event["resume_token"], "stage-1:work")
        self.assertEqual(self.path.read_bytes(), before)

    def test_turn_gate_final_accepts_completed_and_stopped(self):
        self.run_cli(*self.completion_args())
        completed = self.run_cli(
            "turn-gate", str(self.path), "--intent", "final",
        )
        self.assertEqual(json.loads(completed.stdout)["event"], "FINAL_AUTHORIZED")

        stopped_path = Path(self.temp.name) / "stopped.json"
        self.run_cli(
            "init", str(stopped_path), "--task-id", "stopped",
            "--stage", "stage-1", "--verified-action", "initialized",
            "--next-action", "work", "--resume-token", "stage-1:work",
        )
        self.run_cli(
            "terminal", str(stopped_path), "--status", "STOPPED",
            "--outcome", "blocked", "--blocker", "missing evidence",
            "--blocker-class", "missing_material", "--resume-token", "resume:x",
            "--last-completed-step", "audit", "--safe-artifact", "candidate.docx",
            "--recovery-condition", "evidence arrives", "--next-action", "resume audit",
        )
        stopped = self.run_cli(
            "turn-gate", str(stopped_path), "--intent", "final",
        )
        self.assertEqual(json.loads(stopped.stdout)["event"], "FINAL_AUTHORIZED")

    def test_turn_gate_wait_rejects_monitor_only_dispatch_gap(self):
        self.run_cli(
            "session", str(self.path), "--action", "add",
            "--session-id", "watch:primary", "--purpose", "watchdog",
            "--state", "MONITOR_READY", "--monitor",
        )
        result = self.run_cli(
            "turn-gate", str(self.path), "--intent", "wait", check=False,
        )
        self.assertEqual(result.returncode, 4)
        self.assertEqual(json.loads(result.stdout)["event"], "MAIN_ACTION_REQUIRED")

    def test_turn_gate_wait_accepts_pending_tool_or_real_worker(self):
        self.run_cli(
            "prepare-tool", str(self.path), "--call-id", "call-wait",
            "--tool-name", "exec", "--args-digest", SHA_A,
        )
        pending = self.run_cli(
            "turn-gate", str(self.path), "--intent", "wait",
        )
        self.assertEqual(json.loads(pending.stdout)["event"], "WAIT_AUTHORIZED")
        self.assertEqual(
            json.loads(pending.stdout)["pending_tool_call_id"], "call-wait",
        )
        self.run_cli(
            "prepare-tool", str(self.path), "--action", "result",
            "--call-id", "call-wait", "--result-status", "success",
            "--result-digest", SHA_B,
        )
        self.add_worker()
        worker = self.run_cli(
            "turn-gate", str(self.path), "--intent", "wait",
        )
        self.assertEqual(json.loads(worker.stdout)["event"], "WAIT_AUTHORIZED")
        self.assertEqual(json.loads(worker.stdout)["worker_session_ids"], ["worker:1"])

    def test_turn_gate_wait_requires_recovery_for_expired_or_open_alarm(self):
        self.expire()
        before = self.path.read_bytes()
        expired = self.run_cli(
            "turn-gate", str(self.path), "--intent", "wait", check=False,
        )
        self.assertEqual(expired.returncode, 2)
        self.assertEqual(json.loads(expired.stdout)["event"], "RECOVERY_REQUIRED")
        self.assertEqual(self.path.read_bytes(), before)
        self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--max-cycles", "1",
        )
        alarmed_before = self.path.read_bytes()
        alarmed = self.run_cli(
            "turn-gate", str(self.path), "--intent", "wait", check=False,
        )
        self.assertEqual(alarmed.returncode, 2)
        self.assertTrue(json.loads(alarmed.stdout)["unresolved_alarm_ids"])
        self.assertEqual(self.path.read_bytes(), alarmed_before)

    def test_turn_gate_invalid_checkpoint_never_allows_final(self):
        valid = self.path.read_bytes()
        self.path.write_text("{broken", encoding="utf-8")
        broken = self.path.read_bytes()
        invalid_json = self.run_cli(
            "turn-gate", str(self.path), "--intent", "final", check=False,
        )
        self.assertEqual(invalid_json.returncode, 1)
        self.assertEqual(self.path.read_bytes(), broken)

        self.path.write_bytes(valid)
        data = self.read()
        data.pop("stage")
        self.write(data)
        invalid_schema = self.run_cli(
            "turn-gate", str(self.path), "--intent", "final", check=False,
        )
        self.assertEqual(invalid_schema.returncode, 1)
        self.assertEqual(json.loads(invalid_schema.stdout)["event"], "TURN_GATE_INVALID")

    def test_turn_gate_wait_does_not_authorize_terminal_checkpoint(self):
        self.run_cli(*self.completion_args())
        result = self.run_cli(
            "turn-gate", str(self.path), "--intent", "wait", check=False,
        )
        self.assertEqual(result.returncode, 3)
        self.assertEqual(json.loads(result.stdout)["event"], "WAIT_NOT_APPLICABLE")

    # 3. prepare-tool renews once, is idempotent while pending, consumes once,
    #    and forbids call-id reuse.
    def test_prepare_tool_lifecycle_duplicate_reuse_and_result_consumption(self):
        seq = self.read()["heartbeat_seq"]
        self.run_cli(
            "prepare-tool", str(self.path), "--call-id", "call-1",
            "--tool-name", "exec", "--args-digest", SHA_A,
        )
        prepared = self.read()
        self.assertEqual(prepared["heartbeat_seq"], seq + 1)
        self.assertEqual(prepared["pending_tool"]["call_id"], "call-1")
        duplicate = self.run_cli(
            "prepare-tool", str(self.path), "--call-id", "call-1",
            "--tool-name", "exec", "--args-digest", SHA_A,
        )
        self.assertIn('"idempotent": true', duplicate.stdout)
        self.assertEqual(self.read()["heartbeat_seq"], seq + 1)
        self.run_cli(
            "prepare-tool", str(self.path), "--action", "result",
            "--call-id", "call-1", "--result-status", "success",
            "--result-digest", SHA_B, "--last-exit-code", "0",
        )
        consumed = self.read()
        self.assertIsNone(consumed["pending_tool"])
        self.assertEqual([e["event"] for e in consumed["tool_call_history"]],
                         ["PREPARED", "RESULT"])
        again = self.run_cli(
            "prepare-tool", str(self.path), "--action", "result",
            "--call-id", "call-1", "--result-status", "success",
            "--result-digest", SHA_B,
        )
        self.assertIn('"idempotent": true', again.stdout)
        reused = self.run_cli(
            "prepare-tool", str(self.path), "--call-id", "call-1",
            "--tool-name", "exec", "--args-digest", SHA_A, check=False,
        )
        self.assertNotEqual(reused.returncode, 0)

    def test_expired_tool_result_is_recorded_then_recovers_by_rerun_evidence(self):
        self.run_cli(
            "prepare-tool", str(self.path), "--call-id", "long-call",
            "--tool-name", "render", "--args-digest", SHA_A,
        )
        alarm_id = self.alarm()
        before = self.read()
        result = self.run_cli(
            "prepare-tool", str(self.path), "--action", "result",
            "--call-id", "long-call", "--result-status", "success",
            "--result-digest", SHA_B, "--last-exit-code", "0",
        )
        observed = self.read()
        self.assertIn('"renewed": false', result.stdout)
        self.assertEqual(observed["heartbeat_seq"], before["heartbeat_seq"])
        self.assertIsNone(observed["pending_tool"])
        self.assertFalse(observed["tool_call_history"][-1]["renewed"])
        self.run_cli(
            "recover", str(self.path), "--alarm-id", alarm_id,
            "--evidence-type", "idempotent-rerun", "--call-id", "long-call",
            "--result-digest", SHA_B, "--result", "success",
            "--verified-action", "long tool result verified",
        )
        recovered = self.read()
        self.assertEqual(recovered["status"], "RUNNING")
        self.assertEqual(recovered["alarm_events"][0]["status"], "RECOVERED")

    def test_tool_result_between_expiry_and_alarm_auto_recovers(self):
        self.run_cli(
            "prepare-tool", str(self.path), "--call-id", "gap-result",
            "--tool-name", "render", "--args-digest", SHA_A,
        )
        self.expire()
        self.run_cli(
            "prepare-tool", str(self.path), "--action", "result",
            "--call-id", "gap-result", "--result-status", "success",
            "--result-digest", SHA_B, "--last-exit-code", "0",
        )
        self.assertEqual(self.read()["alarm_events"], [])
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "600", "--max-cycles", "1",
        )
        data = self.read()
        self.assertIn("MONITOR_RECOVERED", watched.stdout)
        self.assertEqual(data["status"], "RUNNING")
        self.assertEqual(
            data["alarm_events"][0]["recovery_attempts"][0]["evidence"]["type"],
            "tool-result",
        )

    def test_open_alarm_allows_one_recorded_idempotent_recovery_probe(self):
        alarm_id = self.alarm()
        seq = self.read()["heartbeat_seq"]
        ordinary = self.run_cli(
            "prepare-tool", str(self.path), "--call-id", "ordinary-call",
            "--tool-name", "exec", "--args-digest", SHA_A, check=False,
        )
        self.assertNotEqual(ordinary.returncode, 0)
        prepared = self.run_cli(
            "prepare-tool", str(self.path), "--call-id", "recovery-probe-1",
            "--tool-name", "exec", "--args-digest", SHA_A,
        )
        self.assertIn('"renewed": false', prepared.stdout)
        self.assertEqual(self.read()["heartbeat_seq"], seq)
        self.assertEqual(
            self.read()["pending_tool"]["recovery_alarm_id"], alarm_id,
        )
        self.run_cli(
            "prepare-tool", str(self.path), "--action", "result",
            "--call-id", "recovery-probe-1", "--result-status", "success",
            "--result-digest", SHA_B, "--last-exit-code", "0",
        )
        self.run_cli(
            "recover", str(self.path), "--alarm-id", alarm_id,
            "--evidence-type", "idempotent-rerun",
            "--call-id", "recovery-probe-1", "--result-digest", SHA_B,
            "--result", "success", "--verified-action", "probe verified",
        )
        recovered = self.read()
        self.assertEqual(recovered["status"], "RUNNING")
        self.assertEqual(recovered["alarm_events"][0]["status"], "RECOVERED")

    def test_pre_alarm_tool_result_cannot_recover_a_later_alarm(self):
        self.run_cli(
            "prepare-tool", str(self.path), "--call-id", "old-call",
            "--tool-name", "render", "--args-digest", SHA_A,
        )
        self.run_cli(
            "prepare-tool", str(self.path), "--action", "result",
            "--call-id", "old-call", "--result-status", "success",
            "--result-digest", SHA_B,
        )
        alarm_id = self.alarm()
        rejected = self.run_cli(
            "recover", str(self.path), "--alarm-id", alarm_id,
            "--evidence-type", "idempotent-rerun", "--call-id", "old-call",
            "--result-digest", SHA_B, "--result", "success",
            "--verified-action", "claimed old result", check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertEqual(self.read()["alarm_events"][0]["status"], "OPEN")

    # 4. Same-state/no-output polls change only poll timestamps.
    def test_same_state_poll_records_observation_without_progress_or_renewal(self):
        self.add_worker()
        before = self.read()
        result = self.run_cli(
            "session", str(self.path), "--action", "poll",
            "--session-id", "worker:1", "--state", "running",
        )
        after = self.read()
        self.assertIn('"observation_only": true', result.stdout)
        for field in ("heartbeat_seq", "updated_at", "lease_expires_at",
                      "last_verified_action"):
            self.assertEqual(after[field], before[field])
        self.assertEqual(after["session_history"], before["session_history"])
        self.assertIsNotNone(after["last_session_poll"])

    # 5. New output is progress while the lease is live.
    def test_new_session_output_is_verifiable_progress(self):
        self.add_worker()
        before = self.read()
        self.run_cli(
            "session", str(self.path), "--action", "poll",
            "--session-id", "worker:1", "--state", "running",
            "--output-digest", SHA_A,
        )
        after = self.read()
        self.assertEqual(after["heartbeat_seq"], before["heartbeat_seq"] + 1)
        self.assertEqual(after["active_sessions"][0]["last_output_digest"], SHA_A)
        self.assertEqual(after["session_history"][-1]["event"], "POLL_PROGRESS")

    # 6. An expired poll preserves evidence but cannot renew.
    def test_expired_poll_records_evidence_without_lease_renewal(self):
        self.add_worker()
        self.expire()
        before = self.read()
        self.run_cli(
            "session", str(self.path), "--action", "poll",
            "--session-id", "worker:1", "--state", "still-running",
            "--output-digest", SHA_A,
        )
        after = self.read()
        self.assertEqual(after["heartbeat_seq"], before["heartbeat_seq"])
        self.assertEqual(after["updated_at"], before["updated_at"])
        self.assertEqual(after["lease_expires_at"], before["lease_expires_at"])
        self.assertFalse(after["session_history"][-1]["renewed"])
        self.assertIn("last_expired_poll", after["active_sessions"][0])
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "600", "--max-cycles", "1",
        )
        recovered = self.read()
        self.assertIn("MONITOR_RECOVERED", watched.stdout)
        self.assertEqual(recovered["status"], "RUNNING")
        self.assertEqual(
            recovered["alarm_events"][0]["recovery_attempts"][0]["evidence"]["type"],
            "session-output",
        )

    def test_post_alarm_session_output_auto_recovers_before_stop(self):
        self.add_worker()
        self.alarm()
        self.run_cli(
            "session", str(self.path), "--action", "poll",
            "--session-id", "worker:1", "--state", "still-running",
            "--output-digest", SHA_A,
        )
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "600", "--max-cycles", "1",
        )
        data = self.read()
        self.assertIn("MONITOR_RECOVERED", watched.stdout)
        self.assertEqual(data["status"], "RUNNING")
        self.assertEqual(data["alarm_events"][0]["status"], "RECOVERED")
        self.assertEqual(
            data["alarm_events"][0]["recovery_attempts"][0]["evidence"]["type"],
            "session-output",
        )

    def test_post_alarm_session_registration_without_output_does_not_recover(self):
        self.alarm()
        self.run_cli(
            "session", str(self.path), "--action", "add",
            "--session-id", "worker:new", "--purpose", "replacement worker",
            "--state", "registered",
        )
        data = self.read()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        data["alarm_events"][0]["recovery_deadline_at"] = utc_stamp(
            now - dt.timedelta(seconds=1)
        )
        self.write(data)
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "600", "--max-cycles", "1",
        )
        self.assertIn("MAIN_RECOVERY_SLA_MISSED", watched.stdout)
        self.assertEqual(self.read()["status"], "STOPPED")

    def test_post_alarm_tool_result_auto_recovers_before_stop(self):
        self.run_cli(
            "prepare-tool", str(self.path), "--call-id", "long-auto",
            "--tool-name", "render", "--args-digest", SHA_A,
        )
        self.alarm()
        self.run_cli(
            "prepare-tool", str(self.path), "--action", "result",
            "--call-id", "long-auto", "--result-status", "success",
            "--result-digest", SHA_B, "--last-exit-code", "0",
        )
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "600", "--max-cycles", "1",
        )
        data = self.read()
        self.assertIn("MONITOR_RECOVERED", watched.stdout)
        self.assertEqual(data["status"], "RUNNING")
        self.assertEqual(
            data["alarm_events"][0]["recovery_attempts"][0]["evidence"]["type"],
            "tool-result",
        )

    def test_post_alarm_verified_artifact_auto_recovers_before_stop(self):
        alarm_id = self.alarm()
        artifact = Path(self.temp.name) / "new-evidence.bin"
        artifact.write_bytes(b"verified post-alarm artifact")
        recorded = self.run_cli(
            "heartbeat", str(self.path), "--artifact", str(artifact),
        )
        self.assertIn('"renewed": false', recorded.stdout)
        self.assertEqual(self.read()["alarm_events"][0]["alarm_id"], alarm_id)
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "600", "--max-cycles", "1",
        )
        data = self.read()
        self.assertIn("MONITOR_RECOVERED", watched.stdout)
        self.assertEqual(data["status"], "RUNNING")
        evidence = data["alarm_events"][0]["recovery_evidence"][0]
        self.assertEqual(evidence["type"], "artifact-delta")
        self.assertEqual(evidence["sha256"], hashlib.sha256(
            b"verified post-alarm artifact"
        ).hexdigest())

    def test_artifact_between_expiry_and_watch_creates_recoverable_alarm(self):
        self.expire()
        artifact = Path(self.temp.name) / "gap-evidence.bin"
        artifact.write_bytes(b"created after lease expiry")
        recorded = self.run_cli(
            "heartbeat", str(self.path), "--artifact", str(artifact),
        )
        data = self.read()
        self.assertIn('"renewed": false', recorded.stdout)
        self.assertEqual(data["alarm_events"][0]["status"], "OPEN")
        self.assertEqual(
            data["alarm_events"][0]["evidence_window_start_at"],
            data["lease_expires_at"],
        )
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "600", "--max-cycles", "1",
        )
        self.assertIn("MONITOR_RECOVERED", watched.stdout)
        self.assertEqual(self.read()["status"], "RUNNING")

    def test_post_alarm_modified_tracked_artifact_auto_recovers(self):
        artifact = Path(self.temp.name) / "tracked-evidence.bin"
        artifact.write_bytes(b"baseline")
        self.run_cli(
            "heartbeat", str(self.path), "--artifact", str(artifact),
        )
        self.alarm()
        artifact.write_bytes(b"changed after alarm")
        recorded = self.run_cli(
            "heartbeat", str(self.path), "--artifact", str(artifact),
        )
        self.assertIn('"renewed": false', recorded.stdout)
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "600", "--max-cycles", "1",
        )
        data = self.read()
        self.assertIn("MONITOR_RECOVERED", watched.stdout)
        self.assertEqual(data["status"], "RUNNING")
        evidence = data["alarm_events"][0]["recovery_evidence"][0]
        self.assertTrue(evidence["tracked_before_alarm"])
        self.assertEqual(
            evidence["sha256"], hashlib.sha256(b"changed after alarm").hexdigest(),
        )

    def test_pre_alarm_artifact_path_cannot_prevent_stop(self):
        artifact = Path(self.temp.name) / "old-evidence.bin"
        artifact.write_bytes(b"old")
        old_time = time.time() - 30
        os.utime(artifact, (old_time, old_time))
        self.alarm()
        rejected = self.run_cli(
            "heartbeat", str(self.path), "--artifact", str(artifact), check=False,
        )
        self.assertNotEqual(rejected.returncode, 0)
        self.assertIn("modified after alarm", rejected.stderr)
        self.assertEqual(self.read()["alarm_events"][0]["recovery_evidence"], [])

    def test_forged_artifact_evidence_without_metadata_is_invalid(self):
        self.alarm()
        data = self.read()
        data["alarm_events"][0]["recovery_evidence"].append({
            "type": "artifact-delta", "at": data["alarm_events"][0]["created_at"],
        })
        self.write(data)
        checked = self.run_cli("check", str(self.path), check=False)
        self.assertEqual(checked.returncode, 1)
        self.assertIn("verified artifact metadata", checked.stdout)

    # 7. Bad poll timestamps fail validation.
    def test_invalid_last_poll_is_rejected(self):
        self.add_worker()
        data = self.read()
        data["active_sessions"][0]["last_poll"] = "tomorrow-ish"
        self.write(data)
        checked = self.run_cli("check", str(self.path), check=False)
        self.assertEqual(checked.returncode, 1)
        self.assertIn("last_poll", checked.stdout)

    def test_invalid_container_type_returns_structured_invalid_result(self):
        data = self.read()
        data["active_sessions"] = None
        self.write(data)
        checked = self.run_cli("check", str(self.path), check=False)
        self.assertEqual(checked.returncode, 1)
        self.assertIn('"valid": false', checked.stdout)

    def test_check_rejects_more_than_one_monitor_true_session(self):
        self.run_cli(
            "session", str(self.path), "--action", "add",
            "--session-id", "watch:1", "--purpose", "watchdog",
            "--state", "MONITOR_READY", "--monitor",
        )
        data = self.read()
        data["active_sessions"].append({
            "id": "watch:2", "purpose": "forged", "state": "MONITOR_READY",
            "last_poll": data["updated_at"], "monitor": True,
        })
        self.write(data)
        checked = self.run_cli("check", str(self.path), check=False)
        self.assertEqual(checked.returncode, 1)
        self.assertIn("exactly one", checked.stdout)

    def test_schema_v2_missing_monitor_flag_is_not_silently_migrated(self):
        self.add_worker()
        data = self.read()
        data["active_sessions"][0].pop("monitor")
        self.write(data)
        checked = self.run_cli("check", str(self.path), check=False)
        self.assertEqual(checked.returncode, 1)
        self.assertIn("monitor must be boolean", checked.stdout)

    def test_invalid_checkpoint_never_emits_monitor_ready(self):
        self.path.write_text("{broken", encoding="utf-8")
        before = self.path.read_bytes()
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "90", "--max-cycles", "1", check=False,
        )
        self.assertEqual(watched.returncode, 0)
        self.assertEqual(watched.stdout.count("MONITOR_READ_ERROR"), 1)
        self.assertNotIn("MONITOR_READY", watched.stdout)
        self.assertEqual(self.path.read_bytes(), before)

    def test_watch_survives_transient_json_corruption_after_ready(self):
        valid = self.path.read_bytes()
        process = subprocess.Popen(
            [
                "python3", str(SCRIPT), "watch", str(self.path),
                "--interval-seconds", "1", "--max-cycles", "4",
            ],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertIsNotNone(process.stdout)
        first = process.stdout.readline()
        self.assertIn("MONITOR_READY", first)
        self.path.write_text("{broken", encoding="utf-8")
        time.sleep(1.2)
        self.path.write_bytes(valid)
        stdout, stderr = process.communicate(timeout=6)
        output = first + stdout
        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(output.count("MONITOR_READY"), 1)
        self.assertEqual(output.count("MONITOR_READ_ERROR"), 1)
        self.assertEqual(output.count("MONITOR_READ_RECOVERED"), 1)
        self.assertIn("MONITOR_TEST_EXIT", output)

    def test_watch_never_overwrites_invalid_checkpoint(self):
        self.path.write_text("not-json-at-all", encoding="utf-8")
        before = self.path.read_bytes()
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--max-cycles", "2",
        )
        self.assertEqual(watched.stdout.count("MONITOR_READ_ERROR"), 1)
        self.assertEqual(self.path.read_bytes(), before)
        self.assertNotIn("MONITOR_ALARM", watched.stdout)
        self.assertNotIn("MONITOR_TERMINAL", watched.stdout)

    def test_watch_delays_ready_until_first_valid_checkpoint(self):
        valid = self.path.read_bytes()
        self.path.write_text("{broken", encoding="utf-8")
        process = subprocess.Popen(
            [
                "python3", str(SCRIPT), "watch", str(self.path),
                "--interval-seconds", "1", "--max-cycles", "3",
            ],
            text=True, stdout=subprocess.PIPE, stderr=subprocess.PIPE,
        )
        self.assertIsNotNone(process.stdout)
        first = process.stdout.readline()
        self.assertIn("MONITOR_READ_ERROR", first)
        self.assertNotIn("MONITOR_READY", first)
        self.path.write_bytes(valid)
        stdout, stderr = process.communicate(timeout=5)
        output = first + stdout
        self.assertEqual(process.returncode, 0, stderr)
        self.assertEqual(output.count("MONITOR_READ_RECOVERED"), 1)
        self.assertEqual(output.count("MONITOR_READY"), 1)
        self.assertLess(
            output.index("MONITOR_READ_RECOVERED"), output.index("MONITOR_READY"),
        )

    def test_aux_watchdog_final_keeps_primary_and_creates_no_monitor_exit_alarm(self):
        self.run_cli(
            "session", str(self.path), "--action", "add",
            "--session-id", "watch:primary", "--purpose", "watchdog",
            "--state", "MONITOR_READY", "--monitor",
        )
        self.run_cli(
            "session", str(self.path), "--action", "add",
            "--session-id", "luna:aux", "--purpose", "aux-watchdog",
            "--state", "running",
        )
        self.run_cli(
            "session", str(self.path), "--action", "remove",
            "--session-id", "luna:aux", "--state", "unexpected_exit",
            "--last-exit-code", "0", "--unexpected-exit",
        )
        data = self.read()
        self.assertEqual(data["monitor_agent"], "watch:primary")
        self.assertEqual(
            [item["id"] for item in data["active_sessions"]], ["watch:primary"],
        )
        self.assertEqual(data["alarm_events"], [])
        self.assertIsNone(data["monitor_exit_snapshot"])

    # 8. Alarm creation is persisted and idempotent across watcher restarts.
    def test_watch_persists_one_idempotent_alarm_across_restart(self):
        self.expire()
        first = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "90", "--max-cycles", "1",
        )
        self.assertIn("MONITOR_ALARM", first.stdout)
        alarm = self.read()["alarm_events"][0]
        second = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "90", "--max-cycles", "1",
        )
        data = self.read()
        self.assertEqual(data["monitor_alarm_count"], 1)
        self.assertEqual(len(data["alarm_events"]), 1)
        self.assertEqual(data["alarm_events"][0]["alarm_id"], alarm["alarm_id"])
        self.assertNotIn("MONITOR_ALARM", second.stdout)

    # 9. Two simultaneous watchers cannot lose or duplicate an alarm.
    def test_concurrent_alarm_writes_are_serialized(self):
        self.expire()
        command = (
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "90", "--max-cycles", "1",
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda _: self.run_cli(*command), range(2)))
        self.assertTrue(all(result.returncode == 0 for result in results))
        data = self.read()
        self.assertEqual(len(data["alarm_events"]), 1)
        self.assertEqual(data["monitor_alarm_count"], 1)

    def test_concurrent_alarm_and_heartbeat_have_no_lost_update(self):
        data = self.read()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        data["updated_at"] = utc_stamp(now - dt.timedelta(seconds=30))
        data["lease_expires_at"] = utc_stamp(now + dt.timedelta(seconds=60))
        self.write(data)
        watch = (
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "1", "--max-cycles", "1",
        )
        heartbeat = (
            "heartbeat", str(self.path), "--progress", "items=2",
        )
        with ThreadPoolExecutor(max_workers=2) as pool:
            watch_future = pool.submit(self.run_cli, *watch)
            beat_future = pool.submit(self.run_cli, *heartbeat, check=False)
            self.assertEqual(watch_future.result().returncode, 0)
            beat_result = beat_future.result()
        final = self.read()
        self.assertEqual(beat_result.returncode, 0)
        self.assertEqual(final["observable_progress"]["items"], 2)
        self.assertEqual(final["heartbeat_seq"], 2)
        self.assertEqual(final["alarm_events"], [])

    # 10. Recovery must bind an alarm and carry session evidence.
    def test_recover_binds_alarm_and_accepts_new_session_output(self):
        self.add_worker()
        alarm_id = self.alarm()
        wrong = self.run_cli(
            "recover", str(self.path), "--alarm-id", "alarm-wrong",
            "--evidence-type", "session-output", "--session-id", "worker:1",
            "--output-digest", SHA_A, "--result", "success",
            "--verified-action", "recovered", check=False,
        )
        self.assertNotEqual(wrong.returncode, 0)
        self.run_cli(
            "recover", str(self.path), "--alarm-id", alarm_id,
            "--evidence-type", "session-output", "--session-id", "worker:1",
            "--output-digest", SHA_A, "--result", "success",
            "--verified-action", "worker output verified", "--stage", "stage-2",
            "--next-action", "continue",
        )
        data = self.read()
        self.assertEqual(data["status"], "RUNNING")
        self.assertEqual(data["alarm_events"][0]["status"], "RECOVERED")
        self.assertEqual(data["recovery_attempt"], 1)
        self.assertEqual(data["stage"], "stage-2")

    # 11. A stage change does not reset recovery attempts.
    def test_stage_change_does_not_reset_recovery_attempts(self):
        self.add_worker()
        alarm_id = self.alarm()
        self.run_cli(
            "recover", str(self.path), "--alarm-id", alarm_id,
            "--evidence-type", "session-output", "--session-id", "worker:1",
            "--output-digest", SHA_A, "--result", "success",
            "--verified-action", "recovered", "--stage", "brand-new-stage",
        )
        self.run_cli(
            "heartbeat", str(self.path), "--stage", "another-stage",
            "--verified-action", "one more real step",
        )
        self.assertEqual(self.read()["recovery_attempt"], 1)

    # 12. Two failed recoveries are recorded, but automatic STOPPED waits for
    #     lease expiry plus the full recovery window.
    def test_two_failed_recovery_attempts_stop_only_after_deadline(self):
        self.add_worker()
        alarm_id = self.alarm()
        first = self.run_cli(
            "recover", str(self.path), "--alarm-id", alarm_id,
            "--evidence-type", "session-output", "--session-id", "worker:1",
            "--output-digest", SHA_A, "--result", "failure",
            "--verified-action", "restart failed once", check=False,
        )
        self.assertEqual(first.returncode, 2)
        second = self.run_cli(
            "recover", str(self.path), "--alarm-id", alarm_id,
            "--evidence-type", "session-output", "--session-id", "worker:1",
            "--output-digest", SHA_B, "--result", "failure",
            "--verified-action", "restart failed twice", check=False,
        )
        self.assertEqual(second.returncode, 2)
        running = self.read()
        self.assertEqual(running["status"], "RUNNING")
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        running["alarm_events"][0]["recovery_deadline_at"] = utc_stamp(
            now - dt.timedelta(seconds=1)
        )
        self.write(running)
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "600", "--max-cycles", "1",
        )
        self.assertIn("RECOVERY_EXHAUSTED", watched.stdout)
        data = self.read()
        self.assertEqual(data["status"], "STOPPED")
        self.assertEqual(data["recovery_attempt"], 2)
        self.assertEqual(data["recovery_failure_count"], 2)
        self.assertEqual(data["terminal_evidence"]["reason_code"],
                         "RECOVERY_EXHAUSTED")

    # 13. Missing the fixed 120-second main recovery SLA forces STOPPED.
    def test_recovery_sla_miss_auto_stops(self):
        alarm_id = self.alarm()
        data = self.read()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        data["alarm_events"][0]["recovery_deadline_at"] = utc_stamp(
            now - dt.timedelta(seconds=1)
        )
        self.write(data)
        result = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "90", "--max-cycles", "1",
        )
        stopped = self.read()
        self.assertIn("MAIN_RECOVERY_SLA_MISSED", result.stdout)
        self.assertEqual(stopped["status"], "STOPPED")
        self.assertEqual(stopped["terminal_evidence"]["alarm_id"], alarm_id)
        self.assertIsNotNone(stopped["monitor_exit_snapshot"])

    def test_monitor_exit_alarm_cannot_auto_stop_before_lease_expiry(self):
        self.run_cli(
            "session", str(self.path), "--action", "add",
            "--session-id", "watch:early", "--purpose", "watchdog",
            "--state", "MONITOR_READY", "--monitor",
        )
        self.run_cli(
            "session", str(self.path), "--action", "remove",
            "--session-id", "watch:early", "--state", "unexpected_exit",
            "--last-exit-code", "1", "--unexpected-exit",
        )
        data = self.read()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        lease_expiry = dt.datetime.strptime(
            data["lease_expires_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=dt.timezone.utc)
        recovery_deadline = dt.datetime.strptime(
            data["alarm_events"][0]["recovery_deadline_at"],
            "%Y-%m-%dT%H:%M:%SZ",
        ).replace(tzinfo=dt.timezone.utc)
        self.assertGreater(lease_expiry, now)
        self.assertGreaterEqual(
            (recovery_deadline - lease_expiry).total_seconds(), 120,
        )
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "600", "--max-cycles", "1",
        )
        self.assertNotIn("MAIN_RECOVERY_SLA_MISSED", watched.stdout)
        self.assertEqual(self.read()["status"], "RUNNING")

    def test_watch_sleeps_to_recovery_deadline_instead_of_full_interval(self):
        self.alarm()
        data = self.read()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        data["alarm_events"][0]["recovery_deadline_at"] = utc_stamp(
            now + dt.timedelta(seconds=1)
        )
        self.write(data)
        started = time.monotonic()
        result = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "10",
            "--stale-seconds", "90", "--max-cycles", "3",
        )
        elapsed = time.monotonic() - started
        self.assertLess(elapsed, 6.0)
        self.assertIn("MAIN_RECOVERY_SLA_MISSED", result.stdout)
        self.assertEqual(self.read()["status"], "STOPPED")

    # 14. COMPLETED rejects work sessions, pending calls, unresolved alarms,
    #     and boolean-only evidence; exact evidence succeeds.
    def test_completed_requires_clean_state_and_concrete_evidence(self):
        self.add_worker()
        blocked = self.run_cli(*self.completion_args(), check=False)
        self.assertNotEqual(blocked.returncode, 0)
        self.run_cli(
            "session", str(self.path), "--action", "remove",
            "--session-id", "worker:1", "--state", "completed",
            "--last-exit-code", "0",
        )
        flags_only = self.run_cli(
            "terminal", str(self.path), "--status", "COMPLETED", "--outcome", "done",
            "--plan-clear", "--deliverables-verified", "--links-ready", check=False,
        )
        self.assertNotEqual(flags_only.returncode, 0)
        self.run_cli(*self.completion_args())
        data = self.read()
        self.assertEqual(data["status"], "COMPLETED")
        evidence = data["terminal_evidence"]
        self.assertEqual(evidence["deliverables"][0]["sha256"], SHA_A)
        self.assertEqual(evidence["gates"]["visual_qa"], "passed")
        self.assertEqual(evidence["links"], ["sandbox:/candidate.docx"])

    def test_check_rejects_forged_minimal_completed_evidence(self):
        data = self.read()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        data["status"] = "COMPLETED"
        data["updated_at"] = utc_stamp(now)
        data["lease_expires_at"] = utc_stamp(now)
        data["terminal_evidence"] = {"status": "COMPLETED"}
        data["monitor_exit_snapshot"] = {
            "captured_at": utc_stamp(now), "reason": "forged",
            "monitor_agent": None, "active_sessions": [], "pending_tool": None,
        }
        self.write(data)
        checked = self.run_cli("check", str(self.path), check=False)
        self.assertEqual(checked.returncode, 1)
        self.assertIn("deliverable sha256", checked.stdout)

    def test_check_rejects_shape_only_completed_evidence(self):
        data = self.read()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        data["status"] = "COMPLETED"
        data["updated_at"] = utc_stamp(now)
        data["lease_expires_at"] = utc_stamp(now)
        data["terminal_evidence"] = {
            "status": "COMPLETED", "deliverables": [
                {"name": "ghost.docx", "sha256": SHA_A}
            ], "gates": {"visual": "passed"}, "links": ["x:ghost"],
        }
        data["monitor_exit_snapshot"] = {
            "captured_at": utc_stamp(now), "reason": "forged",
            "monitor_agent": None, "active_sessions": [], "pending_tool": None,
        }
        self.write(data)
        checked = self.run_cli("check", str(self.path), check=False)
        self.assertEqual(checked.returncode, 1)
        self.assertIn("recorded_at", checked.stdout)
        self.assertIn("ready links", checked.stdout)

    def test_completed_rejects_pending_tool_and_unresolved_alarm(self):
        self.run_cli(
            "prepare-tool", str(self.path), "--call-id", "call-pending",
            "--tool-name", "exec", "--args-digest", SHA_A,
        )
        pending = self.run_cli(*self.completion_args(), check=False)
        self.assertNotEqual(pending.returncode, 0)
        self.run_cli(
            "prepare-tool", str(self.path), "--action", "result",
            "--call-id", "call-pending", "--result-status", "success",
            "--result-digest", SHA_B,
        )
        self.alarm()
        unresolved = self.run_cli(*self.completion_args(), check=False)
        self.assertNotEqual(unresolved.returncode, 0)
        self.assertIn("alarm", unresolved.stderr)

    # 15. STOPPED needs structured restart evidence and snapshots sessions.
    def test_stopped_requires_full_evidence_and_preserves_session_snapshot(self):
        self.add_worker()
        incomplete = self.run_cli(
            "terminal", str(self.path), "--status", "STOPPED",
            "--outcome", "blocked", "--blocker", "need source",
            "--blocker-class", "missing_material", "--resume-token", "resume:1",
            check=False,
        )
        self.assertNotEqual(incomplete.returncode, 0)
        self.run_cli(
            "terminal", str(self.path), "--status", "STOPPED",
            "--outcome", "blocked", "--blocker", "need source",
            "--blocker-class", "missing_material", "--resume-token", "resume:1",
            "--last-completed-step", "page 20 audited",
            "--safe-artifact", "candidate-v6.3.docx",
            "--recovery-condition", "source supplied",
            "--next-action", "resume page 21",
        )
        data = self.read()
        self.assertEqual(data["status"], "STOPPED")
        evidence = data["terminal_evidence"]
        self.assertEqual(evidence["last_completed_step"], "page 20 audited")
        self.assertEqual(
            [session["id"] for session in evidence["session_snapshot"]],
            ["worker:1"],
        )
        self.assertEqual(data["active_sessions"], [])
        self.assertIsNotNone(data["monitor_exit_snapshot"])

    def test_check_rejects_shape_only_stopped_evidence(self):
        data = self.read()
        now = dt.datetime.now(dt.timezone.utc).replace(microsecond=0)
        data["status"] = "STOPPED"
        data["updated_at"] = utc_stamp(now)
        data["lease_expires_at"] = utc_stamp(now)
        data["next_action"] = "real next"
        data["resume_token"] = "real token"
        data["blocker"] = "real blocker"
        data["blocker_class"] = "missing_material"
        data["terminal_evidence"] = {
            "status": "STOPPED", "recorded_at": "", "blocker": "",
            "blocker_class": "nonsense", "resume_token": "wrong",
            "last_completed_step": "", "last_safe_artifact": "",
            "recovery_condition": "", "next_action": "wrong",
            "session_snapshot": [], "pending_tool_snapshot": None,
        }
        data["monitor_exit_snapshot"] = {
            "captured_at": utc_stamp(now), "reason": "forged",
            "monitor_agent": None, "active_sessions": [], "pending_tool": None,
        }
        self.write(data)
        checked = self.run_cli("check", str(self.path), check=False)
        self.assertEqual(checked.returncode, 1)
        self.assertIn("non-empty strings", checked.stdout)
        self.assertIn("blocker_class", checked.stdout)
        self.assertIn("resume_token", checked.stdout)

    def test_monitor_exit_snapshot_is_captured_before_monitor_removal(self):
        self.run_cli(
            "session", str(self.path), "--action", "add",
            "--session-id", "watch:1", "--purpose", "watchdog",
            "--state", "MONITOR_READY", "--monitor",
        )
        self.run_cli(
            "session", str(self.path), "--action", "remove",
            "--session-id", "watch:1", "--state", "unexpected_exit",
            "--last-exit-code", "1", "--unexpected-exit",
        )
        data = self.read()
        snapshot = data["monitor_exit_snapshot"]
        self.assertEqual(snapshot["monitor_agent"], "watch:1")
        self.assertEqual(
            [item["id"] for item in snapshot["active_sessions"]],
            ["watch:1"],
        )
        self.assertIsNone(data["monitor_agent"])
        self.assertEqual(data["alarm_events"][0]["reason"], "MONITOR_EXIT")

    def test_monitor_exit_alarm_allows_handshake_then_bound_recovery(self):
        self.run_cli(
            "session", str(self.path), "--action", "add",
            "--session-id", "watch:1", "--purpose", "watchdog",
            "--state", "MONITOR_READY", "--monitor",
        )
        self.run_cli(
            "session", str(self.path), "--action", "remove",
            "--session-id", "watch:1", "--state", "unexpected_exit",
            "--last-exit-code", "1", "--unexpected-exit",
        )
        alarm_id = self.read()["alarm_events"][0]["alarm_id"]
        seq = self.read()["heartbeat_seq"]
        self.run_cli(
            "session", str(self.path), "--action", "add",
            "--session-id", "watch:2", "--purpose", "replacement watchdog",
            "--state", "MONITOR_READY", "--monitor",
        )
        attached = self.read()
        self.assertEqual(attached["heartbeat_seq"], seq)
        self.assertEqual(attached["monitor_agent"], "watch:2")
        self.run_cli(
            "recover", str(self.path), "--alarm-id", alarm_id,
            "--evidence-type", "session-output", "--session-id", "watch:2",
            "--output-digest", SHA_A, "--result", "success",
            "--verified-action", "replacement monitor handshake verified",
        )
        recovered = self.read()
        self.assertEqual(recovered["alarm_events"][0]["status"], "RECOVERED")
        self.assertEqual(recovered["monitor_agent"], "watch:2")

    # 16. v1 migration adds structure only and never forges time/progress/session.
    def test_legacy_migration_is_deterministic_without_forged_progress(self):
        data = self.read()
        original_seq = data["heartbeat_seq"]
        original_updated = data["updated_at"]
        original_lease = data["lease_expires_at"]
        for field in (
            "schema_version", "pending_tool", "tool_call_history",
            "session_history", "alarm_events", "terminal_evidence",
            "monitor_exit_snapshot", "recovery_failure_count",
            "legacy_alarm_count",
        ):
            data.pop(field)
        raw = json.dumps(data)
        self.path.write_text(raw, encoding="utf-8")
        checked = self.run_cli("check", str(self.path), check=False)
        self.assertEqual(checked.returncode, 0)
        self.assertEqual(self.path.read_text(encoding="utf-8"), raw)
        self.run_cli(
            "heartbeat", str(self.path), "--progress", "items=2",
        )
        migrated = self.read()
        self.assertEqual(migrated["schema_version"], 2)
        self.assertEqual(migrated["heartbeat_seq"], original_seq + 1)
        self.assertNotEqual(migrated["updated_at"], "")
        self.assertEqual(migrated["active_sessions"], [])
        self.assertGreaterEqual(migrated["updated_at"], original_updated)
        migrated_expiry = dt.datetime.strptime(
            migrated["lease_expires_at"], "%Y-%m-%dT%H:%M:%SZ"
        ).replace(tzinfo=dt.timezone.utc)
        self.assertLessEqual(
            migrated_expiry,
            dt.datetime.now(dt.timezone.utc) + dt.timedelta(seconds=600),
        )

    def test_legacy_unstructured_alarm_count_is_preserved(self):
        data = self.read()
        for field in (
            "schema_version", "pending_tool", "tool_call_history",
            "session_history", "alarm_events", "terminal_evidence",
            "monitor_exit_snapshot", "recovery_failure_count",
            "legacy_alarm_count",
        ):
            data.pop(field)
        data["monitor_alarm_count"] = 2
        self.write(data)
        self.run_cli("heartbeat", str(self.path), "--progress", "items=2")
        migrated = self.read()
        self.assertEqual(migrated["legacy_alarm_count"], 2)
        self.assertEqual(migrated["monitor_alarm_count"], 2)
        self.assertEqual(migrated["alarm_events"], [])

    def test_rev7_alarm_migration_preserves_post_alarm_session_evidence(self):
        self.add_worker()
        self.alarm()
        data = self.read()
        alarm = data["alarm_events"][0]
        for field in (
            "session_history_length", "artifact_delta_length", "recovery_evidence",
        ):
            alarm.pop(field)
        self.write(data)
        self.run_cli(
            "session", str(self.path), "--action", "poll",
            "--session-id", "worker:1", "--state", "produced-output",
            "--output-digest", SHA_A,
        )
        watched = self.run_cli(
            "watch", str(self.path), "--interval-seconds", "1",
            "--stale-seconds", "600", "--max-cycles", "1",
        )
        self.assertIn("MONITOR_RECOVERED", watched.stdout)
        self.assertEqual(self.read()["status"], "RUNNING")

    # 17. Concurrent session writes are not lost.
    def test_concurrent_session_adds_do_not_lose_updates(self):
        commands = [
            (
                "session", str(self.path), "--action", "add",
                "--session-id", session_id, "--purpose", session_id,
                "--state", "running",
            )
            for session_id in ("worker:a", "worker:b")
        ]
        with ThreadPoolExecutor(max_workers=2) as pool:
            results = list(pool.map(lambda cmd: self.run_cli(*cmd), commands))
        self.assertTrue(all(result.returncode == 0 for result in results))
        data = self.read()
        self.assertEqual(
            {item["id"] for item in data["active_sessions"]},
            {"worker:a", "worker:b"},
        )
        self.assertEqual(data["heartbeat_seq"], 3)

    # 18. End-to-end tool lifecycle leaves a terminal audit trail.
    def test_end_to_end_tool_session_and_completion_audit_trail(self):
        self.add_worker("exec:render")
        self.run_cli(
            "prepare-tool", str(self.path), "--call-id", "render-1",
            "--tool-name", "render_docx", "--args-digest", SHA_A,
        )
        seq = self.read()["heartbeat_seq"]
        self.run_cli(
            "session", str(self.path), "--action", "poll",
            "--session-id", "exec:render", "--state", "running",
        )
        self.assertEqual(self.read()["heartbeat_seq"], seq)
        self.run_cli(
            "session", str(self.path), "--action", "poll",
            "--session-id", "exec:render", "--state", "completed",
            "--output-digest", SHA_B, "--last-exit-code", "0",
        )
        self.run_cli(
            "prepare-tool", str(self.path), "--action", "result",
            "--call-id", "render-1", "--result-status", "success",
            "--result-digest", SHA_C, "--last-exit-code", "0",
        )
        self.run_cli(
            "session", str(self.path), "--action", "remove",
            "--session-id", "exec:render", "--state", "completed",
            "--last-exit-code", "0",
        )
        self.run_cli(*self.completion_args())
        data = self.read()
        self.assertEqual(data["status"], "COMPLETED")
        self.assertEqual(
            [event["event"] for event in data["tool_call_history"]],
            ["PREPARED", "RESULT"],
        )
        self.assertTrue(any(
            event["event"] == "POLL_PROGRESS"
            for event in data["session_history"]
        ))


if __name__ == "__main__":
    unittest.main()
