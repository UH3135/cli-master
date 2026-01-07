"""Plan-Execute 패턴 테스트"""

import pytest
from operator import add


class TestPlanModel:
    """Plan 모델 테스트"""

    def test_plan_with_steps(self):
        """Plan 모델이 단계 리스트를 정상 저장하는지 확인"""
        from cli_master.models import Plan

        plan = Plan(steps=["1단계", "2단계"])
        assert plan.steps == ["1단계", "2단계"]

    def test_plan_empty_steps(self):
        """빈 계획도 유효하게 처리되는지 확인"""
        from cli_master.models import Plan

        plan = Plan(steps=[])
        assert plan.steps == []


class TestResponseModel:
    """Response 모델 테스트"""

    def test_response_with_content(self):
        """Response 모델이 응답 문자열을 저장하는지 확인"""
        from cli_master.models import Response

        resp = Response(response="완료되었습니다")
        assert resp.response == "완료되었습니다"


class TestActModel:
    """Act 모델 테스트 - Replanner의 Union 타입 출력"""

    def test_act_with_response(self):
        """Act가 Response 타입을 올바르게 래핑하는지 확인"""
        from cli_master.models import Act, Response

        act = Act(action=Response(response="완료"))
        assert isinstance(act.action, Response)

    def test_act_with_plan(self):
        """Act가 Plan 타입을 올바르게 래핑하는지 확인 (재계획 시나리오)"""
        from cli_master.models import Act, Plan

        act = Act(action=Plan(steps=["새 단계"]))
        assert isinstance(act.action, Plan)


class TestPlanExecuteState:
    """PlanExecuteState 테스트"""

    def test_state_has_required_fields(self):
        """State가 Plan-Execute에 필요한 모든 필드를 포함하는지 확인"""
        from cli_master.agent import PlanExecuteState

        state: PlanExecuteState = {
            "messages": [],
            "input": "테스트 입력",
            "plan": ["단계1"],
            "current_step_index": 0,
            "past_steps": [],
            "response": None,
            "replan_count": 0,
        }
        assert state["input"] == "테스트 입력"
        assert state["replan_count"] == 0

    def test_past_steps_accumulation(self):
        """past_steps가 operator.add로 누적되는지 확인 (LangGraph 리듀서 동작)"""
        steps1 = [("단계1", "결과1")]
        steps2 = [("단계2", "결과2")]
        result = add(steps1, steps2)
        assert len(result) == 2
        assert result[0] == ("단계1", "결과1")
        assert result[1] == ("단계2", "결과2")


class TestClassifyRequest:
    """요청 분류 테스트 - 하이브리드 라우팅의 핵심"""

    def test_simple_greeting(self):
        """짧은 인사말은 기존 ReAct로 빠르게 처리"""
        from cli_master.agent import classify_request

        assert classify_request("안녕하세요") == "simple"

    def test_simple_question(self):
        """단순 질문은 계획 없이 바로 응답"""
        from cli_master.agent import classify_request

        assert classify_request("오늘 날씨 어때?") == "simple"

    def test_complex_task(self):
        """다단계 작업은 Plan-Execute 패턴으로 처리"""
        from cli_master.agent import classify_request

        assert classify_request("프로젝트 구조를 분석하고 README를 업데이트해줘") == "complex"

    def test_file_operation(self):
        """여러 파일 조작은 계획이 필요한 복잡한 작업"""
        from cli_master.agent import classify_request

        assert classify_request("src 폴더의 모든 파일을 읽고 요약해줘") == "complex"


class TestPlanStep:
    """Planner 노드 테스트 - 계획 수립 단계"""

    @pytest.fixture
    def initial_state(self):
        return {
            "messages": [],
            "input": "파일을 읽고 요약해줘",
            "plan": [],
            "current_step_index": 0,
            "past_steps": [],
            "response": None,
            "replan_count": 0,
        }

    def test_plan_step_generates_plan(self, initial_state):
        """Planner가 사용자 요청을 분석하여 실행 가능한 단계들을 생성"""
        from cli_master.agent import plan_step

        result = plan_step(initial_state)
        assert "plan" in result
        assert isinstance(result["plan"], list)
        assert len(result["plan"]) > 0

    def test_plan_step_initializes_index(self, initial_state):
        """계획 생성 시 실행 인덱스가 0부터 시작"""
        from cli_master.agent import plan_step

        result = plan_step(initial_state)
        assert result.get("current_step_index", 0) == 0


class TestExecuteStep:
    """Executor 노드 테스트 - 단계별 실행"""

    def test_execute_first_step(self):
        """첫 단계 실행: 인덱스 증가 + past_steps 기록"""
        from cli_master.agent import execute_step

        state = {
            "messages": [],
            "input": "테스트",
            "plan": ["단계1", "단계2"],
            "current_step_index": 0,
            "past_steps": [],
            "response": None,
            "replan_count": 0,
        }
        result = execute_step(state)
        assert result["current_step_index"] == 1
        assert len(result["past_steps"]) == 1

    def test_execute_increments_index(self):
        """두 번째 단계 실행: 인덱스가 2가 되는지"""
        from cli_master.agent import execute_step

        state = {
            "messages": [],
            "input": "테스트",
            "plan": ["단계1", "단계2", "단계3"],
            "current_step_index": 1,
            "past_steps": [("단계1", "결과1")],
            "response": None,
            "replan_count": 0,
        }
        result = execute_step(state)
        assert result["current_step_index"] == 2

    def test_execute_records_result(self):
        """실행 결과가 (단계명, 결과) 튜플 형태로 저장"""
        from cli_master.agent import execute_step

        state = {
            "messages": [],
            "input": "테스트",
            "plan": ["파일 읽기"],
            "current_step_index": 0,
            "past_steps": [],
            "response": None,
            "replan_count": 0,
        }
        result = execute_step(state)
        step, output = result["past_steps"][0]
        assert step == "파일 읽기"
        assert isinstance(output, str)


class TestReplanStep:
    """Replanner 노드 테스트 - 완료 판단 및 재계획"""

    def test_replan_returns_response_when_complete(self):
        """모든 단계 성공 완료 시 최종 응답 반환"""
        from cli_master.agent import replan_step

        state = {
            "messages": [],
            "input": "파일 읽기",
            "plan": ["파일 읽기"],
            "current_step_index": 1,
            "past_steps": [("파일 읽기", "성공")],
            "response": None,
            "replan_count": 0,
        }
        result = replan_step(state)
        assert "response" in result

    def test_replan_generates_new_plan(self):
        """실패 또는 추가 작업 필요 시 새 계획 생성"""
        from cli_master.agent import replan_step

        state = {
            "messages": [],
            "input": "복잡한 작업",
            "plan": ["1단계"],
            "current_step_index": 1,
            "past_steps": [("1단계", "부분 성공 - 추가 작업 필요")],
            "response": None,
            "replan_count": 0,
        }
        # 결과는 response 또는 새 plan 중 하나
        result = replan_step(state)
        assert "response" in result or "plan" in result

    def test_replan_limit_reached(self):
        """재계획 3회 도달 시 강제 종료 (무한 루프 방지)"""
        from cli_master.agent import replan_step

        state = {
            "messages": [],
            "input": "복잡한 작업",
            "plan": ["작업"],
            "current_step_index": 1,
            "past_steps": [("작업", "실패")],
            "response": None,
            "replan_count": 3,
        }
        result = replan_step(state)
        assert "response" in result  # 강제 종료

    def test_replan_increments_count(self):
        """재계획 발생 시 카운트 증가"""
        from cli_master.agent import replan_step

        state = {
            "messages": [],
            "input": "복잡한 작업",
            "plan": ["작업"],
            "current_step_index": 1,
            "past_steps": [("작업", "실패 - 재시도 필요")],
            "response": None,
            "replan_count": 1,
        }
        result = replan_step(state)
        # 재계획 시 카운트 증가 확인
        if "plan" in result:
            assert result.get("replan_count", 1) >= 2


class TestHybridGraph:
    """하이브리드 그래프 테스트 - ReAct + Plan-Execute 통합"""

    def test_build_hybrid_graph_compiles(self):
        """_build_hybrid_graph()가 에러 없이 컴파일되는지 확인"""
        from cli_master.agent import _build_hybrid_graph

        graph = _build_hybrid_graph(checkpointer=None)
        assert graph is not None

    def test_hybrid_graph_has_router_node(self):
        """하이브리드 그래프에 router 노드가 존재하는지 확인"""
        from cli_master.agent import _build_hybrid_graph

        graph = _build_hybrid_graph(checkpointer=None)
        # 컴파일된 그래프의 노드 확인
        node_names = list(graph.nodes.keys())
        assert "router" in node_names

    def test_hybrid_graph_has_planner_node(self):
        """하이브리드 그래프에 planner 노드가 존재하는지 확인"""
        from cli_master.agent import _build_hybrid_graph

        graph = _build_hybrid_graph(checkpointer=None)
        node_names = list(graph.nodes.keys())
        assert "planner" in node_names

    def test_hybrid_graph_has_executor_node(self):
        """하이브리드 그래프에 executor 노드가 존재하는지 확인"""
        from cli_master.agent import _build_hybrid_graph

        graph = _build_hybrid_graph(checkpointer=None)
        node_names = list(graph.nodes.keys())
        assert "executor" in node_names

    def test_hybrid_graph_has_replanner_node(self):
        """하이브리드 그래프에 replanner 노드가 존재하는지 확인"""
        from cli_master.agent import _build_hybrid_graph

        graph = _build_hybrid_graph(checkpointer=None)
        node_names = list(graph.nodes.keys())
        assert "replanner" in node_names


class TestStreamEvents:
    """스트리밍 이벤트 테스트 - Plan-Execute UI 표시용"""

    @pytest.fixture(autouse=True)
    def setup_fake_llm(self, monkeypatch):
        """테스트 시 FAKE_LLM 활성화"""
        from cli_master.core import config as cfg_module

        monkeypatch.setattr(cfg_module, "FAKE_LLM", True)

    def test_stream_response_event_for_simple(self):
        """단순 요청 시 response 이벤트 발생 확인"""
        from cli_master.agent import stream_hybrid

        events = list(stream_hybrid("안녕"))
        event_types = [e[0] for e in events]
        assert "response" in event_types

    def test_stream_plan_start_event_for_complex(self):
        """복잡한 요청 시 plan_start 이벤트 발생 확인"""
        from cli_master.agent import stream_hybrid

        events = list(stream_hybrid("프로젝트를 분석하고 README를 업데이트해줘"))
        event_types = [e[0] for e in events]
        assert "plan_start" in event_types

    def test_stream_step_events_for_complex(self):
        """복잡한 요청 시 step_start/step_end 이벤트 발생 확인"""
        from cli_master.agent import stream_hybrid

        events = list(stream_hybrid("파일을 읽고 요약해줘"))
        event_types = [e[0] for e in events]
        # step_start 또는 step_end 중 하나 이상 있어야 함
        has_step_event = "step_start" in event_types or "step_end" in event_types
        assert has_step_event

    def test_stream_plan_start_contains_steps(self):
        """plan_start 이벤트에 계획 단계가 포함되는지 확인"""
        from cli_master.agent import stream_hybrid

        events = list(stream_hybrid("프로젝트를 분석하고 문서를 수정해줘"))
        plan_events = [e for e in events if e[0] == "plan_start"]
        assert len(plan_events) > 0
        # plan_start 이벤트 데이터에 steps 포함
        plan_data = plan_events[0][1]
        assert "steps" in plan_data
        assert isinstance(plan_data["steps"], list)
