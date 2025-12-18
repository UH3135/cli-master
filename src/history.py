"""입력 히스토리 관리"""
import logging
from typing import Optional

from .models import Message
from .storage import VectorStore

logger = logging.getLogger(__name__)


class InputHistory:
    """입력 히스토리를 저장하고 관리하는 클래스 (VectorDB 기반)"""

    def __init__(self, vector_store: Optional[VectorStore] = None):
        # Vector 저장소 초기화
        self.vector = vector_store or VectorStore()

        # 메모리 캐시 (현재 세션의 메시지)
        self._cache: list[Message] = []
        logger.debug("InputHistory 초기화 - 메시지 수: %s", len(self._cache))

    def add(self, text: str) -> None:
        """히스토리에 입력 추가"""
        if not text.strip():
            return

        # 메시지 생성
        message = Message(content=text)

        # Vector DB에 저장
        self.vector.add_message(message)

        # 캐시에 추가
        self._cache.append(message)
        logger.debug("입력 추가됨: %s", text)

    def get_all(self) -> list[str]:
        """전체 히스토리 반환 (텍스트만)"""
        return [msg.content for msg in self._cache]

    def get_messages(self) -> list[Message]:
        """전체 메시지 객체 반환"""
        return self._cache.copy()

    def clear(self) -> None:
        """현재 세션 히스토리 초기화"""
        self._cache.clear()
        logger.debug("히스토리 초기화됨")

    def find_similar(self, query: str, limit: int = 5) -> list[dict]:
        """의미 기반 검색 (Vector DB)"""
        return self.vector.search(query, limit)

    def __len__(self) -> int:
        return len(self._cache)

    def close(self) -> None:
        """리소스 정리"""
        pass
