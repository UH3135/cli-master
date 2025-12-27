"""SQLAlchemy 기반 프롬프트 히스토리 저장소"""

import uuid
from datetime import datetime
from typing import Iterable

from loguru import logger
from prompt_toolkit.history import History
from sqlalchemy import create_engine, Column, Integer, String, DateTime, desc, text
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()


class HistoryEntry(Base):
    """히스토리 항목 모델"""

    __tablename__ = "history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    session_id = Column(String, nullable=False, index=True)
    content = Column(String, nullable=False)
    role = Column(String, nullable=False, default="user")
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return f"<HistoryEntry(id={self.id}, session_id='{self.session_id}', content='{self.content[:20]}...')>"


class SqlHistory(History):
    """
    SQLAlchemy 기반 프롬프트 히스토리

    prompt_toolkit의 History를 상속받아 방향키 탐색 기능 지원
    세션별로 히스토리를 분리하여 관리

    사용법:
        # 새 세션 (자동 UUID 생성)
        history = SqlHistory("sqlite:///history.db")

        # 기존 세션 이어서 사용
        history = SqlHistory("sqlite:///history.db", session_id="existing-id")
    """

    def __init__(
        self,
        connection_string: str = "sqlite:///history.db",
        session_id: str | None = None,
    ):
        super().__init__()
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(bind=self.engine)
        self.session_id = session_id or str(uuid.uuid4())
        self._migrate_add_role_column()

    def _get_session(self) -> Session:
        """DB 세션 생성"""
        return self._session_factory()

    def _migrate_add_role_column(self):
        """role 컬럼 마이그레이션 (기존 데이터 호환성)"""
        with self._get_session() as session:
            # SQLite의 PRAGMA로 컬럼 존재 확인
            result = session.execute(text("PRAGMA table_info(history)")).fetchall()
            columns = [row[1] for row in result]

            if "role" not in columns:
                session.execute(
                    text(
                        "ALTER TABLE history ADD COLUMN role VARCHAR DEFAULT 'user' NOT NULL"
                    )
                )
                session.commit()
                logger.info("role 컬럼이 history 테이블에 추가되었습니다")

    def load_history_strings(self) -> Iterable[str]:
        """
        현재 세션의 히스토리 로드 (역순으로 반환)

        prompt_toolkit이 시작 시 호출하여 방향키 탐색에 사용
        사용자 입력(role='user')만 반환
        """
        with self._get_session() as session:
            entries = (
                session.query(HistoryEntry)
                .filter(
                    HistoryEntry.session_id == self.session_id,
                    HistoryEntry.role == "user",
                )
                .order_by(desc(HistoryEntry.id))
                .all()
            )
            return [entry.content for entry in entries]

    def store_string(self, string: str) -> None:
        """
        새 입력 저장

        prompt_toolkit이 사용자 입력 후 자동 호출
        """
        with self._get_session() as session:
            entry = HistoryEntry(
                session_id=self.session_id, content=string, role="user"
            )
            session.add(entry)
            session.commit()

    def clear(self) -> None:
        """현재 세션의 히스토리 삭제"""
        with self._get_session() as session:
            session.query(HistoryEntry).filter(
                HistoryEntry.session_id == self.session_id
            ).delete()
            session.commit()

    def get_all(self) -> list[str]:
        """현재 세션의 히스토리 조회 (시간순)"""
        with self._get_session() as session:
            entries = (
                session.query(HistoryEntry)
                .filter(HistoryEntry.session_id == self.session_id)
                .order_by(HistoryEntry.id)
                .all()
            )
            return [entry.content for entry in entries]

    def search(self, keyword: str) -> list[HistoryEntry]:
        """현재 세션에서 키워드로 히스토리 검색"""
        with self._get_session() as session:
            entries = (
                session.query(HistoryEntry)
                .filter(
                    HistoryEntry.session_id == self.session_id,
                    HistoryEntry.content.contains(keyword),
                )
                .order_by(desc(HistoryEntry.created_at))
                .all()
            )
            # 세션 종료 전에 데이터 복사
            return [
                HistoryEntry(
                    id=e.id,
                    session_id=e.session_id,
                    content=e.content,
                    created_at=e.created_at,
                )
                for e in entries
            ]

    def store_ai_response(self, response: str) -> None:
        """AI 응답 저장"""
        with self._get_session() as session:
            entry = HistoryEntry(
                session_id=self.session_id, content=response, role="ai"
            )
            session.add(entry)
            session.commit()

    def get_all_with_role(self) -> list[tuple[str, str]]:
        """현재 세션의 히스토리 조회 (role 포함) - 시간순

        Returns:
            list[tuple[str, str]]: [(role, content), ...]
        """
        with self._get_session() as session:
            entries = (
                session.query(HistoryEntry)
                .filter(HistoryEntry.session_id == self.session_id)
                .order_by(HistoryEntry.id)
                .all()
            )
            return [(entry.role, entry.content) for entry in entries]
