"""리서치 모듈 테스트"""

from __future__ import annotations

from pathlib import Path

import pytest
from rich.console import Console

from cli_master.commands import CommandHandler
from cli_master.core.config import config
from cli_master.repository import CheckpointRepository, PromptHistoryRepository
from cli_master.researcher import (
    ResearchPhase,
    create_research_session,
    create_research_agent,
)


# 테스트 전에 FAKE_LLM 모드 활성화
@pytest.fixture(autouse=True)
def enable_fake_llm():
    original = config.FAKE_LLM
    config.FAKE_LLM = True
    yield
    config.FAKE_LLM = original


def _make_console() -> Console:
    return Console(record=True, width=120)


def _get_output(console: Console) -> str:
    return console.export_text()


def _make_repos(checkpoint_db: Path) -> tuple[CheckpointRepository, PromptHistoryRepository]:
    """테스트용 repository 생성"""
    return CheckpointRepository(checkpoint_db), PromptHistoryRepository()


class TestResearchSession:
    """ResearchSession 테스트"""

    def test_create_session(self):
        """세션 생성 테스트"""
        session = create_research_session("에러 핸들링 패턴")

        assert session.topic == "에러 핸들링 패턴"
        assert session.phase == ResearchPhase.INIT
        assert session.clarifying_questions == []
        assert session.user_answers == []
        assert session.plan == []
        assert session.findings == []
        assert session.report == ""

    def test_session_get_context(self):
        """세션 컨텍스트 생성 테스트"""
        session = create_research_session("테스트 주제")
        session.clarifying_questions = ["질문1", "질문2"]
        session.user_answers = ["답변1", "답변2"]
        session.plan = ["단계1", "단계2"]

        context = session.get_context()

        assert "테스트 주제" in context
        assert "질문1" in context
        assert "답변1" in context
        assert "단계1" in context


class TestResearchAgent:
    """ResearchAgent 테스트"""

    def test_generate_clarifying_questions(self):
        """명확화 질문 생성 테스트"""
        session = create_research_session("에러 핸들링")
        agent = create_research_agent(session)

        questions = agent.generate_clarifying_questions()

        assert len(questions) >= 1
        assert len(questions) <= 2
        assert session.phase == ResearchPhase.CLARIFYING

    def test_generate_plan(self):
        """조사 계획 생성 테스트"""
        session = create_research_session("프로젝트 구조")
        session.clarifying_questions = ["특정 디렉토리?"]
        session.user_answers = ["전체 프로젝트"]
        agent = create_research_agent(session)

        plan = agent.generate_plan()

        assert len(plan) >= 1
        assert session.phase == ResearchPhase.PLANNING

    def test_execute_step(self):
        """조사 단계 실행 테스트"""
        session = create_research_session("테스트")
        session.plan = ["단계1", "단계2"]
        agent = create_research_agent(session)

        result = agent.execute_step(0)

        assert "단계1" in result
        assert len(session.findings) == 1
        assert session.phase == ResearchPhase.EXECUTING

    def test_generate_report(self):
        """보고서 생성 테스트"""
        session = create_research_session("테스트 주제")
        session.findings = ["발견1", "발견2"]
        agent = create_research_agent(session)

        report = agent.generate_report()

        assert "테스트 주제" in report
        assert session.phase == ResearchPhase.COMPLETED
        assert session.report == report

    def test_save_report(self, tmp_path):
        """보고서 저장 테스트"""
        session = create_research_session("테스트")
        session.report = "# 테스트 보고서\n\n내용"
        agent = create_research_agent(session)

        filepath = agent.save_report(reports_dir=tmp_path)

        assert filepath.exists()
        assert filepath.suffix == ".md"
        assert "research_" in filepath.name
        content = filepath.read_text(encoding="utf-8")
        assert "테스트 보고서" in content


class TestResearchCommand:
    """/research 명령어 테스트"""

    def test_research_without_topic(self, tmp_path):
        """주제 없이 /research 실행 시 안내 메시지"""
        console = _make_console()
        checkpoint_db = tmp_path / "checkpoints.db"
        checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
        handler = CommandHandler(console, checkpoint_repo, prompt_repo)

        handler.handle("/research")

        output = _get_output(console)
        assert "조사할 주제를 입력해주세요" in output

    def test_research_with_topic(self, tmp_path):
        """주제와 함께 /research 실행"""
        console = _make_console()
        checkpoint_db = tmp_path / "checkpoints.db"
        checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
        handler = CommandHandler(console, checkpoint_repo, prompt_repo)

        handler.handle("/research 에러 핸들링 패턴")

        output = _get_output(console)
        assert "심층 검색 모드" in output
        assert "에러 핸들링 패턴" in output
        assert handler.is_research_mode

    def test_research_mode_property(self, tmp_path):
        """리서치 모드 상태 확인"""
        console = _make_console()
        checkpoint_db = tmp_path / "checkpoints.db"
        checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
        handler = CommandHandler(console, checkpoint_repo, prompt_repo)

        # 초기 상태
        assert not handler.is_research_mode

        # /research 실행 후
        handler.handle("/research 테스트 주제")
        assert handler.is_research_mode

    def test_research_clarifying_questions(self, tmp_path):
        """명확화 질문 표시"""
        console = _make_console()
        checkpoint_db = tmp_path / "checkpoints.db"
        checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
        handler = CommandHandler(console, checkpoint_repo, prompt_repo)

        handler.handle("/research 프로젝트 분석")

        output = _get_output(console)
        assert "다음 질문에 답변해주세요" in output


class TestResearchFlow:
    """리서치 플로우 통합 테스트"""

    def test_full_research_flow(self, tmp_path):
        """전체 리서치 플로우 테스트"""
        console = _make_console()
        checkpoint_db = tmp_path / "checkpoints.db"
        checkpoint_repo, prompt_repo = _make_repos(checkpoint_db)
        handler = CommandHandler(console, checkpoint_repo, prompt_repo)

        # 1. 리서치 시작
        handler.handle("/research 코드 분석")
        assert handler.is_research_mode
        assert handler.research_session is not None
        assert handler.research_session.phase == ResearchPhase.CLARIFYING

        # 2. 첫 번째 답변
        handler.process_research_input("전체 프로젝트")

        # 3. 두 번째 답변 (마지막 답변 시 자동으로 계획 수립 및 실행)
        handler.process_research_input("코드 구현 방식")

        output = _get_output(console)

        # 계획 수립 확인
        assert "조사 계획" in output

        # 리서치 완료 확인
        assert "리서치 보고서" in output or handler.research_session is None
