"""AI 에이전트 모듈 - Deep Agents + 멀티 Provider 지원"""

from deepagents import create_deep_agent
from langchain.chat_models import init_chat_model
from langchain_google_genai import ChatGoogleGenerativeAI

from .config import config

# provider 매핑 (모델명 prefix -> factory 함수)
PROVIDER_MAP = {
    "gemini": lambda model, **kwargs: ChatGoogleGenerativeAI(model=model, **kwargs),
}


def create_chat_model(model_name: str, **kwargs):
    """모델명 prefix로 provider 결정"""
    for prefix, factory in PROVIDER_MAP.items():
        if model_name.startswith(prefix):
            return factory(model_name, **kwargs)
    # fallback: init_chat_model 자동 추론
    return init_chat_model(model=model_name, **kwargs)

DEFAULT_SYSTEM_PROMPT = """당신은 CLI Master의 AI 어시스턴트입니다.
사용자의 질문에 친절하고 정확하게 답변해주세요.
한국어로 응답합니다."""

# 싱글톤 agent 인스턴스
_agent = None


def _get_agent():
    """싱글톤 agent 인스턴스 반환 (지연 초기화)"""
    global _agent
    if _agent is None:
        model = create_chat_model(
            model_name=config.MODEL_NAME,
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
        if "model" in chunk and "messages" in chunk["model"]:
            yield chunk["model"]["messages"][-1].content
