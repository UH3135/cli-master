"""도구 모듈

AI 에이전트가 사용하는 도구들을 제공합니다.
"""

from .registry import ToolCategory, ToolRegistry, get_registry
from .filesystem import cat, tree, grep
from .todo import (
    create_todo,
    list_todos,
    update_todo_status,
    clear_todos,
    get_todos,
    reset_todos,
)


def register_all_tools():
    """모든 커스텀 도구를 레지스트리에 등록"""
    registry = get_registry()

    # 파일시스템 도구
    registry.register(cat, category=ToolCategory.FILESYSTEM)
    registry.register(tree, category=ToolCategory.FILESYSTEM)

    # 검색 도구
    registry.register(grep, category=ToolCategory.SEARCH)

    # TODO 도구
    registry.register(create_todo, category=ToolCategory.TODO)
    registry.register(list_todos, category=ToolCategory.TODO)
    registry.register(update_todo_status, category=ToolCategory.TODO)
    registry.register(clear_todos, category=ToolCategory.TODO)


__all__ = [
    # registry
    "ToolCategory",
    "ToolRegistry",
    "get_registry",
    # filesystem
    "cat",
    "tree",
    "grep",
    # todo
    "create_todo",
    "list_todos",
    "update_todo_status",
    "clear_todos",
    "get_todos",
    "reset_todos",
    # helper
    "register_all_tools",
]

# 모듈 임포트 시 자동 등록
register_all_tools()
