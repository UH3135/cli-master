"""Long Term 저장소: 체크포인트 관리"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass
from pathlib import Path

from langchain_core.messages import BaseMessage
from langgraph.checkpoint.sqlite import SqliteSaver


@dataclass
class ThreadInfo:
    """Thread 정보"""

    thread_id: str
    checkpoint_count: int
    latest_checkpoint_id: str


class CheckpointRepository:
    """SQLite 기반 체크포인트 저장소

    LangGraph의 SqliteSaver를 래핑하여 추가 기능 제공:
    - thread 목록 조회
    - 대화 히스토리 조회
    - 연결 수명 주기 관리
    """

    def __init__(self, db_path: Path) -> None:
        self._db_path = db_path
        self._connection: sqlite3.Connection | None = None
        self._checkpointer: SqliteSaver | None = None

    def _ensure_connection(self) -> sqlite3.Connection:
        """연결 보장 (지연 초기화)"""
        if self._connection is None:
            self._connection = sqlite3.connect(str(self._db_path))
        return self._connection

    def get_checkpointer(self) -> SqliteSaver:
        """동기 checkpointer 반환 (싱글톤)"""
        if self._checkpointer is None:
            conn = self._ensure_connection()
            self._checkpointer = SqliteSaver(conn=conn)
        return self._checkpointer

    def get_history(self, thread_id: str) -> list[BaseMessage] | None:
        """특정 thread의 대화 히스토리 조회

        Returns:
            메시지 목록 또는 None (없는 경우)
        """
        checkpointer = self.get_checkpointer()
        config = {"configurable": {"thread_id": thread_id}}

        tup = checkpointer.get_tuple(config)  # type: ignore[arg-type]
        if not tup:
            return None

        _, checkpoint, _, _, _ = tup
        messages = checkpoint.get("channel_values", {}).get("messages", [])

        if not messages:
            return None

        return list(messages)

    def list_threads(self) -> list[ThreadInfo]:
        """저장된 모든 thread 목록 조회"""
        conn = self._ensure_connection()

        try:
            rows = conn.execute(
                """
                SELECT thread_id, COUNT(*) AS cnt, MAX(checkpoint_id) AS latest
                FROM checkpoints
                GROUP BY thread_id
                ORDER BY latest DESC
                """
            ).fetchall()
        except sqlite3.Error:
            return []

        return [
            ThreadInfo(
                thread_id=str(row[0]),
                checkpoint_count=row[1],
                latest_checkpoint_id=str(row[2]),
            )
            for row in rows
        ]

    def thread_exists(self, thread_id: str) -> bool:
        """thread 존재 여부 확인"""
        history = self.get_history(thread_id)
        return history is not None and len(history) > 0

    def close(self) -> None:
        """리소스 정리"""
        if self._connection is not None:
            self._connection.close()
            self._connection = None
            self._checkpointer = None
