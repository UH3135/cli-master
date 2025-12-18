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
        elif cmd == "search":
            self._search(args)
            return True
        elif cmd == "find":
            self._find_similar(args)
            return True
        elif cmd == "sessions":
            self._show_sessions()
            return True
        elif cmd == "load":
            self._load_session(args)
            return True
        elif cmd == "new":
            self._new_session()
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
        table.add_row("/clear", "새 세션 시작 (히스토리 초기화)")
        table.add_row("/exit", "프로그램 종료")
        table.add_row("", "")
        table.add_row("/search [키워드]", "키워드로 검색")
        table.add_row("/find [문장]", "비슷한 의미로 검색")
        table.add_row("/sessions", "이전 세션 목록")
        table.add_row("/load [번호]", "이전 세션 불러오기")
        table.add_row("/new", "새 세션 시작")

        self.console.print(table)

    def _show_history(self) -> None:
        """히스토리 출력"""
        items = self.history.get_all()
        if not items:
            self.console.print("[yellow]히스토리가 비어있습니다[/yellow]")
            return

        table = Table(title=f"입력 히스토리 (세션: {self.history.session.id[:8]}...)")
        table.add_column("#", style="dim")
        table.add_column("입력", style="white")

        for idx, item in enumerate(items, 1):
            table.add_row(str(idx), item)

        self.console.print(table)

    def _clear_history(self) -> None:
        """히스토리 초기화 (새 세션 시작)"""
        self.history.clear()
        self.console.print("[green]새 세션이 시작되었습니다[/green]")

    def _search(self, query: str) -> None:
        """키워드 검색"""
        if not query:
            self.console.print("[yellow]검색어를 입력하세요: /search [키워드][/yellow]")
            return

        results = self.history.search(query)
        if not results:
            self.console.print(f"[yellow]'{query}'에 대한 검색 결과가 없습니다[/yellow]")
            return

        table = Table(title=f"검색 결과: '{query}'")
        table.add_column("내용", style="white")
        table.add_column("시간", style="dim")

        for msg in results:
            table.add_row(
                msg.content[:50] + "..." if len(msg.content) > 50 else msg.content,
                msg.created_at.strftime("%m/%d %H:%M")
            )

        self.console.print(table)

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

    def _show_sessions(self) -> None:
        """세션 목록"""
        sessions = self.history.get_sessions()
        if not sessions:
            self.console.print("[yellow]저장된 세션이 없습니다[/yellow]")
            return

        table = Table(title="세션 목록")
        table.add_column("#", style="dim")
        table.add_column("세션 ID", style="cyan")
        table.add_column("생성일", style="white")
        table.add_column("메시지 수", style="green")

        for idx, session in enumerate(sessions, 1):
            msg_count = self.history.sqlite.get_message_count(session.id)
            current = " (현재)" if session.id == self.history.session.id else ""
            table.add_row(
                str(idx),
                session.id[:8] + "..." + current,
                session.created_at.strftime("%Y-%m-%d %H:%M"),
                str(msg_count)
            )

        self.console.print(table)
        self.console.print("[dim]/load [번호]로 세션을 불러올 수 있습니다[/dim]")

    def _load_session(self, args: str) -> None:
        """세션 불러오기"""
        if not args:
            self.console.print("[yellow]세션 번호를 입력하세요: /load [번호][/yellow]")
            return

        try:
            idx = int(args) - 1
            sessions = self.history.get_sessions()
            if idx < 0 or idx >= len(sessions):
                self.console.print("[red]잘못된 세션 번호입니다[/red]")
                return

            session = sessions[idx]
            if self.history.load_session(session.id):
                self.console.print(f"[green]세션 {session.id[:8]}...을 불러왔습니다[/green]")
                self._show_history()
            else:
                self.console.print("[red]세션을 불러올 수 없습니다[/red]")
        except ValueError:
            self.console.print("[red]숫자를 입력하세요[/red]")

    def _new_session(self) -> None:
        """새 세션 시작"""
        session = self.history.new_session()
        self.console.print(f"[green]새 세션이 시작되었습니다: {session.id[:8]}...[/green]")

    def _exit(self) -> None:
        """프로그램 종료"""
        self._running = False
        self.history.close()
        self.console.print("[blue]프로그램을 종료합니다[/blue]")
