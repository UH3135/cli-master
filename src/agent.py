"""AI 에이전트 모듈 - Deep Agents + 멀티 Provider 지원"""

from deepagents import create_deep_agent
from deepagents.backends import FilesystemBackend
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

## 도구 사용 원칙
- 파일 시스템 작업이 필요하면 반드시 도구를 사용하세요.
- 정보를 추측하지 말고 도구로 직접 확인하세요.
- 사용자 요청을 완료하기 위해 필요한 모든 도구를 적극 활용하세요.
- 한 번의 응답에서 여러 도구를 연속으로 사용할 수 있습니다.

## 사용 가능한 도구
- `ls`: 디렉토리 내용 나열
- `read_file`: 파일 읽기
- `write_file`: 파일 작성
- `edit_file`: 파일 편집
- `glob`: 파일 패턴 검색
- `grep`: 파일 내용 검색

## 응답 지침
- 사용자의 질문에 친절하고 정확하게 답변하세요.
- 한국어로 응답합니다."""

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
            backend=FilesystemBackend(),
        )
    return _agent


def chat(message: str) -> str:
    """메시지를 보내고 응답을 받음"""
    result = _get_agent().invoke({
        "messages": [{"role": "user", "content": message}]
    })
    return result["messages"][-1].content


def stream(message: str):
    """스트리밍 응답 생성

    Yields:
        tuple: (event_type, data)
        - ("tool_start", {"name": str, "args": str}): 도구 호출 시작
        - ("tool_end", {"name": str, "result": str}): 도구 완료
        - ("response", str): 최종 응답
    """
    for chunk in _get_agent().stream({
        "messages": [{"role": "user", "content": message}]
    }):
        # 모델 응답 처리
        if "model" in chunk and "messages" in chunk["model"]:
            msg = chunk["model"]["messages"][-1]
            additional = getattr(msg, "additional_kwargs", {})

            if "function_call" in additional:
                # 도구 호출 시작
                fc = additional["function_call"]
                yield ("tool_start", {
                    "name": fc.get("name", "unknown"),
                    "args": fc.get("arguments", "")
                })
            elif hasattr(msg, "content") and msg.content:
                # 최종 응답 (text 또는 content 사용)
                response_text = getattr(msg, "text", None) or msg.content
                yield ("response", response_text)

        # 도구 실행 결과
        if "tools" in chunk and "messages" in chunk["tools"]:
            tool_msg = chunk["tools"]["messages"][-1]
            yield ("tool_end", {
                "name": getattr(tool_msg, "name", "unknown"),
                "result": getattr(tool_msg, "content", "")
            })
