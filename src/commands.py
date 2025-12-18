"""슬래시 명령어 처리"""
from rich.console import Console
from rich.table import Table

from .history import InputHistory


class CommandHandler:
    """슬래시 명령어를 처리하는 클래스"""

    def __init__(self, console: Console, history: InputHistory):
        self.console = console
        self.history = history
        self._running = True

    @property
    def running(self) -> bool:
        return self._running

    def handle(self, command: str) -> bool:
        """명령어 처리. 알려진 명령어면 True 반환"""
        parts = command[1:].strip().split(maxsplit=1)  # '/' 제거
        cmd = parts[0].lower()
        args = parts[1] if len(parts) > 1 else ""

        if cmd == "help":
            self._show_help()
            return True
        elif cmd == "exit":
            self._exit()
            return True
        elif cmd == "history":
            self._show_history()
            return True
        elif cmd == "clear":
            self._clear_history()
            return True
        elif cmd == "find":
            self._find_similar(args)
            return True
        else:
            self.console.print(f"[red]알 수 없는 명령어: {cmd}[/red]")
            self.console.print("[dim]/help 로 사용 가능한 명령어를 확인하세요[/dim]")
            return False

    def _show_help(self) -> None:
        """도움말 출력"""
        table = Table(title="사용 가능한 명령어")
        table.add_column("명령어", style="cyan")
        table.add_column("설명", style="green")

        table.add_row("/help", "도움말 표시")
        table.add_row("/history", "현재 세션 히스토리 표시")
        table.add_row("/clear", "히스토리 초기화")
        table.add_row("/exit", "프로그램 종료")
        table.add_row("", "")
        table.add_row("/find [문장]", "비슷한 의미로 검색")

        self.console.print(table)

    def _show_history(self) -> None:
        """히스토리 출력"""
        items = self.history.get_all()
        if not items:
            self.console.print("[yellow]히스토리가 비어있습니다[/yellow]")
            return

        table = Table(title="입력 히스토리")
        table.add_column("#", style="dim")
        table.add_column("입력", style="white")

        for idx, item in enumerate(items, 1):
            table.add_row(str(idx), item)

        self.console.print(table)

    def _clear_history(self) -> None:
        """히스토리 초기화"""
        self.history.clear()
        self.console.print("[green]히스토리가 초기화되었습니다[/green]")

    def _find_similar(self, query: str) -> None:
        """의미 기반 검색"""
        if not query:
            self.console.print("[yellow]검색할 문장을 입력하세요: /find [문장][/yellow]")
            return

        results = self.history.find_similar(query)
        if not results:
            self.console.print(f"[yellow]'{query}'와 비슷한 내용이 없습니다[/yellow]")
            return

        table = Table(title=f"유사 검색 결과: '{query}'")
        table.add_column("내용", style="white")
        table.add_column("유사도", style="cyan")

        for item in results:
            # 거리가 작을수록 유사도가 높음
            similarity = f"{(1 - item['distance']) * 100:.1f}%" if item['distance'] else "-"
            content = item['content']
            table.add_row(
                content[:50] + "..." if len(content) > 50 else content,
                similarity
            )

        self.console.print(table)

    def _exit(self) -> None:
        """프로그램 종료"""
        self._running = False
        self.history.close()
        self.console.print("[blue]프로그램을 종료합니다[/blue]")
