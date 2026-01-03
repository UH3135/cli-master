"""도구 레지스트리"""

from loguru import logger
from langchain_core.tools import BaseTool


class ToolCategory:
    """도구 카테고리"""

    FILESYSTEM = "filesystem"
    CUSTOM = "custom"
    TODO = "todo"
    SEARCH = "search"


class ToolRegistry:
    """도구 중앙 관리 레지스트리 (싱글톤)"""

    _instance = None

    def __new__(cls):
        """싱글톤 구현"""
        if cls._instance is None:
            cls._instance = super().__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self):
        """초기화 (싱글톤이므로 한 번만 실행)"""
        if self._initialized:
            return
        self._tools: dict[str, BaseTool] = {}
        self._categories: dict[str, set[str]] = {}
        self._disabled_tools: set[str] = set()
        self._initialized = True

    def register(
        self, tool: BaseTool, category: str = ToolCategory.CUSTOM, replace: bool = False
    ):
        """도구 등록

        Args:
            tool: LangChain BaseTool 인스턴스
            category: 도구 카테고리
            replace: 기존 도구 덮어쓰기 허용 여부

        Raises:
            ValueError: 이미 존재하는 도구이고 replace=False인 경우
        """
        name = tool.name

        if name in self._tools and not replace:
            raise ValueError(f"도구 '{name}'이 이미 등록되어 있습니다")

        self._tools[name] = tool
        if category not in self._categories:
            self._categories[category] = set()
        self._categories[category].add(tool.name)

        logger.debug("도구 등록: {} (카테고리: {})", name, category)

    def register_multiple(
        self, tools: list[BaseTool], category: str = ToolCategory.CUSTOM, replace: bool = False
    ):
        """여러 도구 일괄 등록

        Args:
            tools: 등록할 도구 리스트
            category: 도구 카테고리
            replace: 기존 도구 덮어쓰기 허용 여부
        """
        for tool in tools:
            self.register(tool, category=category, replace=replace)

    def get_tool(self, name: str) -> BaseTool | None:
        """도구 조회"""
        return self._tools.get(name)

    def get_all_tools(self) -> list[BaseTool]:
        """모든 활성화된 도구 반환"""
        return [
            tool
            for name, tool in self._tools.items()
            if name not in self._disabled_tools
        ]

    def get_tools_by_category(self, category: str) -> list[BaseTool]:
        """카테고리별 도구 조회"""
        tool_names = self._categories.get(category, set())
        return [
            self._tools[name]
            for name in tool_names
            if name in self._tools and name not in self._disabled_tools
        ]

    def disable_tool(self, tool_name: str):
        """도구 비활성화"""
        self._disabled_tools.add(tool_name)
        logger.debug("도구 비활성화: {}", tool_name)

    def enable_tool(self, tool_name: str):
        """도구 활성화"""
        self._disabled_tools.discard(tool_name)
        logger.debug("도구 활성화: {}", tool_name)

    def unregister(self, tool_name: str):
        """도구 등록 해제

        Args:
            tool_name: 제거할 도구 이름
        """
        if tool_name not in self._tools:
            logger.warning("등록되지 않은 도구: {}", tool_name)
            return

        # 모든 카테고리에서 제거
        for category_tools in self._categories.values():
            category_tools.discard(tool_name)

        # disabled 목록에서도 제거
        self._disabled_tools.discard(tool_name)

        del self._tools[tool_name]
        logger.info("도구 등록 해제: {}", tool_name)

    def list_categories(self) -> list[str]:
        """등록된 카테고리 목록

        Returns:
            카테고리 이름 리스트
        """
        return list(self._categories.keys())

    def get_tool_names(self, include_disabled: bool = False) -> list[str]:
        """등록된 도구 이름 목록

        Args:
            include_disabled: 비활성화된 도구 포함 여부

        Returns:
            도구 이름 리스트
        """
        if include_disabled:
            return list(self._tools.keys())

        return [name for name in self._tools.keys() if name not in self._disabled_tools]

    def clear(self):
        """모든 도구 제거 (테스트용)"""
        self._tools.clear()
        self._categories.clear()
        self._disabled_tools.clear()
        logger.debug("ToolRegistry cleared")


def get_registry() -> ToolRegistry:
    """전역 레지스트리 반환"""
    return ToolRegistry()
