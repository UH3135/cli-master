from __future__ import annotations

import pexpect

from tests.e2e_helpers import (
    assert_no_error_strings,
    expect_patterns,
    expect_prompt,
    send_ctrl_d,
    send_exit,
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
    expect_patterns(
        child,
        [
            r"/help",
            r"/history",
            r"/clear",
            r"/threads",
            r"/load",
            r"/exit",
        ],
    )
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    _drain_and_assert(child, session_log.text())


def test_history_empty(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    child.sendline("/history")
    child.expect("히스토리가 비어있습니다", timeout=5)
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
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
    child.expect("사용법: /load <thread_id>", timeout=5)
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    _drain_and_assert(child, session_log.text())


def test_threads_empty(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    child.sendline("/threads")
    child.expect("저장된 thread가 없습니다", timeout=5)
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    _drain_and_assert(child, session_log.text())


def test_history_after_one_turn(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    child.sendline("안 1234")
    child.expect("AI:", timeout=30)
    expect_prompt(child)
    child.sendline("/history")
    expect_patterns(child, [r"user", r"ai"], timeout=10)
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
    _drain_and_assert(child, session_log.text())
