"""ToolRegistry 테스트"""

from langchain_core.tools import tool

from cli_master.registry import ToolRegistry, ToolCategory, get_registry


def test_registry_singleton():
    """싱글톤 동작 검증"""
    r1 = ToolRegistry()
    r2 = get_registry()
    assert r1 is r2


def test_register_and_get_tool():
    """도구 등록 및 조회"""
    registry = get_registry()
    registry.clear()

    @tool
    def dummy_tool() -> str:
        """더미 도구"""
        return "test"

    registry.register(dummy_tool, category=ToolCategory.CUSTOM)
    assert registry.get_tool("dummy_tool") == dummy_tool


def test_get_all_tools():
    """모든 도구 조회"""
    registry = get_registry()
    registry.clear()

    @tool
    def tool1() -> str:
        """도구 1"""
        return "tool1"

    @tool
    def tool2() -> str:
        """도구 2"""
        return "tool2"

    registry.register(tool1, category=ToolCategory.CUSTOM)
    registry.register(tool2, category=ToolCategory.FILESYSTEM)

    tools = registry.get_all_tools()
    assert len(tools) == 2


def test_category_filtering():
    """카테고리별 필터링"""
    registry = get_registry()
    registry.clear()

    @tool
    def fs_tool() -> str:
        """파일시스템 도구"""
        return "fs"

    @tool
    def custom_tool() -> str:
        """커스텀 도구"""
        return "custom"

    registry.register(fs_tool, category=ToolCategory.FILESYSTEM)
    registry.register(custom_tool, category=ToolCategory.CUSTOM)

    fs_tools = registry.get_tools_by_category(ToolCategory.FILESYSTEM)
    assert len(fs_tools) == 1
    assert fs_tools[0].name == "fs_tool"

    custom_tools = registry.get_tools_by_category(ToolCategory.CUSTOM)
    assert len(custom_tools) == 1
    assert custom_tools[0].name == "custom_tool"


def test_disable_enable_tool():
    """도구 활성화/비활성화"""
    registry = get_registry()
    registry.clear()

    @tool
    def dummy_tool() -> str:
        """더미 도구"""
        return "test"

    registry.register(dummy_tool, category=ToolCategory.CUSTOM)

    # 활성화 상태 확인
    assert len(registry.get_all_tools()) == 1

    # 비활성화
    registry.disable_tool("dummy_tool")
    assert len(registry.get_all_tools()) == 0

    # 활성화
    registry.enable_tool("dummy_tool")
    assert len(registry.get_all_tools()) == 1


def test_register_multiple():
    """여러 도구 일괄 등록"""
    registry = get_registry()
    registry.clear()

    @tool
    def tool1() -> str:
        """도구 1"""
        return "1"

    @tool
    def tool2() -> str:
        """도구 2"""
        return "2"

    tools = [tool1, tool2]
    registry.register_multiple(tools, category=ToolCategory.TODO)

    assert len(registry.get_all_tools()) == 2
    assert len(registry.get_tools_by_category(ToolCategory.TODO)) == 2
