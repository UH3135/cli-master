"""커스텀 도구 정의"""

import re
import os
import glob as glob_module
from datetime import datetime

from langchain_core.tools import tool, BaseTool
from .models import TodoItem, TodoStatus


@tool
def cat(file_path: str) -> str:
    """파일 내용을 읽습니다.

    Args:
        file_path: 읽을 파일 경로

    Returns:
        파일 내용 또는 오류 메시지
    """
    try:
        with open(file_path, "r", encoding="utf-8") as f:
            content = f.read()
        return content
    except FileNotFoundError:
        return f"오류: '{file_path}' 파일을 찾을 수 없습니다"
    except PermissionError:
        return f"오류: '{file_path}' 파일에 대한 읽기 권한이 없습니다"
    except Exception as e:
        return f"파일 읽기 오류: {e}"


@tool
def tree(path: str = ".", max_depth: int = 3) -> str:
    """디렉토리 구조를 트리 형태로 표시합니다.

    Args:
        path: 시작 디렉토리 경로 (기본: 현재 디렉토리)
        max_depth: 최대 깊이 (기본: 3)

    Returns:
        디렉토리 트리 구조
    """

    def build_tree(dir_path: str, prefix: str = "", depth: int = 0) -> list:
        if depth >= max_depth:
            return []

        lines = []
        try:
            entries = sorted(os.listdir(dir_path))
        except PermissionError:
            return [f"{prefix}[권한 없음]"]

        # 숨김 파일/디렉토리 및 일반적인 제외 항목 필터링
        exclude = {".git", "__pycache__", "node_modules", ".venv", "venv"}
        entries = [e for e in entries if e not in exclude and not e.startswith(".")]

        for i, entry in enumerate(entries):
            is_last = i == len(entries) - 1
            connector = "└── " if is_last else "├── "
            entry_path = os.path.join(dir_path, entry)

            if os.path.isdir(entry_path):
                lines.append(f"{prefix}{connector}{entry}/")
                extension = "    " if is_last else "│   "
                lines.extend(build_tree(entry_path, prefix + extension, depth + 1))
            else:
                lines.append(f"{prefix}{connector}{entry}")

        return lines

    if not os.path.exists(path):
        return f"오류: '{path}' 경로를 찾을 수 없습니다"

    if not os.path.isdir(path):
        return f"오류: '{path}'는 디렉토리가 아닙니다"

    result = [f"{path}/"]
    result.extend(build_tree(path))
    return "\n".join(result)


@tool
def grep(pattern: str, path: str = ".", file_pattern: str = "*") -> str:
    """파일에서 텍스트 패턴을 검색합니다.

    Args:
        pattern: 검색할 텍스트 또는 정규식 패턴
        path: 검색할 디렉토리 (기본: 현재 디렉토리)
        file_pattern: 파일 패턴 (기본: 모든 파일)

    Returns:
        검색 결과 (파일 경로와 줄 번호 포함)
    """
    results = []
    pattern_re = re.compile(pattern)

    search_pattern = os.path.join(path, "**", file_pattern)
    for file_path in glob_module.glob(search_pattern, recursive=True):
        if os.path.isfile(file_path):
            try:
                with open(file_path, "r", encoding="utf-8") as f:
                    for line_num, line in enumerate(f, 1):
                        if pattern_re.search(line):
                            results.append(f"{file_path}:{line_num}: {line.strip()}")
            except (OSError, UnicodeDecodeError):
                pass

    if not results:
        return f"'{pattern}' 패턴과 일치하는 결과를 찾지 못했습니다"

    return "\n".join(results[:50])  # 최대 50개 결과


# ============================================
# TODO 관리 (모듈 레벨 변수)
# ============================================

_todos: dict[int, TodoItem] = {}
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
        return f"오류: 잘못된 상태값 '{status}' (pending, in_progress, completed 중 선택)"

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


def get_tools() -> list[BaseTool]:
    """모듈 내 모든 도구 자동 수집"""
    return [obj for obj in globals().values() if isinstance(obj, BaseTool)]
