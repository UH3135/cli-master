from __future__ import annotations

from pathlib import Path

from langchain_core.messages import AIMessage, HumanMessage
from rich.console import Console

from cli_master.commands import CommandHandler
from cli_master.config import config
from cli_master.repository import CheckpointRepository, PromptHistoryRepository
from tests.e2e_helpers import seed_checkpoint_db


def _make_console() -> Console:
    return Console(record=True, width=120)


def _get_output(console: Console) -> str:
    return console.export_text()


def _make_repos(checkpoint_db: Path) -> tuple[CheckpointRepository, PromptHistoryRepository]:
    """테스트용 repository 생성"""
    return CheckpointRepository(checkpoint_db), PromptHistoryRepository()


def _seed_other_thread_for_schema(checkpoint_db: Path) -> None:
    # 빈 DB 파일만 있으면 SqliteSaver 조회가 실패할 수 있어, 스키마 생성을 위해 더미 체크포인트를 심는다.
    seed_checkpoint_db(
        checkpoint_db,
        "other-thread",
        [HumanMessage(content="schema seed"), AIMessage(content="schema seed ai")],
    )


def test_help_command(tmp_path):
    console = _make_console()
    checkpoint_db = tmp_path / "checkpoints.db"
    checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
    handler = CommandHandler(console, checkpoint_repo, prompt_repo)

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
    checkpoint_db = tmp_path / "checkpoints.db"
    _seed_other_thread_for_schema(checkpoint_db)
    checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
    handler = CommandHandler(console, checkpoint_repo, prompt_repo)
    # 현재 thread에는 체크포인트가 없으므로 "히스토리가 비어있습니다"가 기대값

    handler.handle("/history")

    output = _get_output(console)
    assert "히스토리가 비어있습니다" in output


def test_history_after_one_turn(tmp_path):
    console = _make_console()
    checkpoint_db = tmp_path / "checkpoints.db"
    seed_checkpoint_db(
        checkpoint_db,
        "seed-thread",
        [HumanMessage(content="안 1234"), AIMessage(content="fake: 안 1234")],
    )
    checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
    handler = CommandHandler(console, checkpoint_repo, prompt_repo)

    handler.handle("/load seed-thread")
    handler.handle("/history")

    output = _get_output(console)
    assert "안 1234" in output


def test_clear_history(tmp_path):
    console = _make_console()
    checkpoint_db = tmp_path / "checkpoints.db"
    seed_checkpoint_db(
        checkpoint_db,
        "seed-thread",
        [HumanMessage(content="테스트"), AIMessage(content="fake: 테스트")],
    )
    checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
    handler = CommandHandler(console, checkpoint_repo, prompt_repo)

    handler.handle("/load seed-thread")
    handler.handle("/clear")
    handler.handle("/history")

    output = _get_output(console)
    assert "히스토리가 비어있습니다" in output


def test_history_output_format(tmp_path):
    console = _make_console()
    checkpoint_db = tmp_path / "checkpoints.db"
    seed_checkpoint_db(
        checkpoint_db,
        "seed-thread",
        [
            HumanMessage(content="첫번째"),
            AIMessage(content="응답"),
            HumanMessage(content="두번째"),
        ],
    )
    checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
    handler = CommandHandler(console, checkpoint_repo, prompt_repo)

    handler.handle("/load seed-thread")
    handler.handle("/history")

    output = _get_output(console)
    assert "대화 히스토리" in output
    assert "역할" in output
    assert "내용" in output
    assert "첫번째" in output
    assert "두번째" in output
    assert "응답" in output


def test_clear_then_resume_history(tmp_path):
    console = _make_console()
    checkpoint_db = tmp_path / "checkpoints.db"
    seed_checkpoint_db(
        checkpoint_db,
        "seed-thread",
        [HumanMessage(content="초기"), AIMessage(content="초기 응답")],
    )
    seed_checkpoint_db(
        checkpoint_db,
        "seed-thread-2",
        [HumanMessage(content="재시작"), AIMessage(content="재응답")],
    )
    checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
    handler = CommandHandler(console, checkpoint_repo, prompt_repo)

    handler.handle("/load seed-thread")
    handler.handle("/clear")
    handler.handle("/load seed-thread-2")
    handler.handle("/history")

    output = _get_output(console)
    assert "재시작" in output
    assert "재응답" in output


def test_unknown_command(tmp_path):
    console = _make_console()
    checkpoint_db = tmp_path / "checkpoints.db"
    checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
    handler = CommandHandler(console, checkpoint_repo, prompt_repo)

    handler.handle("/nope")

    output = _get_output(console)
    assert "알 수 없는 명령어" in output


def test_load_usage(tmp_path):
    console = _make_console()
    checkpoint_db = tmp_path / "checkpoints.db"
    checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
    handler = CommandHandler(console, checkpoint_repo, prompt_repo)

    handler.handle("/load")

    output = _get_output(console)
    assert "사용법: /load" in output


def test_load_missing_thread(tmp_path):
    console = _make_console()
    checkpoint_db = tmp_path / "checkpoints.db"
    checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
    handler = CommandHandler(console, checkpoint_repo, prompt_repo)

    handler.handle("/load missing-thread")

    output = _get_output(console)
    assert "해당 thread_id의 체크포인트가 없습니다" in output


def test_threads_empty(tmp_path):
    console = _make_console()
    checkpoint_db = tmp_path / "checkpoints.db"
    _seed_other_thread_for_schema(checkpoint_db)
    checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
    handler = CommandHandler(console, checkpoint_repo, prompt_repo)

    handler.handle("/threads")

    output = _get_output(console)
    assert "저장된 thread 목록" in output


def test_threads_list(tmp_path):
    console = _make_console()
    checkpoint_db = tmp_path / "checkpoints.db"
    seed_checkpoint_db(
        checkpoint_db,
        "seed-thread",
        [HumanMessage(content="seed user"), AIMessage(content="seed ai")],
    )
    checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
    handler = CommandHandler(console, checkpoint_repo, prompt_repo)

    handler.handle("/threads")

    output = _get_output(console)
    assert "seed-thread" in output


def test_load_thread_success(tmp_path):
    console = _make_console()
    checkpoint_db = tmp_path / "checkpoints.db"
    seed_checkpoint_db(
        checkpoint_db,
        "seed-thread",
        [HumanMessage(content="seed user"), AIMessage(content="seed ai")],
    )
    checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
    handler = CommandHandler(console, checkpoint_repo, prompt_repo)

    handler.handle("/load seed-thread")

    output = _get_output(console)
    assert "seed-thread" in output
    # /load는 사용자 메시지(HumanMessage)만 prompt history에 저장한다.
    assert prompt_repo.get_entries() == ["seed user"]
