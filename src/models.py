"""데이터 모델 정의"""
from dataclasses import dataclass, field
from datetime import datetime
import uuid


@dataclass
class Message:
    """입력 메시지"""
    id: str = field(default_factory=lambda: str(uuid.uuid4()))
    session_id: str = ""
    content: str = ""
    created_at: datetime = field(default_factory=datetime.now)

    def to_dict(self) -> dict:
        return {
            "id": self.id,
            "session_id": self.session_id,
            "content": self.content,
            "created_at": self.created_at.isoformat(),
        }

    @classmethod
    def from_dict(cls, data: dict) -> "Message":
        return cls(
            id=data["id"],
            session_id=data["session_id"],
            content=data["content"],
            created_at=datetime.fromisoformat(data["created_at"]),
        )
