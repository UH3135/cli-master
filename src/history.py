"""입력 히스토리 관리"""
import logging
from typing import Optional

from .models import Session, Message
from .storage import SQLiteStore, VectorStore

logger = logging.getLogger(__name__)


class InputHistory:
    """입력 히스토리를 저장하고 관리하는 클래스"""

    def __init__(
        self,
        sqlite_store: Optional[SQLiteStore] = None,
        vector_store: Optional[VectorStore] = None
    ):
        # 저장소 초기화
        self.sqlite = sqlite_store or SQLiteStore()
        self.vector = vector_store or VectorStore()

        # 현재 세션 설정 (최근 세션 또는 새로 생성)
        self.session = self.sqlite.get_latest_session()
        if self.session is None:
            self.session = self.sqlite.create_session()

        # 메모리 캐시 (현재 세션의 메시지)
        self._cache: list[Message] = self.sqlite.get_messages(self.session.id)
        logger.debug("InputHistory 초기화 - 세션: %s, 메시지 수: %s", self.session.id, len(self._cache))

    def add(self, text: str) -> None:
        """히스토리에 입력 추가"""
        if not text.strip():
            return

        # SQLite에 저장
        message = self.sqlite.add_message(self.session.id, text)

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
        """현재 세션 히스토리 초기화 (새 세션 시작)"""
        self.session = self.sqlite.create_session()
        self._cache.clear()
        logger.debug("새 세션 시작: %s", self.session.id)

    def search(self, query: str, limit: int = 10) -> list[Message]:
        """키워드로 검색 (SQLite FTS)"""
        return self.sqlite.search_messages(query, limit)

    def find_similar(self, query: str, limit: int = 5) -> list[dict]:
        """의미 기반 검색 (Vector DB)"""
        return self.vector.search(query, limit)

    def get_sessions(self, limit: int = 10) -> list[Session]:
        """이전 세션 목록"""
        return self.sqlite.get_all_sessions(limit)

    def load_session(self, session_id: str) -> bool:
        """이전 세션 불러오기"""
        session = self.sqlite.get_session(session_id)
        if session is None:
            return False

        self.session = session
        self._cache = self.sqlite.get_messages(session_id)
        logger.debug("세션 로드됨: %s, 메시지 수: %s", session_id, len(self._cache))
        return True

    def new_session(self) -> Session:
        """새 세션 시작"""
        self.session = self.sqlite.create_session()
        self._cache.clear()
        logger.debug("새 세션 생성: %s", self.session.id)
        return self.session

    def __len__(self) -> int:
        return len(self._cache)

    def close(self) -> None:
        """리소스 정리"""
        self.sqlite.close()
