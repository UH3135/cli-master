"""데이터 모델 정의"""

from dataclasses import dataclass, field
from datetime import datetime
from enum import Enum
import uuid

from typing import Literal

from pydantic import BaseModel, Field


class ComplexityClassification(BaseModel):
    """요청 복잡도 분류 결과 (LLM Structured Output용)"""

    complexity: Literal["simple", "complex"] = Field(
        description="작업 복잡도: 'simple' (단순 질문/조회) 또는 'complex' (다단계 작업)"
    )
    reason: str = Field(description="분류 이유")


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


class TodoStatus(Enum):
    """TODO 상태"""

    PENDING = "pending"
    IN_PROGRESS = "in_progress"
    COMPLETED = "completed"


@dataclass
class TodoItem:
    """TODO 항목"""

    id: int
    title: str
    description: str
    status: TodoStatus
    created_at: datetime
    updated_at: datetime
    completed_at: datetime | None = None


# Plan-Execute 패턴용 Pydantic 모델


class Plan(BaseModel):
    """다단계 실행 계획"""

    steps: list[str] = Field(description="정렬된 순서의 실행 단계 목록")


class Response(BaseModel):
    """최종 응답"""

    response: str = Field(description="사용자에게 전달할 최종 응답")


class Act(BaseModel):
    """Replanner 행동 결정"""

    action: Response | Plan = Field(description="최종 응답 또는 새 계획")
