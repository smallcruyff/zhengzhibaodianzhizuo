#!/usr/bin/env python3
"""Durable, evidence-gated checkpoints for long-running work (schema v2)."""

from __future__ import annotations

import argparse
import contextlib
import copy
import datetime as dt
import fcntl
import hashlib
import json
import os
import re
import sys
import tempfile
import time
from pathlib import Path

SCHEMA_VERSION = 2
MAX_LEASE_SECONDS = 600
DEFAULT_LEASE_SECONDS = 600
RECOVERY_SLA_SECONDS = 120
STATUSES = {"RUNNING", "COMPLETED", "STOPPED"}
ALARM_STATUSES = {"OPEN", "RECOVERED", "STOPPED"}
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REQUIRED = {
    "schema_version", "task_id", "status", "stage", "heartbeat_seq",
    "last_verified_action", "next_action", "observable_progress",
    "artifact_delta", "active_sessions", "last_session_poll",
    "last_exit_code", "monitor_agent", "monitor_alarm_count",
    "recovery_attempt", "recovery_failure_count", "updated_at",
    "lease_expires_at", "resume_token", "pending_tool",
    "tool_call_history", "session_history", "alarm_events",
    "terminal_evidence", "monitor_exit_snapshot",
}


def utcnow() -> dt.datetime:
    return dt.datetime.now(dt.timezone.utc).replace(microsecond=0)


def stamp(value: dt.datetime) -> str:
    return value.astimezone(dt.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")


def parse_stamp(value: str) -> dt.datetime:
    return dt.datetime.strptime(value, "%Y-%m-%dT%H:%M:%SZ").replace(
        tzinfo=dt.timezone.utc
    )


def is_sha256(value: object) -> bool:
    return isinstance(value, str) and bool(SHA256_RE.fullmatch(value))


def migrate_legacy(raw: dict) -> dict:
    """Add only structural defaults; never invent progress, time, or sessions."""
    data = copy.deepcopy(raw)
    version = data.get("schema_version", 1)
    if not isinstance(version, int) or version > SCHEMA_VERSION:
        raise ValueError(f"unsupported schema_version: {version}")
    if version < 2:
        data["schema_version"] = SCHEMA_VERSION
        data.setdefault("pending_tool", None)
        data.setdefault("tool_call_history", [])
        data.setdefault("session_history", [])
        data.setdefault("alarm_events", [])
        data.setdefault("terminal_evidence", None)
        data.setdefault("monitor_exit_snapshot", None)
        data.setdefault("recovery_failure_count", 0)
        # Preserve unstructured v1 alarm counts without inventing alarm events.
        data.setdefault(
            "legacy_alarm_count", int(data.get("monitor_alarm_count", 0) or 0)
        )
        monitor_agent = data.get("monitor_agent")
        sessions = data.get("active_sessions")
        if isinstance(sessions, list):
            for session in sessions:
                if isinstance(session, dict) and "monitor" not in session:
                    session["monitor"] = bool(
                        monitor_agent is not None and session.get("id") == monitor_agent
                    )
    # Revision 8 keeps schema v2, but persisted alarms created by earlier
    # revisions do not have every evidence-boundary field below.  Add only
    # conservative structural defaults: timestamped histories start at the
    # first unambiguously post-alarm event, while untimestamped artifact paths
    # start at their current length.
    alarms = data.get("alarm_events")
    if isinstance(alarms, list):
        tool_history = data.get("tool_call_history", [])
        if not isinstance(tool_history, list):
            tool_history = []
        session_history = data.get("session_history", [])
        if not isinstance(session_history, list):
            session_history = []
        artifact_length = len(data.get("artifact_delta", [])) if isinstance(
            data.get("artifact_delta"), list
        ) else 0
        for alarm in alarms:
            if isinstance(alarm, dict):
                created_at = alarm.get("created_at")
                evidence_start = (
                    alarm.get("lease_expires_at")
                    if alarm.get("reason") == "LEASE_EXPIRED"
                    else created_at
                )
                if not _valid_stamp(evidence_start):
                    evidence_start = created_at
                alarm.setdefault("evidence_window_start_at", evidence_start)
                alarm.setdefault(
                    "tool_history_length",
                    _history_boundary_at_alarm(tool_history, evidence_start),
                )
                alarm.setdefault(
                    "session_history_length",
                    _history_boundary_at_alarm(session_history, evidence_start),
                )
                alarm.setdefault("artifact_delta_length", artifact_length)
                alarm.setdefault("recovery_evidence", [])
    return data


def _history_boundary_at_alarm(
    history: list, created_at: object, *, inclusive: bool = False,
) -> int:
    """Locate the first unambiguously post-alarm event in old history."""
    if not _valid_stamp(created_at):
        return len(history)
    alarm_time = parse_stamp(created_at)  # type: ignore[arg-type]
    for index, item in enumerate(history):
        if not isinstance(item, dict) or not _valid_stamp(item.get("at")):
            continue
        # Old checkpoints only have second-resolution timestamps.  Treat an
        # equal-second event as pre-alarm so migration cannot manufacture live
        # evidence from an ambiguous historical record.
        item_time = parse_stamp(item["at"])
        if item_time > alarm_time or (inclusive and item_time == alarm_time):
            return index
    return len(history)


def load(path: Path) -> dict:
    with path.open("r", encoding="utf-8") as handle:
        raw = json.load(handle)
    if not isinstance(raw, dict):
        raise ValueError("checkpoint root must be an object")
    return migrate_legacy(raw)


def atomic_write(path: Path, data: dict) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(prefix=f".{path.name}.", dir=path.parent)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as handle:
            json.dump(data, handle, ensure_ascii=False, indent=2)
            handle.write("\n")
            handle.flush()
            os.fsync(handle.fileno())
        os.replace(tmp_name, path)
        dir_fd = os.open(path.parent, os.O_RDONLY)
        try:
            os.fsync(dir_fd)
        finally:
            os.close(dir_fd)
    finally:
        if os.path.exists(tmp_name):
            os.unlink(tmp_name)


@contextlib.contextmanager
def checkpoint_lock(path: Path):
    path.parent.mkdir(parents=True, exist_ok=True)
    lock_path = path.parent / f".{path.name}.lock"
    with lock_path.open("a", encoding="utf-8") as handle:
        fcntl.flock(handle.fileno(), fcntl.LOCK_EX)
        try:
            yield
        finally:
            fcntl.flock(handle.fileno(), fcntl.LOCK_UN)


def _valid_stamp(value: object, optional: bool = False) -> bool:
    if optional and value is None:
        return True
    try:
        parse_stamp(value)  # type: ignore[arg-type]
        return True
    except (TypeError, ValueError):
        return False


def unresolved_alarms(data: dict) -> list[dict]:
    events = data.get("alarm_events", [])
    if not isinstance(events, list):
        return []
    return [
        item for item in events
        if isinstance(item, dict) and item.get("status") == "OPEN"
    ]


def validate(data: dict) -> list[str]:
    errors: list[str] = []
    missing = sorted(REQUIRED - data.keys())
    if missing:
        errors.append("missing fields: " + ", ".join(missing))
    if data.get("schema_version") != SCHEMA_VERSION:
        errors.append(f"schema_version must be {SCHEMA_VERSION}")
    if data.get("status") not in STATUSES:
        errors.append("invalid status")
    if not isinstance(data.get("heartbeat_seq"), int) or data.get("heartbeat_seq", 0) < 1:
        errors.append("heartbeat_seq must be a positive integer")
    for field, expected in (
        ("observable_progress", dict), ("artifact_delta", list),
        ("active_sessions", list), ("tool_call_history", list),
        ("session_history", list), ("alarm_events", list),
    ):
        if not isinstance(data.get(field), expected):
            errors.append(f"{field} must be an {expected.__name__}")
    for field in ("monitor_alarm_count", "recovery_attempt", "recovery_failure_count"):
        if not isinstance(data.get(field), int) or data.get(field, -1) < 0:
            errors.append(f"{field} must be a non-negative integer")
    legacy_alarm_count = data.get("legacy_alarm_count", 0)
    if not isinstance(legacy_alarm_count, int) or legacy_alarm_count < 0:
        errors.append("legacy_alarm_count must be a non-negative integer")

    active_sessions = data.get("active_sessions", [])
    if not isinstance(active_sessions, list):
        active_sessions = []
    session_ids = []
    for index, session in enumerate(active_sessions):
        if not isinstance(session, dict):
            errors.append(f"active_sessions[{index}] must be an object")
            continue
        if not all(session.get(key) for key in ("id", "purpose", "state")):
            errors.append(f"active_sessions[{index}] must contain id, purpose, and state")
        if not isinstance(session.get("monitor"), bool):
            errors.append(f"active_sessions[{index}].monitor must be boolean")
        if not _valid_stamp(session.get("last_poll")):
            errors.append(f"active_sessions[{index}].last_poll must be a UTC timestamp")
        if session.get("last_output_digest") is not None and not is_sha256(
            session.get("last_output_digest")
        ):
            errors.append(f"active_sessions[{index}].last_output_digest must be sha256")
        if session.get("id"):
            session_ids.append(session["id"])
    if len(session_ids) != len(set(session_ids)):
        errors.append("active_sessions ids must be unique")
    monitor_agent = data.get("monitor_agent")
    monitor_sessions = [
        item for item in active_sessions
        if isinstance(item, dict) and item.get("monitor") is True
    ]
    if monitor_agent is not None:
        monitors = [
            item for item in active_sessions
            if isinstance(item, dict)
            and item.get("id") == monitor_agent
            and item.get("monitor") is True
        ]
        if len(monitors) != 1 or len(monitor_sessions) != 1:
            errors.append("monitor_agent must name exactly one registered monitor session")
    elif monitor_sessions:
        errors.append("monitor=true session requires monitor_agent")

    pending = data.get("pending_tool")
    if pending is not None:
        if not isinstance(pending, dict) or not all(
            pending.get(key)
            for key in ("call_id", "tool_name", "args_digest", "prepared_at")
        ):
            errors.append("pending_tool must contain call_id, tool_name, args_digest, prepared_at")
        else:
            if not is_sha256(pending.get("args_digest")):
                errors.append("pending_tool.args_digest must be sha256")
            if not _valid_stamp(pending.get("prepared_at")):
                errors.append("pending_tool.prepared_at must be a UTC timestamp")
    tool_history = data.get("tool_call_history", [])
    if not isinstance(tool_history, list):
        tool_history = []
    for index, item in enumerate(tool_history):
        if not isinstance(item, dict) or not all(
            item.get(key) for key in ("event", "call_id", "at")
        ):
            errors.append(f"tool_call_history[{index}] is invalid")
        elif not _valid_stamp(item.get("at")):
            errors.append(f"tool_call_history[{index}].at must be a UTC timestamp")
    session_history = data.get("session_history", [])
    if not isinstance(session_history, list):
        session_history = []
    for index, item in enumerate(session_history):
        if not isinstance(item, dict) or not all(
            item.get(key) for key in ("event", "session_id", "at")
        ):
            errors.append(f"session_history[{index}] is invalid")
        elif not _valid_stamp(item.get("at")):
            errors.append(f"session_history[{index}].at must be a UTC timestamp")
    alarm_ids = []
    alarm_required = {
        "alarm_id", "alarm_key", "created_at", "recovery_deadline_at",
        "evidence_window_start_at",
        "heartbeat_seq", "stage", "lease_expires_at", "resume_token",
        "reason", "status", "recovery_attempts", "tool_history_length",
        "session_history_length", "artifact_delta_length", "recovery_evidence",
    }
    alarm_events = data.get("alarm_events", [])
    if not isinstance(alarm_events, list):
        alarm_events = []
    for index, alarm in enumerate(alarm_events):
        if not isinstance(alarm, dict) or not alarm_required.issubset(alarm):
            errors.append(f"alarm_events[{index}] is invalid")
            continue
        alarm_ids.append(alarm["alarm_id"])
        if alarm.get("status") not in ALARM_STATUSES:
            errors.append(f"alarm_events[{index}].status is invalid")
        if not isinstance(alarm.get("recovery_attempts"), list):
            errors.append(f"alarm_events[{index}].recovery_attempts must be an array")
        if (
            not isinstance(alarm.get("tool_history_length"), int)
            or alarm.get("tool_history_length", -1) < 0
            or alarm.get("tool_history_length", 0) > len(tool_history)
        ):
            errors.append(
                f"alarm_events[{index}].tool_history_length must be within history"
            )
        artifact_history = data.get("artifact_delta", [])
        if not isinstance(artifact_history, list):
            artifact_history = []
        for key, history in (
            ("session_history_length", session_history),
            ("artifact_delta_length", artifact_history),
        ):
            if (
                not isinstance(alarm.get(key), int)
                or alarm.get(key, -1) < 0
                or alarm.get(key, 0) > len(history)
            ):
                errors.append(f"alarm_events[{index}].{key} must be within history")
        evidence_items = alarm.get("recovery_evidence")
        if not isinstance(evidence_items, list):
            errors.append(f"alarm_events[{index}].recovery_evidence must be an array")
        else:
            for evidence_index, evidence in enumerate(evidence_items):
                if not isinstance(evidence, dict) or not all(
                    evidence.get(key) for key in ("type", "at")
                ):
                    errors.append(
                        f"alarm_events[{index}].recovery_evidence[{evidence_index}] "
                        "is invalid"
                    )
                elif not _valid_stamp(evidence.get("at")):
                    errors.append(
                        f"alarm_events[{index}].recovery_evidence[{evidence_index}].at "
                        "must be a UTC timestamp"
                    )
                elif evidence.get("type") != "artifact-delta" or not (
                    isinstance(evidence.get("artifact"), str)
                    and evidence.get("artifact")
                    and isinstance(evidence.get("resolved_path"), str)
                    and evidence.get("resolved_path")
                    and isinstance(evidence.get("size"), int)
                    and evidence.get("size", -1) >= 0
                    and isinstance(evidence.get("mtime_ns"), int)
                    and evidence.get("mtime_ns", -1) >= 0
                    and is_sha256(evidence.get("sha256"))
                ):
                    errors.append(
                        f"alarm_events[{index}].recovery_evidence[{evidence_index}] "
                        "must contain verified artifact metadata"
                    )
                elif (
                    _valid_stamp(alarm.get("created_at"))
                    and _valid_stamp(alarm.get("recovery_deadline_at"))
                    and not (
                        parse_stamp(alarm["evidence_window_start_at"])
                        <= parse_stamp(evidence["at"])
                        <= parse_stamp(alarm["recovery_deadline_at"])
                    )
                ):
                    errors.append(
                        f"alarm_events[{index}].recovery_evidence[{evidence_index}] "
                        "must fall inside the recovery window"
                    )
        for key in (
            "created_at", "evidence_window_start_at",
            "recovery_deadline_at", "lease_expires_at",
        ):
            if not _valid_stamp(alarm.get(key)):
                errors.append(f"alarm_events[{index}].{key} must be a UTC timestamp")
        if (
            _valid_stamp(alarm.get("evidence_window_start_at"))
            and _valid_stamp(alarm.get("recovery_deadline_at"))
            and parse_stamp(alarm["evidence_window_start_at"])
            > parse_stamp(alarm["recovery_deadline_at"])
        ):
            errors.append(
                f"alarm_events[{index}] recovery window must not be negative"
            )
    if len(alarm_ids) != len(set(alarm_ids)):
        errors.append("alarm ids must be unique")
    if data.get("monitor_alarm_count") != (
        legacy_alarm_count + len(alarm_events)
    ):
        errors.append("monitor_alarm_count must equal legacy plus persisted alarm count")
    if not _valid_stamp(data.get("last_session_poll"), optional=True):
        errors.append("last_session_poll must be null or a UTC timestamp")
    try:
        updated = parse_stamp(data["updated_at"])
        expires = parse_stamp(data["lease_expires_at"])
        if data.get("status") == "RUNNING" and not (
            updated < expires <= updated + dt.timedelta(seconds=MAX_LEASE_SECONDS)
        ):
            errors.append(
                f"RUNNING lease must be 1-{MAX_LEASE_SECONDS} seconds"
            )
        if data.get("status") in {"COMPLETED", "STOPPED"} and expires != updated:
            errors.append("terminal lease_expires_at must equal updated_at")
    except (KeyError, TypeError, ValueError):
        errors.append("invalid UTC timestamp")

    terminal = data.get("terminal_evidence")
    if data.get("status") in {"COMPLETED", "STOPPED"}:
        if data.get("active_sessions") or monitor_agent is not None:
            errors.append("terminal checkpoint requires cleared sessions and monitor_agent")
        if data.get("pending_tool") is not None:
            errors.append("terminal checkpoint requires pending_tool to be null")
        if not isinstance(terminal, dict) or terminal.get("status") != data.get("status"):
            errors.append("terminal checkpoint requires matching terminal_evidence")
        elif data.get("status") == "COMPLETED":
            deliverables = terminal.get("deliverables")
            gates = terminal.get("gates")
            links = terminal.get("links")
            if not _valid_stamp(terminal.get("recorded_at")):
                errors.append("COMPLETED evidence requires recorded_at")
            if not isinstance(terminal.get("outcome"), str) or not terminal.get("outcome"):
                errors.append("COMPLETED evidence requires outcome")
            if terminal.get("plan_clear") is not True:
                errors.append("COMPLETED evidence requires plan_clear=true")
            if not isinstance(deliverables, list) or not deliverables or not all(
                isinstance(item, dict)
                and bool(item.get("name"))
                and is_sha256(item.get("sha256"))
                for item in deliverables
            ):
                errors.append("COMPLETED evidence requires deliverable sha256 values")
            if not isinstance(gates, dict) or not gates or not all(
                value == "passed" for value in gates.values()
            ):
                errors.append("COMPLETED evidence requires passed gates")
            if not isinstance(links, list) or not links or not all(
                valid_ready_link(link) for link in links
            ):
                errors.append("COMPLETED evidence requires ready links")
            if not isinstance(terminal.get("session_snapshot"), list):
                errors.append("COMPLETED evidence requires session_snapshot")
            if terminal.get("pending_tool_snapshot") is not None:
                errors.append("COMPLETED evidence requires null pending snapshot")
            if terminal.get("unresolved_alarm_ids") != []:
                errors.append("COMPLETED evidence requires no unresolved alarm ids")
            if unresolved_alarms(data):
                errors.append("COMPLETED cannot retain unresolved alarms")
        else:
            stopped_strings = (
                "blocker", "resume_token", "last_completed_step",
                "recovery_condition", "next_action",
            )
            if not _valid_stamp(terminal.get("recorded_at")):
                errors.append("STOPPED evidence requires recorded_at")
            if not all(
                isinstance(terminal.get(key), str) and bool(terminal.get(key))
                for key in stopped_strings
            ):
                errors.append("STOPPED terminal_evidence requires non-empty strings")
            if terminal.get("blocker_class") not in {
                "permission", "missing_material", "user_decision",
                "unrecoverable_error", "recovery_exhausted",
            }:
                errors.append("STOPPED blocker_class is invalid")
            if not terminal.get("last_safe_artifact"):
                errors.append("STOPPED evidence requires last_safe_artifact")
            if terminal.get("resume_token") != data.get("resume_token"):
                errors.append("STOPPED resume_token must match checkpoint")
            if terminal.get("next_action") != data.get("next_action"):
                errors.append("STOPPED next_action must match checkpoint")
            stopped_sessions = terminal.get("session_snapshot")
            if not isinstance(stopped_sessions, list):
                errors.append("STOPPED session_snapshot must be an array")
            elif not all(
                isinstance(item, dict)
                and all(item.get(key) for key in ("id", "purpose", "state"))
                and isinstance(item.get("monitor"), bool)
                for item in stopped_sessions
            ):
                errors.append("STOPPED session_snapshot entries are invalid")
            if "pending_tool_snapshot" not in terminal:
                errors.append("STOPPED evidence requires pending_tool_snapshot")
        snapshot = data.get("monitor_exit_snapshot")
        if not isinstance(snapshot, dict) or not _valid_stamp(snapshot.get("captured_at")):
            errors.append("terminal checkpoint requires monitor_exit_snapshot")
        elif (
            "monitor_agent" not in snapshot
            or not isinstance(snapshot.get("active_sessions"), list)
            or "pending_tool" not in snapshot
        ):
            errors.append("monitor_exit_snapshot is incomplete")
        if isinstance(terminal, dict):
            if terminal.get("recorded_at") != data.get("updated_at"):
                errors.append("terminal recorded_at must match checkpoint updated_at")
            if data.get("status") == "COMPLETED" and (
                terminal.get("outcome") != data.get("last_verified_action")
            ):
                errors.append("COMPLETED outcome must match last_verified_action")
            if data.get("status") == "STOPPED" and (
                terminal.get("blocker") != data.get("blocker")
                or terminal.get("blocker_class") != data.get("blocker_class")
            ):
                errors.append("STOPPED blocker fields must match checkpoint")
    elif terminal is not None:
        errors.append("RUNNING terminal_evidence must be null")
    return errors


def parse_progress(items: list[str]) -> dict:
    result: dict[str, int | float | str] = {}
    for item in items:
        if "=" not in item:
            raise ValueError(f"progress must be key=value: {item}")
        key, raw = item.split("=", 1)
        if not key:
            raise ValueError("progress key cannot be empty")
        try:
            value: int | float | str = int(raw)
        except ValueError:
            try:
                value = float(raw)
            except ValueError:
                value = raw
        result[key] = value
    return result


def ensure_running(data: dict) -> None:
    if data.get("status") != "RUNNING":
        raise ValueError("operation requires RUNNING")


def ensure_renewable(data: dict, now: dt.datetime) -> None:
    ensure_running(data)
    if parse_stamp(data["lease_expires_at"]) <= now:
        raise ValueError("lease expired; use recover with a persisted alarm")
    if unresolved_alarms(data):
        raise ValueError("unresolved monitor alarm; use recover --alarm-id")


def advance(
    data: dict, now: dt.datetime, action: str, lease_seconds: int,
    next_action: str | None = None,
) -> None:
    # heartbeat_seq supplies strict event ordering.  Never push the wall-clock
    # lease into the future merely because several real events share a second.
    prior = parse_stamp(data["updated_at"])
    effective_now = max(now, prior)
    data["heartbeat_seq"] = int(data["heartbeat_seq"]) + 1
    data["last_verified_action"] = action
    if next_action:
        data["next_action"] = next_action
    data["updated_at"] = stamp(effective_now)
    data["lease_expires_at"] = stamp(
        effective_now + dt.timedelta(seconds=lease_seconds)
    )


def write_valid(path: Path, data: dict) -> None:
    errors = validate(data)
    if errors:
        raise ValueError("; ".join(errors))
    atomic_write(path, data)


def command_init(args: argparse.Namespace) -> int:
    if args.path.exists():
        raise ValueError("init refuses to overwrite an existing checkpoint")
    if args.monitor_agent:
        raise ValueError(
            "init refuses --monitor-agent; register a live monitor with session add"
        )
    now = utcnow()
    data = {
        "schema_version": 2, "task_id": args.task_id, "status": "RUNNING",
        "stage": args.stage, "heartbeat_seq": 1,
        "last_verified_action": args.verified_action,
        "next_action": args.next_action,
        "observable_progress": parse_progress(args.progress),
        "artifact_delta": [], "active_sessions": [],
        "last_session_poll": None, "last_exit_code": None,
        "monitor_agent": None, "monitor_alarm_count": 0,
        "legacy_alarm_count": 0,
        "recovery_attempt": 0, "recovery_failure_count": 0,
        "updated_at": stamp(now),
        "lease_expires_at": stamp(now + dt.timedelta(seconds=args.lease_seconds)),
        "resume_token": args.resume_token, "pending_tool": None,
        "tool_call_history": [], "session_history": [], "alarm_events": [],
        "terminal_evidence": None, "monitor_exit_snapshot": None,
    }
    write_valid(args.path, data)
    print(json.dumps({
        "status": "RUNNING", "schema_version": 2,
        "lease_expires_at": data["lease_expires_at"],
    }))
    return 0


def command_heartbeat(args: argparse.Namespace) -> int:
    data = load(args.path)
    now = utcnow()
    ensure_running(data)
    if args.recovery:
        raise ValueError("--recovery is obsolete; use recover --alarm-id")
    progress = parse_progress(args.progress)
    changed_action = bool(
        args.verified_action and args.verified_action != data.get("last_verified_action")
    )
    changed_progress = any(
        data.get("observable_progress", {}).get(k) != v for k, v in progress.items()
    )
    artifact_candidates = list(dict.fromkeys(args.artifact))
    new_artifacts = [
        item for item in artifact_candidates if item not in data["artifact_delta"]
    ]
    open_alarms = unresolved_alarms(data)
    lease_expired = parse_stamp(data["lease_expires_at"]) <= now
    if lease_expired or open_alarms:
        if lease_expired and not open_alarms:
            alarm, _ = create_alarm(data, now, "LEASE_EXPIRED")
            open_alarms = [alarm]
        if len(open_alarms) != 1:
            raise ValueError(
                "expired or alarmed heartbeat requires exactly one persisted alarm"
            )
        alarm = open_alarms[0]
        if parse_stamp(alarm["recovery_deadline_at"]) < now:
            raise ValueError("recovery evidence deadline expired")
        if changed_action or changed_progress or args.session_poll:
            raise ValueError(
                "open alarm accepts only a newly changed, verifiable artifact; "
                "use registered session/tool evidence for other recovery"
            )
        if not artifact_candidates:
            raise ValueError("alarm recovery requires a changed verifiable artifact")
        for artifact in artifact_candidates:
            record_artifact_recovery_evidence(data, alarm, artifact, now)
        data["artifact_delta"].extend(new_artifacts)
        write_valid(args.path, data)
        print(json.dumps({
            "status": "RUNNING", "heartbeat_seq": data["heartbeat_seq"],
            "renewed": False, "recovery_evidence": "artifact-delta",
            "alarm_id": alarm["alarm_id"],
        }))
        return 0
    ensure_renewable(data, now)
    session_changed = False
    polled_session = None
    polled_state = None
    if args.session_poll:
        if "=" not in args.session_poll:
            raise ValueError("session poll must be SESSION_ID=NEW_STATE")
        session_id, polled_state = args.session_poll.split("=", 1)
        polled_session = next(
            (item for item in data["active_sessions"] if item.get("id") == session_id),
            None,
        )
        if polled_session is None:
            raise ValueError("session poll requires a registered active session")
        session_changed = bool(polled_state and polled_state != polled_session.get("state"))
        if not session_changed:
            raise ValueError("same-state poll is observation only; use session --action poll")
    if not (changed_action or changed_progress or new_artifacts or session_changed):
        raise ValueError("lease renewal requires verifiable progress")
    if args.stage:
        data["stage"] = args.stage
    if args.resume_token:
        data["resume_token"] = args.resume_token
    data["observable_progress"].update(progress)
    data["artifact_delta"].extend(new_artifacts)
    if polled_session is not None:
        polled_session["state"] = polled_state
        polled_session["last_poll"] = stamp(now)
        data["last_session_poll"] = stamp(now)
        data["session_history"].append({
            "event": "STATE_CHANGE", "session_id": polled_session["id"],
            "at": stamp(now), "state": polled_state,
        })
    if args.last_exit_code is not None:
        data["last_exit_code"] = args.last_exit_code
    action = args.verified_action or (
        f"session {polled_session['id']} changed to {polled_state}"
        if polled_session else "observable progress changed"
    )
    advance(data, now, action, args.lease_seconds, args.next_action)
    write_valid(args.path, data)
    print(json.dumps({
        "status": "RUNNING", "heartbeat_seq": data["heartbeat_seq"],
        "lease_expires_at": data["lease_expires_at"],
    }))
    return 0


def _history_result(data: dict, call_id: str) -> dict | None:
    return next((
        item for item in reversed(data["tool_call_history"])
        if item.get("call_id") == call_id and item.get("event") == "RESULT"
    ), None)


def command_prepare_tool(args: argparse.Namespace) -> int:
    data = load(args.path)
    now = utcnow()
    ensure_running(data)
    renewed = False
    if args.action == "prepare":
        recovery_alarm = None
        lease_or_alarm_blocks = (
            parse_stamp(data["lease_expires_at"]) <= now
            or bool(unresolved_alarms(data))
        )
        if lease_or_alarm_blocks:
            open_alarms = unresolved_alarms(data)
            if len(open_alarms) != 1:
                raise ValueError(
                    "recovery probe requires exactly one persisted open alarm"
                )
            candidate = open_alarms[0]
            if parse_stamp(candidate["recovery_deadline_at"]) <= now:
                raise ValueError("recovery probe deadline expired")
            if not args.call_id.startswith("recovery-"):
                raise ValueError(
                    "expired lease permits only a recovery-* idempotent probe"
                )
            recovery_alarm = candidate
        else:
            ensure_renewable(data, now)
        if not args.tool_name or not is_sha256(args.args_digest):
            raise ValueError("prepare requires --tool-name and sha256 --args-digest")
        proposed = {
            "call_id": args.call_id, "tool_name": args.tool_name,
            "args_digest": args.args_digest,
        }
        pending = data["pending_tool"]
        if pending is not None:
            if all(pending.get(k) == v for k, v in proposed.items()):
                print(json.dumps({
                    "status": "RUNNING", "pending_tool": args.call_id,
                    "idempotent": True,
                }))
                return 0
            raise ValueError("another tool call is already pending")
        if any(item.get("call_id") == args.call_id for item in data["tool_call_history"]):
            raise ValueError("call_id reuse is forbidden after a recorded tool event")
        data["pending_tool"] = {
            **proposed,
            "prepared_at": stamp(now),
            "recovery_alarm_id": (
                recovery_alarm["alarm_id"] if recovery_alarm is not None else None
            ),
        }
        data["tool_call_history"].append({
            "event": "PREPARED", "call_id": args.call_id,
            "tool_name": args.tool_name, "args_digest": args.args_digest,
            "at": stamp(now),
            "recovery_alarm_id": (
                recovery_alarm["alarm_id"] if recovery_alarm is not None else None
            ),
        })
        if recovery_alarm is None:
            advance(
                data, now, f"prepared tool {args.tool_name} ({args.call_id})",
                args.lease_seconds, args.next_action,
            )
            renewed = True
    else:
        if not args.result_status or not is_sha256(args.result_digest):
            raise ValueError("result requires --result-status and sha256 --result-digest")
        pending = data["pending_tool"]
        if pending is None:
            prior = _history_result(data, args.call_id)
            if (
                prior and prior.get("result_status") == args.result_status
                and prior.get("result_digest") == args.result_digest
            ):
                print(json.dumps({
                    "status": "RUNNING", "consumed": args.call_id,
                    "idempotent": True,
                }))
                return 0
            raise ValueError("result does not match a pending tool call")
        if pending.get("call_id") != args.call_id:
            raise ValueError("result call_id does not match pending_tool")
        data["tool_call_history"].append({
            "event": "RESULT", "call_id": args.call_id,
            "tool_name": pending["tool_name"],
            "result_status": args.result_status,
            "result_digest": args.result_digest,
            "exit_code": args.last_exit_code, "at": stamp(now),
        })
        data["pending_tool"] = None
        if args.last_exit_code is not None:
            data["last_exit_code"] = args.last_exit_code
        expired_or_alarm = (
            parse_stamp(data["lease_expires_at"]) <= now
            or bool(unresolved_alarms(data))
        )
        data["tool_call_history"][-1]["renewed"] = not expired_or_alarm
        if not expired_or_alarm:
            advance(
                data, now, f"consumed tool result {args.call_id}: {args.result_status}",
                args.lease_seconds, args.next_action,
            )
            renewed = True
    write_valid(args.path, data)
    print(json.dumps({
        "status": "RUNNING", "heartbeat_seq": data["heartbeat_seq"],
        "pending_tool": data["pending_tool"],
        "renewed": renewed,
    }))
    return 0


def _alarm_key(data: dict, reason: str) -> str:
    # One stalled checkpoint state gets one alarm even if its symptom changes
    # from stale to expired while a watcher is still observing it.
    return f"{data['heartbeat_seq']}|{data['lease_expires_at']}"


def create_alarm(data: dict, now: dt.datetime, reason: str) -> tuple[dict, bool]:
    key = _alarm_key(data, reason)
    existing = next(
        (item for item in data["alarm_events"] if item.get("alarm_key") == key), None
    )
    if existing is not None:
        return existing, False
    lease_expiry = parse_stamp(data["lease_expires_at"])
    if reason == "LEASE_EXPIRED":
        # The recovery window starts at the lease boundary, not at the next
        # watcher poll.  This preserves tool/session evidence returned during
        # the bounded polling gap before the alarm record is persisted.
        evidence_start = lease_expiry
        recovery_deadline = lease_expiry + dt.timedelta(
            seconds=RECOVERY_SLA_SECONDS
        )
    else:
        # An early monitor-exit alarm may be created while the progress lease
        # is still live.  Its evidence begins immediately, but automatic
        # STOPPED remains forbidden until lease expiry plus the full window.
        evidence_start = now
        recovery_deadline = max(now, lease_expiry) + dt.timedelta(
            seconds=RECOVERY_SLA_SECONDS
        )
    alarm = {
        "alarm_id": "alarm-" + hashlib.sha256(key.encode()).hexdigest()[:16],
        "alarm_key": key, "created_at": stamp(now),
        "evidence_window_start_at": stamp(evidence_start),
        "recovery_deadline_at": stamp(recovery_deadline),
        "heartbeat_seq": data["heartbeat_seq"], "stage": data["stage"],
        "lease_expires_at": data["lease_expires_at"],
        "resume_token": data["resume_token"], "reason": reason,
        "status": "OPEN", "recovery_attempts": [],
        "tool_history_length": (
            _history_boundary_at_alarm(
                data["tool_call_history"], stamp(evidence_start), inclusive=True,
            )
            if reason == "LEASE_EXPIRED" else len(data["tool_call_history"])
        ),
        "session_history_length": (
            _history_boundary_at_alarm(
                data["session_history"], stamp(evidence_start), inclusive=True,
            )
            if reason == "LEASE_EXPIRED" else len(data["session_history"])
        ),
        "artifact_delta_length": len(data["artifact_delta"]),
        "recovery_evidence": [],
    }
    data["alarm_events"].append(alarm)
    data["monitor_alarm_count"] = (
        int(data.get("legacy_alarm_count", 0)) + len(data["alarm_events"])
    )
    return alarm, True


def _within_alarm_window(alarm: dict, when: dt.datetime) -> bool:
    return (
        parse_stamp(alarm["evidence_window_start_at"])
        <= when
        <= parse_stamp(alarm["recovery_deadline_at"])
    )


def _file_digest(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def record_artifact_recovery_evidence(
    data: dict, alarm: dict, artifact: str, now: dt.datetime,
) -> dict:
    """Verify an on-disk file changed during the alarm recovery window."""
    if not _within_alarm_window(alarm, now):
        raise ValueError("artifact recovery evidence is outside the recovery window")
    path = Path(artifact).expanduser().resolve()
    if not path.is_file():
        raise ValueError("recovery artifact must be an existing regular file")
    stat_result = path.stat()
    created_at_ns = int(
        parse_stamp(alarm["evidence_window_start_at"]).timestamp()
        * 1_000_000_000
    )
    if stat_result.st_mtime_ns < created_at_ns:
        raise ValueError("recovery artifact must be created or modified after alarm")
    evidence = {
        "type": "artifact-delta", "at": stamp(now),
        "artifact": artifact, "resolved_path": str(path),
        "size": stat_result.st_size, "mtime_ns": stat_result.st_mtime_ns,
        "sha256": _file_digest(path),
        "tracked_before_alarm": artifact in data.get("artifact_delta", []),
    }
    alarm["recovery_evidence"].append(evidence)
    return evidence


def verify_artifact_recovery_evidence(alarm: dict, evidence: dict) -> dict | None:
    """Re-read an artifact and return its current verified recovery snapshot."""
    try:
        path = Path(evidence["resolved_path"])
        recorded_mtime_ns = int(evidence["mtime_ns"])
        recorded_size = int(evidence["size"])
        recorded_digest = evidence["sha256"]
    except (KeyError, TypeError, ValueError):
        return None
    if not path.is_file() or not is_sha256(recorded_digest):
        return None
    current = path.stat()
    created_at_ns = int(
        parse_stamp(alarm["evidence_window_start_at"]).timestamp()
        * 1_000_000_000
    )
    if current.st_mtime_ns < created_at_ns or current.st_mtime_ns < recorded_mtime_ns:
        return None
    current_digest = _file_digest(path)
    if current.st_mtime_ns == recorded_mtime_ns and (
        current.st_size != recorded_size or current_digest != recorded_digest
    ):
        return None
    verified = copy.deepcopy(evidence)
    verified.update({
        "size": current.st_size,
        "mtime_ns": current.st_mtime_ns,
        "sha256": current_digest,
    })
    return verified


def recovery_window_evidence(data: dict, alarm: dict) -> dict | None:
    """Return the first real event inside an alarm's recovery window."""
    window_start = parse_stamp(alarm["evidence_window_start_at"])
    deadline = parse_stamp(alarm["recovery_deadline_at"])

    for evidence in alarm.get("recovery_evidence", []):
        if not isinstance(evidence, dict):
            continue
        try:
            at = parse_stamp(evidence["at"])
        except (KeyError, TypeError, ValueError):
            continue
        if window_start <= at <= deadline and evidence.get("type") == "artifact-delta":
            verified = verify_artifact_recovery_evidence(alarm, evidence)
            if verified is not None:
                return verified

    tool_start = int(alarm.get("tool_history_length", 0))
    for item in data.get("tool_call_history", [])[tool_start:]:
        if not isinstance(item, dict) or item.get("event") != "RESULT":
            continue
        try:
            at = parse_stamp(item["at"])
        except (KeyError, TypeError, ValueError):
            continue
        if window_start <= at <= deadline:
            return {
                "type": "tool-result", "at": item["at"],
                "call_id": item.get("call_id"),
                "result_digest": item.get("result_digest"),
            }

    session_start = int(alarm.get("session_history_length", 0))
    for item in data.get("session_history", [])[session_start:]:
        if not isinstance(item, dict) or item.get("event") != "POLL_PROGRESS":
            continue
        try:
            at = parse_stamp(item["at"])
        except (KeyError, TypeError, ValueError):
            continue
        if window_start <= at <= deadline:
            return {
                "type": "session-output", "at": item["at"],
                "session_id": item.get("session_id"),
                "output_digest": item.get("output_digest"),
                "state_after": item.get("state_after"),
                "exit_code": item.get("exit_code"),
            }
    return None


def auto_recover_from_evidence(
    data: dict, alarm: dict, now: dt.datetime, evidence: dict,
) -> None:
    data["recovery_attempt"] += 1
    action = f"automatic recovery from {evidence['type']} after {alarm['alarm_id']}"
    alarm["recovery_attempts"].append({
        "attempt": data["recovery_attempt"], "at": stamp(now),
        "result": "success", "evidence": evidence,
        "verified_action": action, "automatic": True,
    })
    alarm["status"] = "RECOVERED"
    alarm["resolved_at"] = stamp(now)
    alarm["resolution"] = action
    advance(data, now, action, DEFAULT_LEASE_SECONDS)


def capture_monitor_exit(data: dict, now: dt.datetime, reason: str) -> None:
    data["monitor_exit_snapshot"] = {
        "captured_at": stamp(now), "reason": reason,
        "monitor_agent": data.get("monitor_agent"),
        "active_sessions": copy.deepcopy(data.get("active_sessions", [])),
        "pending_tool": copy.deepcopy(data.get("pending_tool")),
    }


def _safe_artifact(data: dict) -> object:
    if data.get("artifact_delta"):
        return copy.deepcopy(data["artifact_delta"][-1])
    return {
        "kind": "checkpoint_state", "task_id": data.get("task_id"),
        "heartbeat_seq": data.get("heartbeat_seq"),
    }


def automatic_stop(data: dict, alarm: dict, now: dt.datetime, reason: str) -> None:
    sessions = copy.deepcopy(data["active_sessions"])
    pending = copy.deepcopy(data["pending_tool"])
    previous_action = data.get("last_verified_action")
    safe_artifact = _safe_artifact(data)
    capture_monitor_exit(data, now, reason)
    for item in data["alarm_events"]:
        if item.get("status") == "OPEN":
            item["status"] = "STOPPED"
            item["resolved_at"] = stamp(now)
            item["resolution"] = reason
    if pending is not None:
        data["tool_call_history"].append({
            "event": "ABANDONED", "call_id": pending["call_id"],
            "at": stamp(now), "reason": reason,
        })
    data["active_sessions"] = []
    data["monitor_agent"] = None
    data["pending_tool"] = None
    data["status"] = "STOPPED"
    data["heartbeat_seq"] += 1
    data["last_verified_action"] = f"automatic STOPPED: {reason}"
    data["next_action"] = f"review alarm {alarm['alarm_id']} and resume from token"
    data["blocker"] = reason
    data["blocker_class"] = "recovery_exhausted"
    data["updated_at"] = stamp(now)
    data["lease_expires_at"] = stamp(now)
    data["terminal_evidence"] = {
        "status": "STOPPED", "recorded_at": stamp(now),
        "reason_code": reason, "blocker": reason,
        "blocker_class": "recovery_exhausted",
        "resume_token": data["resume_token"],
        "last_completed_step": previous_action,
        "last_safe_artifact": safe_artifact,
        "recovery_condition": f"manual evidence resolves {alarm['alarm_id']}",
        "next_action": data["next_action"], "session_snapshot": sessions,
        "pending_tool_snapshot": pending, "alarm_id": alarm["alarm_id"],
    }


def command_session(args: argparse.Namespace) -> int:
    data = load(args.path)
    ensure_running(data)
    now = utcnow()
    sessions = data["active_sessions"]
    existing = next(
        (item for item in sessions if item.get("id") == args.session_id), None
    )
    if args.action == "add":
        open_alarms = unresolved_alarms(data)
        recovery_window_add = bool(open_alarms)
        if recovery_window_add:
            if len(open_alarms) != 1:
                raise ValueError("session recovery registration requires one open alarm")
            if any(
                parse_stamp(item["recovery_deadline_at"]) <= now
                for item in open_alarms
            ):
                raise ValueError("session recovery deadline expired")
        else:
            ensure_renewable(data, now)
        if existing is not None:
            raise ValueError("session is already registered")
        if not args.purpose or not args.state:
            raise ValueError("adding a session requires --purpose and --state")
        if args.monitor and data.get("monitor_agent") is not None:
            raise ValueError("another monitor session is already registered")
        sessions.append({
            "id": args.session_id, "purpose": args.purpose,
            "state": args.state, "last_poll": stamp(now),
            "monitor": bool(args.monitor),
        })
        if args.monitor:
            data["monitor_agent"] = args.session_id
        data["session_history"].append({
            "event": "ADDED", "session_id": args.session_id,
            "state": args.state, "at": stamp(now),
            "monitor": bool(args.monitor), "renewed": not recovery_window_add,
            "recovery_alarm_ids": [
                item["alarm_id"] for item in open_alarms
            ] if recovery_window_add else [],
        })
        if not recovery_window_add:
            advance(
                data, now, f"registered session {args.session_id}: {args.state}",
                args.lease_seconds,
            )
    elif args.action == "remove":
        ensure_renewable(data, now)
        if existing is None:
            raise ValueError("cannot remove an unregistered session")
        snapshot = copy.deepcopy(existing)
        was_monitor = bool(snapshot.get("monitor"))
        if was_monitor:
            # Capture while the monitor is still registered and present.
            capture_monitor_exit(
                data, now, "unexpected_exit" if args.unexpected_exit else "closed"
            )
        sessions.remove(existing)
        data["last_session_poll"] = stamp(now)
        if args.last_exit_code is not None:
            data["last_exit_code"] = args.last_exit_code
        data["session_history"].append({
            "event": "REMOVED", "session_id": args.session_id,
            "state": args.state or snapshot["state"],
            "exit_code": args.last_exit_code,
            "unexpected_exit": bool(args.unexpected_exit), "at": stamp(now),
        })
        if was_monitor:
            data["monitor_agent"] = None
        advance(
            data, now, f"closed session {args.session_id}: {args.state or snapshot['state']}",
            args.lease_seconds,
        )
        if was_monitor and args.unexpected_exit:
            create_alarm(data, now, "MONITOR_EXIT")
    else:
        if existing is None:
            raise ValueError("cannot poll an unregistered session")
        old_state = existing["state"]
        new_state = args.state or old_state
        state_changed = new_state != old_state
        if args.output_digest and not is_sha256(args.output_digest):
            raise ValueError("--output-digest must be sha256")
        output_changed = bool(
            args.output_digest
            and args.output_digest != existing.get("last_output_digest")
        )
        exit_changed = (
            args.last_exit_code is not None
            and args.last_exit_code != existing.get("exit_code")
        )
        existing["last_poll"] = stamp(now)
        data["last_session_poll"] = stamp(now)
        expired_or_alarm = (
            parse_stamp(data["lease_expires_at"]) <= now
            or bool(unresolved_alarms(data))
        )
        if not (state_changed or output_changed or exit_changed):
            if parse_stamp(data["lease_expires_at"]) <= now:
                existing["last_expired_poll"] = stamp(now)
            write_valid(args.path, data)
            print(json.dumps({
                "status": "RUNNING", "heartbeat_seq": data["heartbeat_seq"],
                "renewed": False, "observation_only": True,
            }))
            return 0
        existing["state"] = new_state
        if args.output_digest:
            existing["last_output_digest"] = args.output_digest
        if args.last_exit_code is not None:
            existing["exit_code"] = args.last_exit_code
            data["last_exit_code"] = args.last_exit_code
        data["session_history"].append({
            "event": "POLL_PROGRESS", "session_id": args.session_id,
            "state_before": old_state, "state_after": new_state,
            "output_digest": args.output_digest,
            "exit_code": args.last_exit_code, "at": stamp(now),
            "renewed": not expired_or_alarm,
        })
        if expired_or_alarm:
            existing["last_expired_poll"] = stamp(now)
        else:
            advance(
                data, now, f"session {args.session_id} produced verifiable progress",
                args.lease_seconds,
            )
    write_valid(args.path, data)
    print(json.dumps({
        "status": data["status"], "heartbeat_seq": data["heartbeat_seq"],
        "active_sessions": len(data["active_sessions"]),
    }))
    return 0


def _find_alarm(data: dict, alarm_id: str) -> dict:
    alarm = next(
        (item for item in data["alarm_events"] if item.get("alarm_id") == alarm_id),
        None,
    )
    if alarm is None:
        raise ValueError("unknown --alarm-id")
    return alarm


def command_recover(args: argparse.Namespace) -> int:
    data = load(args.path)
    ensure_running(data)
    now = utcnow()
    alarm = _find_alarm(data, args.alarm_id)
    if alarm.get("status") == "RECOVERED":
        print(json.dumps({
            "status": "RUNNING", "alarm_id": args.alarm_id,
            "idempotent": True,
        }))
        return 0
    if alarm.get("status") != "OPEN":
        raise ValueError("alarm is not recoverable")
    if parse_stamp(alarm["recovery_deadline_at"]) <= now:
        evidence = recovery_window_evidence(data, alarm)
        if evidence is not None:
            auto_recover_from_evidence(data, alarm, now, evidence)
            write_valid(args.path, data)
            print(json.dumps({
                "status": "RUNNING", "alarm_id": args.alarm_id,
                "automatic": True, "evidence_type": evidence["type"],
            }))
            return 0
        if parse_stamp(data["lease_expires_at"]) > now:
            raise ValueError("automatic STOPPED is forbidden before lease expiry")
        reason = (
            "RECOVERY_EXHAUSTED"
            if alarm.get("recovery_exhausted") else "MAIN_RECOVERY_SLA_MISSED"
        )
        automatic_stop(data, alarm, now, reason)
        write_valid(args.path, data)
        print(json.dumps({
            "status": "STOPPED", "reason": reason,
        }))
        return 3
    if args.evidence_type == "session-output":
        if not args.session_id or not is_sha256(args.output_digest):
            raise ValueError(
                "session-output recovery requires --session-id and sha256 --output-digest"
            )
        session = next(
            (item for item in data["active_sessions"] if item.get("id") == args.session_id),
            None,
        )
        if session is None:
            raise ValueError("recovery session is not registered")
        if session.get("last_output_digest") == args.output_digest:
            raise ValueError("recovery requires new session output evidence")
        session["last_output_digest"] = args.output_digest
        session["last_poll"] = stamp(now)
        data["last_session_poll"] = stamp(now)
        evidence = {
            "type": "session-output", "session_id": args.session_id,
            "output_digest": args.output_digest,
        }
    else:
        if not args.call_id or not is_sha256(args.result_digest):
            raise ValueError(
                "idempotent-rerun requires --call-id and sha256 --result-digest"
            )
        prior_index = next((
            index for index, item in reversed(list(enumerate(data["tool_call_history"])))
            if item.get("call_id") == args.call_id and item.get("event") == "RESULT"
        ), None)
        prior = (
            data["tool_call_history"][prior_index]
            if prior_index is not None else None
        )
        if (
            prior is None
            or prior.get("result_digest") != args.result_digest
            or prior_index < alarm["tool_history_length"]
            or parse_stamp(prior["at"]) < parse_stamp(
                alarm["evidence_window_start_at"]
            )
        ):
            raise ValueError(
                "rerun evidence must be a recorded tool result produced after this alarm"
            )
        evidence = {
            "type": "idempotent-rerun", "call_id": args.call_id,
            "result_digest": args.result_digest,
        }
    data["recovery_attempt"] += 1
    alarm["recovery_attempts"].append({
        "attempt": data["recovery_attempt"], "at": stamp(now),
        "result": args.result, "evidence": evidence,
        "verified_action": args.verified_action,
    })
    if args.result == "failure":
        data["recovery_failure_count"] += 1
        if data["recovery_failure_count"] >= 2:
            # Do not terminate early.  Revision 8 permits automatic STOPPED
            # only after the progress lease and the full recovery window have
            # both elapsed without post-alarm evidence.  The watcher will use
            # RECOVERY_EXHAUSTED as the eventual reason if that condition is
            # met.
            alarm["recovery_exhausted"] = True
        write_valid(args.path, data)
        print(json.dumps({
            "status": data["status"],
            "recovery_failure_count": data["recovery_failure_count"],
        }))
        return 2
    alarm["status"] = "RECOVERED"
    alarm["resolved_at"] = stamp(now)
    alarm["resolution"] = args.verified_action
    if args.stage:
        data["stage"] = args.stage
    if args.resume_token:
        data["resume_token"] = args.resume_token
    advance(data, now, args.verified_action, args.lease_seconds, args.next_action)
    write_valid(args.path, data)
    print(json.dumps({
        "status": "RUNNING", "alarm_id": args.alarm_id,
        "heartbeat_seq": data["heartbeat_seq"],
        "recovery_attempt": data["recovery_attempt"],
    }))
    return 0


def command_check(args: argparse.Namespace) -> int:
    data = load(args.path)
    errors = validate(data)
    if errors:
        print(json.dumps({"valid": False, "errors": errors}, ensure_ascii=False))
        return 1
    expired = (
        data["status"] == "RUNNING"
        and parse_stamp(data["lease_expires_at"]) <= utcnow()
    )
    print(json.dumps({
        "valid": True, "schema_version": data["schema_version"],
        "status": data["status"], "expired": expired,
        "stage": data["stage"], "heartbeat_seq": data["heartbeat_seq"],
        "resume_token": data["resume_token"],
        "unresolved_alarm_ids": [
            item["alarm_id"] for item in unresolved_alarms(data)
        ],
    }, ensure_ascii=False))
    if expired:
        return 2
    if data["status"] in {"COMPLETED", "STOPPED"}:
        return 3
    return 0


def _turn_gate_payload(data: dict, event: str, intent: str) -> dict:
    now = utcnow()
    lease_expired = (
        data.get("status") == "RUNNING"
        and parse_stamp(data["lease_expires_at"]) <= now
    )
    return {
        "event": event,
        "intent": intent,
        "status": data.get("status"),
        "stage": data.get("stage"),
        "next_action": data.get("next_action"),
        "resume_token": data.get("resume_token"),
        "lease_expired": lease_expired,
        "unresolved_alarm_ids": [
            item["alarm_id"] for item in unresolved_alarms(data)
        ],
    }


def command_turn_gate(args: argparse.Namespace) -> int:
    """Read-only boundary check before a caller sends final or enters wait."""
    data = load(args.path)
    errors = validate(data)
    if errors:
        print(json.dumps({
            "event": "TURN_GATE_INVALID", "intent": args.intent,
            "valid": False, "errors": errors,
        }, ensure_ascii=False))
        return 1

    if args.intent == "final":
        if data["status"] in {"COMPLETED", "STOPPED"}:
            print(json.dumps(
                _turn_gate_payload(data, "FINAL_AUTHORIZED", args.intent),
                ensure_ascii=False,
            ))
            return 0
        print(json.dumps(
            _turn_gate_payload(data, "TURN_CONTINUE_REQUIRED", args.intent),
            ensure_ascii=False,
        ))
        return 4

    if data["status"] in {"COMPLETED", "STOPPED"}:
        print(json.dumps(
            _turn_gate_payload(data, "WAIT_NOT_APPLICABLE", args.intent),
            ensure_ascii=False,
        ))
        return 3

    if (
        parse_stamp(data["lease_expires_at"]) <= utcnow()
        or unresolved_alarms(data)
    ):
        print(json.dumps(
            _turn_gate_payload(data, "RECOVERY_REQUIRED", args.intent),
            ensure_ascii=False,
        ))
        return 2

    workers = [
        item for item in data["active_sessions"]
        if not item.get("monitor")
    ]
    if data["pending_tool"] is not None or workers:
        payload = _turn_gate_payload(data, "WAIT_AUTHORIZED", args.intent)
        payload["pending_tool_call_id"] = (
            data["pending_tool"].get("call_id")
            if data["pending_tool"] is not None else None
        )
        payload["worker_session_ids"] = [item["id"] for item in workers]
        print(json.dumps(payload, ensure_ascii=False))
        return 0

    print(json.dumps(
        _turn_gate_payload(data, "MAIN_ACTION_REQUIRED", args.intent),
        ensure_ascii=False,
    ))
    return 4


def _parse_deliverables(items: list[str]) -> list[dict]:
    result = []
    for item in items:
        if "=" not in item:
            raise ValueError("deliverable must be NAME=SHA256")
        name, digest = item.rsplit("=", 1)
        if not name or not is_sha256(digest):
            raise ValueError("deliverable must contain a name and sha256")
        result.append({"name": name, "sha256": digest})
    return result


def _parse_gates(items: list[str]) -> dict:
    result = {}
    for item in items:
        if "=" not in item:
            raise ValueError("gate must be NAME=passed")
        name, value = item.split("=", 1)
        if not name or value.lower() not in {"passed", "pass", "true"}:
            raise ValueError("every completion gate must explicitly pass")
        result[name] = "passed"
    return result


def valid_ready_link(value: object) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(
        r"(?:sandbox:/|https?://|library:|libfile:)[^\s]+", value
    ))


def command_terminal(args: argparse.Namespace) -> int:
    data = load(args.path)
    ensure_running(data)
    now = utcnow()
    workers = [item for item in data["active_sessions"] if not item.get("monitor")]
    if args.status == "COMPLETED" and workers:
        raise ValueError("terminal state requires all work sessions to be closed")
    session_snapshot = copy.deepcopy(data["active_sessions"])
    pending_snapshot = copy.deepcopy(data["pending_tool"])
    if args.status == "COMPLETED":
        if pending_snapshot is not None:
            raise ValueError("COMPLETED requires no pending tool call")
        if unresolved_alarms(data):
            raise ValueError("COMPLETED requires every monitor alarm to be resolved")
        deliverables = _parse_deliverables(args.deliverable)
        gates = _parse_gates(args.gate)
        links = [item for item in args.link if valid_ready_link(item)]
        if not (
            args.plan_clear and args.deliverables_verified and args.links_ready
            and deliverables and gates and links
        ):
            raise ValueError(
                "COMPLETED requires plan flags plus deliverable sha256, gates, and links"
            )
        evidence = {
            "status": "COMPLETED", "recorded_at": stamp(now),
            "outcome": args.outcome, "plan_clear": True,
            "deliverables": deliverables, "gates": gates, "links": links,
            "session_snapshot": session_snapshot,
            "pending_tool_snapshot": None, "unresolved_alarm_ids": [],
        }
        next_action = "none"
    else:
        if not all((
            args.blocker, args.blocker_class, args.resume_token,
            args.last_completed_step, args.safe_artifact,
            args.recovery_condition, args.next_action,
        )):
            raise ValueError(
                "STOPPED requires blocker/class/token, last completed step, "
                "safe artifact, recovery condition, and next action"
            )
        evidence = {
            "status": "STOPPED", "recorded_at": stamp(now),
            "blocker": args.blocker, "blocker_class": args.blocker_class,
            "resume_token": args.resume_token,
            "last_completed_step": args.last_completed_step,
            "last_safe_artifact": args.safe_artifact,
            "recovery_condition": args.recovery_condition,
            "next_action": args.next_action,
            "session_snapshot": session_snapshot,
            "pending_tool_snapshot": pending_snapshot,
            "unresolved_alarm_ids": [
                item["alarm_id"] for item in unresolved_alarms(data)
            ],
        }
        data["blocker"] = args.blocker
        data["blocker_class"] = args.blocker_class
        data["resume_token"] = args.resume_token
        next_action = args.next_action
        for alarm in unresolved_alarms(data):
            alarm["status"] = "STOPPED"
            alarm["resolved_at"] = stamp(now)
            alarm["resolution"] = "manual STOPPED"
    capture_monitor_exit(data, now, f"terminal:{args.status}")
    if pending_snapshot is not None:
        data["tool_call_history"].append({
            "event": "ABANDONED", "call_id": pending_snapshot["call_id"],
            "at": stamp(now), "reason": f"terminal:{args.status}",
        })
    data["active_sessions"] = []
    data["monitor_agent"] = None
    data["pending_tool"] = None
    data["status"] = args.status
    data["heartbeat_seq"] += 1
    data["last_verified_action"] = args.outcome
    data["next_action"] = next_action
    data["updated_at"] = stamp(now)
    data["lease_expires_at"] = stamp(now)
    data["terminal_evidence"] = evidence
    write_valid(args.path, data)
    print(json.dumps({"status": args.status}))
    return 0


def _watch_cycle(path: Path, _stale_seconds: int) -> tuple[dict, list[dict]]:
    events: list[dict] = []
    with checkpoint_lock(path):
        data = load(path)
        errors = validate(data)
        if errors:
            return data, [{"event": "MONITOR_INVALID", "errors": errors}]
        if data["status"] in {"COMPLETED", "STOPPED"}:
            return data, [{
                "event": "MONITOR_TERMINAL", "status": data["status"],
                "heartbeat_seq": data["heartbeat_seq"],
            }]
        now = utcnow()
        age = int((now - parse_stamp(data["updated_at"])).total_seconds())
        expired = parse_stamp(data["lease_expires_at"]) <= now
        changed = False
        # A stale-age threshold may be useful for monitor diagnostics, but it
        # must never open a blocking alarm while the verified lease is live.
        # The lease itself is the single automatic-stop clock.
        if expired:
            alarm, created = create_alarm(
                data, now, "LEASE_EXPIRED"
            )
            changed |= created
            if created:
                events.append({
                    "event": "MONITOR_ALARM", "alarm_id": alarm["alarm_id"],
                    "heartbeat_seq": data["heartbeat_seq"],
                    "stage": data["stage"], "age_seconds": age,
                    "lease_expired": expired,
                    "resume_token": data["resume_token"],
                    "recovery_deadline_at": alarm["recovery_deadline_at"],
                })

        # Tool results, registered session output/state, and verified artifact
        # changes produced inside the recovery window prove that work resumed.
        # Resolve the alarm deterministically before considering automatic
        # STOPPED, even if the watcher wakes after the recovery deadline or
        # persisted the alarm after an in-window tool/session result arrived.
        for alarm in list(unresolved_alarms(data)):
            evidence = recovery_window_evidence(data, alarm)
            if evidence is None:
                continue
            auto_recover_from_evidence(data, alarm, utcnow(), evidence)
            changed = True
            events.append({
                "event": "MONITOR_RECOVERED", "alarm_id": alarm["alarm_id"],
                "heartbeat_seq": data["heartbeat_seq"],
                "evidence_type": evidence["type"],
            })

        now = utcnow()
        overdue = next((
            item for item in unresolved_alarms(data)
            if parse_stamp(item["recovery_deadline_at"]) <= now
            and parse_stamp(data["lease_expires_at"]) <= now
        ), None)
        if overdue is not None:
            reason = (
                "RECOVERY_EXHAUSTED"
                if overdue.get("recovery_exhausted")
                else "MAIN_RECOVERY_SLA_MISSED"
            )
            automatic_stop(data, overdue, now, reason)
            changed = True
            events.append({
                "event": "MONITOR_TERMINAL", "status": "STOPPED",
                "reason": reason,
                "alarm_id": overdue["alarm_id"],
                "heartbeat_seq": data["heartbeat_seq"],
            })
        if changed:
            write_valid(path, data)
        return data, events


def command_watch(args: argparse.Namespace) -> int:
    cycle = 0
    previous_seq = None
    ready = False
    read_error_active = False
    while True:
        read_error = None
        try:
            data, events = _watch_cycle(args.path, args.stale_seconds)
            if events and events[0].get("event") == "MONITOR_INVALID":
                read_error = "; ".join(events[0].get("errors", []))
        except (
            OSError, TypeError, AttributeError, ValueError, json.JSONDecodeError
        ) as exc:
            data, events = None, []
            read_error = f"{type(exc).__name__}: {exc}"

        if read_error is not None:
            if not read_error_active:
                digest = hashlib.sha256(read_error.encode("utf-8")).hexdigest()
                print(json.dumps({
                    "event": "MONITOR_READ_ERROR", "path": str(args.path),
                    "error": read_error, "error_digest": digest,
                }, ensure_ascii=False), flush=True)
            read_error_active = True
            cycle += 1
            if args.max_cycles is not None and cycle >= args.max_cycles:
                print(json.dumps({
                    "event": "MONITOR_TEST_EXIT", "cycles": cycle,
                }), flush=True)
                return 0
            time.sleep(float(args.interval_seconds))
            continue

        if read_error_active:
            print(json.dumps({
                "event": "MONITOR_READ_RECOVERED", "path": str(args.path),
            }), flush=True)
            read_error_active = False
        if not ready:
            print(json.dumps({
                "event": "MONITOR_READY", "path": str(args.path),
                "interval_seconds": args.interval_seconds,
                "recovery_sla_seconds": RECOVERY_SLA_SECONDS,
                "max_lease_seconds": MAX_LEASE_SECONDS,
            }), flush=True)
            ready = True
        seq = data.get("heartbeat_seq")
        if data.get("status") == "RUNNING" and seq != previous_seq:
            print(json.dumps({
                "event": "MONITOR_PROGRESS", "heartbeat_seq": seq,
                "stage": data.get("stage"),
            }), flush=True)
            previous_seq = seq
        for event in events:
            print(json.dumps(event, ensure_ascii=False), flush=True)
        if data.get("status") in {"COMPLETED", "STOPPED"}:
            if not any(e.get("event") == "MONITOR_TERMINAL" for e in events):
                print(json.dumps({
                    "event": "MONITOR_TERMINAL", "status": data["status"],
                    "heartbeat_seq": data["heartbeat_seq"],
                }), flush=True)
            return 0
        cycle += 1
        if args.max_cycles is not None and cycle >= args.max_cycles:
            print(json.dumps({"event": "MONITOR_TEST_EXIT", "cycles": cycle}), flush=True)
            return 0
        sleep_seconds = float(args.interval_seconds)
        deadlines = [
            parse_stamp(item["recovery_deadline_at"])
            for item in unresolved_alarms(data)
        ]
        if deadlines:
            until_deadline = (min(deadlines) - utcnow()).total_seconds()
            sleep_seconds = min(sleep_seconds, max(0.0, until_deadline))
        if sleep_seconds > 0:
            time.sleep(sleep_seconds)


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser()
    subs = parser.add_subparsers(dest="command", required=True)
    init = subs.add_parser("init")
    init.add_argument("path", type=Path)
    init.add_argument("--task-id", required=True)
    init.add_argument("--stage", required=True)
    init.add_argument("--verified-action", required=True)
    init.add_argument("--next-action", required=True)
    init.add_argument("--resume-token", required=True)
    init.add_argument("--monitor-agent")
    init.add_argument("--progress", action="append", default=[])
    init.add_argument(
        "--lease-seconds", type=int,
        choices=range(1, MAX_LEASE_SECONDS + 1), default=DEFAULT_LEASE_SECONDS,
    )
    init.set_defaults(func=command_init)
    beat = subs.add_parser("heartbeat")
    beat.add_argument("path", type=Path)
    beat.add_argument("--stage")
    beat.add_argument("--verified-action")
    beat.add_argument("--next-action")
    beat.add_argument("--resume-token")
    beat.add_argument("--progress", action="append", default=[])
    beat.add_argument("--artifact", action="append", default=[])
    beat.add_argument("--session-poll")
    beat.add_argument("--last-exit-code", type=int)
    beat.add_argument("--recovery", action="store_true")
    beat.add_argument(
        "--lease-seconds", type=int,
        choices=range(1, MAX_LEASE_SECONDS + 1), default=DEFAULT_LEASE_SECONDS,
    )
    beat.set_defaults(func=command_heartbeat)
    tool = subs.add_parser("prepare-tool")
    tool.add_argument("path", type=Path)
    tool.add_argument("--action", choices=["prepare", "result"], default="prepare")
    tool.add_argument("--call-id", required=True)
    tool.add_argument("--tool-name")
    tool.add_argument("--args-digest")
    tool.add_argument("--result-status", choices=["success", "failure"])
    tool.add_argument("--result-digest")
    tool.add_argument("--last-exit-code", type=int)
    tool.add_argument("--next-action")
    tool.add_argument(
        "--lease-seconds", type=int,
        choices=range(1, MAX_LEASE_SECONDS + 1), default=DEFAULT_LEASE_SECONDS,
    )
    tool.set_defaults(func=command_prepare_tool)
    check = subs.add_parser("check")
    check.add_argument("path", type=Path)
    check.set_defaults(func=command_check)
    turn_gate = subs.add_parser("turn-gate")
    turn_gate.add_argument("path", type=Path)
    turn_gate.add_argument("--intent", choices=["final", "wait"], required=True)
    turn_gate.set_defaults(func=command_turn_gate)
    session = subs.add_parser("session")
    session.add_argument("path", type=Path)
    session.add_argument("--action", choices=["add", "remove", "poll"], required=True)
    session.add_argument("--session-id", required=True)
    session.add_argument("--purpose")
    session.add_argument("--state")
    session.add_argument("--output-digest")
    session.add_argument("--last-exit-code", type=int)
    session.add_argument("--monitor", action="store_true")
    session.add_argument("--unexpected-exit", action="store_true")
    session.add_argument(
        "--lease-seconds", type=int,
        choices=range(1, MAX_LEASE_SECONDS + 1), default=DEFAULT_LEASE_SECONDS,
    )
    session.set_defaults(func=command_session)
    recover = subs.add_parser("recover")
    recover.add_argument("path", type=Path)
    recover.add_argument("--alarm-id", required=True)
    recover.add_argument(
        "--evidence-type", choices=["session-output", "idempotent-rerun"],
        required=True,
    )
    recover.add_argument("--session-id")
    recover.add_argument("--output-digest")
    recover.add_argument("--call-id")
    recover.add_argument("--result-digest")
    recover.add_argument("--result", choices=["success", "failure"], required=True)
    recover.add_argument("--verified-action", required=True)
    recover.add_argument("--stage")
    recover.add_argument("--next-action")
    recover.add_argument("--resume-token")
    recover.add_argument(
        "--lease-seconds", type=int,
        choices=range(1, MAX_LEASE_SECONDS + 1), default=DEFAULT_LEASE_SECONDS,
    )
    recover.set_defaults(func=command_recover)
    term = subs.add_parser("terminal")
    term.add_argument("path", type=Path)
    term.add_argument("--status", choices=["COMPLETED", "STOPPED"], required=True)
    term.add_argument("--outcome", required=True)
    term.add_argument("--next-action")
    term.add_argument("--blocker")
    term.add_argument("--blocker-class", choices=[
        "permission", "missing_material", "user_decision",
        "unrecoverable_error", "recovery_exhausted",
    ])
    term.add_argument("--resume-token")
    term.add_argument("--last-completed-step")
    term.add_argument("--safe-artifact")
    term.add_argument("--recovery-condition")
    term.add_argument("--plan-clear", action="store_true")
    term.add_argument("--deliverables-verified", action="store_true")
    term.add_argument("--links-ready", action="store_true")
    term.add_argument("--deliverable", action="append", default=[])
    term.add_argument("--gate", action="append", default=[])
    term.add_argument("--link", action="append", default=[])
    term.set_defaults(func=command_terminal)
    watch = subs.add_parser("watch")
    watch.add_argument("path", type=Path)
    watch.add_argument("--interval-seconds", type=int, choices=range(1, 46), default=30)
    watch.add_argument(
        "--stale-seconds", type=int,
        choices=range(1, MAX_LEASE_SECONDS + 1), default=MAX_LEASE_SECONDS,
    )
    watch.add_argument("--max-cycles", type=int)
    watch.set_defaults(func=command_watch)
    return parser


def main() -> int:
    args = build_parser().parse_args()
    try:
        if args.command in {
            "init", "heartbeat", "prepare-tool", "session", "recover", "terminal"
        }:
            with checkpoint_lock(args.path):
                return args.func(args)
        return args.func(args)
    except (OSError, TypeError, AttributeError, ValueError, json.JSONDecodeError) as exc:
        print(f"checkpoint error: {exc}", file=sys.stderr)
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
