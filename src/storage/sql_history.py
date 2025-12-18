"""SQLAlchemy 기반 프롬프트 히스토리 저장소"""
from datetime import datetime
from typing import Iterable

from prompt_toolkit.history import History
from sqlalchemy import create_engine, Column, Integer, String, DateTime, desc
from sqlalchemy.orm import declarative_base, sessionmaker, Session

Base = declarative_base()


class HistoryEntry(Base):
    """히스토리 항목 모델"""
    __tablename__ = "history"

    id = Column(Integer, primary_key=True, autoincrement=True)
    content = Column(String, nullable=False)
    created_at = Column(DateTime, default=datetime.now)

    def __repr__(self) -> str:
        return f"<HistoryEntry(id={self.id}, content='{self.content[:20]}...')>"


class SqlHistory(History):
    """
    SQLAlchemy 기반 프롬프트 히스토리

    prompt_toolkit의 History를 상속받아 방향키 탐색 기능 지원
    DB 연결 문자열만 변경하면 PostgreSQL, MySQL 등으로 전환 가능

    사용법:
        # SQLite (기본)
        history = SqlHistory("sqlite:///history.db")

        # PostgreSQL
        history = SqlHistory("postgresql://user:pass@localhost/db")

        # MySQL
        history = SqlHistory("mysql+pymysql://user:pass@localhost/db")
    """

    def __init__(self, connection_string: str = "sqlite:///history.db"):
        super().__init__()
        self.engine = create_engine(connection_string)
        Base.metadata.create_all(self.engine)
        self._session_factory = sessionmaker(bind=self.engine)

    def _get_session(self) -> Session:
        """DB 세션 생성"""
        return self._session_factory()

    def load_history_strings(self) -> Iterable[str]:
        """
        히스토리 로드 (역순으로 반환)

        prompt_toolkit이 시작 시 호출하여 방향키 탐색에 사용
        """
        with self._get_session() as session:
            entries = session.query(HistoryEntry).order_by(desc(HistoryEntry.id)).all()
            return [entry.content for entry in entries]

    def store_string(self, string: str) -> None:
        """
        새 입력 저장

        prompt_toolkit이 사용자 입력 후 자동 호출
        """
        with self._get_session() as session:
            entry = HistoryEntry(content=string)
            session.add(entry)
            session.commit()

    def clear(self) -> None:
        """모든 히스토리 삭제"""
        with self._get_session() as session:
            session.query(HistoryEntry).delete()
            session.commit()

    def get_all(self) -> list[str]:
        """모든 히스토리 조회 (시간순)"""
        with self._get_session() as session:
            entries = session.query(HistoryEntry).order_by(HistoryEntry.id).all()
            return [entry.content for entry in entries]

    def search(self, keyword: str) -> list[HistoryEntry]:
        """키워드로 히스토리 검색"""
        with self._get_session() as session:
            entries = session.query(HistoryEntry).filter(
                HistoryEntry.content.contains(keyword)
            ).order_by(desc(HistoryEntry.created_at)).all()
            # 세션 종료 전에 데이터 복사
            return [
                HistoryEntry(id=e.id, content=e.content, created_at=e.created_at)
                for e in entries
            ]
