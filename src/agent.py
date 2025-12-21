"""AI 에이전트 모듈 - Deep Agents + Gemini 2.5 Flash"""

import os
from typing import Optional

from deepagents import create_deep_agent
from langchain_google_genai import ChatGoogleGenerativeAI


# 기본 시스템 프롬프트
DEFAULT_SYSTEM_PROMPT = """당신은 CLI Master의 AI 어시스턴트입니다.
사용자의 질문에 친절하고 정확하게 답변해주세요.
한국어로 응답합니다."""


def create_gemini_model(
    temperature: float = 0.7,
    api_key: Optional[str] = None,
) -> ChatGoogleGenerativeAI:
    """Gemini 2.5 Flash 모델 생성"""
    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        temperature=temperature,
        google_api_key=api_key or os.getenv("GOOGLE_API_KEY"),
    )


def create_agent(
    system_prompt: str = DEFAULT_SYSTEM_PROMPT,
    tools: Optional[list] = None,
    temperature: float = 0.7,
):
    """Deep Agent 생성

    Args:
        system_prompt: 시스템 프롬프트
        tools: 에이전트가 사용할 도구 목록
        temperature: 생성 온도 (0.0 ~ 1.0)

    Returns:
        Deep Agent 인스턴스
    """
    model = create_gemini_model(temperature=temperature)

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
        temperature: float = 0.7,
    ):
        """에이전트 초기화

        Args:
            system_prompt: 커스텀 시스템 프롬프트
            tools: 에이전트가 사용할 도구 목록
            temperature: 생성 온도
        """
        self.agent = create_agent(
            system_prompt=system_prompt or DEFAULT_SYSTEM_PROMPT,
            tools=tools,
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
