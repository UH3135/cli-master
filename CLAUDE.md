# CLI Master

## Table of Contents

- [Development Commands](#development-commands)
  - [Code Quality & Testing](#code-quality--testing)
- [Architecture Overview](#architecture-overview)
  - [Project Structure](#project-structure)
  - [Architecture Rules](#architecture-rules)
- [AI Agent Architecture](#ai-agent-architecture)
  - [LangGraph ReAct Agent](#langgraph-react-agent)
  - [Graph Structure](#graph-structure)
  - [Core Components](#core-components)
  - [Public API](#public-api)
- [Tool Registry Architecture](#tool-registry-architecture)
  - [Overview](#overview)
  - [ToolRegistry 클래스](#toolregistry-클래스)
  - [도구 카테고리](#도구-카테고리)
  - [사용 방법](#사용-방법)
- [Repository Pattern Architecture](#repository-pattern-architecture)
  - [Overview](#overview-1)
  - [CheckpointRepository](#checkpointrepository)
  - [PromptHistoryRepository](#prompthistoryrepository)
- [Development Notes](#development-notes)
  - [Code Style](#code-style)

---

## Development Commands

### Code Quality & Testing

- **Lint**: `uv run ruff check .` / `uv run ruff format .`
- **Type checking**: `uv run mypy cli_master`
- **Run tests**: `uv run pytest tests/`
- **Pre-commit hooks**: `uv run pre-commit run --all-files`

---

## Architecture Overview

### Project Structure

```
cli_master/
  main.py        # 진입점 (조립만)
  agent.py       # AI 에이전트 (LangGraph 기반)
  commands.py    # 슬래시 명령어 처리
  models.py      # 데이터 모델
  completer.py   # 자동완성
  config.py      # 설정 관리
  log.py         # 로깅 설정
  tools.py       # 커스텀 도구
  registry.py    # 도구 레지스트리 (중앙 집중식 도구 관리)
  repository/    # 데이터 저장소 계층 (Repository 패턴)
    __init__.py
    checkpoint.py      # 체크포인트 저장소
    prompt_history.py  # 프롬프트 히스토리 저장소
```

### Architecture Rules

- **main.py는 조립(Composition) 전용**: 모듈을 조립하고 실행하는 역할만 수행
- 비즈니스 로직 작성 금지
- 새로운 기능은 반드시 `cli_master/` 하위 모듈에 구현

---

## AI Agent Architecture

### LangGraph ReAct Agent

- **프레임워크**: LangGraph (Deep Agents에서 마이그레이션)
- **목적**: 코드 투명성, 커스터마이징 용이성, 디버깅 개선

### Graph Structure

```
[Start] → Agent 노드 → (도구 필요?) → Tools 노드 → Agent 노드 → ... → [End]
                         ↓ (응답 완료)
                        [End]
```

### Core Components

**1. State 정의**
```python
class AgentState(TypedDict):
    """LangGraph 에이전트 상태"""
    messages: Annotated[Sequence[BaseMessage], add]
```

**2. Graph 노드**
- `call_model`: 에이전트 노드 - 도구와 함께 모델 호출
- `execute_tools`: 도구 노드 - 요청된 도구 실행
- `should_continue`: 라우팅 로직 - 도구 필요 여부 판단

**3. 도구 (Tools)**
- **LangChain 통합 도구**: read_file, list_directory, file_search
- **커스텀 도구**: cat, tree, grep

**4. 스트리밍**
- 이벤트 타입: `tool_start`, `tool_end`, `response`
- 비동기 처리: `astream_events`를 동기 제너레이터로 변환

### Public API

```python
def chat(message: str) -> str:
    """동기 메시지 처리"""

def stream(message: str):
    """스트리밍 응답 생성
    Yields: (event_type, data)
    """
```

---

## Tool Registry Architecture

### Overview

ToolRegistry는 옵저버/레지스트리 패턴 기반의 중앙 집중식 도구 관리 시스템입니다. 모든 도구(LangChain 공식 도구 + 커스텀 도구)를 한 곳에서 관리하여 확장성과 유지보수성을 향상시킵니다.

**주요 특징**:
- 싱글톤 패턴으로 전역 도구 관리
- 카테고리별 도구 분류 (filesystem, custom, todo, search)
- 도구 활성화/비활성화 기능
- 자동 등록 메커니즘
- 중복 등록 방지

### ToolRegistry 클래스

**위치**: `cli_master/registry.py`

**핵심 메서드**:
```python
class ToolRegistry:
    def register(tool: BaseTool, category: str, replace: bool = False)
        """도구 등록 (중복 시 ValueError)"""

    def register_multiple(tools: list[BaseTool], category: str, replace: bool = False)
        """여러 도구 일괄 등록"""

    def get_tool(name: str) -> BaseTool | None
        """이름으로 도구 조회"""

    def get_all_tools() -> list[BaseTool]
        """모든 활성화된 도구 반환"""

    def get_tools_by_category(category: str) -> list[BaseTool]
        """카테고리별 도구 조회"""

    def disable_tool(tool_name: str)
        """도구 비활성화"""

    def enable_tool(tool_name: str)
        """도구 활성화"""

    def unregister(tool_name: str)
        """도구 등록 해제"""

    def list_categories() -> list[str]
        """등록된 카테고리 목록"""

    def get_tool_names(include_disabled: bool = False) -> list[str]
        """등록된 도구 이름 목록"""

    def clear()
        """모든 도구 제거 (테스트용)"""
```

**사용 예시**:
```python
from cli_master.registry import get_registry, ToolCategory

registry = get_registry()

# 도구 등록
registry.register(my_tool, category=ToolCategory.CUSTOM)

# 모든 도구 조회
all_tools = registry.get_all_tools()

# 카테고리별 조회
fs_tools = registry.get_tools_by_category(ToolCategory.FILESYSTEM)
```

### 도구 카테고리

```python
class ToolCategory:
    FILESYSTEM = "filesystem"  # 파일 시스템 도구 (cat, tree, read_file 등)
    CUSTOM = "custom"          # 일반 커스텀 도구
    TODO = "todo"              # TODO 관리 도구
    SEARCH = "search"          # 검색 도구 (grep, file_search 등)
```

### 사용 방법

#### 1. 커스텀 도구 추가

**단계 1**: `tools.py`에 `@tool` 데코레이터로 함수 정의
```python
@tool
def my_custom_tool(arg: str) -> str:
    """새로운 커스텀 도구"""
    return f"Result: {arg}"
```

**단계 2**: `_auto_register_tools()` 함수에 등록 추가
```python
def _auto_register_tools():
    registry = get_registry()
    # ... 기존 등록들
    registry.register(my_custom_tool, category=ToolCategory.CUSTOM)
```

**단계 3**: 모듈 임포트 시 자동으로 등록됨

#### 2. LangChain 도구 추가

LangChain 도구는 `agent.py`의 `_build_graph()` 함수에서 자동으로 등록됩니다:
```python
# FileManagementToolkit 도구들이 자동 등록됨
toolkit = FileManagementToolkit(...)
registry.register_multiple(toolkit.get_tools(), category=ToolCategory.FILESYSTEM, replace=True)
```

#### 3. 도구 비활성화

환경 변수나 설정을 통해 특정 도구를 비활성화할 수 있습니다:
```python
registry = get_registry()
registry.disable_tool("write_file")  # 쓰기 도구 비활성화
```

---

## Repository Pattern Architecture

### Overview

Repository 패턴을 도입하여 데이터 저장소 계층을 분리합니다. 이를 통해 비즈니스 로직과 데이터 접근 로직을 명확히 분리하고, 테스트 용이성을 높입니다.

**위치**: `cli_master/repository/`

**주요 저장소**:
- `CheckpointRepository`: LangGraph 체크포인트 (Long Term 저장소)
- `PromptHistoryRepository`: 프롬프트 입력 히스토리 (Short Term 저장소)

### CheckpointRepository

SQLite 기반 체크포인트 저장소. LangGraph의 SqliteSaver를 래핑하여 추가 기능 제공.

```python
class CheckpointRepository:
    def __init__(self, db_path: Path)
        """저장소 초기화"""

    def get_checkpointer() -> SqliteSaver
        """동기 checkpointer 반환 (싱글톤)"""

    def get_history(thread_id: str) -> list[BaseMessage] | None
        """특정 thread의 대화 히스토리 조회"""

    def list_threads() -> list[ThreadInfo]
        """저장된 모든 thread 목록 조회"""

    def thread_exists(thread_id: str) -> bool
        """thread 존재 여부 확인"""

    def close()
        """리소스 정리"""
```

**사용 예시**:
```python
from cli_master.repository import CheckpointRepository

repo = CheckpointRepository(Path("db/checkpoint.db"))

# thread 목록 조회
threads = repo.list_threads()

# 대화 히스토리 조회
messages = repo.get_history("thread_id")
```

### PromptHistoryRepository

InMemoryHistory 래핑 - prompt_toolkit 히스토리 관리.

```python
class PromptHistoryRepository:
    def get_history() -> History
        """prompt_toolkit History 객체 반환"""

    def add_entry(text: str)
        """히스토리 항목 추가"""

    def clear()
        """히스토리 초기화"""

    def load_from_messages(messages: list[str])
        """메시지 목록으로 히스토리 갱신"""

    def get_entries() -> list[str]
        """모든 히스토리 항목 반환"""
```

**사용 예시**:
```python
from cli_master.repository import PromptHistoryRepository

repo = PromptHistoryRepository()

# PromptSession에 연결
session = PromptSession(history=repo.get_history())

# 히스토리 갱신
repo.load_from_messages(["질문1", "질문2"])
```

---

## Development Notes

### Code Style

- 주석은 한국어로 작성
- 로그 포맷팅은 `%s` 사용 (f-string 금지)
- 패키지 관리는 uv 사용
- 모든 docstring은 한국어로 작성
