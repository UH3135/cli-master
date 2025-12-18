"""CLI Master - 대화 세션을 저장하는 CLI 도구"""

import logging

from rich.console import Console
from prompt_toolkit import PromptSession
from prompt_toolkit.styles import Style
from prompt_toolkit.history import InMemoryHistory

from src.history import InputHistory
from src.commands import CommandHandler
from src.completer import SlashCompleter

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# 명령어 정의 (명령어, 설명)
COMMANDS = [
    ("help", "도움말 표시"),
    ("history", "현재 세션 히스토리 표시"),
    ("clear", "히스토리 초기화"),
    ("exit", "프로그램 종료"),
    ("find", "비슷한 의미로 검색"),
]


# prompt_toolkit 스타일 정의
prompt_style = Style.from_dict(
    {
        "prompt": "bold green",
        "completion-menu.completion": "bg:#333333 #ffffff",
        "completion-menu.completion.current": "bg:#00aa00 #000000",
        "completion-menu.meta.completion": "bg:#333333 #888888",
        "completion-menu.meta.completion.current": "bg:#00aa00 #000000",
    }
)


def main():
    console = Console()

    console.print("[bold cyan]CLI Master[/bold cyan]")
    console.print("[dim]저장소 초기화 중...[/dim]")

    # 히스토리 초기화 (VectorDB)
    history = InputHistory()
    handler = CommandHandler(console, history)

    console.print("[dim]Ctrl+C: 현재 입력 취소 | /: 명령어 보기[/dim]\n")

    # 자동완성 설정
    completer = SlashCompleter(COMMANDS)
    cli_history = InMemoryHistory()

    session = PromptSession(
        "> ",
        style=prompt_style,
        completer=completer,
        complete_while_typing=True,
        history=cli_history,
    )

    while handler.running:
        try:
            # 방향키 ↑/↓로 이전·다음 입력 탐색 가능
            user_input = session.prompt()

            if user_input.startswith("/"):
                handler.handle(user_input)
            elif user_input.strip():
                history.add(user_input)
                console.print(f"[dim]입력됨: {user_input}[/dim]")

        except KeyboardInterrupt:
            # Ctrl+C: 현재 입력 무시하고 계속
            console.print("\n[yellow]입력이 취소되었습니다[/yellow]")
            continue
        except EOFError:
            # Ctrl+D: 종료
            console.print("\n[blue]프로그램을 종료합니다[/blue]")
            history.close()
            break


if __name__ == "__main__":
    main()
