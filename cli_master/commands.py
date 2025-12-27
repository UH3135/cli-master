"""슬래시 명령어 처리"""

from typing import Callable

from rich.console import Console
from rich.table import Table

from .history import SqlHistory

# 모듈 레벨 명령어 레지스트리: {name: (handler, description)}
_commands: dict[str, tuple[Callable, str]] = {}


def command(name: str, description: str = ""):
    """명령어 등록 데코레이터"""

    def decorator(func: Callable):
        _commands[name] = (func, description)
        return func

    return decorator


class CommandHandler:
    """슬래시 명령어를 처리하는 클래스"""

    def __init__(self, console: Console, history: SqlHistory):
        self.console = console
        self.history = history
        self._running = True
        self._debug = False

    @property
    def running(self) -> bool:
        return self._running

    @property
    def debug(self) -> bool:
        return self._debug

    def handle(self, command: str) -> bool:
        """명령어 처리. 알려진 명령어면 True 반환"""
        parts = command[1:].strip().split(maxsplit=1)  # '/' 제거
        cmd = parts[0].lower()

        if cmd in _commands:
            handler, _ = _commands[cmd]
            handler(self)
            return True

        self.console.print(f"[red]알 수 없는 명령어: {cmd}[/red]")
        self.console.print("[dim]/help 로 사용 가능한 명령어를 확인하세요[/dim]")
        return False

    @command("help", "도움말 표시")
    def _show_help(self) -> None:
        """도움말 출력"""
        table = Table(title="사용 가능한 명령어")
        table.add_column("명령어", style="cyan")
        table.add_column("설명", style="green")

        for name, (_, desc) in sorted(_commands.items()):
            table.add_row(f"/{name}", desc)

        self.console.print(table)

    @command("history", "현재 세션 히스토리 표시")
    def _show_history(self) -> None:
        """히스토리 출력 (user와 ai 구분)"""
        items = self.history.get_all_with_role()
        if not items:
            self.console.print("[yellow]히스토리가 비어있습니다[/yellow]")
            return

        table = Table(title="대화 히스토리")
        table.add_column("#", style="dim", width=4)
        table.add_column("역할", style="bold", width=6)
        table.add_column("내용", style="white")

        for idx, (role, content) in enumerate(items, 1):
            if role == "user":
                role_display = "[cyan]사용자[/cyan]"
            else:  # ai
                role_display = "[green]AI[/green]"

            table.add_row(str(idx), role_display, content)

        self.console.print(table)

    @command("clear", "히스토리 초기화")
    def _clear_history(self) -> None:
        """히스토리 초기화"""
        self.history.clear()
        self.console.print("[green]히스토리가 초기화되었습니다[/green]")

    @command("exit", "프로그램 종료")
    def _exit(self) -> None:
        """프로그램 종료"""
        self._running = False
        self.console.print("[blue]프로그램을 종료합니다[/blue]")
