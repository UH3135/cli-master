"""SQLite 저장소 - 세션과 메시지를 영구 저장"""
import sqlite3
import logging
from pathlib import Path
from datetime import datetime
from typing import Optional

from ..models import Session, Message

logger = logging.getLogger(__name__)


class SQLiteStore:
    """SQLite 기반 저장소"""

    def __init__(self, db_path: Optional[Path] = None):
        # 기본 저장 경로: ~/.cli-master/data.db
        if db_path is None:
            db_path = Path.home() / ".cli-master" / "data.db"

        self.db_path = db_path
        self.db_path.parent.mkdir(parents=True, exist_ok=True)

        self.conn = sqlite3.connect(str(self.db_path))
        self.conn.row_factory = sqlite3.Row
        self._init_tables()
        logger.debug("SQLite 저장소 초기화: %s", self.db_path)

    def _init_tables(self) -> None:
        """테이블 생성"""
        cursor = self.conn.cursor()

        # 세션 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS sessions (
                id TEXT PRIMARY KEY,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)

        # 메시지 테이블
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS messages (
                id TEXT PRIMARY KEY,
                session_id TEXT NOT NULL,
                content TEXT NOT NULL,
                created_at TEXT NOT NULL,
                FOREIGN KEY (session_id) REFERENCES sessions(id)
            )
        """)

        # 전문 검색 인덱스 (FTS5)
        cursor.execute("""
            CREATE VIRTUAL TABLE IF NOT EXISTS messages_fts USING fts5(
                content,
                content='messages',
                content_rowid='rowid'
            )
        """)

        # FTS 트리거 - 메시지 추가 시 자동 인덱싱
        cursor.execute("""
            CREATE TRIGGER IF NOT EXISTS messages_ai AFTER INSERT ON messages BEGIN
                INSERT INTO messages_fts(rowid, content)
                VALUES (NEW.rowid, NEW.content);
            END
        """)

        self.conn.commit()

    def create_session(self) -> Session:
        """새 세션 생성"""
        session = Session()
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO sessions (id, created_at, updated_at) VALUES (?, ?, ?)",
            (session.id, session.created_at.isoformat(), session.updated_at.isoformat())
        )
        self.conn.commit()
        logger.debug("세션 생성됨: %s", session.id)
        return session

    def get_session(self, session_id: str) -> Optional[Session]:
        """세션 조회"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sessions WHERE id = ?", (session_id,))
        row = cursor.fetchone()
        if row:
            return Session.from_dict(dict(row))
        return None

    def get_latest_session(self) -> Optional[Session]:
        """가장 최근 세션 조회"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM sessions ORDER BY updated_at DESC LIMIT 1")
        row = cursor.fetchone()
        if row:
            return Session.from_dict(dict(row))
        return None

    def get_all_sessions(self, limit: int = 10) -> list[Session]:
        """모든 세션 조회"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM sessions ORDER BY updated_at DESC LIMIT ?",
            (limit,)
        )
        return [Session.from_dict(dict(row)) for row in cursor.fetchall()]

    def update_session(self, session_id: str) -> None:
        """세션 업데이트 시간 갱신"""
        cursor = self.conn.cursor()
        cursor.execute(
            "UPDATE sessions SET updated_at = ? WHERE id = ?",
            (datetime.now().isoformat(), session_id)
        )
        self.conn.commit()

    def add_message(self, session_id: str, content: str) -> Message:
        """메시지 추가"""
        message = Message(session_id=session_id, content=content)
        cursor = self.conn.cursor()
        cursor.execute(
            "INSERT INTO messages (id, session_id, content, created_at) VALUES (?, ?, ?, ?)",
            (message.id, message.session_id, message.content, message.created_at.isoformat())
        )
        self.conn.commit()

        # 세션 업데이트 시간 갱신
        self.update_session(session_id)
        logger.debug("메시지 추가됨: %s", message.id)
        return message

    def get_messages(self, session_id: str) -> list[Message]:
        """세션의 모든 메시지 조회"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT * FROM messages WHERE session_id = ? ORDER BY created_at ASC",
            (session_id,)
        )
        return [Message.from_dict(dict(row)) for row in cursor.fetchall()]

    def search_messages(self, query: str, limit: int = 10) -> list[Message]:
        """키워드로 메시지 검색 (FTS5)"""
        cursor = self.conn.cursor()
        cursor.execute("""
            SELECT m.* FROM messages m
            JOIN messages_fts fts ON m.rowid = fts.rowid
            WHERE messages_fts MATCH ?
            ORDER BY rank
            LIMIT ?
        """, (query, limit))
        return [Message.from_dict(dict(row)) for row in cursor.fetchall()]

    def get_message_count(self, session_id: str) -> int:
        """세션의 메시지 개수"""
        cursor = self.conn.cursor()
        cursor.execute(
            "SELECT COUNT(*) FROM messages WHERE session_id = ?",
            (session_id,)
        )
        return cursor.fetchone()[0]

    def close(self) -> None:
        """연결 종료"""
        self.conn.close()
        logger.debug("SQLite 연결 종료")
