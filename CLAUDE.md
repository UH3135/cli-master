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
  commands.py    # 명령어 처리
  history.py     # 히스토리 관리
  models.py      # 데이터 모델
  completer.py   # 자동완성
  config.py      # 설정 관리
  tools.py       # 커스텀 도구
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

## Development Notes

### Code Style

- 주석은 한국어로 작성
- 로그 포맷팅은 `%s` 사용 (f-string 금지)
- 패키지 관리는 uv 사용
- 모든 docstring은 한국어로 작성
