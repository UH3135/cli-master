"""Vector DB 기반 도구 선택기"""
import logging
import os
from typing import List

# 모든 로그 출력 방지
logger = logging.getLogger(__name__)
logger.setLevel(logging.WARNING)

# ChromaDB 로그 끄기
logging.getLogger("chromadb").setLevel(logging.WARNING)
# Sentence Transformers 로그 끄기
logging.getLogger("sentence_transformers").setLevel(logging.WARNING)

# HuggingFace tokenizers fork 경고 끄기
os.environ["TOKENIZERS_PARALLELISM"] = "false"


class VectorToolSelector:
    """유저 질문과 유사한 도구를 Vector DB로 검색"""

    def __init__(self, embedding_model: str = "intfloat/multilingual-e5-small"):
        """
        Args:
            embedding_model: 임베딩 모델 (HuggingFace 모델명)
        """
        self.embedding_model = embedding_model
        self.client = None
        self.collection = None
        self._initialized = False

    def _lazy_init(self):
        """지연 초기화 - ChromaDB와 임베딩 설정"""
        if self._initialized:
            return

        try:
            import chromadb
            from chromadb.utils import embedding_functions
        except ImportError:
            logger.warning(
                "ChromaDB가 설치되지 않았습니다. "
                "설치: uv pip install chromadb"
            )
            return

        # ChromaDB 클라이언트 생성 (인메모리, telemetry 끄기)
        settings = chromadb.Settings(
            anonymized_telemetry=False,
            allow_reset=True
        )
        self.client = chromadb.Client(settings)

        # 임베딩 함수 설정
        # ChromaDB의 기본 함수는 progress bar를 끌 수 없으므로 직접 생성
        from sentence_transformers import SentenceTransformer

        class QuietEmbeddingFunction:
            """Progress bar 없는 임베딩 함수"""
            def __init__(self, model_name):
                self.model = SentenceTransformer(model_name)

            def __call__(self, input):
                # show_progress_bar=False로 progress bar 끄기
                return self.model.encode(input, show_progress_bar=False).tolist()

        embedding_fn = QuietEmbeddingFunction(self.embedding_model)

        # 컬렉션 생성 또는 가져오기
        self.collection = self.client.get_or_create_collection(
            name="tool_embeddings",
            embedding_function=embedding_fn,
        )

        self._initialized = True
        logger.info("VectorToolSelector 초기화 완료")

    def index_tools(self, tool_metadata: dict):
        """도구들을 Vector DB에 인덱싱

        Args:
            tool_metadata: {tool_name: {"description": str, "use_cases": list, ...}}
        """
        self._lazy_init()
        if not self._initialized:
            logger.warning("초기화 실패로 인덱싱을 건너뜁니다")
            return

        from .tool_metadata import get_tool_embedding_text

        # 기존 데이터 삭제 (재인덱싱)
        try:
            self.client.delete_collection("tool_embeddings")
            embedding_fn = self.collection._embedding_function
            self.collection = self.client.create_collection(
                name="tool_embeddings",
                embedding_function=embedding_fn,
            )
        except Exception:
            pass

        # 각 도구를 임베딩하여 저장
        documents = []
        metadatas = []
        ids = []

        for tool_name in tool_metadata:
            embedding_text = get_tool_embedding_text(tool_name)
            documents.append(embedding_text)
            metadatas.append({
                "tool_name": tool_name,
                "description": tool_metadata[tool_name]["description"],
            })
            ids.append(tool_name)

        if documents:
            self.collection.add(
                documents=documents,
                metadatas=metadatas,
                ids=ids,
            )
            logger.info("도구 %d개 인덱싱 완료", len(documents))

    def select_tools(self, query: str, top_k: int = 3) -> List[str]:
        """유저 질문에 가장 유사한 도구 선택

        Args:
            query: 유저 질문
            top_k: 반환할 도구 개수

        Returns:
            선택된 도구 이름 리스트 (유사도 순)
        """
        self._lazy_init()
        if not self._initialized:
            logger.warning("초기화 실패로 모든 도구 반환")
            return []

        try:
            results = self.collection.query(
                query_texts=[query],
                n_results=min(top_k, self.collection.count()),
            )

            # 결과에서 도구 이름 추출
            if results and results["ids"]:
                tool_names = results["ids"][0]  # 첫 번째 쿼리 결과
                logger.info(
                    "질문: '%s' → 선택된 도구: %s",
                    query[:50],
                    tool_names,
                )
                return tool_names

        except Exception as e:
            logger.error("도구 선택 중 오류: %s", e)

        return []

    def get_tool_prompt_hint(self, query: str, top_k: int = 3) -> str:
        """유저 질문에 대한 도구 사용 힌트 생성

        Args:
            query: 유저 질문
            top_k: 고려할 도구 개수

        Returns:
            프롬프트에 추가할 힌트 문자열
        """
        selected_tools = self.select_tools(query, top_k)
        if not selected_tools:
            return ""

        tool_list = ", ".join(selected_tools)
        return f"\n[도구 추천] 이 질문에는 다음 도구가 유용할 수 있습니다: {tool_list}"


# 싱글톤 인스턴스
_selector = None


def get_tool_selector() -> VectorToolSelector:
    """싱글톤 도구 선택기 반환"""
    global _selector
    if _selector is None:
        _selector = VectorToolSelector()
        # 초기 인덱싱
        from .tool_metadata import TOOL_METADATA
        _selector.index_tools(TOOL_METADATA)
    return _selector
