"""VectorToolSelector 단위 테스트"""
import pytest

from src.tool_metadata import TOOL_METADATA
from src.tool_selector import VectorToolSelector


class TestVectorToolSelector:
    """VectorToolSelector 단위 테스트"""

    @pytest.fixture
    def selector(self):
        """테스트용 VectorToolSelector 인스턴스 생성"""
        return VectorToolSelector()

    def test_vector_db_creation(self, selector):
        """Vector DB 생성 테스트"""
        # 지연 초기화 트리거
        selector._lazy_init()

        # Vector DB 클라이언트가 생성되었는지 확인
        assert selector.client is not None, "ChromaDB 클라이언트가 생성되지 않았습니다"
        assert selector.collection is not None, "Collection이 생성되지 않았습니다"
        assert selector._initialized is True, "초기화 플래그가 설정되지 않았습니다"
        assert selector.collection.name == "tool_embeddings", "Collection 이름이 올바르지 않습니다"

    def test_index_tools(self, selector):
        """도구 등록(인덱싱) 테스트"""
        # 도구 인덱싱
        selector.index_tools(TOOL_METADATA)

        # Collection에 도구가 저장되었는지 확인
        count = selector.collection.count()
        expected_count = len(TOOL_METADATA)

        assert count == expected_count, (
            f"인덱싱된 도구 개수가 올바르지 않습니다. "
            f"기대: {expected_count}, 실제: {count}"
        )

        # 각 도구가 올바르게 저장되었는지 확인
        stored_ids = selector.collection.get()["ids"]
        for tool_name in TOOL_METADATA:
            assert tool_name in stored_ids, f"도구 '{tool_name}'가 인덱싱되지 않았습니다"

    def test_select_tools(self, selector):
        """도구 검색 테스트"""
        # 먼저 도구 인덱싱
        selector.index_tools(TOOL_METADATA)

        # 테스트 케이스: 질문 → 기대 도구
        test_cases = [
            {
                "query": "파일 내용을 읽어서 보여줘",
                "expected_tools": ["read_file"],
                "description": "파일 읽기 요청"
            },
            {
                "query": "*.py 파일들을 찾아줘",
                "expected_tools": ["glob"],
                "description": "패턴 검색 요청"
            },
            {
                "query": "코드에서 함수 정의를 검색해줘",
                "expected_tools": ["grep"],
                "description": "텍스트 검색 요청"
            },
            {
                "query": "파일을 수정해줘",
                "expected_tools": ["edit_file"],
                "description": "파일 편집 요청"
            },
            {
                "query": "디렉토리 안에 뭐가 있어?",
                "expected_tools": ["ls"],
                "description": "디렉토리 목록 요청"
            },
        ]

        for case in test_cases:
            query = case["query"]
            expected = case["expected_tools"]
            description = case["description"]

            # 도구 검색 (top_k=3으로 여유있게)
            selected = selector.select_tools(query, top_k=3)

            # 검증: 기대하는 도구가 선택된 도구에 포함되어 있는지
            for expected_tool in expected:
                assert expected_tool in selected, (
                    f"{description} 실패\n"
                    f"질문: '{query}'\n"
                    f"기대 도구: {expected_tool}\n"
                    f"선택된 도구: {selected}"
                )

    def test_select_tools_with_different_top_k(self, selector):
        """top_k 파라미터에 따른 도구 검색 테스트"""
        selector.index_tools(TOOL_METADATA)

        query = "파일 읽어줘"

        # top_k=1: 1개만 반환
        result_1 = selector.select_tools(query, top_k=1)
        assert len(result_1) == 1, f"top_k=1일 때 1개만 반환되어야 함: {result_1}"

        # top_k=3: 3개 반환
        result_3 = selector.select_tools(query, top_k=3)
        assert len(result_3) == 3, f"top_k=3일 때 3개 반환되어야 함: {result_3}"

        # top_k=5: 5개 반환
        result_5 = selector.select_tools(query, top_k=5)
        assert len(result_5) == 5, f"top_k=5일 때 5개 반환되어야 함: {result_5}"

    def test_get_tool_prompt_hint(self, selector):
        """프롬프트 힌트 생성 테스트"""
        selector.index_tools(TOOL_METADATA)

        query = "파일 내용 확인"
        hint = selector.get_tool_prompt_hint(query, top_k=2)

        # 힌트가 생성되었는지 확인
        assert hint, "프롬프트 힌트가 생성되지 않았습니다"
        assert "[도구 추천]" in hint, "힌트에 '[도구 추천]' 접두사가 없습니다"

        # 적어도 하나의 도구 이름이 포함되어 있는지 확인
        has_tool = any(
            tool_name in hint
            for tool_name in TOOL_METADATA.keys()
        )
        assert has_tool, f"힌트에 도구 이름이 포함되지 않았습니다: {hint}"

    def test_empty_query(self, selector):
        """빈 질문에 대한 처리 테스트"""
        selector.index_tools(TOOL_METADATA)

        # 빈 문자열 검색
        result = selector.select_tools("", top_k=3)

        # 빈 질문이라도 결과를 반환해야 함 (오류 발생하지 않아야 함)
        assert isinstance(result, list), "결과가 리스트여야 합니다"
