from __future__ import annotations

import pexpect

from tests.e2e_helpers import (
    assert_no_error_strings,
    assert_log_contains,
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


def test_basic_chat_flow(cli_process):
    child, session_log = cli_process
    expect_prompt(child)
    child.sendline("안 1234")
    child.expect("AI:", timeout=30)
    expect_prompt(child)
    send_exit(child)
    child.expect(pexpect.EOF, timeout=5)
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
