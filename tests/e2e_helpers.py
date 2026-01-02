from __future__ import annotations

import io
import os
import re
import sys
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Iterable
from uuid import uuid4

import pexpect
import sqlite3
from langgraph.checkpoint.sqlite import SqliteSaver

PROMPT = "> "
ERROR_STRINGS = [
    "Traceback",
    "RuntimeWarning",
    "Task was destroyed but it is pending!",
]


class TeeIO(io.TextIOBase):
    """로그를 여러 스트림에 동시에 기록하기 위한 간단한 tee."""

    def __init__(self, *streams: io.TextIOBase) -> None:
        self._streams = streams

    def write(self, s: str) -> int:  # type: ignore[override]
        for stream in self._streams:
            stream.write(s)
        return len(s)

    def flush(self) -> None:  # type: ignore[override]
        for stream in self._streams:
            stream.flush()

    def close(self) -> None:  # type: ignore[override]
        for stream in self._streams:
            stream.close()


_ANSI_RE = re.compile(r"\x1b\[[0-9;]*[A-Za-z]")


def normalize_log(text: str) -> str:
    cleaned = _ANSI_RE.sub("", text)
    return cleaned.replace("\r", "\n")


@dataclass
class SessionLog:
    tee: TeeIO
    buffer: io.StringIO
    file: io.TextIOWrapper
    path: Path

    def close(self) -> None:
        self.file.close()

    def text(self) -> str:
        return self.buffer.getvalue()


def make_session_log(tmp_path: Path, name: str = "session.log") -> SessionLog:
    path = tmp_path / name
    buffer = io.StringIO()
    file = path.open("w", encoding="utf-8")
    tee = TeeIO(buffer, file)
    return SessionLog(tee=tee, buffer=buffer, file=file, path=path)


def build_cli_env(
    tmp_path: Path, extra_env: dict[str, str] | None = None
) -> dict[str, str]:
    db_dir = tmp_path / "db"
    db_dir.mkdir(parents=True, exist_ok=True)
    history_db = db_dir / "history.db"
    checkpoint_db = db_dir / "checkpoints.db"

    env = os.environ.copy()
    env.update(
        {
            "DATABASE_DIR": str(db_dir),
            "DATABASE_URL": f"sqlite:///{history_db}",
            "CHECKPOINT_DB_PATH": str(checkpoint_db),
            "MODEL_NAME": "fake",
            "CLI_MASTER_FAKE_LLM": "1",
            "LANGSMITH_TRACING": "false",
        }
    )
    if extra_env:
        env.update({k: str(v) for k, v in extra_env.items()})
    return env


def spawn_cli(
    env: dict[str, str],
    cwd: Path,
    timeout: float = 10,
    cmd: list[str] | None = None,
    logfile: io.TextIOBase | None = None,
) -> pexpect.spawn:
    if cmd is None:
        command = sys.executable
        args = ["-m", "cli_master.main"]
    else:
        command = cmd[0]
        args = cmd[1:]
    child = pexpect.spawn(
        command,
        args,
        cwd=str(cwd),
        env=env,
        encoding="utf-8",
        timeout=timeout,
    )
    if logfile is not None:
        child.logfile = logfile
    return child


def expect_prompt(child: pexpect.spawn, timeout: float = 10) -> None:
    child.expect(r"(?:\x1b\[[0-9;]*[A-Za-z])*>\s", timeout=timeout)


def expect_patterns(
    child: pexpect.spawn, patterns: Iterable[str], timeout: float = 10
) -> None:
    for pattern in patterns:
        child.expect(pattern, timeout=timeout)


def send_exit(child: pexpect.spawn, timeout: float = 10) -> None:
    child.sendline("/exit")
    child.expect("프로그램을 종료합니다", timeout=timeout)


def send_ctrl_d(child: pexpect.spawn, timeout: float = 10) -> None:
    child.sendcontrol("d")
    child.expect("프로그램을 종료합니다", timeout=timeout)


def assert_no_error_strings(
    log_text: str, extra_errors: Iterable[str] | None = None
) -> None:
    errors = list(ERROR_STRINGS)
    if extra_errors:
        errors.extend(extra_errors)
    normalized = normalize_log(log_text)
    for err in errors:
        assert err not in normalized


def assert_log_contains(log_text: str, *needles: str) -> None:
    normalized = normalize_log(log_text)
    for needle in needles:
        assert needle in normalized


def seed_checkpoint_db(checkpoint_db_path: Path, thread_id: str, messages) -> None:
    # 테스트용 체크포인트를 만들어 /load 검증에 사용한다.
    checkpoint = {
        "id": str(uuid4()),
        "ts": datetime.now(timezone.utc).isoformat(),
        "channel_values": {"messages": messages},
    }
    metadata = {"source": "test", "step": 0, "writes": {}}
    config = {"configurable": {"thread_id": thread_id, "checkpoint_ns": ""}}

    with sqlite3.connect(str(checkpoint_db_path)) as conn:
        saver = SqliteSaver(conn=conn)
        saver.put(config, checkpoint, metadata, {})
