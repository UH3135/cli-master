"""AI 에이전트 모듈 - LangGraph ReAct Agent"""

from typing import TypedDict, Annotated, Sequence
from operator import add
import sqlite3

from loguru import logger

from langchain_core.messages import (
    BaseMessage,
    HumanMessage,
    ToolMessage,
    SystemMessage,
)
from langchain.chat_models import init_chat_model
from langchain_google_genai import ChatGoogleGenerativeAI
from langchain_community.agent_toolkits import FileManagementToolkit
from langgraph.checkpoint.sqlite import SqliteSaver
import aiosqlite
from langgraph.checkpoint.sqlite.aio import AsyncSqliteSaver
from langgraph.graph import StateGraph, END

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

## 작업 방식 (TODO 기반)
- 사용자가 복잡한 문제를 던지면, 바로 답을 단정하지 말고 먼저 문제를 작은 작업 단위로 분해해 TODO를 생성하세요.
- TODO는 반드시 도구로 관리합니다: create_todo / list_todos / update_todo_status / clear_todos
- 기본 흐름:
  - (1) 필요한 TODO를 생성한다 (create_todo)
  - (2) TODO를 하나씩 진행 처리한다 (update_todo_status: in_progress → completed)
  - (3) 중간/최종 응답에는 현재 TODO 진행 상황을 간단히 요약한다
- 단순 질문(설명/정의/짧은 조회)은 굳이 TODO를 만들지 말고 바로 답변합니다.

## 도구 사용 원칙
- 파일 시스템 작업이 필요하면 반드시 도구를 사용하세요.
- 정보를 추측하지 말고 도구로 직접 확인하세요.
- 사용자 요청을 완료하기 위해 필요한 모든 도구를 적극 활용하세요.
- 한 번의 응답에서 여러 도구를 연속으로 사용할 수 있습니다.

## 응답 지침
- 사용자의 질문에 친절하고 정확하게 답변하세요.
- 한국어로 응답합니다."""


# State 정의
class AgentState(TypedDict):
    """LangGraph 에이전트 상태"""

    messages: Annotated[Sequence[BaseMessage], add]


# 싱글톤 graph 인스턴스
_graph = None
_checkpointer = None
_checkpointer_connection = None


def _build_graph(checkpointer):
    """checkpointer를 받아 graph를 생성"""
    # 1. 모델 생성
    model = create_chat_model(
        model_name=config.MODEL_NAME,
        temperature=config.MODEL_TEMPERATURE,
    )

    # 2. 도구 준비 (Registry 사용)
    from .registry import get_registry, ToolCategory

    registry = get_registry()

    # LangChain 도구를 Registry에 등록
    toolkit = FileManagementToolkit(
        root_dir=".",
        selected_tools=[
            "read_file",
            "write_file",
            "list_directory",
            "file_search",
            "copy_file",
            "move_file",
            "file_delete",
        ],
    )
    registry.register_multiple(
        toolkit.get_tools(), category=ToolCategory.FILESYSTEM, replace=True
    )

    # Registry에서 모든 도구 가져오기
    all_tools = registry.get_all_tools()

    tools_by_name = {tool.name: tool for tool in all_tools}
    logger.info("Loaded {} tools: {}", len(all_tools), list(tools_by_name.keys()))

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
            tool = tools_by_name.get(tool_call["name"])
            if not tool:
                tool_messages.append(
                    ToolMessage(
                        content=f"오류: 도구 '{tool_call['name']}'를 찾을 수 없습니다",
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"],
                    )
                )
                continue

            try:
                result = tool.invoke(tool_call["args"])
                tool_messages.append(
                    ToolMessage(
                        content=str(result),
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"],
                    )
                )
            except Exception as e:
                logger.error("Tool execution error: {}", str(e))
                tool_messages.append(
                    ToolMessage(
                        content=f"오류: {str(e)}",
                        tool_call_id=tool_call["id"],
                        name=tool_call["name"],
                    )
                )

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
        "agent", should_continue, {"tools": "tools", END: END}
    )
    workflow.add_edge("tools", "agent")

    return workflow.compile(checkpointer=checkpointer)


def _get_graph():
    """싱글톤 graph 인스턴스 반환 (지연 초기화)"""
    global _graph, _checkpointer

    if _graph is None:
        global _checkpointer_connection
        if _checkpointer_connection is None:
            _checkpointer_connection = sqlite3.connect(str(config.CHECKPOINT_DB_PATH))
        _checkpointer = SqliteSaver(conn=_checkpointer_connection)
        _graph = _build_graph(_checkpointer)
        logger.info("LangGraph agent initialized with memory")

    return _graph


def chat(message: str, session_id: str = "default") -> str:
    """메시지를 보내고 응답을 받음 (메모리 지원)

    Args:
        message: 사용자 메시지
        session_id: 세션 ID (동일 ID면 대화 컨텍스트 유지)
    """
    if config.FAKE_LLM:
        # 테스트에서 외부 호출 없이 즉시 응답
        return f"fake: {message}"
    graph = _get_graph()

    runtime_config = {"configurable": {"thread_id": session_id}}
    result = graph.invoke({"messages": [HumanMessage(content=message)]}, runtime_config)

    return result["messages"][-1].content


def stream(message: str, session_id: str = "default"):
    """스트리밍 응답 생성 (메모리 지원)

    Args:
        message: 사용자 메시지
        session_id: 세션 ID (동일 ID면 대화 컨텍스트 유지)

    Yields:
        tuple: (event_type, data)
        - ("tool_start", {"name": str, "args": str}): 도구 호출 시작
        - ("tool_end", {"name": str, "result": str}): 도구 완료
        - ("response", str): 최종 응답
    """
    import asyncio

    if config.FAKE_LLM:
        # 테스트에서 체크포인트/LLM 호출 없이 응답 반환
        yield ("response", f"fake: {message}")
        return

    runtime_config = {"configurable": {"thread_id": session_id}}
    initial_state = {"messages": [HumanMessage(content=message)]}

    response_chunks = []
    current_tool_calls = {}

    async def _async_stream():
        """내부 비동기 스트리밍"""
        async with aiosqlite.connect(str(config.CHECKPOINT_DB_PATH)) as conn:
            # langgraph-checkpoint-sqlite가 기대하는 is_alive가 없으면 보완
            if not hasattr(conn, "is_alive"):
                conn.is_alive = lambda: conn._running
            checkpointer = AsyncSqliteSaver(conn)
            graph = _build_graph(checkpointer)

            async for event in graph.astream_events(
                initial_state, config=runtime_config, version="v2"
            ):
                kind = event["event"]

                if kind == "on_tool_start":
                    tool_name = event.get("name", "unknown")
                    tool_input = event.get("data", {}).get("input", {})
                    args_str = str(tool_input) if tool_input else ""

                    # tool_end와 매칭하기 위해 저장
                    run_id = event.get("run_id", "")
                    current_tool_calls[run_id] = tool_name

                    yield ("tool_start", {"name": tool_name, "args": args_str})

                elif kind == "on_tool_end":
                    tool_name = event.get("name", "unknown")
                    tool_output = event.get("data", {}).get("output", "")

                    yield ("tool_end", {"name": tool_name, "result": str(tool_output)})

                elif kind == "on_chat_model_stream":
                    chunk = event.get("data", {}).get("chunk")
                    if chunk and hasattr(chunk, "content") and chunk.content:
                        # content 추출
                        content = chunk.content

                        # content가 리스트일 경우 (Gemini의 경우)
                        if isinstance(content, list):
                            # [{'type': 'text', 'text': '...'}, ...] 형태에서 텍스트 추출
                            for item in content:
                                if (
                                    isinstance(item, dict)
                                    and item.get("type") == "text"
                                ):
                                    response_chunks.append(item.get("text", ""))
                        elif isinstance(content, str):
                            response_chunks.append(content)

        # 최종 응답 반환
        if response_chunks:
            final_response = "".join(response_chunks)
            yield ("response", final_response)

    # 비동기 제너레이터를 동기로 변환
    async_gen = _async_stream()

    created_new_loop = False
    try:
        loop = asyncio.get_event_loop()
    except RuntimeError:
        loop = asyncio.new_event_loop()
        asyncio.set_event_loop(loop)
        created_new_loop = True

    try:
        while True:
            try:
                yield loop.run_until_complete(async_gen.__anext__())
            except StopAsyncIteration:
                break
    finally:
        # 비동기 리소스 정리를 보장
        try:
            loop.run_until_complete(async_gen.aclose())
        except Exception:
            pass

        if created_new_loop:
            try:
                pending = asyncio.all_tasks(loop)
                for task in pending:
                    task.cancel()
                loop.run_until_complete(
                    asyncio.gather(*pending, return_exceptions=True)
                )
                loop.run_until_complete(loop.shutdown_asyncgens())
            except Exception:
                pass
            finally:
                loop.close()
