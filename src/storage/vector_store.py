"""Vector 저장소 - 의미 기반 검색을 위한 ChromaDB"""
import logging
from pathlib import Path
from typing import Optional

import chromadb
from chromadb.config import Settings

from ..models import Message

logger = logging.getLogger(__name__)


class VectorStore:
    """ChromaDB 기반 벡터 저장소"""

    def __init__(self, db_path: Optional[Path] = None):
        # 기본 저장 경로: ~/.cli-master/vector_db
        if db_path is None:
            db_path = Path.home() / ".cli-master" / "vector_db"

        self.db_path = db_path
        self.db_path.mkdir(parents=True, exist_ok=True)

        # ChromaDB 클라이언트 초기화
        self.client = chromadb.PersistentClient(
            path=str(self.db_path),
            settings=Settings(anonymized_telemetry=False)
        )

        # 메시지 컬렉션 생성/로드
        self.collection = self.client.get_or_create_collection(
            name="messages",
            metadata={"description": "CLI 입력 메시지"}
        )

        logger.debug("Vector 저장소 초기화: %s", self.db_path)

    def add_message(self, message: Message) -> None:
        """메시지를 벡터 저장소에 추가"""
        self.collection.add(
            ids=[message.id],
            documents=[message.content],
            metadatas=[{
                "session_id": message.session_id,
                "created_at": message.created_at.isoformat()
            }]
        )
        logger.debug("벡터 저장소에 메시지 추가: %s", message.id)

    def search(self, query: str, limit: int = 5) -> list[dict]:
        """의미 기반 검색"""
        results = self.collection.query(
            query_texts=[query],
            n_results=limit
        )

        # 결과 포맷팅
        messages = []
        if results["ids"] and results["ids"][0]:
            for i, msg_id in enumerate(results["ids"][0]):
                messages.append({
                    "id": msg_id,
                    "content": results["documents"][0][i],
                    "metadata": results["metadatas"][0][i] if results["metadatas"] else {},
                    "distance": results["distances"][0][i] if results["distances"] else None
                })

        return messages

    def get_count(self) -> int:
        """저장된 메시지 개수"""
        return self.collection.count()

    def delete_message(self, message_id: str) -> None:
        """메시지 삭제"""
        self.collection.delete(ids=[message_id])
        logger.debug("벡터 저장소에서 메시지 삭제: %s", message_id)

    def clear(self) -> None:
        """모든 메시지 삭제"""
        # 컬렉션 삭제 후 재생성
        self.client.delete_collection("messages")
        self.collection = self.client.get_or_create_collection(
            name="messages",
            metadata={"description": "CLI 입력 메시지"}
        )
        logger.debug("벡터 저장소 초기화됨")
