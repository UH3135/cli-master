"""TODO 관리 도구

작업 항목을 생성, 조회, 업데이트, 삭제하는 기능을 제공합니다.
"""

from datetime import datetime

from langchain_core.tools import tool

from cli_master.core.models import TodoItem, TodoStatus


# 모듈 레벨 상태 변수
_todos: dict[int, TodoItem] = {}
_next_id = 1


def get_todos() -> dict[int, TodoItem]:
    """현재 TODO 목록 반환 (테스트용)"""
    return _todos


def reset_todos() -> None:
    """TODO 목록 초기화 (테스트용)"""
    global _todos, _next_id
    _todos.clear()
    _next_id = 1


@tool
def create_todo(title: str, description: str = "") -> str:
    """새로운 TODO 항목을 생성합니다.

    Args:
        title: TODO 제목
        description: 상세 설명 (선택)

    Returns:
        생성 확인 메시지
    """
    global _next_id

    todo = TodoItem(
        id=_next_id,
        title=title,
        description=description,
        status=TodoStatus.PENDING,
        created_at=datetime.now(),
        updated_at=datetime.now(),
    )
    _todos[_next_id] = todo
    _next_id += 1

    return f"📝 TODO #{todo.id} 생성: {title}"


@tool
def list_todos(status: str = "all") -> str:
    """TODO 목록을 조회합니다.

    Args:
        status: "all" | "pending" | "in_progress" | "completed"

    Returns:
        포맷된 TODO 리스트
    """
    if not _todos:
        return "📋 TODO 리스트가 비어있습니다"

    # 필터링
    if status == "all":
        filtered = list(_todos.values())
    else:
        try:
            status_enum = TodoStatus(status)
            filtered = [t for t in _todos.values() if t.status == status_enum]
        except ValueError:
            return f"오류: 잘못된 상태값 '{status}' (all, pending, in_progress, completed 중 선택)"

    if not filtered:
        return f"📋 {status} 상태의 TODO가 없습니다"

    # 진행률 계산
    total = len(_todos)
    completed = len([t for t in _todos.values() if t.status == TodoStatus.COMPLETED])
    percentage = (completed * 100 // total) if total > 0 else 0

    # 아이콘 매핑
    icon_map = {
        TodoStatus.PENDING: "⏸️ ",
        TodoStatus.IN_PROGRESS: "🔄",
        TodoStatus.COMPLETED: "✅",
    }

    # 출력 생성
    lines = [f"📋 TODO 리스트 ({completed}/{total} 완료, {percentage}%)"]
    for todo in sorted(filtered, key=lambda t: t.id):
        icon = icon_map[todo.status]
        lines.append(f"{icon} [{todo.id}] {todo.title}")

    return "\n".join(lines)


@tool
def update_todo_status(todo_id: int, status: str) -> str:
    """TODO 상태를 업데이트합니다.

    Args:
        todo_id: TODO 식별자
        status: "pending" | "in_progress" | "completed"

    Returns:
        업데이트 확인 메시지 + 진행률
    """
    if todo_id not in _todos:
        return f"오류: TODO #{todo_id}를 찾을 수 없습니다"

    # 상태 검증
    try:
        status_enum = TodoStatus(status)
    except ValueError:
        return (
            f"오류: 잘못된 상태값 '{status}' (pending, in_progress, completed 중 선택)"
        )

    todo = _todos[todo_id]
    todo.status = status_enum
    todo.updated_at = datetime.now()

    if status_enum == TodoStatus.COMPLETED:
        todo.completed_at = datetime.now()

    # 진행률 계산
    total = len(_todos)
    completed = len([t for t in _todos.values() if t.status == TodoStatus.COMPLETED])
    percentage = (completed * 100 // total) if total > 0 else 0

    # 상태별 메시지
    if status_enum == TodoStatus.COMPLETED:
        return f"✅ [{todo_id}] {todo.title} 완료 ({completed}/{total}, {percentage}%)"
    elif status_enum == TodoStatus.IN_PROGRESS:
        return f"🔄 [{todo_id}] {todo.title} 진행 중"
    else:
        return f"⏸️  [{todo_id}] {todo.title} 대기"


@tool
def clear_todos() -> str:
    """모든 TODO를 삭제합니다.

    Returns:
        삭제 확인 메시지
    """
    global _next_id

    count = len(_todos)
    _todos.clear()
    _next_id = 1

    return f"🗑️  TODO {count}개 삭제 완료"
