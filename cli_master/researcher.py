"""심층 검색(Research) 모듈

사용자의 조사 요청을 받아 다단계 리서치를 수행하고 보고서를 생성합니다.

플로우:
1. 주제 입력 → clarifying questions 생성 (1~2개)
2. 사용자 답변 수집
3. 리서치 계획 수립
4. 각 단계 실행 (도구 활용)
5. 보고서 생성 (터미널 + 파일 저장)
"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Callable

from langchain_core.messages import HumanMessage, SystemMessage
from loguru import logger

from .core.config import config


class ResearchPhase(Enum):
    """리서치 진행 단계"""

    INIT = "init"  # 초기 상태
    CLARIFYING = "clarifying"  # 질문 대기 중
    PLANNING = "planning"  # 계획 수립 중
    EXECUTING = "executing"  # 조사 수행 중
    REPORTING = "reporting"  # 보고서 작성 중
    COMPLETED = "completed"  # 완료


@dataclass
class ResearchSession:
    """리서치 세션 상태 관리"""

    topic: str
    phase: ResearchPhase = ResearchPhase.INIT
    clarifying_questions: list[str] = field(default_factory=list)
    user_answers: list[str] = field(default_factory=list)
    plan: list[str] = field(default_factory=list)
    findings: list[str] = field(default_factory=list)
    report: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def get_context(self) -> str:
        """현재 세션 컨텍스트를 문자열로 반환"""
        context_parts = [f"주제: {self.topic}"]

        if self.clarifying_questions and self.user_answers:
            context_parts.append("\n추가 정보:")
            for q, a in zip(self.clarifying_questions, self.user_answers):
                context_parts.append(f"  Q: {q}")
                context_parts.append(f"  A: {a}")

        if self.plan:
            context_parts.append("\n조사 계획:")
            for i, step in enumerate(self.plan, 1):
                context_parts.append(f"  {i}. {step}")

        return "\n".join(context_parts)


# 시스템 프롬프트들
CLARIFYING_PROMPT = """당신은 심층 조사를 도와주는 리서치 어시스턴트입니다.

사용자가 조사하고 싶은 주제를 제시했습니다. 더 정확하고 유용한 조사를 위해 핵심적인 질문 1~2개만 해주세요.

규칙:
- 질문은 반드시 1~2개만 생성하세요
- 조사 범위나 방향을 명확히 하는 질문이어야 합니다
- 각 질문은 한 줄로 작성하세요
- 질문 앞에 번호를 붙이세요 (1. 2.)
- 불필요한 설명 없이 질문만 출력하세요

예시 출력:
1. 특정 디렉토리나 파일에 집중해서 분석할까요, 아니면 전체 프로젝트를 대상으로 할까요?
2. 코드 구현 방식에 초점을 맞출까요, 아니면 아키텍처/설계 패턴에 초점을 맞출까요?"""

PLANNING_PROMPT = """당신은 코드베이스 조사를 계획하는 리서치 어시스턴트입니다.

주어진 주제와 추가 정보를 바탕으로 조사 계획을 수립하세요.

규칙:
- 3~5개의 구체적인 조사 단계를 생성하세요
- 각 단계는 실행 가능한 작업이어야 합니다
- 파일 시스템 도구(grep, cat, tree 등)로 수행할 수 있는 작업으로 구성하세요
- 각 단계는 한 줄로 작성하세요
- 단계 앞에 번호를 붙이세요 (1. 2. 3. ...)
- 불필요한 설명 없이 계획만 출력하세요

예시 출력:
1. 프로젝트 구조 파악 (디렉토리 트리 확인)
2. 관련 파일 검색 (키워드로 grep)
3. 핵심 파일 내용 분석
4. 패턴 및 구현 방식 정리
5. 개선점 또는 주의사항 도출"""

RESEARCH_PROMPT = """당신은 코드베이스를 조사하는 리서치 어시스턴트입니다.

현재 수행해야 할 조사 단계가 주어집니다. 해당 단계를 수행하고 발견한 내용을 정리하세요.

규칙:
- 파일 시스템 도구를 적극 활용하세요 (cat, tree, grep 등)
- 발견한 내용을 명확하고 구조화된 형식으로 정리하세요
- 코드 예시가 있다면 포함하세요
- 마크다운 형식으로 작성하세요"""

REPORT_PROMPT = """당신은 조사 결과를 보고서로 정리하는 리서치 어시스턴트입니다.

지금까지의 조사 결과를 종합하여 마크다운 보고서를 작성하세요.

보고서 구조:
1. 개요 (Summary) - 조사 주제와 핵심 발견사항 요약
2. 조사 방법 (Methodology) - 어떤 방식으로 조사했는지
3. 주요 발견사항 (Findings) - 상세한 조사 결과
4. 결론 (Conclusion) - 종합적인 분석과 제안사항

규칙:
- 마크다운 형식으로 작성하세요
- 코드 예시는 코드 블록으로 감싸세요
- 명확하고 읽기 쉽게 작성하세요"""


class ResearchAgent:
    """리서치 에이전트 - 조사 수행 및 보고서 생성"""

    def __init__(self, session: ResearchSession):
        self.session = session
        self._model = None

    def _get_model(self):
        """모델 인스턴스 반환 (지연 초기화)"""
        if self._model is None:
            from .agent import create_chat_model

            self._model = create_chat_model(
                model_name=config.MODEL_NAME,
                temperature=config.MODEL_TEMPERATURE,
            )
        return self._model

    def generate_clarifying_questions(self) -> list[str]:
        """명확화 질문 생성"""
        if config.FAKE_LLM:
            # 테스트 모드
            questions = [
                "특정 디렉토리에 집중할까요, 전체 프로젝트를 조사할까요?",
                "코드 구현에 초점을 맞출까요, 아키텍처에 초점을 맞출까요?",
            ]
        else:
            model = self._get_model()
            messages = [
                SystemMessage(content=CLARIFYING_PROMPT),
                HumanMessage(content=f"조사 주제: {self.session.topic}"),
            ]

            response = model.invoke(messages)
            content = self._normalize_content(response.content)

            # 질문 파싱 (번호로 시작하는 라인)
            questions = []
            for line in content.split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    # 번호나 불릿 제거
                    cleaned = line.lstrip("0123456789.-) ").strip()
                    if cleaned:
                        questions.append(cleaned)

        self.session.clarifying_questions = questions[:2]  # 최대 2개
        self.session.phase = ResearchPhase.CLARIFYING

        return self.session.clarifying_questions

    def generate_plan(self) -> list[str]:
        """조사 계획 생성"""
        if config.FAKE_LLM:
            # 테스트 모드
            plan = [
                "프로젝트 구조 파악",
                "관련 파일 검색",
                "핵심 파일 분석",
                "결과 정리",
            ]
        else:
            model = self._get_model()
            context = self.session.get_context()

            messages = [
                SystemMessage(content=PLANNING_PROMPT),
                HumanMessage(content=context),
            ]

            response = model.invoke(messages)
            content = self._normalize_content(response.content)

            # 계획 파싱
            plan = []
            for line in content.split("\n"):
                line = line.strip()
                if line and (line[0].isdigit() or line.startswith("-")):
                    cleaned = line.lstrip("0123456789.-) ").strip()
                    if cleaned:
                        plan.append(cleaned)

        self.session.plan = plan[:5]  # 최대 5단계
        self.session.phase = ResearchPhase.PLANNING

        return self.session.plan

    def execute_step(
        self, step_index: int, stream_callback: Callable | None = None
    ) -> str:
        """조사 단계 실행

        Args:
            step_index: 실행할 단계 인덱스
            stream_callback: 스트리밍 콜백 (event_type, data)

        Returns:
            해당 단계의 조사 결과
        """
        if step_index >= len(self.session.plan):
            return ""

        step = self.session.plan[step_index]
        self.session.phase = ResearchPhase.EXECUTING

        if config.FAKE_LLM:
            # 테스트 모드
            result = f"[{step}] 조사 결과: 테스트 모드에서 실행됨"
            self.session.findings.append(result)
            return result

        # 에이전트 스트리밍으로 조사 수행
        from . import agent

        context = self.session.get_context()
        prompt = f"""다음 조사 단계를 수행하세요:

{context}

현재 단계: {step}

파일 시스템 도구를 사용하여 조사하고 발견한 내용을 정리하세요."""

        result_parts = []

        for event_type, data in agent.stream(prompt, session_id="research_temp"):
            if stream_callback:
                stream_callback(event_type, data)

            if event_type == "response":
                result_parts.append(data)

        result = "".join(result_parts)
        self.session.findings.append(f"### {step}\n\n{result}")

        return result

    def generate_report(self) -> str:
        """최종 보고서 생성"""
        self.session.phase = ResearchPhase.REPORTING

        if config.FAKE_LLM:
            # 테스트 모드
            report = f"""# 리서치 보고서: {self.session.topic}

## 개요
테스트 모드에서 생성된 보고서입니다.

## 조사 방법
- 프로젝트 구조 분석
- 관련 파일 검색 및 분석

## 주요 발견사항
{chr(10).join(self.session.findings) if self.session.findings else '발견사항 없음'}

## 결론
테스트 모드 완료.
"""
            self.session.report = report
            self.session.phase = ResearchPhase.COMPLETED
            return report

        model = self._get_model()

        # 조사 결과 종합
        findings_text = "\n\n".join(self.session.findings)
        context = self.session.get_context()

        messages = [
            SystemMessage(content=REPORT_PROMPT),
            HumanMessage(
                content=f"""{context}

## 조사 결과
{findings_text}

위 내용을 바탕으로 종합 보고서를 작성하세요."""
            ),
        ]

        response = model.invoke(messages)
        report = self._normalize_content(response.content)

        self.session.report = report
        self.session.phase = ResearchPhase.COMPLETED

        return report

    def save_report(self, reports_dir: Path | None = None) -> Path:
        """보고서를 파일로 저장

        Args:
            reports_dir: 저장 디렉토리 (기본값: ./reports)

        Returns:
            저장된 파일 경로
        """
        if reports_dir is None:
            reports_dir = Path("reports")

        reports_dir.mkdir(parents=True, exist_ok=True)

        # 파일명 생성
        timestamp = self.session.created_at.strftime("%Y%m%d_%H%M%S")
        # 주제에서 파일명에 사용할 수 없는 문자 제거
        safe_topic = "".join(
            c if c.isalnum() or c in (" ", "-", "_") else "_"
            for c in self.session.topic[:30]
        ).strip()
        safe_topic = safe_topic.replace(" ", "_")

        filename = f"research_{timestamp}_{safe_topic}.md"
        filepath = reports_dir / filename

        # 보고서 저장
        with open(filepath, "w", encoding="utf-8") as f:
            f.write(self.session.report)

        logger.info("보고서 저장: %s", filepath)
        return filepath

    def _normalize_content(self, content) -> str:
        """메시지 content를 문자열로 정규화"""
        if isinstance(content, list):
            parts = []
            for item in content:
                if isinstance(item, dict) and item.get("type") == "text":
                    parts.append(item.get("text", ""))
            return "".join(parts).strip()
        if isinstance(content, str):
            return content.strip()
        return str(content).strip()


def create_research_session(topic: str) -> ResearchSession:
    """새 리서치 세션 생성"""
    return ResearchSession(topic=topic)


def create_research_agent(session: ResearchSession) -> ResearchAgent:
    """리서치 에이전트 생성"""
    return ResearchAgent(session)
