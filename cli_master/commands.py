"""슬래시 명령어 처리"""

from typing import Callable
import sqlite3
import uuid

from rich.console import Console
from rich.table import Table
from prompt_toolkit.history import History

from .config import config
from langchain_core.messages import AIMessage, HumanMessage
from langgraph.checkpoint.sqlite import SqliteSaver

# 모듈 레벨 명령어 레지스트리: {name: (handler, description)}
_commands: dict[str, tuple[Callable, str]] = {}


def get_command_names() -> list[str]:
    """등록된 명령어 목록 반환"""
    return sorted(_commands.keys())


def command(name: str, description: str = ""):
    """명령어 등록 데코레이터"""

    def decorator(func: Callable):
        _commands[name] = (func, description)
        return func

    return decorator


class CommandHandler:
    """슬래시 명령어를 처리하는 클래스"""

    def __init__(self, console: Console, history: History):
        self.console = console
        self.history = history
        self._running = True
        self._debug = False
        self._thread_cache: list[str] = []  # /threads 결과를 번호로 접근하기 위한 캐시
        self._current_thread_id = str(uuid.uuid4())  # 현재 대화 컨텍스트의 thread ID

    @property
    def running(self) -> bool:
        return self._running

    @property
    def debug(self) -> bool:
        return self._debug

    @property
    def current_thread_id(self) -> str:
        """현재 대화 컨텍스트의 thread ID"""
        return self._current_thread_id

    def handle(self, command: str) -> bool:
        """명령어 처리. 알려진 명령어면 True 반환"""
        parts = command[1:].strip().split(maxsplit=1)  # '/' 제거
        cmd = parts[0].lower()
        arg = parts[1] if len(parts) > 1 else ""

        if cmd in _commands:
            handler, _ = _commands[cmd]
            handler(self, arg)
            return True

        self.console.print(f"[red]알 수 없는 명령어: {cmd}[/red]")
        self.console.print("[dim]/help 로 사용 가능한 명령어를 확인하세요[/dim]")
        return False

    @command("help", "도움말 표시")
    def _show_help(self, _: str = "") -> None:
        """도움말 출력"""
        table = Table(title="사용 가능한 명령어")
        table.add_column("명령어", style="cyan")
        table.add_column("설명", style="green")

        for name, (handler_func, desc) in sorted(_commands.items()):  # type: ignore
            table.add_row(f"/{name}", desc)

        self.console.print(table)

    @command("history", "현재 thread 히스토리 표시")
    def _show_history(self, _: str = "") -> None:
        """SqliteSaver에서 현재 thread의 히스토리 출력"""
        try:
            with sqlite3.connect(str(config.CHECKPOINT_DB_PATH)) as conn:
                saver = SqliteSaver(conn=conn)
                runtime_config = {
                    "configurable": {"thread_id": self._current_thread_id}
                }
                tup = saver.get_tuple(runtime_config)  # type: ignore
        except sqlite3.Error as e:
            self.console.print(f"[red]체크포인트 DB 조회 실패: {e}[/red]")
            return

        if not tup:
            self.console.print("[yellow]히스토리가 비어있습니다[/yellow]")
            return

        _, checkpoint, _, _, _ = tup  # type: ignore
        messages = checkpoint.get("channel_values", {}).get("messages", [])
        if not messages:
            self.console.print("[yellow]히스토리가 비어있습니다[/yellow]")
            return

        def normalize_content(content) -> str:
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item.get("text", ""))
                return "".join(parts).strip()
            if isinstance(content, str):
                return content.strip()
            return str(content).strip()

        # 메시지 추출
        items: list[tuple[str, str]] = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                text = normalize_content(msg.content)
                if text:
                    items.append(("user", text))
            elif isinstance(msg, AIMessage):
                text = normalize_content(msg.content)
                if text:
                    items.append(("ai", text))

        if not items:
            self.console.print("[yellow]히스토리가 비어있습니다[/yellow]")
            return

        table = Table(title=f"대화 히스토리 (thread: {self._current_thread_id[:8]}...)")
        table.add_column("#", style="dim", width=4)
        table.add_column("역할", style="bold", width=6)
        table.add_column("내용", style="white")

        for idx, (role, content) in enumerate(items, 1):
            if role == "user":
                role_display = "[cyan]사용자[/cyan]"
            else:
                role_display = "[green]AI[/green]"

            table.add_row(str(idx), role_display, content)

        self.console.print(table)

    @command("clear", "새 대화 시작")
    def _clear_history(self, _: str = "") -> None:
        """새 thread ID로 대화 시작"""
        # 새 thread ID 생성
        self._current_thread_id = str(uuid.uuid4())

        # InMemoryHistory 초기화
        if hasattr(self.history, "_storage"):
            self.history._storage.clear()

        self.console.print(
            f"[green]새 대화를 시작합니다 (thread: {self._current_thread_id[:8]}...)[/green]"
        )

    @command("exit", "프로그램 종료")
    def _exit(self, _: str = "") -> None:
        """프로그램 종료"""
        self._running = False
        self.console.print("[blue]프로그램을 종료합니다[/blue]")

    @command("threads", "체크포인트에 저장된 thread 목록 표시")
    def _show_threads(self, _: str = "") -> None:
        """체크포인트 DB의 thread 목록 출력 (번호 포함)"""
        try:
            with sqlite3.connect(str(config.CHECKPOINT_DB_PATH)) as conn:
                rows = conn.execute(
                    "SELECT thread_id, COUNT(*) AS cnt, MAX(checkpoint_id) AS latest "
                    "FROM checkpoints GROUP BY thread_id ORDER BY latest DESC"
                ).fetchall()
        except sqlite3.Error as e:
            self.console.print(f"[red]체크포인트 DB 조회 실패: {e}[/red]")
            return

        if not rows:
            self.console.print("[yellow]저장된 thread가 없습니다[/yellow]")
            self._thread_cache.clear()
            return

        # 캐시 갱신
        self._thread_cache = [str(thread_id) for thread_id, _, _ in rows]

        table = Table(title="저장된 thread 목록")
        table.add_column("#", style="bold magenta", width=4)
        table.add_column("thread_id", style="cyan")
        table.add_column("checkpoint 수", style="green", justify="right")
        table.add_column("latest checkpoint", style="dim")

        for idx, (thread_id, cnt, latest) in enumerate(rows, 1):
            table.add_row(str(idx), str(thread_id), str(cnt), str(latest))

        self.console.print(table)
        self.console.print("[dim]사용법: /load <번호> 또는 /load <thread_id>[/dim]")

    @command("load", "지정한 thread의 대화를 현재 히스토리로 전환")
    def _load_thread(self, arg: str = "") -> None:
        """thread_id 또는 번호로 대화 컨텍스트 전환"""
        input_arg = arg.strip()
        if not input_arg:
            self.console.print(
                "[yellow]사용법: /load <번호> 또는 /load <thread_id>[/yellow]"
            )
            return

        if input_arg.isdigit():
            idx = int(input_arg)
            if idx < 1 or idx > len(self._thread_cache):
                self.console.print(
                    f"[yellow]번호가 범위를 벗어났습니다 (1-{len(self._thread_cache)})[/yellow]"
                )
                self.console.print(
                    "[dim]/threads 명령어로 목록을 먼저 확인하세요[/dim]"
                )
                return
            thread_id = self._thread_cache[idx - 1]
        else:
            thread_id = input_arg

        try:
            with sqlite3.connect(str(config.CHECKPOINT_DB_PATH)) as conn:
                saver = SqliteSaver(conn=conn)
                runtime_config = {"configurable": {"thread_id": thread_id}}
                tup = saver.get_tuple(runtime_config)  # type: ignore
        except sqlite3.Error as e:
            self.console.print(f"[red]체크포인트 DB 조회 실패: {e}[/red]")
            return

        if not tup:
            self.console.print(
                "[yellow]해당 thread_id의 체크포인트가 없습니다[/yellow]"
            )
            return

        _, checkpoint, _, _, _ = tup  # type: ignore
        messages = checkpoint.get("channel_values", {}).get("messages", [])
        if not messages:
            self.console.print("[yellow]체크포인트에 메시지가 없습니다[/yellow]")
            return

        def normalize_content(content) -> str:
            if isinstance(content, list):
                parts = []
                for item in content:
                    if isinstance(item, dict) and item.get("type") == "text":
                        parts.append(item.get("text", ""))
                return "".join(parts).strip()
            if isinstance(content, str):
                return content.strip()
            return str(content).strip()

        # 사용자 메시지만 추출 (방향키 탐색용)
        user_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                text = normalize_content(msg.content)
                if text:
                    user_messages.append(text)

        # InMemoryHistory 갱신
        if hasattr(self.history, "_storage"):
            self.history._storage.clear()
        for msg in user_messages:
            self.history.store_string(msg)

        # 현재 thread ID 전환
        self._current_thread_id = thread_id

        self.console.print(
            f"[green]thread {thread_id}로 전환했습니다 (메시지 {len(user_messages)}건)[/green]"
        )
