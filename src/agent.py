"""AI 에이전트 모듈 - Deep Agents + 멀티 Provider 지원"""

from typing import Optional

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

from .config import config


# 기본 시스템 프롬프트
DEFAULT_SYSTEM_PROMPT = """당신은 CLI Master의 AI 어시스턴트입니다.
사용자의 질문에 친절하고 정확하게 답변해주세요.
한국어로 응답합니다."""


def create_chat_model(
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
):
    """LLM 모델 생성 (멀티 provider 지원)

    지원 모델 예시:
        - gemini-2.5-flash, gemini-2.5-pro (Google)
        - gpt-4o, gpt-4-turbo (OpenAI)
        - claude-sonnet-4-20250514 (Anthropic)
    """
    return init_chat_model(
        model=model_name or config.MODEL_NAME,
        temperature=temperature or config.MODEL_TEMPERATURE,
    )


def create_agent(
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    tools: Optional[list] = None,
    model_name: Optional[str] = None,
    temperature: Optional[float] = None,
):
    """Deep Agent 생성

    Args:
        system_prompt: 시스템 프롬프트
        tools: 에이전트가 사용할 도구 목록
        model_name: 모델명 (기본값: config.MODEL_NAME)
        temperature: 생성 온도 (기본값: config.MODEL_TEMPERATURE)

    Returns:
        Deep Agent 인스턴스
    """
    model = create_chat_model(model_name=model_name, temperature=temperature)

    return create_deep_agent(
        model=model,
        system_prompt=system_prompt,
        tools=tools or [],
    )


class AIAgent:
    """AI 에이전트 래퍼 클래스"""

    def __init__(
        self,
        system_prompt: Optional[str] = None,
        tools: Optional[list] = None,
        model_name: Optional[str] = None,
        temperature: Optional[float] = None,
    ):
        """에이전트 초기화

        Args:
            system_prompt: 커스텀 시스템 프롬프트
            tools: 에이전트가 사용할 도구 목록
            model_name: 모델명 (기본값: config.MODEL_NAME)
            temperature: 생성 온도 (기본값: config.MODEL_TEMPERATURE)
        """
        self.agent = create_agent(
            system_prompt=system_prompt or DEFAULT_SYSTEM_PROMPT,
            tools=tools,
            model_name=model_name,
            temperature=temperature,
        )

    def chat(self, message: str) -> str:
        """메시지를 보내고 응답을 받음

        Args:
            message: 사용자 메시지

        Returns:
            AI 응답 텍스트
        """
        result = self.agent.invoke({
            "messages": [{"role": "user", "content": message}]
        })
        return result["messages"][-1].content

    def stream(self, message: str):
        """스트리밍 응답 생성

        Args:
            message: 사용자 메시지

        Yields:
            응답 청크
        """
        for chunk in self.agent.stream({
            "messages": [{"role": "user", "content": message}]
        }):
            if "messages" in chunk and chunk["messages"]:
                yield chunk["messages"][-1].content
