"""AI 에이전트 모듈 - LangGraph ReAct Agent"""

import logging
from typing import TypedDict, Annotated, Sequence
from operator import add

from langchain_core.messages import BaseMessage, HumanMessage, AIMessage, ToolMessage, SystemMessage
from langchain.chat_models import init_chat_model
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.agent_toolkits import FileManagementToolkit
from langchain_core.tools import tool
from langgraph.graph import StateGraph, END

from .config import config

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

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
- `list_directory`: 디렉토리 내용 나열
- `read_file`: 파일 읽기
- `write_file`: 파일 작성
- `file_search`: 파일 패턴 검색 (glob)
- `edit_file`: 파일 편집
- `grep`: 파일 내용 검색
- `copy_file`: 파일 복사
- `move_file`: 파일 이동
- `file_delete`: 파일 삭제

## 응답 지침
- 사용자의 질문에 친절하고 정확하게 답변하세요.
- 한국어로 응답합니다."""


# 커스텀 도구 정의
@tool
def edit_file(file_path: str, old_text: str, new_text: str) -> str:
    """파일의 일부를 수정합니다.

    Args:
        file_path: 파일 경로
        old_text: 찾을 텍스트
        new_text: 교체할 텍스트

    Returns:
        성공/실패 메시지
    """
    try:
        with open(file_path, 'r', encoding='utf-8') as f:
            content = f.read()

        if old_text not in content:
            return f"오류: '{old_text}'를 {file_path}에서 찾을 수 없습니다"

        new_content = content.replace(old_text, new_text)

        with open(file_path, 'w', encoding='utf-8') as f:
            f.write(new_content)

        return f"{file_path} 파일이 성공적으로 수정되었습니다"
    except Exception as e:
        return f"파일 편집 오류: {str(e)}"


@tool
def grep(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    """파일에서 텍스트 패턴을 검색합니다.

    Args:
        pattern: 검색할 텍스트 또는 정규식 패턴
        path: 검색할 디렉토리 (기본: 현재 디렉토리)
        file_pattern: 파일 패턴 (기본: 모든 파일)

    Returns:
        검색 결과 (파일 경로와 줄 번호 포함)
    """
    import re
    import glob
    import os

    results = []
    pattern_re = re.compile(pattern)

    search_pattern = os.path.join(path, "**", file_pattern)
    for file_path in glob.glob(search_pattern, recursive=True):
        if os.path.isfile(file_path):
            try:
                with open(file_path, 'r', encoding='utf-8') as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern_re.search(line):
                            results.append(f"{file_path}:{line_num}: {line.strip()}")
            except:
                pass

    if not results:
        return f"'{pattern}' 패턴과 일치하는 결과를 찾지 못했습니다"

    return "\n".join(results[:50])  # 최대 50개 결과


# State 정의
class AgentState(TypedDict):
    """LangGraph 에이전트 상태"""
    messages: Annotated[Sequence[BaseMessage], add]


# 싱글톤 graph 인스턴스
_graph = None
_tools_by_name = {}


def _get_graph():
    """싱글톤 graph 인스턴스 반환 (지연 초기화)"""
    global _graph, _tools_by_name

    if _graph is None:
        # 1. 모델 생성
        model = create_chat_model(
            model_name=config.MODEL_NAME,
            temperature=config.MODEL_TEMPERATURE,
        )

        # 2. 도구 준비
        toolkit = FileManagementToolkit(
            root_dir=".",
            selected_tools=["read_file", "write_file", "list_directory", "file_search",
                          "copy_file", "move_file", "file_delete"]
        )
        toolkit_tools = toolkit.get_tools()
        custom_tools = [edit_file, grep]
        all_tools = toolkit_tools + custom_tools

        _tools_by_name = {tool.name: tool for tool in all_tools}
        logger.info("Loaded %s tools: %s", len(all_tools), list(_tools_by_name.keys()))

        # 3. 모델에 도구 바인딩
        model_with_tools = model.bind_tools(all_tools)

        # 4. 노드 정의
        def call_model(state: AgentState):
            """에이전트 노드: 도구와 함께 모델 호출"""
            messages = state["messages"]

            # 첫 턴일 경우 시스템 프롬프트 주입
            if len(messages) == 1 and isinstance(messages[0], HumanMessage):
                messages = [SystemMessage(content=DEFAULT_SYSTEM_PROMPT)] + list(messages)

            response = model_with_tools.invoke(messages)
            return {"messages": [response]}

        def execute_tools(state: AgentState):
            """도구 노드: 요청된 도구 실행"""
            messages = state["messages"]
            last_message = messages[-1]

            if not hasattr(last_message, "tool_calls"):
                return {"messages": []}

            tool_calls = last_message.tool_calls

            tool_messages = []
            for tool_call in tool_calls:
                tool = _tools_by_name.get(tool_call["name"])
                if not tool:
                    tool_messages.append(ToolMessage(
                        content=f"오류: 도구 '{tool_call['name']}'를 찾을 수 없습니다",
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"]
                    ))
                    continue

                try:
                    result = tool.invoke(tool_call["args"])
                    tool_messages.append(ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"]
                    ))
                except Exception as e:
                    logger.error("Tool execution error: %s", str(e))
                    tool_messages.append(ToolMessage(
                        content=f"오류: {str(e)}",
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"]
                    ))

            return {"messages": tool_messages}

        def should_continue(state: AgentState):
            """라우팅 로직"""
            last_message = state["messages"][-1]
            if hasattr(last_message, "tool_calls") and last_message.tool_calls:
                return "tools"
            return END

        # 5. 그래프 구축
        workflow = StateGraph(AgentState)
        workflow.add_node("agent", call_model)
        workflow.add_node("tools", execute_tools)
        workflow.set_entry_point("agent")
        workflow.add_conditional_edges(
            "agent",
            should_continue,
            {
                "tools": "tools",
                END: END
            }
        )
        workflow.add_edge("tools", "agent")

        _graph = workflow.compile()
        logger.info("LangGraph agent initialized successfully")

    return _graph


def chat(message: str) -> str:
    """메시지를 보내고 응답을 받음"""
    graph = _get_graph()

    result = graph.invoke({
        "messages": [HumanMessage(content=message)]
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
    import asyncio

    graph = _get_graph()

    initial_state = {
        "messages": [HumanMessage(content=message)]
    }

    response_chunks = []
    current_tool_calls = {}

    async def _async_stream():
        """내부 비동기 스트리밍"""
        async for event in graph.astream_events(initial_state, version="v2"):
            kind = event["event"]

            if kind == "on_tool_start":
                tool_name = event.get("name", "unknown")
                tool_input = event.get("data", {}).get("input", {})
                args_str = str(tool_input) if tool_input else ""

                # tool_end와 매칭하기 위해 저장
                run_id = event.get("run_id", "")
                current_tool_calls[run_id] = tool_name

                yield ("tool_start", {
                    "name": tool_name,
                    "args": args_str
                })

            elif kind == "on_tool_end":
                tool_name = event.get("name", "unknown")
                tool_output = event.get("data", {}).get("output", "")

                yield ("tool_end", {
                    "name": tool_name,
                    "result": str(tool_output)
                })

            elif kind == "on_chat_model_stream":
                chunk = event.get("data", {}).get("chunk")
                if chunk and hasattr(chunk, "content") and chunk.content:
                    # content 추출
                    content = chunk.content

                    # content가 리스트일 경우 (Gemini의 경우)
                    if isinstance(content, list):
                        # [{'type': 'text', 'text': '...'}, ...] 형태에서 텍스트 추출
                        for item in content:
                            if isinstance(item, dict) and item.get('type') == 'text':
                                response_chunks.append(item.get('text', ''))
                    elif isinstance(content, str):
                        response_chunks.append(content)

        # 최종 응답 반환
        if response_chunks:
            final_response = "".join(response_chunks)
            yield ("response", final_response)

    # 비동기 제너레이터를 동기로 변환
    async_gen = _async_stream()

    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)

    while True:
        try:
            yield loop.run_until_complete(async_gen.__anext__())
        except StopAsyncIteration:
            break
