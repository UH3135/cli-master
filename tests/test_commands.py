from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from rich.console import Console

from cli_master.commands import CommandHandler
from cli_master.config import config
from cli_master.history import SqlHistory
from tests.e2e_helpers import seed_checkpoint_db


def _make_console() -> Console:
    return Console(record=True, width=120)


def _get_output(console: Console) -> str:
    return console.export_text()


def _make_history(tmp_path: Path) -> SqlHistory:
    db_path = tmp_path / "history.db"
    return SqlHistory(f"sqlite:///{db_path}")


def test_help_command(tmp_path):
    console = _make_console()
    history = _make_history(tmp_path)
    handler = CommandHandler(console, history)

    handler.handle("/help")

    output = _get_output(console)
    assert "/help" in output
    assert "/history" in output
    assert "/clear" in output
    assert "/threads" in output
    assert "/load" in output
    assert "/exit" in output


def test_history_empty(tmp_path):
    console = _make_console()
    history = _make_history(tmp_path)
    handler = CommandHandler(console, history)

    handler.handle("/history")

    output = _get_output(console)
    assert "히스토리가 비어있습니다" in output


def test_history_after_one_turn(tmp_path):
    console = _make_console()
    history = _make_history(tmp_path)
    handler = CommandHandler(console, history)

    history.store_string("안 1234")
    history.store_ai_response("fake: 안 1234")

    handler.handle("/history")

    output = _get_output(console)
    assert "사용자" in output
    assert "AI" in output
    assert "안 1234" in output


def test_clear_history(tmp_path):
    console = _make_console()
    history = _make_history(tmp_path)
    handler = CommandHandler(console, history)

    history.store_string("테스트")
    history.store_ai_response("fake: 테스트")

    handler.handle("/clear")
    handler.handle("/history")

    output = _get_output(console)
    assert "히스토리가 초기화되었습니다" in output
    assert "히스토리가 비어있습니다" in output


def test_history_output_format(tmp_path):
    console = _make_console()
    history = _make_history(tmp_path)
    handler = CommandHandler(console, history)

    history.store_string("첫번째")
    history.store_ai_response("응답")
    history.store_string("두번째")

    handler.handle("/history")

    output = _get_output(console)
    assert "대화 히스토리" in output
    assert "역할" in output
    assert "내용" in output
    assert "사용자" in output
    assert "AI" in output
    assert "첫번째" in output
    assert "두번째" in output
    assert "응답" in output


def test_clear_then_resume_history(tmp_path):
    console = _make_console()
    history = _make_history(tmp_path)
    handler = CommandHandler(console, history)

    history.store_string("초기")
    history.store_ai_response("초기 응답")
    handler.handle("/clear")

    history.store_string("재시작")
    history.store_ai_response("재응답")
    handler.handle("/history")

    output = _get_output(console)
    assert "재시작" in output
    assert "재응답" in output
    assert history.get_all_with_role() == [
        ("user", "재시작"),
        ("ai", "재응답"),
    ]


def test_unknown_command(tmp_path):
    console = _make_console()
    history = _make_history(tmp_path)
    handler = CommandHandler(console, history)

    handler.handle("/nope")

    output = _get_output(console)
    assert "알 수 없는 명령어" in output


def test_load_usage(tmp_path):
    console = _make_console()
    history = _make_history(tmp_path)
    handler = CommandHandler(console, history)

    handler.handle("/load")

    output = _get_output(console)
    assert "사용법: /load <thread_id>" in output


def test_load_missing_thread(tmp_path, monkeypatch):
    console = _make_console()
    history = _make_history(tmp_path)
    checkpoint_db = tmp_path / "checkpoints.db"
    monkeypatch.setattr(config, "CHECKPOINT_DB_PATH", checkpoint_db)
    handler = CommandHandler(console, history)

    handler.handle("/load missing-thread")

    output = _get_output(console)
    assert "해당 thread_id의 체크포인트가 없습니다" in output


def test_threads_empty(tmp_path, monkeypatch):
    console = _make_console()
    history = _make_history(tmp_path)
    checkpoint_db = tmp_path / "checkpoints.db"
    monkeypatch.setattr(config, "CHECKPOINT_DB_PATH", checkpoint_db)
    handler = CommandHandler(console, history)

    handler.handle("/threads")

    output = _get_output(console)
    assert "저장된 thread가 없습니다" in output


def test_threads_list(tmp_path, monkeypatch):
    console = _make_console()
    history = _make_history(tmp_path)
    checkpoint_db = tmp_path / "checkpoints.db"
    monkeypatch.setattr(config, "CHECKPOINT_DB_PATH", checkpoint_db)
    handler = CommandHandler(console, history)

    seed_checkpoint_db(
        checkpoint_db,
        "seed-thread",
        [HumanMessage(content="seed user"), AIMessage(content="seed ai")],
    )

    handler.handle("/threads")

    output = _get_output(console)
    assert "seed-thread" in output


def test_load_thread_success(tmp_path, monkeypatch):
    console = _make_console()
    history = _make_history(tmp_path)
    checkpoint_db = tmp_path / "checkpoints.db"
    monkeypatch.setattr(config, "CHECKPOINT_DB_PATH", checkpoint_db)
    handler = CommandHandler(console, history)

    seed_checkpoint_db(
        checkpoint_db,
        "seed-thread",
        [HumanMessage(content="seed user"), AIMessage(content="seed ai")],
    )

    handler.handle("/load seed-thread")

    output = _get_output(console)
    assert "thread seed-thread의 대화 2건으로 히스토리를 갱신했습니다" in output
    assert history.get_all_with_role() == [
        ("user", "seed user"),
        ("ai", "seed ai"),
    ]
