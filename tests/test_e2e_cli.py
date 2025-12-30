from __future__ import annotations

from pathlib import Path

import pexpect
from langchain_core.messages import AIMessage, HumanMessage

from tests.e2e_helpers import (
    assert_no_error_strings,
    assert_log_contains,
    build_cli_env,
    expect_prompt,
    make_session_log,
    seed_checkpoint_db,
    send_ctrl_d,
    send_exit,
    spawn_cli,
)


def _drain_and_assert(child: pexpect.spawn, log_text: str) -> None:
    # 종료 직후는 출력이 덮어쓰기 형태라서 전체 로그로만 검증한다.
    assert_no_error_strings(log_text)


def test_exit_command(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    _drain_and_assert(child, session_log.text())


def test_ctrl_d_exit(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    send_ctrl_d(child)
    child.expect(pexpect.EOF, timeout=5)
    _drain_and_assert(child, session_log.text())


def test_help_command(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    child.sendline("/help")
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    assert_log_contains(
        session_log.text(),
        "/help",
        "/history",
        "/clear",
        "/threads",
        "/load",
        "/exit",
    )
    _drain_and_assert(child, session_log.text())


def test_history_empty(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    child.sendline("/history")
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    assert_log_contains(session_log.text(), "히스토리가 비어있습니다")
    _drain_and_assert(child, session_log.text())


def test_unknown_command(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    child.sendline("/nope")
    child.expect("알 수 없는 명령어", timeout=5)
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    _drain_and_assert(child, session_log.text())


def test_load_usage(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    child.sendline("/load")
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    assert_log_contains(session_log.text(), "사용법: /load <thread_id>")
    _drain_and_assert(child, session_log.text())


def test_threads_empty(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    child.sendline("/threads")
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    assert_log_contains(session_log.text(), "저장된 thread가 없습니다")
    _drain_and_assert(child, session_log.text())


def test_history_after_one_turn(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    child.sendline("안 1234")
    child.expect("AI:", timeout=30)
    expect_prompt(child)
    child.sendline("/history")
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    assert_log_contains(session_log.text(), "사용자", "AI", "안 1234")
    _drain_and_assert(child, session_log.text())


def test_ctrl_c_stays_alive(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    child.sendcontrol("c")
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    assert_log_contains(session_log.text(), "입력이 취소되었습니다")
    _drain_and_assert(child, session_log.text())


def test_clear_history(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    child.sendline("테스트")
    child.expect("AI:", timeout=10)
    expect_prompt(child)
    child.sendline("/clear")
    expect_prompt(child)
    child.sendline("/history")
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    assert_log_contains(
        session_log.text(), "히스토리가 초기화되었습니다", "히스토리가 비어있습니다"
    )
    _drain_and_assert(child, session_log.text())


def test_load_thread_success(tmp_path, repo_root):
    env = build_cli_env(tmp_path)
    thread_id = "seed-thread"
    seed_checkpoint_db(
        Path(env["CHECKPOINT_DB_PATH"]),
        thread_id,
        [HumanMessage(content="seed user"), AIMessage(content="seed ai")],
    )
    session_log = make_session_log(tmp_path, name="load-success.log")
    child = spawn_cli(env=env, cwd=repo_root, logfile=session_log.tee)
    try:
        expect_prompt(child)
        child.sendline(f"/load {thread_id}")
        expect_prompt(child)
        child.sendline("/history")
        expect_prompt(child)
        send_exit(child)
        child.expect(pexpect.EOF, timeout=5)
    finally:
        if child.isalive():
            child.terminate(force=True)
        session_log.close()
    assert_log_contains(
        session_log.text(),
        f"thread {thread_id}의 대화 2건으로 히스토리를 갱신했습니다",
        "사용자",
        "AI",
        "seed user",
        "seed ai",
    )
