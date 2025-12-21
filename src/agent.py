"""AI 에이전트 모듈 - Deep Agents + 멀티 Provider 지원"""

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model

from .config import config

DEFAULT_SYSTEM_PROMPT = """당신은 CLI Master의 AI 어시스턴트입니다.
사용자의 질문에 친절하고 정확하게 답변해주세요.
한국어로 응답합니다."""

# 싱글톤 agent 인스턴스
_agent = None


def _get_agent():
    """싱글톤 agent 인스턴스 반환 (지연 초기화)"""
    global _agent
    if _agent is None:
        model = init_chat_model(
            model=config.MODEL_NAME,
            temperature=config.MODEL_TEMPERATURE,
        )
        _agent = create_deep_agent(
            model=model,
            system_prompt=DEFAULT_SYSTEM_PROMPT,
            tools=[],
        )
    return _agent


def chat(message: str) -> str:
    """메시지를 보내고 응답을 받음"""
    result = _get_agent().invoke({
        "messages": [{"role": "user", "content": message}]
    })
    return result["messages"][-1].content


def stream(message: str):
    """스트리밍 응답 생성"""
    for chunk in _get_agent().stream({
        "messages": [{"role": "user", "content": message}]
    }):
        if "messages" in chunk and chunk["messages"]:
            yield chunk["messages"][-1].content
