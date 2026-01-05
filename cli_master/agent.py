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


class PlanExecuteState(TypedDict):
    """Plan-and-Execute 에이전트 상태"""

    # 기존 호환성
    messages: Annotated[Sequence[BaseMessage], add]
    # Plan-Execute 필드
    input: str  # 원래 사용자 입력
    plan: list[str]  # 실행할 계획 단계들
    current_step_index: int  # 현재 실행 중인 단계 인덱스
    past_steps: Annotated[list[tuple[str, str]], add]  # (단계, 결과) 히스토리
    response: str | None  # 최종 응답 (완료 시)
    replan_count: int  # 재계획 횟수 (최대 3회)


def classify_request(message: str, llm: ChatGoogleGenerativeAI | None = None) -> str:
    """단순 질문 vs 복잡한 작업 분류

    Args:
        message: 사용자 입력 메시지
        llm: LLM 인스턴스 (제공 시 LLM 기반 분류, 없으면 룰베이스)

    Returns:
        "simple" | "complex"
    """
    # LLM 기반 분류
    if llm is not None:
        from .models import ComplexityClassification

        classifier = llm.with_structured_output(ComplexityClassification)
        prompt = f"""다음 사용자 요청을 분류하세요:

요청: {message}

분류 기준:
- simple: 단순 질문, 정보 조회, 한 번의 응답으로 완료 가능
- complex: 여러 단계 필요, 파일 수정, 분석 후 작업 등"""

        result: ComplexityClassification = classifier.invoke(prompt)  # type: ignore[assignment]
        return result.complexity

    # 룰베이스 fallback
    complex_keywords = [
        "분석",
        "업데이트",
        "수정",
        "생성",
        "삭제",
        "리팩토링",
        "그리고",
        "후에",
        "읽고",
        "요약",
    ]

    if any(kw in message for kw in complex_keywords):
        return "complex"

    if len(message) < 20:
        return "simple"

    return "complex"


def plan_step(state: PlanExecuteState) -> dict:
    """Planner 노드: 사용자 요청을 분석하여 다단계 계획 생성

    Args:
        state: 현재 에이전트 상태

    Returns:
        plan과 current_step_index를 포함하는 dict
    """
    if config.FAKE_LLM:
        # 테스트 모드: 간단한 계획 반환
        return {"plan": ["단계 1: 작업 수행"], "current_step_index": 0}

    # TODO: 실제 LLM 호출로 계획 생성
    # 지금은 간단한 기본 계획 반환
    user_input = state.get("input", "")
    return {
        "plan": [f"작업 수행: {user_input}"],
        "current_step_index": 0,
    }


def execute_step(state: PlanExecuteState) -> dict:
    """Executor 노드: 현재 단계를 실행

    Args:
        state: 현재 에이전트 상태

    Returns:
        current_step_index 증가 + past_steps에 결과 추가
    """
    plan = state.get("plan", [])
    current_idx = state.get("current_step_index", 0)

    # 모든 단계가 완료된 경우
    if current_idx >= len(plan):
        return {"response": "모든 단계가 완료되었습니다."}

    current_task = plan[current_idx]

    if config.FAKE_LLM:
        # 테스트 모드: 간단한 결과 반환
        result = f"fake 실행 결과: {current_task}"
    else:
        # TODO: 실제 도구 호출로 작업 수행
        result = f"실행 완료: {current_task}"

    return {
        "past_steps": [(current_task, result)],
        "current_step_index": current_idx + 1,
    }


# 최대 재계획 횟수
MAX_REPLAN_COUNT = 3


def replan_step(state: PlanExecuteState) -> dict:
    """Replanner 노드: 실행 결과를 평가하고 완료/재계획 결정

    Args:
        state: 현재 에이전트 상태

    Returns:
        response (완료 시) 또는 새 plan + replan_count 증가 (재계획 시)
    """
    replan_count = state.get("replan_count", 0)
    past_steps = state.get("past_steps", [])
    user_input = state.get("input", "")

    # 재계획 횟수 제한 도달 시 강제 종료
    if replan_count >= MAX_REPLAN_COUNT:
        # 지금까지의 결과를 요약하여 응답
        results_summary = "\n".join([f"- {step}: {result}" for step, result in past_steps])
        return {
            "response": f"최대 재계획 횟수({MAX_REPLAN_COUNT}회)에 도달했습니다.\n\n실행 결과:\n{results_summary}"
        }

    if config.FAKE_LLM:
        # 테스트 모드: 간단한 응답 반환
        results_summary = "\n".join([f"- {step}: {result}" for step, result in past_steps])
        return {"response": f"작업이 완료되었습니다.\n\n결과:\n{results_summary}"}

    # TODO: 실제 LLM 호출로 완료 여부 판단
    # 지금은 간단히 완료 처리
    results_summary = "\n".join([f"- {step}: {result}" for step, result in past_steps])
    return {"response": f"'{user_input}' 작업이 완료되었습니다.\n\n결과:\n{results_summary}"}


def _build_hybrid_graph(checkpointer):
    """하이브리드 그래프 생성 (ReAct + Plan-Execute)

    구조:
    [Start] → Router → (단순) → agent → tools → ... → [End]
                     → (복잡) → planner → executor → replanner → [End]
    """
    from langchain_core.messages import HumanMessage

    # 노드 함수 정의
    def router_node(state: PlanExecuteState) -> dict:
        """라우터: 요청 복잡도에 따라 경로 결정"""
        messages = state.get("messages", [])
        if messages:
            last_human = None
            for msg in reversed(messages):
                if isinstance(msg, HumanMessage):
                    last_human = msg.content
                    break
            if last_human:
                return {"input": last_human}
        return {"input": state.get("input", "")}

    def route_by_complexity(state: PlanExecuteState) -> str:
        """복잡도 기반 라우팅 결정"""
        user_input = state.get("input", "")
        return classify_request(user_input)

    def planner_node(state: PlanExecuteState) -> dict:
        """Planner 노드 래퍼"""
        return plan_step(state)

    def executor_node(state: PlanExecuteState) -> dict:
        """Executor 노드 래퍼"""
        return execute_step(state)

    def replanner_node(state: PlanExecuteState) -> dict:
        """Replanner 노드 래퍼"""
        return replan_step(state)

    def should_continue_execution(state: PlanExecuteState) -> str:
        """실행 계속 여부 결정"""
        # 응답이 생성되었으면 종료
        if state.get("response"):
            return END

        # 모든 단계가 완료되면 replanner로
        plan = state.get("plan", [])
        current_idx = state.get("current_step_index", 0)
        if current_idx >= len(plan):
            return "replanner"

        # 아직 실행할 단계가 있으면 계속 실행
        return "executor"

    def should_replan(state: PlanExecuteState) -> str:
        """재계획 또는 종료 결정"""
        # 응답이 있으면 종료
        if state.get("response"):
            return END
        # 새 계획이 있으면 다시 실행
        return "executor"

    # 그래프 구축
    workflow = StateGraph(PlanExecuteState)

    # 노드 추가
    workflow.add_node("router", router_node)
    workflow.add_node("planner", planner_node)
    workflow.add_node("executor", executor_node)
    workflow.add_node("replanner", replanner_node)

    # 시작점
    workflow.set_entry_point("router")

    # 라우터 조건부 엣지 (simple → END, complex → planner)
    workflow.add_conditional_edges(
        "router",
        route_by_complexity,
        {"simple": END, "complex": "planner"},
    )

    # planner → executor
    workflow.add_edge("planner", "executor")

    # executor → (조건부) → executor/replanner/END
    workflow.add_conditional_edges(
        "executor",
        should_continue_execution,
        {"executor": "executor", "replanner": "replanner", END: END},
    )

    # replanner → (조건부) → executor/END
    workflow.add_conditional_edges(
        "replanner",
        should_replan,
        {"executor": "executor", END: END},
    )

    return workflow.compile(checkpointer=checkpointer)


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


def stream_hybrid(message: str, session_id: str = "default"):
    """하이브리드 그래프 스트리밍 응답 생성

    Args:
        message: 사용자 메시지
        session_id: 세션 ID

    Yields:
        tuple: (event_type, data)
        - ("plan_start", {"steps": list[str]}): 계획 생성 완료
        - ("step_start", {"step": str, "index": int}): 단계 실행 시작
        - ("step_end", {"step": str, "result": str}): 단계 실행 완료
        - ("response", str): 최종 응답
    """
    if config.FAKE_LLM:
        # 테스트 모드: 하이브리드 그래프를 실제로 실행
        _graph = _build_hybrid_graph(checkpointer=None)

        initial_state: PlanExecuteState = {
            "messages": [HumanMessage(content=message)],
            "input": message,
            "plan": [],
            "current_step_index": 0,
            "past_steps": [],
            "response": None,
            "replan_count": 0,
        }

        # 단순 요청인 경우
        if classify_request(message) == "simple":
            yield ("response", f"fake: {message}")
            return

        # 복잡한 요청: Plan-Execute 흐름
        # 1. 계획 생성
        plan_result = plan_step(initial_state)
        steps = plan_result.get("plan", [])
        yield ("plan_start", {"steps": steps})

        # 2. 각 단계 실행
        current_state: PlanExecuteState = {
            **initial_state,
            "plan": plan_result.get("plan", []),
            "current_step_index": plan_result.get("current_step_index", 0),
        }
        while current_state.get("current_step_index", 0) < len(steps):
            step_idx = current_state["current_step_index"]
            step_name = steps[step_idx]

            yield ("step_start", {"step": step_name, "index": step_idx})

            exec_result = execute_step(current_state)

            # past_steps는 리듀서로 누적되므로 직접 병합
            new_past_steps = list(current_state.get("past_steps", []))
            if "past_steps" in exec_result:
                new_past_steps.extend(exec_result["past_steps"])

            current_state = {
                **current_state,
                "current_step_index": exec_result.get(
                    "current_step_index", current_state["current_step_index"]
                ),
                "past_steps": new_past_steps,
                "response": exec_result.get("response"),
            }

            if exec_result.get("past_steps"):
                _, result = exec_result["past_steps"][0]
                yield ("step_end", {"step": step_name, "result": result})

        # 3. Replanner로 최종 응답 생성
        replan_result = replan_step(current_state)
        if replan_result.get("response"):
            yield ("response", replan_result["response"])

        return

    # 실제 LLM 모드 (향후 구현)
    yield ("response", f"LLM 응답: {message}")
