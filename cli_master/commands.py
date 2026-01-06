"""슬래시 명령어 처리"""

from typing import Callable
import uuid

from rich.console import Console
from rich.table import Table
from rich.panel import Panel
from rich.markdown import Markdown
from langchain_core.messages import AIMessage, HumanMessage

from .repository import CheckpointRepository, PromptHistoryRepository
from .researcher import (
    ResearchSession,
    ResearchAgent,
    ResearchPhase,
    create_research_session,
    create_research_agent,
)

# 모듈 레벨 명령어 레지스트리: {name: (handler, description)}
_commands: dict[str, tuple[Callable, str]] = {}


def _normalize_content(content) -> str:
    """메시지 content를 문자열로 정규화 (Gemini 등 리스트 형태 지원)"""
    if isinstance(content, list):
        parts = []
        for item in content:
            if isinstance(item, dict) and item.get("type") == "text":
                parts.append(item.get("text", ""))
        return "".join(parts).strip()
    if isinstance(content, str):
        return content.strip()
    return str(content).strip()


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

    def __init__(
        self,
        console: Console,
        checkpoint_repo: CheckpointRepository,
        prompt_repo: PromptHistoryRepository,
    ):
        self.console = console
        self._checkpoint_repo = checkpoint_repo
        self._prompt_repo = prompt_repo
        self._running = True
        self._debug = False
        self._thread_cache: list[str] = []  # /threads 결과를 번호로 접근하기 위한 캐시
        self._current_thread_id = str(uuid.uuid4())  # 현재 대화 컨텍스트의 thread ID

        # Research 모드 상태
        self._research_session: ResearchSession | None = None
        self._research_agent: ResearchAgent | None = None

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

    @property
    def is_research_mode(self) -> bool:
        """리서치 모드 활성화 여부"""
        return (
            self._research_session is not None
            and self._research_session.phase != ResearchPhase.COMPLETED
        )

    @property
    def research_session(self) -> ResearchSession | None:
        """현재 리서치 세션"""
        return self._research_session

    @property
    def research_agent(self) -> ResearchAgent | None:
        """현재 리서치 에이전트"""
        return self._research_agent

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
        """현재 thread의 히스토리 출력"""
        messages = self._checkpoint_repo.get_history(self._current_thread_id)
        if not messages:
            self.console.print("[yellow]히스토리가 비어있습니다[/yellow]")
            return

        # 메시지 추출
        items: list[tuple[str, str]] = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                text = _normalize_content(msg.content)
                if text:
                    items.append(("user", text))
            elif isinstance(msg, AIMessage):
                text = _normalize_content(msg.content)
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

        # 프롬프트 히스토리 초기화
        self._prompt_repo.clear()

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
        threads = self._checkpoint_repo.list_threads()

        if not threads:
            self.console.print("[yellow]저장된 thread가 없습니다[/yellow]")
            self._thread_cache.clear()
            return

        # 캐시 갱신
        self._thread_cache = [t.thread_id for t in threads]

        table = Table(title="저장된 thread 목록")
        table.add_column("#", style="bold magenta", width=4)
        table.add_column("thread_id", style="cyan")
        table.add_column("checkpoint 수", style="green", justify="right")
        table.add_column("latest checkpoint", style="dim")

        for idx, t in enumerate(threads, 1):
            table.add_row(
                str(idx), t.thread_id, str(t.checkpoint_count), t.latest_checkpoint_id
            )

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

        messages = self._checkpoint_repo.get_history(thread_id)
        if not messages:
            self.console.print(
                "[yellow]해당 thread_id의 체크포인트가 없습니다[/yellow]"
            )
            return

        # 사용자 메시지만 추출 (방향키 탐색용)
        user_messages = []
        for msg in messages:
            if isinstance(msg, HumanMessage):
                text = _normalize_content(msg.content)
                if text:
                    user_messages.append(text)

        # 프롬프트 히스토리 갱신
        self._prompt_repo.load_from_messages(user_messages)

        # 현재 thread ID 전환
        self._current_thread_id = thread_id

        self.console.print(
            f"[green]thread {thread_id}로 전환했습니다 (메시지 {len(user_messages)}건)[/green]"
        )

    @command("research", "심층 검색 모드 시작")
    def _research(self, arg: str = "") -> None:
        """심층 검색(research) 모드 시작

        사용법:
            /research <주제>  - 지정한 주제로 리서치 시작
            /research         - 주제 입력 요청
        """
        topic = arg.strip()

        if not topic:
            self.console.print("[yellow]조사할 주제를 입력해주세요.[/yellow]")
            self.console.print("[dim]예: /research 이 프로젝트의 에러 핸들링 패턴[/dim]")
            return

        # 리서치 세션 시작
        self._research_session = create_research_session(topic)
        self._research_agent = create_research_agent(self._research_session)

        self.console.print(
            Panel(
                f"[bold cyan]심층 검색 모드[/bold cyan]\n\n"
                f"주제: [green]{topic}[/green]\n\n"
                "[dim]더 정확한 조사를 위해 몇 가지 질문을 드리겠습니다.[/dim]",
                title="Research Mode",
                border_style="cyan",
            )
        )

        # 명확화 질문 생성
        self._generate_and_show_questions()

    def _generate_and_show_questions(self) -> None:
        """명확화 질문 생성 및 표시"""
        if not self._research_agent:
            return

        self.console.print("\n[dim]질문 생성 중...[/dim]")
        questions = self._research_agent.generate_clarifying_questions()

        self.console.print("\n[bold yellow]다음 질문에 답변해주세요:[/bold yellow]\n")
        for i, q in enumerate(questions, 1):
            self.console.print(f"  [cyan]{i}.[/cyan] {q}")

        self.console.print(
            "\n[dim]각 질문에 대한 답변을 입력하세요. "
            "(한 번에 모두 입력하거나, 번호별로 입력 가능)[/dim]"
        )

    def process_research_input(self, user_input: str) -> bool:
        """리서치 모드에서 사용자 입력 처리

        Args:
            user_input: 사용자 입력

        Returns:
            True if handled, False otherwise
        """
        if not self.is_research_mode or not self._research_session:
            return False

        session = self._research_session
        agent = self._research_agent

        if not agent:
            return False

        # 현재 단계에 따라 처리
        if session.phase == ResearchPhase.CLARIFYING:
            return self._handle_clarifying_answer(user_input)

        return False

    def _handle_clarifying_answer(self, answer: str) -> bool:
        """명확화 질문에 대한 답변 처리"""
        if not self._research_session or not self._research_agent:
            return False

        session = self._research_session
        agent = self._research_agent

        # 답변 저장
        session.user_answers.append(answer.strip())

        # 모든 질문에 답변했는지 확인
        if len(session.user_answers) < len(session.clarifying_questions):
            remaining = len(session.clarifying_questions) - len(session.user_answers)
            self.console.print(
                f"\n[dim]답변이 저장되었습니다. 남은 질문: {remaining}개[/dim]"
            )
            return True

        # 모든 답변 완료 - 계획 수립 단계로 진행
        self.console.print("\n[dim]조사 계획을 수립하고 있습니다...[/dim]")

        plan = agent.generate_plan()

        self.console.print("\n[bold green]조사 계획:[/bold green]\n")
        for i, step in enumerate(plan, 1):
            self.console.print(f"  [cyan]{i}.[/cyan] {step}")

        self.console.print(
            "\n[dim]계획을 실행합니다. 잠시만 기다려주세요...[/dim]\n"
        )

        # 각 단계 실행
        self._execute_research_plan()

        return True

    def _execute_research_plan(self) -> None:
        """조사 계획 실행"""
        if not self._research_session or not self._research_agent:
            return

        session = self._research_session
        agent = self._research_agent

        from rich.live import Live
        from rich.text import Text

        # 각 단계 실행
        for i, step in enumerate(session.plan):
            self.console.print(f"\n[bold cyan]단계 {i + 1}:[/bold cyan] {step}")

            logs = []

            def stream_callback(event_type: str, data: dict) -> None:
                if event_type == "tool_start":
                    logs.append(f"  ⚙ {data['name']} 실행 중...")
                elif event_type == "tool_end":
                    result = data["result"][:60] + "..." if len(data["result"]) > 60 else data["result"]
                    logs.append(f"    ✓ 완료: {result}")

            with Live(Text("분석 중...", style="dim"), transient=True) as live:
                agent.execute_step(i, stream_callback)
                if logs:
                    live.update(Text("\n".join(logs), style="dim"))

            self.console.print("  [green]✓ 완료[/green]")

        # 보고서 생성
        self.console.print("\n[dim]보고서를 생성하고 있습니다...[/dim]")
        report = agent.generate_report()

        # 보고서 저장
        filepath = agent.save_report()

        # 결과 출력
        self.console.print("\n")
        self.console.print(
            Panel(
                Markdown(report),
                title="[bold cyan]리서치 보고서[/bold cyan]",
                border_style="cyan",
            )
        )

        self.console.print(f"\n[green]✓ 보고서가 저장되었습니다: {filepath}[/green]")
        self.console.print("[dim]리서치 모드가 종료되었습니다.[/dim]\n")

        # 세션 정리
        self._research_session = None
        self._research_agent = None
